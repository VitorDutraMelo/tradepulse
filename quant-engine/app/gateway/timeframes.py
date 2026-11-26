"""UTC candle-boundary helpers shared by the gateway."""

from datetime import UTC, datetime, timedelta

TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


def timeframe_seconds(timeframe: str) -> int:
    """Return the interval length of a supported timeframe."""

    seconds = TIMEFRAME_SECONDS.get(timeframe)

    if seconds is None:
        supported = ", ".join(TIMEFRAME_SECONDS)
        raise ValueError(f"unsupported timeframe; supported values are: {supported}")

    return seconds


def ensure_utc(value: datetime, field_name: str = "timestamp") -> datetime:
    """Reject naive datetimes and normalize aware ones to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    return value.astimezone(UTC)


def latest_expected_close(now: datetime, timeframe: str) -> datetime:
    """Return the most recent candle boundary at or before ``now``.

    A candle whose close time equals this boundary is the newest candle that
    can be closed at ``now``.
    """

    seconds = timeframe_seconds(timeframe)
    epoch = int(ensure_utc(now, "now").timestamp())

    return datetime.fromtimestamp(epoch - (epoch % seconds), tz=UTC)


def candle_close(open_time: datetime, timeframe: str) -> datetime:
    """Derive the close of a candle from its open time and interval."""

    return ensure_utc(open_time, "open_time") + timedelta(
        seconds=timeframe_seconds(timeframe)
    )


def candle_id(symbol: str, timeframe: str, open_time: datetime) -> str:
    """Return a stable identifier: SYMBOL:TIMEFRAME:OPEN_EPOCH_SECONDS."""

    epoch = int(ensure_utc(open_time, "open_time").timestamp())

    return f"{symbol.strip().upper()}:{timeframe}:{epoch}"


def to_iso(value: datetime | None) -> str | None:
    """Serialize an aware datetime as ISO-8601 UTC (or ``None``)."""

    if value is None:
        return None

    return ensure_utc(value).isoformat()
