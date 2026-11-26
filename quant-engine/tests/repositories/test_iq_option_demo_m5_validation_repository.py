from datetime import UTC, datetime
from pathlib import Path

from app.domain.candle import Candle
from app.repositories.iq_option_demo_m5_validation_repository import (
    IqOptionDemoM5ValidationRepository,
)


def create_payload(action: str = "CALL") -> dict[str, object]:
    return {
        "symbol": "GBPUSD-OTC",
        "timeframe": "5m",
        "latestClosedCandle": {
            "timestamp": "2026-11-21T12:00:00+00:00",
            "open": 1.3000,
            "high": 1.3010,
            "low": 1.2990,
            "close": 1.3000,
            "volume": 0.0,
            "closed": True,
            "closeTime": "2026-11-21T12:05:00+00:00",
        },
        "indicators": {"ema200": 1.2900},
        "dataQuality": {
            "requiredClosedCandles": 250,
            "receivedClosedCandles": 260,
            "candlesContiguous": True,
        },
        "contextM15": {
            "state": "UPDATED",
            "trend": "BULLISH" if action == "CALL" else "BEARISH",
            "timeframe": "15m",
        },
        "decision": {
            "action": "WAIT",
            "candidateAction": action,
            "m5CandidateAction": action,
            "actionability": "NOT_ACTIONABLE_LATE",
            "theoreticalEntryTime": "2026-11-21T12:05:00+00:00",
            "theoreticalExpirationTime": "2026-11-21T12:10:00+00:00",
            "reasons": ["M5 and M15 are aligned."],
        },
    }


def settlement_candle(close: float) -> Candle:
    return Candle(
        timestamp=datetime(2026, 11, 21, 12, 5, tzinfo=UTC),
        open=1.3000,
        high=max(1.3000, close),
        low=min(1.3000, close),
        close=close,
        volume=0.0,
    )


def test_saves_pending_m5_validation_with_separate_record_id(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoM5ValidationRepository(tmp_path)

    path = repository.save_pending(
        signal_payload=create_payload(),
        recorded_at=datetime(2026, 11, 21, 12, 4, tzinfo=UTC),
    )

    record = repository.get_record(path.stem)

    assert path.stem.startswith("iq-demo-m5-")
    assert record["analysis"]["timeframe"] == "5m"
    assert record["analysis"]["contextM15"]["trend"] == "BULLISH"
    assert record["outcome"]["status"] == "PENDING"


def test_deduplicates_same_theoretical_m5_reference(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoM5ValidationRepository(tmp_path)
    payload = create_payload()

    first = repository.save_pending(
        signal_payload=payload,
        recorded_at=datetime(2026, 11, 21, 12, 4, tzinfo=UTC),
    )
    second = repository.save_pending(
        signal_payload=payload,
        recorded_at=datetime(2026, 11, 21, 12, 4, 30, tzinfo=UTC),
    )

    assert first == second
    assert len(repository.list_records(10)) == 1


def test_settles_call_as_win_from_closed_expiration_candle(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoM5ValidationRepository(tmp_path)

    path = repository.save_pending(
        signal_payload=create_payload("CALL"),
        recorded_at=datetime(2026, 11, 21, 12, 4, tzinfo=UTC),
    )

    settled = repository.settle_due_references(
        candles=(settlement_candle(1.3010),),
        settled_at=datetime(2026, 11, 21, 12, 10, tzinfo=UTC),
    )

    assert len(settled) == 1
    assert settled[0]["recordId"] == path.stem
    assert settled[0]["status"] == "WIN"
    assert settled[0]["settlementPrice"] == 1.3010


def test_rejects_unaligned_context_before_persisting(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoM5ValidationRepository(tmp_path)
    payload = create_payload("CALL")
    payload["contextM15"]["trend"] = "NEUTRAL"

    try:
        repository.save_pending(
            signal_payload=payload,
            recorded_at=datetime(2026, 11, 21, 12, 4, tzinfo=UTC),
        )
    except ValueError as error:
        assert "BULLISH" in str(error)
    else:
        raise AssertionError("Expected unaligned M15 context to be rejected.")
