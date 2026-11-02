from datetime import UTC, datetime
from urllib.error import HTTPError

import pytest

import app.streams.otcharts_iq_option_stream as stream_module
from app.streams.otcharts_iq_option_stream import (
    OtchartsIqOptionStream,
    OtchartsIqOptionStreamEvent,
    OtchartsIqOptionStreamPlanUnavailableError,
)


def create_client() -> OtchartsIqOptionStream:
    return OtchartsIqOptionStream(
        api_key="test-api-key",
        now=lambda: datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )


def test_parses_sse_events_and_ignores_comments() -> None:
    client = create_client()

    events = list(
        client._parse_sse_lines(
            [
                b": OTCharts keep-alive\n",
                b"event: connected\n",
                b'data: {"symbol":"EURUSD-OTC"}\n',
                b"\n",
                b"event: tick\n",
                b'data: {"symbol":"EURUSD-OTC","time":1793613660,"price":1.12345}\n',
                b"\n",
            ]
        )
    )

    assert [event.event for event in events] == ["connected", "tick"]
    assert events[0].data == {"symbol": "EURUSD-OTC"}
    assert events[1].data["price"] == 1.12345
    assert events[1].received_at == datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def test_converts_tick_event_to_normalized_market_tick() -> None:
    stream_event = OtchartsIqOptionStreamEvent(
        event="tick",
        data={
            "symbol": "eurusd-otc",
            "time": 1793613660,
            "price": 1.12345,
            "volume": 7,
        },
        received_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )

    tick = OtchartsIqOptionStream.event_to_tick(stream_event)

    assert tick.symbol == "EURUSD-OTC"
    assert tick.timestamp == datetime(2026, 11, 2, 10, 1, tzinfo=UTC)
    assert tick.price == 1.12345
    assert tick.volume == 7.0


def test_rejects_invalid_tick_event() -> None:
    stream_event = OtchartsIqOptionStreamEvent(
        event="tick",
        data={
            "symbol": "EURUSD-OTC",
            "time": 1793613660,
            "price": 0,
        },
        received_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="invalid tick price"):
        OtchartsIqOptionStream.event_to_tick(stream_event)


def test_iter_ticks_rejects_unexpected_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    client = create_client()

    def fake_iter_events(_: str):
        yield OtchartsIqOptionStreamEvent(
            event="tick",
            data={
                "symbol": "GBPUSD-OTC",
                "time": 1793613660,
                "price": 1.2500,
            },
            received_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
        )

    monkeypatch.setattr(client, "iter_events", fake_iter_events)

    with pytest.raises(ValueError, match="unexpected IQ Option symbol"):
        list(client.iter_ticks("EURUSD-OTC"))


def test_uses_iq_venue_and_requested_symbol_in_stream_url() -> None:
    client = create_client()

    assert (
        client._build_stream_url("EURUSD-OTC")
        == "https://otcharts.com/v1/stream?venue=iq&symbol=EURUSD-OTC"
    )


def test_maps_http_402_to_explicit_plan_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = create_client()

    def raise_payment_required(*_: object, **__: object):
        raise HTTPError(
            url="https://otcharts.com/v1/stream",
            code=402,
            msg="Payment Required",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(stream_module, "urlopen", raise_payment_required)

    with pytest.raises(
        OtchartsIqOptionStreamPlanUnavailableError,
        match="streaming is unavailable",
    ):
        list(client.iter_events("EURUSD-OTC"))