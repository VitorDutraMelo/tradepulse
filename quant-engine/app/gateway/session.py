"""One persistent, PRACTICE-only IQ Option session per worker process."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite

from app.domain.candle import Candle
from app.gateway.redaction import redact
from app.gateway.timeframes import timeframe_seconds, to_iso
from app.gateway.transport import IqTransport, TransportFatalError


class GatewayError(Exception):
    """Expected gateway failure with a stable machine-readable code."""

    code = "IQ_OPTION_UNAVAILABLE"

    def __init__(self, message: str, retry_at: datetime | None = None) -> None:
        super().__init__(message)
        self.retry_at = retry_at


class CredentialsMissingError(GatewayError):
    code = "IQ_OPTION_CREDENTIALS_MISSING"


class AuthenticationFailedError(GatewayError):
    code = "IQ_OPTION_AUTH_FAILED"


class PracticeNotConfirmedError(GatewayError):
    """The session could not prove that the PRACTICE balance is selected."""

    code = "IQ_OPTION_PRACTICE_NOT_CONFIRMED"


class BackoffActiveError(GatewayError):
    code = "IQ_OPTION_RECONNECT_BACKOFF"


class SourceUnavailableError(GatewayError):
    code = "IQ_OPTION_UNAVAILABLE"


class SourceTimeoutError(GatewayError):
    code = "IQ_OPTION_TIMEOUT"


@dataclass(frozen=True, slots=True)
class ObservedQuote:
    """Last price of the still-open candle, as reported by the source."""

    price: float
    source_timestamp: datetime | None
    observed_at: datetime

    def to_payload(self) -> dict[str, object]:
        return {
            "price": self.price,
            "sourceTimestamp": to_iso(self.source_timestamp),
            "sourceTimestampKind": (
                "OBSERVED_SOURCE" if self.source_timestamp is not None else "NOT_AVAILABLE"
            ),
            "observedAt": to_iso(self.observed_at),
            "observedAtKind": "OBSERVED_LOCAL_CLOCK",
        }


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Closed candles of one IQ Option request plus observed timing."""

    symbol: str
    timeframe: str
    requested_count: int
    candles: tuple[Candle, ...]
    source_close_times: tuple[datetime, ...]
    observed_quote: ObservedQuote | None
    requested_at: datetime
    received_at: datetime
    reference_now: datetime
    reference_clock: str
    server_time_at_receipt: datetime | None


@dataclass(slots=True)
class SessionCounters:
    login_attempts: int = 0
    logins_succeeded: int = 0
    login_failures: int = 0
    reconnects: int = 0
    candle_requests: int = 0
    candle_request_failures: int = 0
    practice_checks_failed: int = 0
    extra: dict[str, int] = field(default_factory=dict)


def _parse_source_timestamp(value: object) -> datetime | None:
    """Parse IQ Option ``at`` values given in s, ms, us or ns."""

    if not isinstance(value, (int, float)) or not isfinite(float(value)) or value <= 0:
        return None

    number = float(value)

    if number > 1e17:
        number /= 1e9
    elif number > 1e14:
        number /= 1e6
    elif number > 1e11:
        number /= 1e3

    try:
        return datetime.fromtimestamp(number, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_raw_candle(raw: object, interval_seconds: int) -> tuple[Candle, datetime]:
    if not isinstance(raw, dict):
        raise ValueError("IQ Option returned an invalid candle")

    try:
        open_time = datetime.fromtimestamp(float(raw["from"]), tz=UTC)
        close_time = datetime.fromtimestamp(
            float(raw.get("to", open_time.timestamp() + interval_seconds)),
            tz=UTC,
        )
        values = (
            float(raw["open"]),
            float(raw["max"]),
            float(raw["min"]),
            float(raw["close"]),
            float(raw.get("volume", 0)),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError("IQ Option returned an invalid candle") from error

    if not all(isfinite(value) for value in values):
        raise ValueError("IQ Option returned a non-finite candle value")

    if close_time <= open_time:
        raise ValueError("IQ Option returned an invalid candle close timestamp")

    open_price, high, low, close, volume = values

    return (
        Candle(
            timestamp=open_time,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        ),
        close_time,
    )


class IqSession:
    """Reuse one authenticated session, reconnecting with progressive backoff.

    * Exactly one login is attempted at a time (the worker is single-threaded).
    * After every login the PRACTICE balance is selected and verified; if the
      library cannot confirm PRACTICE the session is closed and every request
      fails with ``IQ_OPTION_PRACTICE_NOT_CONFIRMED``.
    * Failed logins and dropped connections schedule the next attempt with an
      exponential backoff (``base * 2**(n-1)``, capped).
    """

    def __init__(
        self,
        email: str,
        password: str,
        transport_factory: Callable[[str, str], IqTransport],
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        backoff_base_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
        request_timeout_seconds: float = 12.0,
        logger: Callable[[str, dict[str, object]], None] | None = None,
    ) -> None:
        self._email = email.strip()
        self._password = password.strip()
        self._transport_factory = transport_factory
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._monotonic = monotonic
        self._backoff_base = backoff_base_seconds
        self._backoff_max = backoff_max_seconds
        self._request_timeout = request_timeout_seconds
        self._log = logger or (lambda event, data: None)

        self._transport: IqTransport | None = None
        self._state = "DISCONNECTED"
        self._consecutive_failures = 0
        self._next_attempt_monotonic = 0.0
        self._next_attempt_at: datetime | None = None
        self._connected_since: datetime | None = None
        self._last_error_code: str | None = None
        self._last_error_at: datetime | None = None
        self._server_offset_seconds: float | None = None
        self.counters = SessionCounters()

    # ------------------------------------------------------------------ state

    @property
    def state(self) -> str:
        return self._state

    def snapshot(self) -> dict[str, object]:
        """Public session status. Never contains credentials or tokens."""

        return {
            "state": self._state,
            "accountMode": "PRACTICE" if self._state == "CONNECTED" else None,
            "credentialsConfigured": bool(self._email and self._password),
            "connectedSince": to_iso(self._connected_since),
            "nextReconnectAt": to_iso(self._next_attempt_at),
            "consecutiveFailures": self._consecutive_failures,
            "lastErrorCode": self._last_error_code,
            "lastErrorAt": to_iso(self._last_error_at),
            "serverClockOffsetMs": (
                round(self._server_offset_seconds * 1000, 1)
                if self._server_offset_seconds is not None
                else None
            ),
            "counters": {
                "loginAttempts": self.counters.login_attempts,
                "loginsSucceeded": self.counters.logins_succeeded,
                "loginFailures": self.counters.login_failures,
                "reconnects": self.counters.reconnects,
                "candleRequests": self.counters.candle_requests,
                "candleRequestFailures": self.counters.candle_request_failures,
                "practiceChecksFailed": self.counters.practice_checks_failed,
            },
        }

    def reference_now(self) -> tuple[datetime, str]:
        """Return (now, clock) using the IQ server clock when it is known."""

        local_now = self._clock()

        if self._server_offset_seconds is None:
            return local_now, "LOCAL_UTC_CLOCK"

        return (
            datetime.fromtimestamp(
                local_now.timestamp() + self._server_offset_seconds,
                tz=UTC,
            ),
            "IQ_SERVER_CLOCK",
        )

    # ------------------------------------------------------------ connection

    def ensure_connected(self) -> None:
        if self._state == "CONNECTED" and self._transport is not None:
            if self._transport.is_connected():
                return

            self._log("iq_session_dropped", {})
            self.counters.reconnects += 1
            self._drop_transport()
            self._state = "DISCONNECTED"

        if not self._email or not self._password:
            self._state = "CREDENTIALS_MISSING"
            self._set_error(CredentialsMissingError.code)
            raise CredentialsMissingError(
                "IQ_OPTION_DEMO_EMAIL and IQ_OPTION_DEMO_PASSWORD must be configured"
            )

        if self._monotonic() < self._next_attempt_monotonic:
            self._state = "BACKOFF"
            raise BackoffActiveError(
                "IQ Option reconnection is waiting for its backoff interval",
                retry_at=self._next_attempt_at,
            )

        self._login()

    def _login(self) -> None:
        self._state = "CONNECTING"
        self.counters.login_attempts += 1
        self._log("iq_login_started", {"attempt": self.counters.login_attempts})

        try:
            transport = self._transport_factory(self._email, self._password)
            connected, reason = transport.connect()
        except TransportFatalError:
            self._register_failure("IQ_OPTION_CONNECT_HUNG")
            raise
        except Exception as error:  # noqa: BLE001 - library raises anything
            self._register_failure(SourceUnavailableError.code)
            raise SourceUnavailableError(
                f"could not connect to IQ Option: {self._safe(error)}",
                retry_at=self._next_attempt_at,
            ) from error

        if not connected:
            transport.close()
            self._register_failure(AuthenticationFailedError.code)
            raise AuthenticationFailedError(
                "IQ Option PRACTICE authentication failed"
                + (f": {self._safe(self._reason_text(reason))}" if reason else ""),
                retry_at=self._next_attempt_at,
            )

        try:
            transport.select_practice()
            mode = transport.balance_mode()
        except TransportFatalError:
            transport.close()
            self._register_failure("IQ_OPTION_CONNECT_HUNG")
            raise
        except Exception as error:  # noqa: BLE001
            mode = None
            self._log("iq_practice_check_error", {"error": self._safe(error)})

        if mode != "PRACTICE":
            transport.close()
            self.counters.practice_checks_failed += 1
            self._register_failure(PracticeNotConfirmedError.code)
            self._state = "PRACTICE_NOT_CONFIRMED"
            raise PracticeNotConfirmedError(
                "the IQ Option PRACTICE balance could not be confirmed; "
                "the session was closed and no data will be read",
                retry_at=self._next_attempt_at,
            )

        self._transport = transport
        self._state = "CONNECTED"
        self._consecutive_failures = 0
        self._next_attempt_monotonic = 0.0
        self._next_attempt_at = None
        self._connected_since = self._clock()
        self.counters.logins_succeeded += 1
        self._refresh_server_offset()
        self._log(
            "iq_login_succeeded",
            {"accountMode": "PRACTICE", "logins": self.counters.logins_succeeded},
        )

    def _register_failure(self, code: str) -> None:
        self.counters.login_failures += 1
        self._consecutive_failures += 1
        delay = min(
            self._backoff_base * (2 ** (self._consecutive_failures - 1)),
            self._backoff_max,
        )
        self._next_attempt_monotonic = self._monotonic() + delay
        self._next_attempt_at = datetime.fromtimestamp(
            self._clock().timestamp() + delay,
            tz=UTC,
        )
        self._state = "BACKOFF"
        self._set_error(code)
        self._log("iq_login_failed", {"code": code, "retryInSeconds": delay})

    def _set_error(self, code: str) -> None:
        self._last_error_code = code
        self._last_error_at = self._clock()

    def _drop_transport(self) -> None:
        if self._transport is not None:
            self._transport.close()

        self._transport = None
        self._connected_since = None

    def _refresh_server_offset(self) -> None:
        if self._transport is None:
            return

        server_seconds = self._transport.server_timestamp()

        if server_seconds is not None:
            self._server_offset_seconds = server_seconds - self._clock().timestamp()

    def close(self) -> None:
        """Close the websocket. Safe to call more than once."""

        if self._transport is None and self._state == "DISCONNECTED":
            return

        self._drop_transport()
        self._state = "DISCONNECTED"
        self._log("iq_session_closed", {})

    # ---------------------------------------------------------------- candles

    def fetch_candles(self, symbol: str, timeframe: str, count: int) -> FetchResult:
        interval = timeframe_seconds(timeframe)

        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 1000:
            raise ValueError("count must be an integer between 1 and 1000")

        self.ensure_connected()
        assert self._transport is not None

        requested_at = self._clock()
        self.counters.candle_requests += 1

        try:
            raw_candles = self._transport.request_candles(
                symbol=symbol,
                interval_seconds=interval,
                count=count,
                end_time=int(self.reference_now()[0].timestamp()),
                timeout_seconds=self._request_timeout,
            )
        except LookupError:
            self.counters.candle_request_failures += 1
            raise
        except TimeoutError as error:
            self.counters.candle_request_failures += 1
            self._on_transport_failure(SourceTimeoutError.code)
            raise SourceTimeoutError(str(error)) from error
        except (ConnectionError, OSError) as error:
            self.counters.candle_request_failures += 1
            self._on_transport_failure(SourceUnavailableError.code)
            raise SourceUnavailableError(
                f"IQ Option candle request failed: {self._safe(error)}"
            ) from error

        received_at = self._clock()
        self._refresh_server_offset()
        reference_now, reference_clock = self.reference_now()
        server_time = reference_now if reference_clock == "IQ_SERVER_CLOCK" else None

        closed: list[tuple[Candle, datetime]] = []
        quote: ObservedQuote | None = None

        for raw in raw_candles:
            candle, close_time = _parse_raw_candle(raw, interval)

            if close_time <= reference_now:
                closed.append((candle, close_time))
            else:
                at = raw.get("at") if isinstance(raw, dict) else None
                quote = ObservedQuote(
                    price=candle.close,
                    source_timestamp=_parse_source_timestamp(at),
                    observed_at=received_at,
                )

        closed.sort(key=lambda item: item[0].timestamp)

        return FetchResult(
            symbol=symbol,
            timeframe=timeframe,
            requested_count=count,
            candles=tuple(item[0] for item in closed),
            source_close_times=tuple(item[1] for item in closed),
            observed_quote=quote,
            requested_at=requested_at,
            received_at=received_at,
            reference_now=reference_now,
            reference_clock=reference_clock,
            server_time_at_receipt=server_time,
        )

    def _on_transport_failure(self, code: str) -> None:
        """Drop the broken session; the next request reconnects immediately."""

        self._set_error(code)
        self.counters.reconnects += 1
        self._drop_transport()
        self._state = "DISCONNECTED"
        self._log("iq_session_failed", {"code": code})

    # ---------------------------------------------------------------- helpers

    def _safe(self, value: object) -> str:
        return redact(value, secrets=(self._email, self._password))

    @staticmethod
    def _reason_text(reason: object) -> str:
        if isinstance(reason, str):
            try:
                payload = json.loads(reason)
            except json.JSONDecodeError:
                return reason[:200]

            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("code")
                if isinstance(message, str):
                    return message[:200]

            return "authentication rejected"

        return "authentication rejected"
