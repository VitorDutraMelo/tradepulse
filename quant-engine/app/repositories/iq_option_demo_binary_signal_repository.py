import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.candle import Candle
from app.domain.iq_option_binary_signal import IqOptionBinarySignal
from app.domain.trade_signal import TradeAction


class IqOptionDemoBinarySignalRepository:
    """Store and read IQ Option DEMO technical references and outcomes."""

    source = "iq_option_demo"
    account_mode = "PRACTICE"
    _record_id_pattern = re.compile(
        r"^iq-demo-binary-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$"
    )

    def __init__(self, root_directory: Path) -> None:
        self._root_directory = Path(root_directory)

    def save_pending(
        self,
        signal: IqOptionBinarySignal,
        recorded_at: datetime,
    ) -> Path:
        if signal.action not in {TradeAction.CALL, TradeAction.PUT}:
            raise ValueError("only CALL and PUT references can be persisted")

        if (
            signal.reference_price is None
            or signal.reference_entry_time is None
            or signal.reference_expiration_time is None
        ):
            raise ValueError(
                "CALL and PUT references require price, entry and expiration"
            )

        recorded_at_utc = self._to_utc(recorded_at, "recorded_at")
        existing_path = self._find_existing_reference(signal)

        if existing_path is not None:
            return existing_path

        self._root_directory.mkdir(parents=True, exist_ok=True)

        record_id = self._create_record_id(
            symbol=signal.symbol,
            recorded_at=recorded_at_utc,
        )
        record_path = self._root_directory / f"{record_id}.json"

        payload = {
            "schemaVersion": 1,
            "recordId": record_id,
            "recordedAt": self._to_iso(recorded_at_utc),
            "source": self.source,
            "accountMode": self.account_mode,
            "analysis": {
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "analysisAt": self._to_iso(signal.analysis_at),
                "action": signal.action.value,
                "reasons": list(signal.reasons),
                "reference": {
                    "price": signal.reference_price,
                    "entryTime": self._to_iso(signal.reference_entry_time),
                    "expirationTime": self._to_iso(
                        signal.reference_expiration_time
                    ),
                },
            },
            "outcome": {
                "status": "PENDING",
                "settledAt": None,
                "settlementPrice": None,
            },
            "disclaimer": (
                "Technical reference only. No IQ Option order was sent. "
                "WIN, LOSS and DRAW are technical candle comparisons only, "
                "not broker settlement records."
            ),
        }

        self._write_record(record_path, payload)
        return record_path

    def settle_due_references(
        self,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        settled_at: datetime,
    ) -> tuple[dict[str, object], ...]:
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip()
        settled_at_utc = self._to_utc(settled_at, "settled_at")

        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        if not normalized_timeframe:
            raise ValueError("timeframe must not be empty")

        candles_by_open_time = {
            self._to_iso(candle.timestamp): candle
            for candle in candles
        }
        settled_records: list[dict[str, object]] = []

        for record_path in self._record_paths():
            record = self._read_record(record_path)
            analysis = record["analysis"]
            outcome = record["outcome"]
            reference = analysis["reference"]

            if (
                analysis["symbol"] != normalized_symbol
                or analysis["timeframe"] != normalized_timeframe
                or outcome["status"] != "PENDING"
            ):
                continue

            expiration_time = self._parse_timestamp(
                reference["expirationTime"]
            )

            if settled_at_utc < expiration_time:
                continue

            settlement_candle = candles_by_open_time.get(
                reference["entryTime"]
            )

            if settlement_candle is None:
                continue

            settlement_price = settlement_candle.close
            reference_price = float(reference["price"])
            action = analysis["action"]

            if action == "CALL":
                status = (
                    "WIN"
                    if settlement_price > reference_price
                    else "LOSS"
                    if settlement_price < reference_price
                    else "DRAW"
                )
            else:
                status = (
                    "WIN"
                    if settlement_price < reference_price
                    else "LOSS"
                    if settlement_price > reference_price
                    else "DRAW"
                )

            record["outcome"] = {
                "status": status,
                "settledAt": self._to_iso(settled_at_utc),
                "settlementPrice": settlement_price,
            }

            self._write_record(record_path, record)
            settled_records.append(self._tracking_from_record(record))

        return tuple(settled_records)

    def list_records(self, limit: int) -> tuple[dict[str, object], ...]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        return tuple(
            self._read_record(record_path)
            for record_path in self._record_paths()[:limit]
        )

    def get_record(self, record_id: str) -> dict[str, object]:
        return self._read_record(self._record_path_for_id(record_id))

    def get_tracking(self, record_id: str) -> dict[str, object]:
        return self._tracking_from_record(self.get_record(record_id))

    def _record_path_for_id(self, record_id: str) -> Path:
        if not isinstance(record_id, str) or not self._record_id_pattern.fullmatch(
            record_id
        ):
            raise ValueError("IQ Option DEMO binary reference id is invalid")

        record_path = self._root_directory / f"{record_id}.json"

        if not record_path.is_file():
            raise FileNotFoundError(
                f"IQ Option DEMO binary reference was not found: {record_id}"
            )

        return record_path

    def _find_existing_reference(
        self,
        signal: IqOptionBinarySignal,
    ) -> Path | None:
        if signal.reference_entry_time is None:
            raise ValueError("reference_entry_time must be configured")

        entry_time = self._to_iso(signal.reference_entry_time)

        for record_path in self._record_paths():
            record = self._read_record(record_path)
            analysis = record["analysis"]
            reference = analysis["reference"]

            if (
                analysis["symbol"] == signal.symbol
                and analysis["timeframe"] == signal.timeframe
                and analysis["action"] == signal.action.value
                and reference["entryTime"] == entry_time
            ):
                return record_path

        return None

    def _record_paths(self) -> tuple[Path, ...]:
        if not self._root_directory.exists():
            return ()

        return tuple(
            sorted(
                self._root_directory.glob("iq-demo-binary-*.json"),
                key=lambda path: path.name,
                reverse=True,
            )
        )

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

        return (
            f"iq-demo-binary-{timestamp_part}-"
            f"{normalized_symbol}-{uuid4().hex[:10]}"
        )

    @staticmethod
    def _write_record(
        record_path: Path,
        payload: dict[str, object],
    ) -> None:
        temporary_path = record_path.with_suffix(".tmp")
        temporary_path.write_text(
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n",
            encoding="utf-8",
        )
        temporary_path.replace(record_path)

    @staticmethod
    def _read_record(record_path: Path) -> dict[str, object]:
        payload = json.loads(record_path.read_text(encoding="utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("IQ Option DEMO binary reference is invalid")

        return payload

    @staticmethod
    def _tracking_from_record(
        record: dict[str, object],
    ) -> dict[str, object]:
        outcome = record["outcome"]

        return {
            "recordId": record["recordId"],
            "status": outcome["status"],
            "settledAt": outcome["settledAt"],
            "settlementPrice": outcome["settlementPrice"],
        }

    @staticmethod
    def _to_utc(timestamp: datetime, field_name: str) -> datetime:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")

        return timestamp.astimezone(UTC)

    @staticmethod
    def _to_iso(timestamp: datetime) -> str:
        return timestamp.astimezone(UTC).isoformat()

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError("stored expiration time is invalid")

        timestamp = datetime.fromisoformat(value)

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("stored expiration time is invalid")

        return timestamp.astimezone(UTC)
