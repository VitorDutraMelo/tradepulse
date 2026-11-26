import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.candle import Candle


class IqOptionDemoM5ValidationRepository:
    """Persist theoretical M5+M15 validations and technical outcomes.

    This repository is intentionally separate from M1 binary-signal history.
    It records no broker order, balance, payout or settlement information.
    """

    source = "iq_option_demo"
    venue = "iq"
    account_mode = "PRACTICE"

    _record_id_pattern = re.compile(
        r"^iq-demo-m5-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$"
    )

    def __init__(self, root_directory: Path) -> None:
        self._root_directory = Path(root_directory)

    def save_pending(
        self,
        signal_payload: dict[str, object],
        recorded_at: datetime,
    ) -> Path:
        decision = self._required_object(signal_payload, "decision")
        context_m15 = self._required_object(signal_payload, "contextM15")
        latest_candle = self._required_object(
            signal_payload,
            "latestClosedCandle",
        )

        symbol = self._required_string(signal_payload, "symbol")
        timeframe = self._required_string(signal_payload, "timeframe")
        action = self._required_string(decision, "candidateAction")

        if timeframe != "5m":
            raise ValueError("only M5 validations can be persisted")

        if action not in {"CALL", "PUT"}:
            raise ValueError("only aligned CALL and PUT candidates can be persisted")

        if context_m15.get("state") != "UPDATED":
            raise ValueError("M15 context must be UPDATED before persistence")

        required_trend = "BULLISH" if action == "CALL" else "BEARISH"

        if context_m15.get("trend") != required_trend:
            raise ValueError(
                f"{action} requires {required_trend} M15 confirmation"
            )

        reference_price = self._required_number(latest_candle, "close")
        entry_time = self._required_string(
            decision,
            "theoreticalEntryTime",
        )
        expiration_time = self._required_string(
            decision,
            "theoreticalExpirationTime",
        )
        recorded_at_utc = self._to_utc(recorded_at, "recorded_at")

        existing_path = self._find_existing_reference(
            symbol=symbol,
            action=action,
            entry_time=entry_time,
        )

        if existing_path is not None:
            return existing_path

        self._root_directory.mkdir(parents=True, exist_ok=True)

        record_id = self._create_record_id(
            symbol=symbol,
            recorded_at=recorded_at_utc,
        )
        record_path = self._root_directory / f"{record_id}.json"

        payload = {
            "schemaVersion": 1,
            "recordId": record_id,
            "recordedAt": self._to_iso(recorded_at_utc),
            "source": self.source,
            "venue": self.venue,
            "accountMode": self.account_mode,
            "analysis": {
                "symbol": symbol,
                "timeframe": timeframe,
                "action": action,
                "m5CandidateAction": decision.get("m5CandidateAction"),
                "actionability": decision.get("actionability"),
                "reasons": list(decision.get("reasons", [])),
                "reference": {
                    "price": reference_price,
                    "entryTime": entry_time,
                    "expirationTime": expiration_time,
                },
                "latestClosedCandle": latest_candle,
                "indicators": signal_payload.get("indicators"),
                "dataQuality": signal_payload.get("dataQuality"),
                "contextM15": context_m15,
            },
            "outcome": {
                "status": "PENDING",
                "settledAt": None,
                "settlementPrice": None,
            },
            "disclaimer": (
                "Technical validation only. No IQ Option order was sent. "
                "WIN, LOSS and DRAW compare closed candles and are not "
                "broker settlement records, payout records or guarantees."
            ),
        }

        self._write_record(record_path, payload)
        return record_path

    def settle_due_references(
        self,
        candles: Sequence[Candle],
        settled_at: datetime,
    ) -> tuple[dict[str, object], ...]:
        settled_at_utc = self._to_utc(settled_at, "settled_at")
        candles_by_open_time = {
            self._to_iso(candle.timestamp): candle
            for candle in candles
        }
        settled_records: list[dict[str, object]] = []

        for record_path in self._record_paths():
            record = self._read_record(record_path)
            analysis = self._required_object(record, "analysis")
            outcome = self._required_object(record, "outcome")

            if outcome.get("status") != "PENDING":
                continue

            reference = self._required_object(analysis, "reference")
            expiration_time = self._parse_timestamp(
                reference.get("expirationTime")
            )

            if settled_at_utc < expiration_time:
                continue

            settlement_candle = candles_by_open_time.get(
                reference.get("entryTime")
            )

            if settlement_candle is None:
                continue

            action = self._required_string(analysis, "action")
            reference_price = self._required_number(reference, "price")
            settlement_price = settlement_candle.close

            if action == "CALL":
                status = (
                    "WIN"
                    if settlement_price > reference_price
                    else "LOSS"
                    if settlement_price < reference_price
                    else "DRAW"
                )
            elif action == "PUT":
                status = (
                    "WIN"
                    if settlement_price < reference_price
                    else "LOSS"
                    if settlement_price > reference_price
                    else "DRAW"
                )
            else:
                raise ValueError("stored M5 validation action is invalid")

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
            self._read_record(path)
            for path in self._record_paths()[:limit]
        )

    def get_record(self, record_id: str) -> dict[str, object]:
        return self._read_record(self._record_path_for_id(record_id))

    def get_tracking(self, record_id: str) -> dict[str, object]:
        return self._tracking_from_record(self.get_record(record_id))

    def _find_existing_reference(
        self,
        symbol: str,
        action: str,
        entry_time: str,
    ) -> Path | None:
        for path in self._record_paths():
            record = self._read_record(path)
            analysis = self._required_object(record, "analysis")
            reference = self._required_object(analysis, "reference")

            if (
                analysis.get("symbol") == symbol
                and analysis.get("action") == action
                and reference.get("entryTime") == entry_time
            ):
                return path

        return None

    def _record_paths(self) -> tuple[Path, ...]:
        if not self._root_directory.exists():
            return ()

        return tuple(
            sorted(
                self._root_directory.glob("iq-demo-m5-*.json"),
                key=lambda path: path.name,
                reverse=True,
            )
        )

    def _record_path_for_id(self, record_id: str) -> Path:
        if not isinstance(record_id, str) or not self._record_id_pattern.fullmatch(
            record_id
        ):
            raise ValueError("IQ Option DEMO M5 validation id is invalid")

        path = self._root_directory / f"{record_id}.json"

        if not path.is_file():
            raise FileNotFoundError(
                f"IQ Option DEMO M5 validation was not found: {record_id}"
            )

        return path

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
            f"iq-demo-m5-{timestamp_part}-"
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
            raise ValueError("IQ Option DEMO M5 validation is invalid")

        return payload

    @staticmethod
    def _tracking_from_record(
        record: dict[str, object],
    ) -> dict[str, object]:
        outcome = IqOptionDemoM5ValidationRepository._required_object(
            record,
            "outcome",
        )

        return {
            "recordId": record.get("recordId"),
            "status": outcome.get("status"),
            "settledAt": outcome.get("settledAt"),
            "settlementPrice": outcome.get("settlementPrice"),
        }

    @staticmethod
    def _required_object(
        payload: dict[str, object],
        field_name: str,
    ) -> dict[str, object]:
        value = payload.get(field_name)

        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be an object")

        return value

    @staticmethod
    def _required_string(
        payload: dict[str, object],
        field_name: str,
    ) -> str:
        value = payload.get(field_name)

        if not isinstance(value, str) or not value:
            raise ValueError(f"{field_name} must be a non-empty string")

        return value

    @staticmethod
    def _required_number(
        payload: dict[str, object],
        field_name: str,
    ) -> float:
        value = payload.get(field_name)

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be a number")

        return float(value)

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
