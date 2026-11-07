import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.candle import Candle
from app.domain.signal import Signal


class IqOptionDemoAnalysisRepository:
    """Persist and read IQ Option DEMO analyses with their closed candles."""

    source = "iq_option_demo"
    venue = "iq"
    account_mode = "PRACTICE"

    _record_id_pattern = re.compile(
        r"^iq-demo-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-z0-9]+$"
    )

    def __init__(self, root_directory: Path) -> None:
        self._root_directory = Path(root_directory)

    @property
    def root_directory(self) -> Path:
        """Return the local directory that contains analysis records."""

        return self._root_directory

    def save(
        self,
        signal: Signal,
        candles: tuple[Candle, ...],
        recorded_at: datetime,
    ) -> Path:
        """Write one immutable JSON record and return its path."""

        if not candles:
            raise ValueError("candles must contain at least one closed candle")

        recorded_at_utc = self._to_utc_timestamp(
            recorded_at,
            "recorded_at",
        )
        record_id = self._create_record_id(
            symbol=signal.symbol,
            recorded_at=recorded_at_utc,
        )

        if not self._record_id_pattern.fullmatch(record_id):
            raise RuntimeError("generated an invalid IQ Option DEMO record id")

        self._root_directory.mkdir(parents=True, exist_ok=True)

        record_path = self._root_directory / f"{record_id}.json"

        if record_path.exists():
            raise FileExistsError(
                f"IQ Option DEMO analysis record already exists: {record_id}"
            )

        payload = {
            "schemaVersion": 1,
            "recordId": record_id,
            "recordedAt": self._to_iso_timestamp(recorded_at_utc),
            "source": self.source,
            "venue": self.venue,
            "accountMode": self.account_mode,
            "analysis": {
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "timestamp": self._to_iso_timestamp(signal.timestamp),
                "direction": signal.direction.value,
                "score": signal.score,
                "reasons": list(signal.reasons),
                "strategy": "ema_crossover",
                "indicators": {
                    "fastEmaPeriod": 9,
                    "slowEmaPeriod": 21,
                },
            },
            "candles": [
                self._candle_to_payload(candle)
                for candle in candles
            ],
        }

        self._write_json_record(
            record_path=record_path,
            payload=payload,
        )

        return record_path

    def list_summaries(
        self,
        limit: int,
    ) -> tuple[dict[str, object], ...]:
        """Return the newest local analysis summaries without candle payloads."""

        if isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be greater than zero")

        if not self._root_directory.exists():
            return ()

        record_paths = sorted(
            self._root_directory.glob("iq-demo-*.json"),
            key=lambda path: path.name,
            reverse=True,
        )

        return tuple(
            self._record_to_summary(self._read_record(record_path))
            for record_path in record_paths[:limit]
        )

    def get_record(self, record_id: str) -> dict[str, object]:
        """Return one complete analysis record, including closed candles."""

        normalized_record_id = record_id.strip()

        if not self._record_id_pattern.fullmatch(normalized_record_id):
            raise ValueError("record_id has an invalid format")

        record_path = self._root_directory / f"{normalized_record_id}.json"

        if not record_path.is_file():
            raise FileNotFoundError(
                f"IQ Option DEMO analysis record was not found: "
                f"{normalized_record_id}"
            )

        return self._read_record(record_path)

    @classmethod
    def _create_record_id(
        cls,
        symbol: str,
        recorded_at: datetime,
    ) -> str:
        timestamp_part = recorded_at.strftime("%Y%m%d-%H%M%S-%f")
        normalized_symbol = re.sub(
            r"[^a-z0-9]+",
            "-",
            symbol.lower(),
        ).strip("-")
        unique_part = uuid4().hex[:10]

        return f"iq-demo-{timestamp_part}-{normalized_symbol}-{unique_part}"

    @classmethod
    def _write_json_record(
        cls,
        record_path: Path,
        payload: dict[str, object],
    ) -> None:
        temporary_path = record_path.with_suffix(".tmp")
        serialized_payload = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

        temporary_path.write_text(
            f"{serialized_payload}\n",
            encoding="utf-8",
        )
        temporary_path.replace(record_path)

    @classmethod
    def _read_record(cls, record_path: Path) -> dict[str, object]:
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"IQ Option DEMO analysis record is unreadable: "
                f"{record_path.name}"
            ) from error

        if not isinstance(payload, dict):
            raise ValueError(
                f"IQ Option DEMO analysis record is invalid: "
                f"{record_path.name}"
            )

        cls._validate_record(
            payload=payload,
            expected_record_id=record_path.stem,
        )

        return payload

    @classmethod
    def _validate_record(
        cls,
        payload: dict[str, object],
        expected_record_id: str,
    ) -> None:
        analysis = payload.get("analysis")
        candles = payload.get("candles")

        if (
            payload.get("schemaVersion") != 1
            or payload.get("recordId") != expected_record_id
            or not isinstance(payload.get("recordedAt"), str)
            or payload.get("source") != cls.source
            or payload.get("venue") != cls.venue
            or payload.get("accountMode") != cls.account_mode
            or not isinstance(analysis, Mapping)
            or not isinstance(candles, list)
        ):
            raise ValueError(
                f"IQ Option DEMO analysis record is invalid: "
                f"{expected_record_id}.json"
            )

        required_analysis_fields = (
            "symbol",
            "timeframe",
            "timestamp",
            "direction",
            "score",
            "reasons",
            "strategy",
            "indicators",
        )

        if any(field not in analysis for field in required_analysis_fields):
            raise ValueError(
                f"IQ Option DEMO analysis record is invalid: "
                f"{expected_record_id}.json"
            )

    @classmethod
    def _record_to_summary(
        cls,
        record: dict[str, object],
    ) -> dict[str, object]:
        analysis = record["analysis"]

        if not isinstance(analysis, Mapping):
            raise RuntimeError("validated IQ Option DEMO record has no analysis")

        return {
            "recordId": record["recordId"],
            "recordedAt": record["recordedAt"],
            "source": record["source"],
            "venue": record["venue"],
            "accountMode": record["accountMode"],
            "symbol": analysis["symbol"],
            "timeframe": analysis["timeframe"],
            "timestamp": analysis["timestamp"],
            "direction": analysis["direction"],
            "score": analysis["score"],
            "strategy": analysis["strategy"],
        }

    @classmethod
    def _candle_to_payload(
        cls,
        candle: Candle,
    ) -> dict[str, object]:
        return {
            "timestamp": cls._to_iso_timestamp(candle.timestamp),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
            "closed": True,
        }

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