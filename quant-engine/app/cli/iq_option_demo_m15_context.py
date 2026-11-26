from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.cli.get_iq_option_demo_m5_signal import (
    M5_SYMBOL,
    duration_ms,
    ema_series,
    normalize_symbol,
    now_utc,
)
from app.domain.candle import Candle
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)

M15_TIMEFRAME = "15m"
M15_INTERVAL_SECONDS = 15 * 60
FETCH_LIMIT = 260
REQUIRED_CLOSED_CANDLES = 250
EMA_PERIOD = 200
EMA_SLOPE_LOOKBACK = 3
SWING_RADIUS = 2


def candle_close_time(candle: Candle) -> datetime:
    return candle.timestamp + timedelta(seconds=M15_INTERVAL_SECONDS)


def expected_latest_close_time(observed_at: datetime) -> datetime:
    seconds = int(observed_at.timestamp())

    return datetime.fromtimestamp(
        seconds - (seconds % M15_INTERVAL_SECONDS),
        tz=UTC,
    )


def determine_state(latest_close: datetime, expected_close: datetime) -> str:
    if latest_close >= expected_close:
        return "UPDATED"

    if latest_close == expected_close - timedelta(seconds=M15_INTERVAL_SECONDS):
        return "AWAITING_CONFIRMATION"

    return "STALE"


def candles_are_contiguous(candles: tuple[Candle, ...]) -> bool:
    expected_interval = timedelta(seconds=M15_INTERVAL_SECONDS)

    return all(
        current.timestamp - previous.timestamp == expected_interval
        for previous, current in zip(candles, candles[1:])
    )


def find_confirmed_swings(
    candles: tuple[Candle, ...],
) -> tuple[list[Candle], list[Candle]]:
    swing_highs: list[Candle] = []
    swing_lows: list[Candle] = []

    for index in range(SWING_RADIUS, len(candles) - SWING_RADIUS):
        candidate = candles[index]
        neighbours = candles[
            index - SWING_RADIUS : index + SWING_RADIUS + 1
        ]
        other_candles = [
            candle
            for neighbour_index, candle in enumerate(neighbours)
            if neighbour_index != SWING_RADIUS
        ]

        if all(candidate.high > candle.high for candle in other_candles):
            swing_highs.append(candidate)

        if all(candidate.low < candle.low for candle in other_candles):
            swing_lows.append(candidate)

    return swing_highs, swing_lows


def classify_structure(
    swing_highs: list[Candle],
    swing_lows: list[Candle],
) -> str:
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "UNCONFIRMED"

    previous_high, current_high = swing_highs[-2:]
    previous_low, current_low = swing_lows[-2:]

    if (
        current_high.high > previous_high.high
        and current_low.low > previous_low.low
    ):
        return "HIGHER_HIGH_HIGHER_LOW"

    if (
        current_high.high < previous_high.high
        and current_low.low < previous_low.low
    ):
        return "LOWER_HIGH_LOWER_LOW"

    return "MIXED"


def candle_to_payload(candle: Candle) -> dict[str, object]:
    return {
        "timestamp": candle.timestamp.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "closed": True,
        "closeTime": candle_close_time(candle).isoformat(),
    }


def get_iq_option_demo_m15_context(
    symbol: str,
    provider: IqOptionMarketDataProvider | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    resolved_now = now or now_utc
    normalized_symbol = normalize_symbol(symbol)

    if normalized_symbol != M5_SYMBOL:
        raise ValueError(
            "only GBPUSD-OTC is available for the first M15 context validation"
        )

    provider_call_started_at = resolved_now()
    resolved_provider = provider or IqOptionMarketDataProvider()

    candles = tuple(
        resolved_provider.get_candles(
            symbol=M5_SYMBOL,
            timeframe=M15_TIMEFRAME,
            limit=FETCH_LIMIT,
        )
    )

    provider_call_completed_at = resolved_now()

    if not candles:
        raise LookupError(
            "IQ Option returned no closed M15 candles for GBPUSD-OTC"
        )

    candles = tuple(sorted(candles, key=lambda candle: candle.timestamp))
    latest_candle = candles[-1]
    latest_close = candle_close_time(latest_candle)
    expected_close = expected_latest_close_time(provider_call_completed_at)
    state = determine_state(latest_close, expected_close)
    contiguous = candles_are_contiguous(candles)
    closes = [candle.close for candle in candles]
    ema200_values = ema_series(closes, EMA_PERIOD)
    ema200 = ema200_values[-1]
    ema200_previous = (
        ema200_values[-1 - EMA_SLOPE_LOOKBACK]
        if len(ema200_values) > EMA_SLOPE_LOOKBACK
        else None
    )

    swing_highs, swing_lows = find_confirmed_swings(candles)
    structure = classify_structure(swing_highs, swing_lows)

    reasons: list[str] = []

    if len(candles) < REQUIRED_CLOSED_CANDLES:
        trend = "NEUTRAL"
        reasons.append(
            f"Only {len(candles)} closed M15 candles were received; "
            f"{REQUIRED_CLOSED_CANDLES} are required."
        )
    elif not contiguous:
        trend = "NEUTRAL"
        reasons.append("Closed M15 candles contain a timestamp gap.")
    elif state != "UPDATED":
        trend = "NEUTRAL"
        reasons.append(
            f"M15 data state is {state}; directional confirmation is blocked."
        )
    elif ema200 is None or ema200_previous is None:
        trend = "NEUTRAL"
        reasons.append("EMA 200 could not be calculated from closed M15 candles.")
    elif (
        latest_candle.close > ema200
        and ema200 > ema200_previous
        and structure == "HIGHER_HIGH_HIGHER_LOW"
    ):
        trend = "BULLISH"
        reasons.extend(
            [
                "Close is above M15 EMA 200.",
                "M15 EMA 200 is rising over the configured three-candle lookback.",
                "Confirmed M15 swings form higher highs and higher lows.",
            ]
        )
    elif (
        latest_candle.close < ema200
        and ema200 < ema200_previous
        and structure == "LOWER_HIGH_LOWER_LOW"
    ):
        trend = "BEARISH"
        reasons.extend(
            [
                "Close is below M15 EMA 200.",
                "M15 EMA 200 is falling over the configured three-candle lookback.",
                "Confirmed M15 swings form lower highs and lower lows.",
            ]
        )
    else:
        trend = "NEUTRAL"

        if latest_candle.close == ema200:
            reasons.append("M15 close equals EMA 200.")
        elif latest_candle.close > ema200:
            reasons.append(
                "M15 close is above EMA 200, but slope and confirmed structure do not "
                "fully confirm a bullish trend."
            )
        else:
            reasons.append(
                "M15 close is below EMA 200, but slope and confirmed structure do not "
                "fully confirm a bearish trend."
            )

        reasons.append(
            f"Confirmed M15 structure is {structure}."
        )

    observed_age_seconds = max(
        0.0,
        round((provider_call_completed_at - latest_close).total_seconds(), 3),
    )

    return {
        "state": state,
        "trend": trend,
        "timeframe": M15_TIMEFRAME,
        "latestClosedCandle": candle_to_payload(latest_candle),
        "expectedLatestCloseTime": expected_close.isoformat(),
        "ema200": ema200,
        "ema200ThreeCandlesAgo": ema200_previous,
        "structure": structure,
        "dataQuality": {
            "requiredClosedCandles": REQUIRED_CLOSED_CANDLES,
            "receivedClosedCandles": len(candles),
            "candlesContiguous": contiguous,
        },
        "reasons": reasons,
        "timing": {
            "sourceCandleCloseTime": latest_close.isoformat(),
            "observedClosedCandleAgeSeconds": observed_age_seconds,
            "providerCallStartedAt": provider_call_started_at.isoformat(),
            "providerCallCompletedAt": provider_call_completed_at.isoformat(),
            "providerCallDurationMs": duration_ms(
                provider_call_started_at,
                provider_call_completed_at,
            ),
            "providerCallScope": (
                "IQ Option connection, M15 candle retrieval and provider parsing"
            ),
        },
    }
