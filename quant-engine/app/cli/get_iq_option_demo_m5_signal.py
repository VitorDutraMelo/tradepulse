import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from app.domain.candle import Candle
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)

M5_SYMBOL = "GBPUSD-OTC"
M5_TIMEFRAME = "5m"
M5_INTERVAL_SECONDS = 300
REQUIRED_CLOSED_CANDLES = 250
FETCH_LIMIT = 260
RSI_PERIOD = 14
ADX_PERIOD = 14
EMA_PERIOD = 200


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def duration_ms(started_at: datetime, completed_at: datetime) -> float:
    return max(
        0.0,
        round((completed_at - started_at).total_seconds() * 1000, 3),
    )


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("/", "")


def candle_close_time(candle: Candle) -> datetime:
    return candle.timestamp + timedelta(seconds=M5_INTERVAL_SECONDS)


def expected_latest_close_time(observed_at: datetime) -> datetime:
    seconds = int(observed_at.timestamp())
    return datetime.fromtimestamp(
        seconds - (seconds % M5_INTERVAL_SECONDS),
        tz=UTC,
    )


def determine_state(latest_close: datetime, expected_close: datetime) -> str:
    if latest_close >= expected_close:
        return "UPDATED"

    if latest_close == expected_close - timedelta(seconds=M5_INTERVAL_SECONDS):
        return "AWAITING_CONFIRMATION"

    return "STALE"


def ema_series(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)

    if len(values) < period:
        return result

    multiplier = 2 / (period + 1)
    result[period - 1] = sum(values[:period]) / period

    for index in range(period, len(values)):
        previous = result[index - 1]

        if previous is None:
            raise RuntimeError("EMA calculation lost its previous value")

        result[index] = (values[index] - previous) * multiplier + previous

    return result


def latest_rsi(values: list[float], period: int = RSI_PERIOD) -> float | None:
    if len(values) < period + 1:
        return None

    gains: list[float] = []
    losses: list[float] = []

    for previous, current in zip(values, values[1:]):
        difference = current - previous
        gains.append(max(difference, 0.0))
        losses.append(max(-difference, 0.0))

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period

    if average_loss == 0:
        return 100.0

    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def latest_macd(
    values: list[float],
) -> tuple[float | None, float | None, float | None, float | None]:
    fast = ema_series(values, 12)
    slow = ema_series(values, 26)

    macd_values = [
        fast_value - slow_value
        for fast_value, slow_value in zip(fast, slow)
        if fast_value is not None and slow_value is not None
    ]

    signal_values = ema_series(macd_values, 9)

    if len(macd_values) < 10 or signal_values[-1] is None:
        return None, None, None, None

    signal = signal_values[-1]
    previous_signal = signal_values[-2]

    if signal is None or previous_signal is None:
        return None, None, None, None

    histogram = macd_values[-1] - signal
    previous_histogram = macd_values[-2] - previous_signal

    return macd_values[-1], signal, histogram, previous_histogram


def latest_adx_atr(
    candles: tuple[Candle, ...],
    period: int = ADX_PERIOD,
) -> tuple[float | None, float | None]:
    if len(candles) < (period * 2) + 1:
        return None, None

    true_ranges: list[float] = []
    positive_dm: list[float] = []
    negative_dm: list[float] = []

    for previous, current in zip(candles, candles[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )

        upward_move = current.high - previous.high
        downward_move = previous.low - current.low

        positive_dm.append(
            upward_move if upward_move > downward_move and upward_move > 0 else 0.0
        )
        negative_dm.append(
            downward_move if downward_move > upward_move and downward_move > 0 else 0.0
        )

    smoothed_tr = sum(true_ranges[:period])
    smoothed_positive = sum(positive_dm[:period])
    smoothed_negative = sum(negative_dm[:period])
    dx_values: list[float] = []

    def calculate_dx() -> float:
        if smoothed_tr == 0:
            return 0.0

        positive_di = 100 * (smoothed_positive / smoothed_tr)
        negative_di = 100 * (smoothed_negative / smoothed_tr)
        denominator = positive_di + negative_di

        if denominator == 0:
            return 0.0

        return 100 * abs(positive_di - negative_di) / denominator

    dx_values.append(calculate_dx())

    for index in range(period, len(true_ranges)):
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + true_ranges[index]
        smoothed_positive = (
            smoothed_positive
            - (smoothed_positive / period)
            + positive_dm[index]
        )
        smoothed_negative = (
            smoothed_negative
            - (smoothed_negative / period)
            + negative_dm[index]
        )
        dx_values.append(calculate_dx())

    if len(dx_values) < period:
        return None, smoothed_tr / period

    adx = sum(dx_values[:period]) / period

    for dx in dx_values[period:]:
        adx = ((adx * (period - 1)) + dx) / period

    return adx, smoothed_tr / period


def candles_are_contiguous(candles: tuple[Candle, ...]) -> bool:
    expected_interval = timedelta(seconds=M5_INTERVAL_SECONDS)

    return all(
        current.timestamp - previous.timestamp == expected_interval
        for previous, current in zip(candles, candles[1:])
    )


def evaluate_candidate(
    close: float,
    ema200: float,
    rsi14: float,
    macd: float,
    macd_signal: float,
    histogram: float,
    previous_histogram: float,
    adx14: float,
    atr14: float,
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if atr14 <= 0:
        return "WAIT", ["ATR 14 is not positive."]

    distance_in_atr = abs(close - ema200) / atr14

    if adx14 < 20:
        reasons.append(f"ADX 14 is {adx14:.2f}; minimum is 20.00.")

    if distance_in_atr < 0.20:
        reasons.append(
            "Close is too near EMA 200 "
            f"({distance_in_atr:.3f} ATR; minimum is 0.200 ATR)."
        )

    if close > ema200:
        if not 55 <= rsi14 <= 68:
            reasons.append(
                f"RSI 14 is {rsi14:.2f}; CALL requires 55.00 to 68.00."
            )

        if not (macd > macd_signal and histogram > 0 and histogram > previous_histogram):
            reasons.append(
                "MACD CALL confirmation failed: line, histogram and momentum "
                "must all be positive."
            )

        if reasons:
            return "WAIT", reasons

        return "CALL", [
            "Close is above EMA 200 with sufficient ATR distance.",
            "RSI 14 is within the configured CALL range.",
            "MACD is above signal with positive and rising histogram.",
            "ADX 14 confirms the configured minimum trend strength.",
        ]

    if close < ema200:
        if not 32 <= rsi14 <= 45:
            reasons.append(
                f"RSI 14 is {rsi14:.2f}; PUT requires 32.00 to 45.00."
            )

        if not (macd < macd_signal and histogram < 0 and histogram < previous_histogram):
            reasons.append(
                "MACD PUT confirmation failed: line, histogram and momentum "
                "must all be negative."
            )

        if reasons:
            return "WAIT", reasons

        return "PUT", [
            "Close is below EMA 200 with sufficient ATR distance.",
            "RSI 14 is within the configured PUT range.",
            "MACD is below signal with negative and falling histogram.",
            "ADX 14 confirms the configured minimum trend strength.",
        ]

    return "WAIT", ["Close equals EMA 200; no directional candidate exists."]


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


def get_iq_option_demo_m5_signal(
    symbol: str,
    provider: IqOptionMarketDataProvider | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    resolved_now = now or now_utc
    normalized_symbol = normalize_symbol(symbol)

    if normalized_symbol != M5_SYMBOL:
        raise ValueError(
            "only GBPUSD-OTC is available for the first M5 signal validation"
        )

    analysis_started_at = resolved_now()
    provider_call_started_at = resolved_now()
    resolved_provider = provider or IqOptionMarketDataProvider()

    candles = tuple(
        resolved_provider.get_candles(
            symbol=M5_SYMBOL,
            timeframe=M5_TIMEFRAME,
            limit=FETCH_LIMIT,
        )
    )

    provider_call_completed_at = resolved_now()

    if not candles:
        raise LookupError("IQ Option returned no closed M5 candles for GBPUSD-OTC")

    candles = tuple(sorted(candles, key=lambda candle: candle.timestamp))
    latest_candle = candles[-1]
    latest_close = candle_close_time(latest_candle)
    expected_close = expected_latest_close_time(provider_call_completed_at)
    state = determine_state(latest_close, expected_close)
    contiguous = candles_are_contiguous(candles)
    closes = [candle.close for candle in candles]

    ema200_values = ema_series(closes, EMA_PERIOD)
    ema200 = ema200_values[-1]
    rsi14 = latest_rsi(closes)
    macd, macd_signal, histogram, previous_histogram = latest_macd(closes)
    adx14, atr14 = latest_adx_atr(candles)

    entry_time = latest_close
    expiration_time = latest_close + timedelta(seconds=M5_INTERVAL_SECONDS)

    indicators_available = all(
        value is not None
        for value in (
            ema200,
            rsi14,
            macd,
            macd_signal,
            histogram,
            previous_histogram,
            adx14,
            atr14,
        )
    )

    if len(candles) < REQUIRED_CLOSED_CANDLES:
        candidate_action = "WAIT"
        actionability = "DATA_INSUFFICIENT"
        reasons = [
            f"Only {len(candles)} closed M5 candles were received; "
            f"{REQUIRED_CLOSED_CANDLES} are required."
        ]
    elif not contiguous:
        candidate_action = "WAIT"
        actionability = "DATA_INSUFFICIENT"
        reasons = ["Closed M5 candles contain a timestamp gap."]
    elif state != "UPDATED":
        candidate_action = "WAIT"
        actionability = "DATA_NOT_CURRENT"
        reasons = [
            f"M5 data state is {state}; no current technical candidate is allowed."
        ]
    elif not indicators_available:
        candidate_action = "WAIT"
        actionability = "DATA_INSUFFICIENT"
        reasons = ["The M5 indicators could not be calculated from closed candles."]
    else:
        candidate_action, reasons = evaluate_candidate(
            close=latest_candle.close,
            ema200=float(ema200),
            rsi14=float(rsi14),
            macd=float(macd),
            macd_signal=float(macd_signal),
            histogram=float(histogram),
            previous_histogram=float(previous_histogram),
            adx14=float(adx14),
            atr14=float(atr14),
        )

        if candidate_action == "WAIT":
            actionability = "NO_CANDIDATE"
        else:
            actionability = "NOT_ACTIONABLE_LATE"
            reasons.append(
                "The theoretical next M5 opening already passed after closed-candle confirmation; no order is executable."
            )

    payload_built_at = resolved_now()
    observed_age_seconds = max(
        0.0,
        round((provider_call_completed_at - latest_close).total_seconds(), 3),
    )

    return {
        "source": IqOptionMarketDataProvider.source,
        "venue": IqOptionMarketDataProvider.venue,
        "accountMode": "PRACTICE",
        "symbol": M5_SYMBOL,
        "timeframe": M5_TIMEFRAME,
        "state": state,
        "latestClosedCandle": candle_to_payload(latest_candle),
        "expectedLatestCloseTime": expected_close.isoformat(),
        "indicators": {
            "ema200": ema200,
            "rsi14": rsi14,
            "macd": macd,
            "macdSignal": macd_signal,
            "macdHistogram": histogram,
            "previousMacdHistogram": previous_histogram,
            "adx14": adx14,
            "atr14": atr14,
        },
        "dataQuality": {
            "requiredClosedCandles": REQUIRED_CLOSED_CANDLES,
            "receivedClosedCandles": len(candles),
            "candlesContiguous": contiguous,
        },
        "decision": {
            "action": "WAIT",
            "candidateAction": candidate_action,
            "actionability": actionability,
            "theoreticalEntryTime": entry_time.isoformat(),
            "theoreticalExpirationTime": expiration_time.isoformat(),
            "reasons": reasons,
        },
        "timing": {
            "clockSource": "application_utc_clock",
            "iqCandleAvailabilityAt": None,
            "iqCandleAvailabilityMeasurement": (
                "NOT_AVAILABLE_FROM_IQ_OPTION_API"
            ),
            "sourceCandleCloseTime": latest_close.isoformat(),
            "observedClosedCandleAgeSeconds": observed_age_seconds,
            "python": {
                "analysisStartedAt": analysis_started_at.isoformat(),
                "providerCallStartedAt": provider_call_started_at.isoformat(),
                "providerCallCompletedAt": provider_call_completed_at.isoformat(),
                "payloadBuiltAt": payload_built_at.isoformat(),
                "providerCallDurationMs": duration_ms(
                    provider_call_started_at,
                    provider_call_completed_at,
                ),
                "payloadProcessingDurationMs": duration_ms(
                    provider_call_completed_at,
                    payload_built_at,
                ),
                "totalDurationMs": duration_ms(
                    analysis_started_at,
                    payload_built_at,
                ),
                "providerCallScope": (
                    "IQ Option connection, candle retrieval and provider parsing"
                ),
            },
        },
    }


def error_to_payload(error: Exception) -> dict[str, object]:
    if isinstance(error, PermissionError):
        code = "IQ_OPTION_ACCESS_DENIED"
    elif isinstance(error, ConnectionError):
        code = "IQ_OPTION_UNAVAILABLE"
    elif isinstance(error, LookupError):
        code = "IQ_OPTION_M5_SIGNAL_UNAVAILABLE"
    else:
        code = "INVALID_IQ_OPTION_M5_SIGNAL_REQUEST"

    return {"error": {"code": code, "message": str(error)}}


def main(argv: Sequence[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description="Evaluate a closed-candle GBPUSD-OTC M5 technical candidate.",
    )
    parser.add_argument("--symbol", default=M5_SYMBOL)

    try:
        arguments = parser.parse_args(argv)
        payload = get_iq_option_demo_m5_signal(symbol=arguments.symbol)
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