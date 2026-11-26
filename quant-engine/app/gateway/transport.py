"""Read-only transport over the unofficial ``iqoptionapi`` library.

The library has hazards that this adapter neutralizes:

* ``IQ_Option.get_candles`` busy-waits forever when the websocket drops and
  silently performs a new login on errors. The adapter sends the candle
  request itself and waits with a deadline, so a session is never re-created
  behind the gateway's back and a call can never hang indefinitely.
* ``IQ_Option.connect`` may busy-wait without a deadline. The adapter runs it
  in a daemon thread and raises :class:`TransportFatalError` on timeout so the
  worker process can be restarted cleanly.
* ``change_balance`` returns nothing. PRACTICE selection is verified with
  ``get_balance_mode`` by the session.

Only read operations are exposed. There is deliberately no method that can
place, close or modify an order.
"""

import threading
import time
from collections.abc import Callable
from typing import Protocol

# Methods of IQ_Option that the gateway is allowed to call. Anything that can
# trade (buy, sell, close_position, ...) is intentionally absent.
ALLOWED_LIBRARY_METHODS = frozenset(
    {
        "connect",
        "check_connect",
        "change_balance",
        "get_balance_mode",
        "get_server_timestamp",
    }
)


class TransportFatalError(RuntimeError):
    """The library is in an unknown state; the worker must be restarted."""


class IqTransport(Protocol):
    """Minimal read-only contract used by :class:`IqSession`."""

    def connect(self) -> tuple[bool, str | None]: ...

    def is_connected(self) -> bool: ...

    def select_practice(self) -> None: ...

    def balance_mode(self) -> str | None: ...

    def server_timestamp(self) -> float | None: ...

    def request_candles(
        self,
        symbol: str,
        interval_seconds: int,
        count: int,
        end_time: int,
        timeout_seconds: float,
    ) -> list[dict[str, object]]: ...

    def close(self) -> None: ...


def _run_with_deadline(
    operation: Callable[[], object],
    timeout_seconds: float,
    description: str,
) -> object:
    outcome: dict[str, object] = {}

    def target() -> None:
        try:
            outcome["value"] = operation()
        except BaseException as error:  # noqa: BLE001 - re-raised below
            outcome["error"] = error

    thread = threading.Thread(target=target, name=description, daemon=True)
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        raise TransportFatalError(f"{description} did not finish in {timeout_seconds:.0f}s")

    if "error" in outcome:
        raise outcome["error"]  # type: ignore[misc]

    return outcome.get("value")


class IqOptionApiTransport:
    """Adapter around ``iqoptionapi.stable_api.IQ_Option``."""

    def __init__(
        self,
        email: str,
        password: str,
        connect_timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.01,
    ) -> None:
        from iqoptionapi.stable_api import IQ_Option

        self._client = IQ_Option(email, password)
        self._connect_timeout_seconds = connect_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    def connect(self) -> tuple[bool, str | None]:
        result = _run_with_deadline(
            self._client.connect,
            self._connect_timeout_seconds,
            "iq-option-connect",
        )

        if not isinstance(result, tuple) or len(result) != 2:
            return False, "unexpected connect response"

        connected, reason = result
        return connected is True, reason if isinstance(reason, str) else None

    def is_connected(self) -> bool:
        from iqoptionapi import global_value

        return bool(global_value.check_websocket_if_connect)

    def select_practice(self) -> None:
        _run_with_deadline(
            lambda: self._client.change_balance("PRACTICE"),
            self._connect_timeout_seconds,
            "iq-option-select-practice",
        )

    def balance_mode(self) -> str | None:
        mode = _run_with_deadline(
            self._client.get_balance_mode,
            self._connect_timeout_seconds,
            "iq-option-balance-mode",
        )
        return mode if isinstance(mode, str) else None

    def server_timestamp(self) -> float | None:
        try:
            value = self._client.get_server_timestamp()
        except Exception:  # noqa: BLE001 - timesync may not exist yet
            return None

        if isinstance(value, (int, float)) and value > 0:
            return float(value)

        return None

    def request_candles(
        self,
        symbol: str,
        interval_seconds: int,
        count: int,
        end_time: int,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        from iqoptionapi import constants, global_value

        active_id = constants.ACTIVES.get(symbol)

        if active_id is None:
            raise LookupError(f"IQ Option asset is not known by the client: {symbol}")

        api = self._client.api
        api.candles.candles_data = None

        try:
            api.getcandles(active_id, interval_seconds, count, end_time)
        except Exception as error:
            raise ConnectionError("could not send the IQ Option candle request") from error

        deadline = time.monotonic() + timeout_seconds

        while api.candles.candles_data is None:
            if not global_value.check_websocket_if_connect:
                raise ConnectionError("IQ Option websocket disconnected")

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"IQ Option did not answer the candle request in {timeout_seconds:.0f}s"
                )

            time.sleep(self._poll_interval_seconds)

        data = api.candles.candles_data

        if not isinstance(data, list):
            raise ValueError("IQ Option returned an invalid candle response")

        return data

    def close(self) -> None:
        try:
            self._client.api.close()
        except Exception:  # noqa: BLE001 - closing a dead socket is best effort
            pass
