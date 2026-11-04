import json
import re
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path

from app.domain.collected_candle import CollectedCandle
from app.domain.market_tick import MarketTick
from app.streams.otcharts_iq_option_stream import OtchartsIqOptionStreamEvent


class IqOptionSessionRepository:
    """Persist one read-only IQ Option streaming capture session locally."""

    _allowed_final_statuses = {"completed", "failed", "cancelled"}
    _session_id_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    _otcharts_key_pattern = re.compile(r"otc_(?:live|test)_[A-Za-z0-9]+")

    def __init__(
        self,
        session_directory: Path,
        manifest: dict[str, object],
    ) -> None:
        self._session_directory = session_directory
        self._manifest = manifest
        self._is_closed = False

    @property
    def session_directory(self) -> Path:
        return self._session_directory

    @property
    def manifest_path(self) -> Path:
        return self._session_directory / "manifest.json"

    @classmethod
    def create(
        cls,
        root_directory: Path,
        symbol: str,
        started_at: datetime,
        session_id: str | None = None,
    ) -> "IqOptionSessionRepository":
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        started_at_utc = cls._to_utc_timestamp(started_at, "started_at")
        resolved_session_id = session_id or cls._create_session_id(
            normalized_symbol,
            started_at_utc,
        )

        if not cls._session_id_pattern.fullmatch(resolved_session_id):
            raise ValueError("session_id contains unsupported characters")

        session_directory = Path(root_directory) / resolved_session_id

        if session_directory.exists():
            raise FileExistsError(
                f"IQ Option session directory already exists: {resolved_session_id}"
            )

        session_directory.mkdir(parents=True, exist_ok=False)

        manifest: dict[str, object] = {
            "schemaVersion": 1,
            "sessionId": resolved_session_id,
            "symbol": normalized_symbol,
            "venue": "iq",
            "source": "otcharts_iq_option_stream",
            "status": "collecting",
            "startedAt": cls._to_iso_timestamp(started_at_utc),
            "endedAt": None,
            "eventCount": 0,
            "tickCount": 0,
            "candleCount": 0,
            "errorCount": 0,
            "chartObservationCount": 0,
        }

        repository = cls(
            session_directory=session_directory,
            manifest=manifest,
        )
        repository._write_manifest()

        return repository

    def record_stream_event(
        self,
        stream_event: OtchartsIqOptionStreamEvent,
    ) -> None:
        self._assert_open()

        self._append_json_line(
            "events.jsonl",
            {
                "event": stream_event.event,
                "receivedAt": self._to_iso_timestamp(stream_event.received_at),
                "data": stream_event.data,
            },
        )
        self._increment_manifest_counter("eventCount")

    def record_tick(
        self,
        tick: MarketTick,
        received_at: datetime,
    ) -> None:
        self._assert_open()

        if tick.symbol != self._manifest["symbol"]:
            raise ValueError("tick symbol does not match the session symbol")

        received_at_utc = self._to_utc_timestamp(received_at, "received_at")

        self._append_json_line(
            "ticks.jsonl",
            {
                "symbol": tick.symbol,
                "sourceTimestamp": self._to_iso_timestamp(tick.timestamp),
                "receivedAt": self._to_iso_timestamp(received_at_utc),
                "price": tick.price,
                "volume": tick.volume,
            },
        )
        self._increment_manifest_counter("tickCount")

    def record_candle(self, collected_candle: CollectedCandle) -> None:
        self._assert_open()

        candle = collected_candle.candle

        self._append_json_line(
            "candles.jsonl",
            {
                "openTimestamp": self._to_iso_timestamp(candle.timestamp),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "volumeAvailable": collected_candle.volume_available,
                "tickCount": collected_candle.tick_count,
                "sourceFirstTimestamp": self._to_iso_timestamp(
                    collected_candle.source_first_timestamp
                ),
                "sourceLastTimestamp": self._to_iso_timestamp(
                    collected_candle.source_last_timestamp
                ),
                "missingMinutesAfter": collected_candle.missing_minutes_after,
            },
        )
        self._increment_manifest_counter("candleCount")

    def record_chart_observation(
        self,
        observed_at: datetime,
        displayed_price: float,
        note: str | None = None,
    ) -> None:
        self._assert_open()

        observed_at_utc = self._to_utc_timestamp(observed_at, "observed_at")

        if not isfinite(displayed_price) or displayed_price <= 0:
            raise ValueError("displayed_price must be a finite positive number")

        normalized_note = note.strip() if note is not None else None

        self._append_json_line(
            "iq-chart-observations.jsonl",
            {
                "observedAt": self._to_iso_timestamp(observed_at_utc),
                "displayedPrice": displayed_price,
                "note": normalized_note or None,
            },
        )
        self._increment_manifest_counter("chartObservationCount")

    def record_error(
        self,
        error: Exception,
        occurred_at: datetime,
    ) -> None:
        self._assert_open()

        occurred_at_utc = self._to_utc_timestamp(occurred_at, "occurred_at")

        self._append_json_line(
            "errors.jsonl",
            {
                "occurredAt": self._to_iso_timestamp(occurred_at_utc),
                "errorType": type(error).__name__,
                "message": self._redact_sensitive_text(str(error)),
            },
        )
        self._increment_manifest_counter("errorCount")

    def close(
        self,
        status: str,
        ended_at: datetime,
    ) -> None:
        self._assert_open()

        if status not in self._allowed_final_statuses:
            allowed_statuses = ", ".join(sorted(self._allowed_final_statuses))
            raise ValueError(f"status must be one of: {allowed_statuses}")

        ended_at_utc = self._to_utc_timestamp(ended_at, "ended_at")

        self._manifest["status"] = status
        self._manifest["endedAt"] = self._to_iso_timestamp(ended_at_utc)
        self._write_manifest()
        self._is_closed = True

    def _increment_manifest_counter(self, counter_name: str) -> None:
        current_value = self._manifest[counter_name]

        if not isinstance(current_value, int):
            raise RuntimeError(f"invalid manifest counter: {counter_name}")

        self._manifest[counter_name] = current_value + 1
        self._write_manifest()

    def _append_json_line(
        self,
        file_name: str,
        payload: dict[str, object],
    ) -> None:
        serialized_payload = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with (self._session_directory / file_name).open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as file:
            file.write(f"{serialized_payload}\n")

    def _write_manifest(self) -> None:
        temporary_path = self.manifest_path.with_suffix(".tmp")
        serialized_manifest = json.dumps(
            self._manifest,
            ensure_ascii=False,
            indent=2,
        )

        temporary_path.write_text(
            f"{serialized_manifest}\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.manifest_path)

    def _assert_open(self) -> None:
        if self._is_closed:
            raise RuntimeError("IQ Option session is already closed")

    @classmethod
    def _create_session_id(
        cls,
        symbol: str,
        started_at: datetime,
    ) -> str:
        timestamp_part = started_at.strftime("%Y%m%d-%H%M%S")
        symbol_part = symbol.lower().replace("/", "-")

        return f"iq-{timestamp_part}-{symbol_part}"

    @staticmethod
    def _to_utc_timestamp(
        timestamp: datetime,
        field_name: str,
    ) -> datetime:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")

        return timestamp.astimezone(UTC)

    @staticmethod
    def _to_iso_timestamp(timestamp: datetime) -> str:
        return timestamp.astimezone(UTC).isoformat()

    @classmethod
    def _redact_sensitive_text(cls, text: str) -> str:
        return cls._otcharts_key_pattern.sub(
            "[REDACTED_OTCHARTS_KEY]",
            text,
        )