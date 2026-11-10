import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.repositories.iq_option_demo_binary_signal_repository import (
    IqOptionDemoBinarySignalRepository,
)

DEFAULT_BINARY_SIGNAL_DIRECTORY = Path(__file__).resolve().parents[2] / "data/iq-option-demo-binary-signals"


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises JSON-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def to_summary(record: dict[str, object]) -> dict[str, object]:
    analysis = record["analysis"]
    outcome = record["outcome"]

    return {
        "recordId": record["recordId"],
        "recordedAt": record["recordedAt"],
        "source": record["source"],
        "accountMode": record["accountMode"],
        "symbol": analysis["symbol"],
        "timeframe": analysis["timeframe"],
        "action": analysis["action"],
        "analysisAt": analysis["analysisAt"],
        "reference": analysis["reference"],
        "outcome": outcome,
        "disclaimer": record["disclaimer"],
    }


def list_binary_signal_records(limit: int) -> dict[str, object]:
    repository = IqOptionDemoBinarySignalRepository(
        DEFAULT_BINARY_SIGNAL_DIRECTORY
    )

    return {
        "source": "iq_option_demo",
        "accountMode": "PRACTICE",
        "records": [
            to_summary(record)
            for record in repository.list_records(limit)
        ],
    }


def get_binary_signal_record(record_id: str) -> dict[str, object]:
    repository = IqOptionDemoBinarySignalRepository(
        DEFAULT_BINARY_SIGNAL_DIRECTORY
    )
    return repository.get_record(record_id)


def error_to_payload(error: Exception) -> dict[str, object]:
    return {
        "error": {
            "code": "IQ_OPTION_DEMO_BINARY_SIGNAL_HISTORY_UNAVAILABLE",
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description="Read local IQ Option DEMO binary technical references.",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--record-id")

    try:
        arguments = parser.parse_args(argv)

        if arguments.record_id is not None:
            payload = get_binary_signal_record(arguments.record_id)
        else:
            payload = list_binary_signal_records(arguments.limit)
    except (FileNotFoundError, OSError, ValueError) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
