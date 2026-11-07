import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.repositories.iq_option_demo_analysis_repository import (
    IqOptionDemoAnalysisRepository,
)

DEFAULT_ANALYSIS_DIRECTORY = Path("data/iq-option-demo-analyses")


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises structured-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def list_iq_option_demo_analysis_history(
    limit: int,
    repository: IqOptionDemoAnalysisRepository | None = None,
) -> dict[str, object]:
    """Return recent IQ Option DEMO analysis summaries."""

    resolved_repository = repository or IqOptionDemoAnalysisRepository(
        DEFAULT_ANALYSIS_DIRECTORY
    )

    return {
        "source": IqOptionDemoAnalysisRepository.source,
        "venue": IqOptionDemoAnalysisRepository.venue,
        "accountMode": IqOptionDemoAnalysisRepository.account_mode,
        "records": list(resolved_repository.list_summaries(limit)),
    }


def get_iq_option_demo_analysis_record(
    record_id: str,
    repository: IqOptionDemoAnalysisRepository | None = None,
) -> dict[str, object]:
    """Return one complete local IQ Option DEMO analysis record."""

    resolved_repository = repository or IqOptionDemoAnalysisRepository(
        DEFAULT_ANALYSIS_DIRECTORY
    )

    return resolved_repository.get_record(record_id)


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected history-reading errors into structured JSON."""

    if isinstance(error, FileNotFoundError):
        code = "IQ_OPTION_DEMO_ANALYSIS_NOT_FOUND"
    else:
        code = "INVALID_IQ_OPTION_DEMO_HISTORY_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print IQ Option DEMO analysis history as JSON."""

    parser = JsonArgumentParser(
        description="Read local IQ Option DEMO analysis history.",
    )
    requested_action = parser.add_mutually_exclusive_group()
    requested_action.add_argument("--record-id")
    parser.add_argument("--limit", type=int, default=20)

    try:
        arguments = parser.parse_args(argv)

        if arguments.record_id is not None:
            payload = get_iq_option_demo_analysis_record(
                record_id=arguments.record_id
            )
        else:
            payload = list_iq_option_demo_analysis_history(
                limit=arguments.limit
            )
    except (FileNotFoundError, ValueError) as error:
        print(json.dumps(error_to_payload(error), indent=2), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())