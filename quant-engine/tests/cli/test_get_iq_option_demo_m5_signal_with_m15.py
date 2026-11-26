from app.cli.get_iq_option_demo_m5_signal_with_m15 import (
    apply_m15_confirmation,
)


def create_m5_payload(
    candidate_action: str,
    actionability: str = "NOT_ACTIONABLE_LATE",
) -> dict[str, object]:
    return {
        "decision": {
            "action": "WAIT",
            "candidateAction": candidate_action,
            "actionability": actionability,
            "theoreticalEntryTime": "2026-11-20T18:00:00+00:00",
            "theoreticalExpirationTime": "2026-11-20T18:05:00+00:00",
            "reasons": ["M5 technical candidate was evaluated."],
        }
    }


def create_m15_context(
    trend: str,
    state: str = "UPDATED",
) -> dict[str, object]:
    return {
        "state": state,
        "trend": trend,
    }


def test_blocks_call_when_m15_is_neutral() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("CALL"),
        create_m15_context("NEUTRAL"),
    )

    assert decision["m5CandidateAction"] == "CALL"
    assert decision["candidateAction"] == "WAIT"
    assert decision["actionability"] == "M15_CONTEXT_NOT_ALIGNED"
    assert "CALL requires BULLISH confirmation." in decision["reasons"][-1]


def test_blocks_call_when_m15_is_bearish() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("CALL"),
        create_m15_context("BEARISH"),
    )

    assert decision["m5CandidateAction"] == "CALL"
    assert decision["candidateAction"] == "WAIT"
    assert decision["actionability"] == "M15_CONTEXT_NOT_ALIGNED"


def test_blocks_put_when_m15_is_neutral() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("PUT"),
        create_m15_context("NEUTRAL"),
    )

    assert decision["m5CandidateAction"] == "PUT"
    assert decision["candidateAction"] == "WAIT"
    assert decision["actionability"] == "M15_CONTEXT_NOT_ALIGNED"
    assert "PUT requires BEARISH confirmation." in decision["reasons"][-1]


def test_blocks_put_when_m15_is_bullish() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("PUT"),
        create_m15_context("BULLISH"),
    )

    assert decision["m5CandidateAction"] == "PUT"
    assert decision["candidateAction"] == "WAIT"
    assert decision["actionability"] == "M15_CONTEXT_NOT_ALIGNED"


def test_blocks_candidate_when_m15_is_not_current() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("CALL"),
        create_m15_context("BULLISH", state="STALE"),
    )

    assert decision["m5CandidateAction"] == "CALL"
    assert decision["candidateAction"] == "WAIT"
    assert decision["actionability"] == "M15_CONTEXT_NOT_CURRENT"


def test_preserves_call_when_m15_is_bullish() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("CALL"),
        create_m15_context("BULLISH"),
    )

    assert decision["m5CandidateAction"] == "CALL"
    assert decision["candidateAction"] == "CALL"
    assert decision["actionability"] == "NOT_ACTIONABLE_LATE"
    assert "M15 BULLISH context confirms the M5 CALL candidate." in decision["reasons"][-1]


def test_preserves_put_when_m15_is_bearish() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("PUT"),
        create_m15_context("BEARISH"),
    )

    assert decision["m5CandidateAction"] == "PUT"
    assert decision["candidateAction"] == "PUT"
    assert decision["actionability"] == "NOT_ACTIONABLE_LATE"
    assert "M15 BEARISH context confirms the M5 PUT candidate." in decision["reasons"][-1]


def test_keeps_wait_as_wait_without_m15_override() -> None:
    decision = apply_m15_confirmation(
        create_m5_payload("WAIT", actionability="NO_CANDIDATE"),
        create_m15_context("BULLISH"),
    )

    assert decision["m5CandidateAction"] == "WAIT"
    assert decision["candidateAction"] == "WAIT"
    assert decision["actionability"] == "NO_CANDIDATE"
