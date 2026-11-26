import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from app.cli.get_iq_option_demo_m5_signal import (
    JsonArgumentParser,
    M5_SYMBOL,
    error_to_payload,
    get_iq_option_demo_m5_signal,
    now_utc,
)
from app.cli.iq_option_demo_m15_context import (
    get_iq_option_demo_m15_context,
)
from app.domain.candle import Candle
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)
from app.repositories.iq_option_demo_m5_validation_repository import (
    IqOptionDemoM5ValidationRepository,
)

DEFAULT_M5_VALIDATION_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "data/iq-option-demo-m5-validations"
)

M5_TIMEFRAME = "5m"
M5_DURATION = timedelta(minutes=5)
SETTLEMENT_HISTORY_LIMIT = 260


def apply_m15_confirmation(
    m5_payload: dict[str, object],
    context_m15: dict[str, object],
) -> dict[str, object]:
    decision = dict(m5_payload["decision"])
    raw_candidate = str(decision["candidateAction"])
    reasons = list(decision["reasons"])

    decision["m5CandidateAction"] = raw_candidate

    if raw_candidate == "WAIT":
        decision["candidateAction"] = "WAIT"
        decision["reasons"] = reasons
        return decision

    context_state = str(context_m15["state"])
    context_trend = str(context_m15["trend"])
    required_trend = "BULLISH" if raw_candidate == "CALL" else "BEARISH"

    if context_state != "UPDATED":
        decision["candidateAction"] = "WAIT"
        decision["actionability"] = "M15_CONTEXT_NOT_CURRENT"
        reasons.append(
            f"M15 context state is {context_state}; "
            "the M5 candidate is blocked."
        )
    elif context_trend != required_trend:
        decision["candidateAction"] = "WAIT"
        decision["actionability"] = "M15_CONTEXT_NOT_ALIGNED"
        reasons.append(
            f"M15 trend is {context_trend}; "
            f"{raw_candidate} requires {required_trend} confirmation."
        )
    else:
        decision["candidateAction"] = raw_candidate
        reasons.append(
            f"M15 {context_trend} context confirms the M5 "
            f"{raw_candidate} candidate."
        )

    decision["reasons"] = reasons
    return decision


def candle_from_payload(payload: dict[str, object]) -> Candle:
    timestamp = payload.get("timestamp")

    if not isinstance(timestamp, str):
        raise ValueError("latestClosedCandle timestamp is invalid")

    return Candle(
        timestamp=datetime.fromisoformat(timestamp),
        open=float(payload["open"]),
        high=float(payload["high"]),
        low=float(payload["low"]),
        close=float(payload["close"]),
        volume=float(payload["volume"]),
    )


def get_closed_m5_settlement_candles(
    symbol: str,
    provider: IqOptionMarketDataProvider,
    observed_at: datetime,
    limit: int = SETTLEMENT_HISTORY_LIMIT,
) -> tuple[Candle, ...]:
    if limit < 1:
        raise ValueError("Settlement history limit must be positive")

    candles = provider.get_candles(
        symbol=symbol,
        timeframe=M5_TIMEFRAME,
        limit=limit,
    )

    return tuple(
        candle
        for candle in candles
        if candle.timestamp + M5_DURATION <= observed_at
    )


def unavailable_tracking() -> dict[str, object]:
    return {
        "recordId": None,
        "status": "UNAVAILABLE",
        "settledAt": None,
        "settlementPrice": None,
    }


def not_applicable_tracking() -> dict[str, object]:
    return {
        "recordId": None,
        "status": "NOT_APPLICABLE",
        "settledAt": None,
        "settlementPrice": None,
    }


def get_iq_option_demo_m5_signal_with_m15(
    symbol: str,
    provider: IqOptionMarketDataProvider | None = None,
    now: Callable[[], datetime] | None = None,
    validation_repository: IqOptionDemoM5ValidationRepository | None = None,
) -> dict[str, object]:
    resolved_provider = provider or IqOptionMarketDataProvider()
    resolved_now = now or now_utc
    recorded_at = resolved_now()

    m5_payload = get_iq_option_demo_m5_signal(
        symbol=symbol,
        provider=resolved_provider,
        now=resolved_now,
    )

    context_m15 = get_iq_option_demo_m15_context(
        symbol=symbol,
        provider=resolved_provider,
        now=resolved_now,
    )

    payload = dict(m5_payload)
    payload["contextM15"] = context_m15
    payload["decision"] = apply_m15_confirmation(
        m5_payload,
        context_m15,
    )

    repository = validation_repository or IqOptionDemoM5ValidationRepository(
        DEFAULT_M5_VALIDATION_DIRECTORY
    )

    try:
        settlement_candles = get_closed_m5_settlement_candles(
            symbol=symbol,
            provider=resolved_provider,
            observed_at=recorded_at,
        )

        repository.settle_due_references(
            candles=settlement_candles,
            settled_at=recorded_at,
        )

        decision = payload["decision"]

        if not isinstance(decision, dict):
            raise ValueError("decision must be an object")

        if decision.get("candidateAction") not in {"CALL", "PUT"}:
            payload["tracking"] = not_applicable_tracking()
        else:
            record_path = repository.save_pending(
                signal_payload=payload,
                recorded_at=recorded_at,
            )
            payload["tracking"] = repository.get_tracking(
                record_path.stem,
            )
    except (OSError, ValueError, TypeError):
        payload["tracking"] = unavailable_tracking()

    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description=(
            "Evaluate a closed-candle GBPUSD-OTC M5 candidate "
            "with M15 context and theoretical outcome tracking."
        ),
    )
    parser.add_argument("--symbol", default=M5_SYMBOL)

    try:
        arguments = parser.parse_args(argv)
        payload = get_iq_option_demo_m5_signal_with_m15(
            symbol=arguments.symbol,
        )
    except (
        ConnectionError,
        LookupError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
