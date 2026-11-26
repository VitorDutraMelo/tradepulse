import io
import json

from gateway_fakes import FakeClock, FakeTransport, utc

from app.gateway.candle_cache import CandleCache
from app.gateway.redaction import redact
from app.gateway.session import IqSession
from app.gateway.worker import Worker, serve


def build_worker(clock: FakeClock, tmp_path, monkeypatch, **transport_kwargs):
    transports: list[FakeTransport] = []

    def factory(email: str, password: str) -> FakeTransport:
        transport = FakeTransport(clock, **transport_kwargs)
        transports.append(transport)
        return transport

    session = IqSession(
        email="owner@example.com",
        password="pw-123456",
        transport_factory=factory,
        clock=clock.now,
        monotonic=clock.monotonic,
    )
    cache = CandleCache(session, monotonic=clock.monotonic)

    # Keep persisted records inside the test directory.
    import app.cli.analyze_iq_option_binary_signal as m1_cli
    import app.cli.get_iq_option_demo_m5_signal_with_m15 as m5_cli

    monkeypatch.setattr(m1_cli, "DEFAULT_BINARY_SIGNAL_DIRECTORY", tmp_path / "m1")
    monkeypatch.setattr(m5_cli, "DEFAULT_M5_VALIDATION_DIRECTORY", tmp_path / "m5")

    worker = Worker(session=session, cache=cache, clock=clock.now,
                    secrets=("owner@example.com", "pw-123456"))
    return worker, transports


def test_m1_analysis_reuses_the_session_and_reports_timing(tmp_path, monkeypatch) -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 2))
    worker, transports = build_worker(clock, tmp_path, monkeypatch)

    first = worker.handle({"id": "a", "cmd": "analyze_m1",
                           "args": {"symbol": "EURUSD-OTC", "timeframe": "1m", "limit": 120}})
    chart = worker.handle({"id": "b", "cmd": "candles",
                           "args": {"symbol": "EURUSD-OTC", "timeframe": "1m", "limit": 100}})

    assert first["ok"] is True, first
    assert chart["ok"] is True, chart
    assert len(transports) == 1
    assert len(transports[0].candle_requests) == 1  # chart served from cache
    meta = first["meta"]
    assert meta["session"]["counters"]["loginsSucceeded"] == 1
    assert meta["fetches"][0]["latestClosedCandle"]["closeTime"] == "2026-11-26T12:03:00+00:00"
    assert first["result"]["reference"]["entryTime"] in (None, "2026-11-26T12:03:00+00:00")
    assert first["result"]["lastClosedCandle"]["closeTime"] == "2026-11-26T12:03:00+00:00"


def test_m5_engine_with_m15_uses_one_login_and_no_duplicate_m5_fetch(tmp_path, monkeypatch) -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 5, 3))

    transports: list[FakeTransport] = []

    class MultiIntervalTransport(FakeTransport):
        def request_candles(self, symbol, interval_seconds, count, end_time, timeout_seconds):
            self.interval = interval_seconds
            return super().request_candles(symbol, interval_seconds, count, end_time,
                                           timeout_seconds)

    def factory(email, password):
        transport = MultiIntervalTransport(clock)
        transports.append(transport)
        return transport

    session = IqSession(email="owner@example.com", password="pw-123456",
                        transport_factory=factory, clock=clock.now, monotonic=clock.monotonic)
    import app.cli.get_iq_option_demo_m5_signal_with_m15 as m5_cli

    monkeypatch.setattr(m5_cli, "DEFAULT_M5_VALIDATION_DIRECTORY", tmp_path / "m5")
    worker = Worker(session=session, cache=CandleCache(session, monotonic=clock.monotonic),
                    clock=clock.now)

    response = worker.handle({"id": "m5", "cmd": "analyze_m5", "args": {"symbol": "GBPUSD-OTC"}})

    assert response["ok"] is True, response
    assert len(transports) == 1
    intervals = [request[1] for request in transports[0].candle_requests]
    assert intervals == [300, 900]  # the settlement M5 read is a cache hit
    result = response["result"]
    assert result["latestClosedCandle"]["closeTime"] == "2026-11-26T12:05:00+00:00"
    assert result["decision"]["theoreticalEntryTime"] == "2026-11-26T12:05:00+00:00"
    assert result["decision"]["action"] == "WAIT"  # engine rules preserved


def test_errors_are_structured_and_redacted(tmp_path, monkeypatch) -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 2))
    worker, _ = build_worker(clock, tmp_path, monkeypatch,
                             connect_result=(False, "rejected owner@example.com pw-123456"))

    response = worker.handle({"id": "x", "cmd": "candles",
                              "args": {"symbol": "EURUSD-OTC", "limit": 10}})

    assert response["ok"] is False
    assert response["error"]["code"] == "IQ_OPTION_AUTH_FAILED"
    assert "retryAt" in response["error"]
    serialized = json.dumps(response)
    assert "owner@example.com" not in serialized
    assert "pw-123456" not in serialized


def test_unknown_commands_are_rejected(tmp_path, monkeypatch) -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 2))
    worker, transports = build_worker(clock, tmp_path, monkeypatch)

    for command in ("buy", "sell", "close_position", "__init__"):
        response = worker.handle({"id": command, "cmd": command, "args": {}})
        assert response["ok"] is False
        assert response["error"]["code"] == "INVALID_GATEWAY_REQUEST"

    assert transports == []


def test_serve_speaks_json_lines_and_shuts_down_cleanly(tmp_path, monkeypatch) -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 2))
    worker, transports = build_worker(clock, tmp_path, monkeypatch)
    stdin = io.StringIO(
        "not json\n"
        + json.dumps({"id": "1", "cmd": "status", "args": {"connect": True}}) + "\n"
        + json.dumps({"id": "2", "cmd": "shutdown", "args": {}}) + "\n"
        + json.dumps({"id": "3", "cmd": "status", "args": {}}) + "\n"
    )
    protocol = io.StringIO()

    exit_code = serve(worker, stdin, protocol, io.StringIO())

    lines = [json.loads(line) for line in protocol.getvalue().splitlines()]
    assert exit_code == 0
    assert lines[0]["type"] == "ready"
    assert lines[1]["error"]["code"] == "INVALID_GATEWAY_REQUEST"
    assert lines[2]["id"] == "1" and lines[2]["result"]["session"]["state"] == "CONNECTED"
    assert lines[3]["id"] == "2"
    assert len(lines) == 4  # request "3" is never processed after shutdown
    assert transports[0].closed is True


def test_redaction_removes_emails_tokens_and_known_secrets() -> None:
    text = redact('user a.b@mail.com ssid="abc123" password: hunter2 key xyz789',
                  secrets=("xyz789",))

    assert "a.b@mail.com" not in text
    assert "abc123" not in text
    assert "hunter2" not in text
    assert "xyz789" not in text


def test_redaction_keeps_ordinary_words() -> None:
    message = "IQ_OPTION_DEMO_EMAIL and IQ_OPTION_DEMO_PASSWORD must be configured"

    assert redact(message) == message
