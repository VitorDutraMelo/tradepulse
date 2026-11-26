from datetime import UTC, datetime


class FakeClock:
    """Controllable wall clock and monotonic clock."""

    def __init__(self, start: datetime) -> None:
        self.current = start
        self.mono = 1000.0

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self.current += timedelta(seconds=seconds)
        self.mono += seconds


class FakeTransport:
    """In-memory IqTransport. Records every call; never touches the network."""

    instances: list["FakeTransport"] = []

    def __init__(
        self,
        clock: FakeClock,
        connect_result: tuple[bool, str | None] = (True, None),
        mode: str | None = "PRACTICE",
        interval_seconds: int = 60,
        server_offset_seconds: float | None = None,
    ) -> None:
        self.clock = clock
        self.connect_result = connect_result
        self.mode = mode
        self.interval = interval_seconds
        self.server_offset = server_offset_seconds
        self.connected = False
        self.closed = False
        self.calls: list[str] = []
        self.fail_next: Exception | None = None
        self.candle_requests: list[tuple[str, int, int]] = []
        FakeTransport.instances.append(self)

    def connect(self) -> tuple[bool, str | None]:
        self.calls.append("connect")
        self.connected = self.connect_result[0]
        return self.connect_result

    def is_connected(self) -> bool:
        return self.connected and not self.closed

    def select_practice(self) -> None:
        self.calls.append("select_practice")

    def balance_mode(self) -> str | None:
        self.calls.append("balance_mode")
        return self.mode

    def server_timestamp(self) -> float | None:
        if self.server_offset is None:
            return None

        return self.clock.now().timestamp() + self.server_offset

    def request_candles(
        self,
        symbol: str,
        interval_seconds: int,
        count: int,
        end_time: int,
        timeout_seconds: float,
    ) -> list[dict[str, object]]:
        self.calls.append("request_candles")
        self.candle_requests.append((symbol, interval_seconds, count))

        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error

        return make_raw_candles(end_time, interval_seconds, count)

    def close(self) -> None:
        self.calls.append("close")
        self.closed = True


def make_raw_candles(end_time: int, interval: int, count: int) -> list[dict[str, object]]:
    """IQ-style payload: ``count`` candles, the last one still open."""

    current_open = end_time - (end_time % interval)
    candles = []

    for index in range(count):
        open_epoch = current_open - interval * (count - 1 - index)
        price = 1.25 + index * 0.0001
        candles.append(
            {
                "id": index,
                "from": open_epoch,
                "to": open_epoch + interval,
                "at": (end_time * 1_000_000_000),
                "open": price,
                "close": price + 0.00005,
                "min": price - 0.0001,
                "max": price + 0.0002,
                "volume": 10,
            }
        )

    return candles


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)
