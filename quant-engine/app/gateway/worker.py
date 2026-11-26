"""Long-lived JSON-lines worker that owns the single IQ Option session.

Protocol (one JSON object per line):

    request  -> {"id": "r1", "cmd": "analyze_m1", "args": {...}}
    response <- {"type": "response", "id": "r1", "ok": true, "result": {...}, "meta": {...}}
    response <- {"type": "response", "id": "r1", "ok": false,
                 "error": {"code": ..., "message": ...}}

The protocol is written to a private duplicate of the original stdout. The
process-wide ``sys.stdout`` is redirected to stderr, so anything printed by
third-party code can never corrupt the protocol. Logs are JSON lines on
stderr and never contain credentials.

Run with: ``python -m app.gateway.worker``.
"""

import json
import logging
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TextIO

from app.gateway.candle_cache import CandleCache
from app.gateway.provider import SessionBackedProvider
from app.gateway.redaction import redact
from app.gateway.session import GatewayError, IqSession
from app.gateway.timeframes import timeframe_seconds, to_iso
from app.gateway.transport import IqOptionApiTransport, TransportFatalError

WORKER_PROTOCOL_VERSION = 1
COMMANDS = ("status", "candles", "analyze_m1", "analyze_m5", "m5_sync", "shutdown")
FATAL_EXIT_CODE = 3


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


class Worker:
    def __init__(
        self,
        session: IqSession,
        cache: CandleCache,
        clock: Callable[[], datetime] = now_utc,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.session = session
        self.cache = cache
        self.clock = clock
        self._secrets = secrets
        self.running = True

    # ------------------------------------------------------------ dispatch

    def handle(self, message: object) -> dict[str, object]:
        request_id = message.get("id") if isinstance(message, dict) else None
        started_at = self.clock()

        try:
            if not isinstance(message, dict) or not isinstance(request_id, str):
                raise ValueError("request must be an object with a string id")

            command = message.get("cmd")
            args = message.get("args") or {}

            if command not in COMMANDS or not isinstance(args, dict):
                raise ValueError(f"unsupported command: {command!r}")

            provider = SessionBackedProvider(self.cache)
            result = getattr(self, f"_cmd_{command}")(args, provider)
            completed_at = self.clock()

            return {
                "type": "response",
                "id": request_id,
                "ok": True,
                "result": result,
                "meta": self._meta(started_at, completed_at, provider),
            }
        except TransportFatalError:
            raise
        except Exception as error:  # noqa: BLE001 - every failure is reported
            return {
                "type": "response",
                "id": request_id,
                "ok": False,
                "error": self._error_payload(error),
                "meta": self._meta(started_at, self.clock(), None),
            }

    def _meta(
        self,
        started_at: datetime,
        completed_at: datetime,
        provider: SessionBackedProvider | None,
    ) -> dict[str, object]:
        return {
            "workerProtocolVersion": WORKER_PROTOCOL_VERSION,
            "analysisStartedAt": to_iso(started_at),
            "analysisCompletedAt": to_iso(completed_at),
            "workerDurationMs": round((completed_at - started_at).total_seconds() * 1000, 3),
            "clock": "LOCAL_UTC_CLOCK",
            "fetches": provider.fetch_metadata() if provider is not None else [],
            "session": self.session.snapshot(),
            "cache": {"hits": self.cache.hits, "misses": self.cache.misses},
        }

    def _error_payload(self, error: Exception) -> dict[str, object]:
        if isinstance(error, GatewayError):
            code = error.code
        elif isinstance(error, LookupError):
            code = "IQ_OPTION_DATA_NOT_FOUND"
        elif isinstance(error, ValueError):
            code = "INVALID_GATEWAY_REQUEST"
        else:
            code = "GATEWAY_INTERNAL_ERROR"

        payload: dict[str, object] = {
            "code": code,
            "message": redact(error, self._secrets)[:500],
        }

        if isinstance(error, GatewayError) and error.retry_at is not None:
            payload["retryAt"] = to_iso(error.retry_at)

        return payload

    # ------------------------------------------------------------ commands

    def _cmd_status(self, args: dict, provider: SessionBackedProvider) -> dict:
        if args.get("connect") is True:
            self.session.ensure_connected()

        return {"session": self.session.snapshot()}

    def _cmd_candles(self, args: dict, provider: SessionBackedProvider) -> dict:
        from app.cli.get_iq_option_demo_candles import get_iq_option_demo_candles

        return get_iq_option_demo_candles(
            symbol=str(args.get("symbol", "")),
            timeframe=str(args.get("timeframe", "1m")),
            limit=int(args.get("limit", 100)),
            provider=provider,  # type: ignore[arg-type]
        )

    def _cmd_analyze_m1(self, args: dict, provider: SessionBackedProvider) -> dict:
        from app.cli.analyze_iq_option_binary_signal import analyze_iq_option_binary_signal

        timeframe = str(args.get("timeframe", "1m"))

        return analyze_iq_option_binary_signal(
            symbol=str(args.get("symbol", "")),
            timeframe=timeframe,
            limit=int(args.get("limit", 120)),
            # Freshness is one full timeframe (A.2): replaces the former
            # generic 120 s limit that was wrong for M5.
            max_candle_age_seconds=timeframe_seconds(timeframe),
            provider=provider,  # type: ignore[arg-type]
            now=self.clock,
        )

    def _cmd_analyze_m5(self, args: dict, provider: SessionBackedProvider) -> dict:
        from app.cli.get_iq_option_demo_m5_signal_with_m15 import (
            get_iq_option_demo_m5_signal_with_m15,
        )

        return get_iq_option_demo_m5_signal_with_m15(
            symbol=str(args.get("symbol", "")),
            provider=provider,  # type: ignore[arg-type]
            now=self.clock,
        )

    def _cmd_m5_sync(self, args: dict, provider: SessionBackedProvider) -> dict:
        from app.cli.get_iq_option_demo_m5_sync import get_iq_option_demo_m5_sync

        return get_iq_option_demo_m5_sync(
            symbol=str(args.get("symbol", "")),
            provider=provider,  # type: ignore[arg-type]
            now=self.clock,
        )

    def _cmd_shutdown(self, args: dict, provider: SessionBackedProvider) -> dict:
        self.running = False
        self.session.close()
        return {"session": self.session.snapshot()}


# ---------------------------------------------------------------- process


def _json_log(stream: TextIO, secrets: tuple[str, ...]) -> Callable[[str, dict], None]:
    def log(event: str, data: dict) -> None:
        record = {
            "type": "log",
            "at": to_iso(now_utc()),
            "event": event,
            **{key: redact(value, secrets) if isinstance(value, str) else value
               for key, value in data.items()},
        }
        stream.write(json.dumps(record) + "\n")
        stream.flush()

    return log


def build_worker(env: dict[str, str], log_stream: TextIO) -> Worker:
    email = env.get("IQ_OPTION_DEMO_EMAIL", "")
    password = env.get("IQ_OPTION_DEMO_PASSWORD", "")
    secrets = tuple(value for value in (email.strip(), password.strip()) if value)
    log = _json_log(log_stream, secrets)

    session = IqSession(
        email=email,
        password=password,
        transport_factory=lambda user, secret: IqOptionApiTransport(user, secret),
        backoff_base_seconds=float(env.get("IQ_GATEWAY_BACKOFF_BASE_SECONDS", "1")),
        backoff_max_seconds=float(env.get("IQ_GATEWAY_BACKOFF_MAX_SECONDS", "60")),
        request_timeout_seconds=float(env.get("IQ_GATEWAY_CANDLE_TIMEOUT_SECONDS", "12")),
        logger=log,
    )
    cache = CandleCache(
        session,
        min_refetch_seconds=float(env.get("IQ_GATEWAY_MIN_REFETCH_SECONDS", "1")),
    )

    return Worker(session=session, cache=cache, secrets=secrets)


def serve(worker: Worker, stdin: TextIO, protocol: TextIO, log_stream: TextIO) -> int:
    def write(payload: dict) -> None:
        protocol.write(json.dumps(payload, default=str) + "\n")
        protocol.flush()

    write({"type": "ready", "protocolVersion": WORKER_PROTOCOL_VERSION, "pid": os.getpid()})

    try:
        for line in stdin:
            if not line.strip():
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                write({"type": "response", "id": None, "ok": False,
                       "error": {"code": "INVALID_GATEWAY_REQUEST", "message": "invalid JSON"}})
                continue

            try:
                write(worker.handle(message))
            except TransportFatalError as error:
                write({
                    "type": "response",
                    "id": message.get("id") if isinstance(message, dict) else None,
                    "ok": False,
                    "error": {"code": "IQ_OPTION_CONNECT_HUNG", "message": str(error)},
                })
                write({"type": "fatal", "reason": "IQ_OPTION_CONNECT_HUNG"})
                return FATAL_EXIT_CODE

            if not worker.running:
                break
    finally:
        worker.session.close()

    return 0


def main() -> int:
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr

    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    logging.getLogger("iqoptionapi").setLevel(logging.ERROR)
    logging.getLogger("websocket").setLevel(logging.ERROR)

    worker = build_worker(dict(os.environ), sys.stderr)
    return serve(worker, sys.stdin, protocol, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
