import pytest
from gateway_fakes import FakeClock, FakeTransport, utc

from app.gateway.session import (
    AuthenticationFailedError,
    BackoffActiveError,
    CredentialsMissingError,
    IqSession,
    PracticeNotConfirmedError,
    SourceTimeoutError,
    SourceUnavailableError,
)
from app.gateway.transport import ALLOWED_LIBRARY_METHODS, IqOptionApiTransport


def build_session(clock: FakeClock, **transport_kwargs):
    created: list[FakeTransport] = []

    def factory(email: str, password: str) -> FakeTransport:
        transport = FakeTransport(clock, **transport_kwargs)
        created.append(transport)
        return transport

    session = IqSession(
        email="owner@example.com",
        password="s3cret-pass",
        transport_factory=factory,
        clock=clock.now,
        monotonic=clock.monotonic,
        backoff_base_seconds=1,
        backoff_max_seconds=8,
    )
    return session, created


def test_reuses_one_login_for_many_candle_requests() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock)

    for _ in range(5):
        session.fetch_candles("EURUSD-OTC", "1m", 10)

    assert len(created) == 1
    assert created[0].calls.count("connect") == 1
    assert session.counters.login_attempts == 1
    assert session.counters.logins_succeeded == 1
    assert session.counters.candle_requests == 5


def test_selects_and_verifies_practice_after_login() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock)

    session.ensure_connected()

    assert created[0].calls[:3] == ["connect", "select_practice", "balance_mode"]
    assert session.snapshot()["accountMode"] == "PRACTICE"


@pytest.mark.parametrize("mode", ["REAL", "TOURNAMENT", None])
def test_refuses_and_closes_a_session_that_is_not_practice(mode) -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock, mode=mode)

    with pytest.raises(PracticeNotConfirmedError):
        session.fetch_candles("EURUSD-OTC", "1m", 10)

    assert created[0].closed is True
    assert "request_candles" not in created[0].calls
    assert session.state == "PRACTICE_NOT_CONFIRMED"
    assert session.snapshot()["accountMode"] is None


def test_missing_credentials_never_attempt_a_login() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session = IqSession(
        email="",
        password="",
        transport_factory=lambda *_: pytest.fail("must not create a transport"),
        clock=clock.now,
        monotonic=clock.monotonic,
    )

    with pytest.raises(CredentialsMissingError):
        session.ensure_connected()

    assert session.state == "CREDENTIALS_MISSING"
    assert session.counters.login_attempts == 0


def test_failed_logins_use_progressive_backoff_without_hammering() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock, connect_result=(False, '{"message":"bad"}'))

    with pytest.raises(AuthenticationFailedError):
        session.ensure_connected()

    # Inside the 1 s backoff: no new login is attempted.
    with pytest.raises(BackoffActiveError):
        session.ensure_connected()

    assert len(created) == 1

    clock.advance(1.01)
    with pytest.raises(AuthenticationFailedError):
        session.ensure_connected()

    clock.advance(1.5)  # second backoff is 2 s
    with pytest.raises(BackoffActiveError):
        session.ensure_connected()

    clock.advance(0.6)
    with pytest.raises(AuthenticationFailedError):
        session.ensure_connected()

    assert len(created) == 3
    assert session.counters.login_failures == 3
    assert session.snapshot()["consecutiveFailures"] == 3


def test_backoff_is_capped() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, _ = build_session(clock, connect_result=(False, None))

    for _ in range(8):
        try:
            session.ensure_connected()
        except (AuthenticationFailedError, BackoffActiveError):
            pass
        clock.advance(9)

    retry_at = session.snapshot()["nextReconnectAt"]
    assert retry_at is not None
    assert (clock.now() - utc(2026, 11, 26, 12, 0, 30)).total_seconds() > 60


def test_reconnects_after_the_websocket_drops() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock)

    session.fetch_candles("EURUSD-OTC", "1m", 5)
    created[0].connected = False  # websocket dropped
    session.fetch_candles("EURUSD-OTC", "1m", 5)

    assert len(created) == 2
    assert created[0].closed is True
    assert session.counters.reconnects == 1
    assert session.counters.logins_succeeded == 2


def test_candle_timeout_drops_the_session_and_reports_timeout() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock)
    session.ensure_connected()
    created[0].fail_next = TimeoutError("no answer")

    with pytest.raises(SourceTimeoutError):
        session.fetch_candles("EURUSD-OTC", "1m", 5)

    assert session.state == "DISCONNECTED"
    assert created[0].closed is True
    assert session.snapshot()["lastErrorCode"] == "IQ_OPTION_TIMEOUT"


def test_connection_error_is_reported_as_unavailable() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock)
    session.ensure_connected()
    created[0].fail_next = ConnectionError("socket closed")

    with pytest.raises(SourceUnavailableError):
        session.fetch_candles("EURUSD-OTC", "1m", 5)

    assert session.counters.candle_request_failures == 1


def test_open_candle_is_never_returned_as_closed() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 20))
    session, _ = build_session(clock)

    result = session.fetch_candles("EURUSD-OTC", "1m", 5)

    assert len(result.candles) == 4
    assert result.candles[-1].timestamp == utc(2026, 11, 26, 12, 2)
    assert result.observed_quote is not None
    assert result.observed_quote.source_timestamp == utc(2026, 11, 26, 12, 3, 20)


@pytest.mark.parametrize(
    ("timeframe", "interval", "now", "latest_open"),
    [
        ("1m", 60, utc(2026, 11, 26, 12, 3, 0, ), utc(2026, 11, 26, 12, 2)),
        ("5m", 300, utc(2026, 11, 26, 12, 5, 1), utc(2026, 11, 26, 12, 0)),
        ("15m", 900, utc(2026, 11, 26, 12, 14, 59), utc(2026, 11, 26, 11, 45)),
    ],
)
def test_candle_close_identification_per_timeframe(timeframe, interval, now, latest_open) -> None:
    clock = FakeClock(now)
    session, _ = build_session(clock, interval_seconds=interval)

    result = session.fetch_candles("EURUSD-OTC", timeframe, 6)

    assert result.candles[-1].timestamp == latest_open


def test_uses_the_iq_server_clock_when_available() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 2, 59, 500000))
    # Server is 1 s ahead: the 12:02 candle is already closed at the source.
    session, _ = build_session(clock, server_offset_seconds=1.0)
    session.ensure_connected()

    result = session.fetch_candles("EURUSD-OTC", "1m", 5)

    assert result.reference_clock == "IQ_SERVER_CLOCK"
    assert result.candles[-1].timestamp == utc(2026, 11, 26, 12, 2)
    assert session.snapshot()["serverClockOffsetMs"] == 1000.0


def test_snapshot_never_exposes_credentials() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, _ = build_session(clock, connect_result=(False, "owner@example.com s3cret-pass"))

    with pytest.raises(AuthenticationFailedError) as raised:
        session.ensure_connected()

    text = str(session.snapshot()) + str(raised.value)
    assert "owner@example.com" not in text
    assert "s3cret-pass" not in text


def test_close_is_idempotent() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 0, 30))
    session, created = build_session(clock)
    session.ensure_connected()

    session.close()
    session.close()

    assert created[0].closed is True
    assert session.state == "DISCONNECTED"


def test_transport_exposes_no_order_capability() -> None:
    forbidden = {"buy", "buy_multi", "sell_option", "close_position", "buy_digital_spot"}

    assert not forbidden & ALLOWED_LIBRARY_METHODS
    assert not any(hasattr(IqOptionApiTransport, name) for name in forbidden)
    assert not any("buy" in name or "sell" in name for name in dir(IqOptionApiTransport))
