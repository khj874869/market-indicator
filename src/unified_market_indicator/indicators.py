from __future__ import annotations

import math
from collections.abc import Sequence

from .models import Candle, IndicatorSnapshot


def _validate_period(period: int) -> None:
    if period <= 0:
        raise ValueError("period must be positive")


def sma(values: Sequence[float], period: int) -> list[float | None]:
    _validate_period(period)
    output: list[float | None] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        if index >= period - 1:
            output[index] = running / period
    return output


def ema(values: Sequence[float], period: int) -> list[float | None]:
    _validate_period(period)
    output: list[float | None] = [None] * len(values)
    if len(values) < period:
        return output
    seed = sum(values[:period]) / period
    output[period - 1] = seed
    multiplier = 2 / (period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = (values[index] - previous) * multiplier + previous
        output[index] = previous
    return output


def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    _validate_period(period)
    output: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return output
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values, values[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    output[period] = _rsi_value(average_gain, average_loss)
    for index in range(period, len(gains)):
        average_gain = ((average_gain * (period - 1)) + gains[index]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index]) / period
        output[index + 1] = _rsi_value(average_gain, average_loss)
    return output


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def macd(
    values: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    line: list[float | None] = [
        None if fast_value is None or slow_value is None else fast_value - slow_value
        for fast_value, slow_value in zip(fast, slow)
    ]
    signal: list[float | None] = [None] * len(values)
    valid = [value for value in line if value is not None]
    valid_signal = ema(valid, signal_period)
    first_valid = next((index for index, value in enumerate(line) if value is not None), len(line))
    for offset, value in enumerate(valid_signal):
        signal[first_valid + offset] = value
    histogram = [
        None if line_value is None or signal_value is None else line_value - signal_value
        for line_value, signal_value in zip(line, signal)
    ]
    return line, signal, histogram


def bollinger_bands(
    values: Sequence[float],
    period: int = 20,
    standard_deviations: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    middle = sma(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1 : index + 1]
        mean = middle[index]
        assert mean is not None
        variance = sum((value - mean) ** 2 for value in window) / period
        deviation = math.sqrt(variance) * standard_deviations
        upper[index] = mean + deviation
        lower[index] = mean - deviation
    return upper, middle, lower


def atr(candles: Sequence[Candle], period: int = 14) -> list[float | None]:
    _validate_period(period)
    if not candles:
        return []
    true_ranges = [candles[0].high - candles[0].low]
    for previous, current in zip(candles, candles[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return ema(true_ranges, period)


def stochastic(
    candles: Sequence[Candle],
    period: int = 14,
    smooth: int = 3,
) -> tuple[list[float | None], list[float | None]]:
    _validate_period(period)
    k_values: list[float | None] = [None] * len(candles)
    for index in range(period - 1, len(candles)):
        window = candles[index - period + 1 : index + 1]
        highest = max(candle.high for candle in window)
        lowest = min(candle.low for candle in window)
        spread = highest - lowest
        k_values[index] = 50.0 if spread == 0 else 100 * (candles[index].close - lowest) / spread
    valid_k = [value for value in k_values if value is not None]
    valid_d = sma(valid_k, smooth)
    d_values: list[float | None] = [None] * len(candles)
    first_valid = period - 1
    for offset, value in enumerate(valid_d):
        d_values[first_valid + offset] = value
    return k_values, d_values


def obv(candles: Sequence[Candle]) -> list[float]:
    if not candles:
        return []
    output = [0.0]
    for previous, current in zip(candles, candles[1:]):
        if current.close > previous.close:
            output.append(output[-1] + current.volume)
        elif current.close < previous.close:
            output.append(output[-1] - current.volume)
        else:
            output.append(output[-1])
    return output


def adx(
    candles: Sequence[Candle],
    period: int = 14,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    _validate_period(period)
    length = len(candles)
    plus_di: list[float | None] = [None] * length
    minus_di: list[float | None] = [None] * length
    adx_values: list[float | None] = [None] * length
    if length <= period:
        return plus_di, minus_di, adx_values
    true_ranges = [0.0] * length
    plus_dm = [0.0] * length
    minus_dm = [0.0] * length
    for index in range(1, length):
        previous = candles[index - 1]
        current = candles[index]
        true_ranges[index] = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        upward = current.high - previous.high
        downward = previous.low - current.low
        plus_dm[index] = upward if upward > downward and upward > 0 else 0.0
        minus_dm[index] = downward if downward > upward and downward > 0 else 0.0

    smoothed_tr = sum(true_ranges[1 : period + 1])
    smoothed_plus = sum(plus_dm[1 : period + 1])
    smoothed_minus = sum(minus_dm[1 : period + 1])
    dx_values: list[float | None] = [None] * length
    for index in range(period, length):
        if index > period:
            smoothed_tr = smoothed_tr - smoothed_tr / period + true_ranges[index]
            smoothed_plus = smoothed_plus - smoothed_plus / period + plus_dm[index]
            smoothed_minus = smoothed_minus - smoothed_minus / period + minus_dm[index]
        if smoothed_tr == 0:
            plus_value = minus_value = 0.0
        else:
            plus_value = 100 * smoothed_plus / smoothed_tr
            minus_value = 100 * smoothed_minus / smoothed_tr
        plus_di[index] = plus_value
        minus_di[index] = minus_value
        total = plus_value + minus_value
        dx_values[index] = 0.0 if total == 0 else 100 * abs(plus_value - minus_value) / total

    first_adx_index = period * 2 - 1
    if first_adx_index < length:
        seed = [value for value in dx_values[period : first_adx_index + 1] if value is not None]
        previous_adx = sum(seed) / len(seed)
        adx_values[first_adx_index] = previous_adx
        for index in range(first_adx_index + 1, length):
            current_dx = dx_values[index]
            assert current_dx is not None
            previous_adx = ((previous_adx * (period - 1)) + current_dx) / period
            adx_values[index] = previous_adx
    return plus_di, minus_di, adx_values


def money_flow_index(candles: Sequence[Candle], period: int = 14) -> list[float | None]:
    _validate_period(period)
    output: list[float | None] = [None] * len(candles)
    if len(candles) <= period:
        return output
    typical = [(candle.high + candle.low + candle.close) / 3 for candle in candles]
    positive = [0.0] * len(candles)
    negative = [0.0] * len(candles)
    for index in range(1, len(candles)):
        flow = typical[index] * candles[index].volume
        if typical[index] > typical[index - 1]:
            positive[index] = flow
        elif typical[index] < typical[index - 1]:
            negative[index] = flow
    positive_sum = 0.0
    negative_sum = 0.0
    for index in range(1, len(candles)):
        positive_sum += positive[index]
        negative_sum += negative[index]
        if index > period:
            positive_sum = max(0.0, positive_sum - positive[index - period])
            negative_sum = max(0.0, negative_sum - negative[index - period])
        if index >= period:
            if negative_sum == 0:
                output[index] = 100.0 if positive_sum > 0 else 50.0
            else:
                ratio = positive_sum / negative_sum
                output[index] = max(0.0, min(100.0, 100 - 100 / (1 + ratio)))
    return output


def rate_of_change(values: Sequence[float], period: int = 12) -> list[float | None]:
    _validate_period(period)
    output: list[float | None] = [None] * len(values)
    for index in range(period, len(values)):
        previous = values[index - period]
        output[index] = None if previous == 0 else (values[index] / previous - 1) * 100
    return output


def rolling_vwap(candles: Sequence[Candle], period: int = 20) -> list[float | None]:
    _validate_period(period)
    output: list[float | None] = [None] * len(candles)
    price_volume = [
        ((candle.high + candle.low + candle.close) / 3) * candle.volume
        for candle in candles
    ]
    volume_sum = 0.0
    price_volume_sum = 0.0
    for index, candle in enumerate(candles):
        volume_sum += candle.volume
        price_volume_sum += price_volume[index]
        if index >= period:
            volume_sum -= candles[index - period].volume
            price_volume_sum -= price_volume[index - period]
        if index >= period - 1:
            output[index] = None if volume_sum == 0 else price_volume_sum / volume_sum
    return output


def snapshot(candles: Sequence[Candle]) -> IndicatorSnapshot:
    if not candles:
        raise ValueError("at least one candle is required")
    closes = [candle.close for candle in candles]
    volumes = [candle.volume for candle in candles]
    sma_fast = sma(closes, 20)
    sma_slow = sma(closes, 50)
    ema_fast = ema(closes, 12)
    ema_slow = ema(closes, 26)
    rsi_values = rsi(closes)
    macd_line, macd_signal, macd_histogram = macd(closes)
    upper, middle, lower = bollinger_bands(closes)
    atr_values = atr(candles)
    stochastic_k, stochastic_d = stochastic(candles)
    obv_values = obv(candles)
    plus_di, minus_di, adx_values = adx(candles)
    mfi_values = money_flow_index(candles)
    roc_values = rate_of_change(closes)
    vwap_values = rolling_vwap(candles)
    average_volume = sma(volumes, 20)
    latest_average_volume = average_volume[-1]
    volume_ratio = (
        None
        if latest_average_volume in (None, 0)
        else candles[-1].volume / latest_average_volume
    )
    return IndicatorSnapshot(
        timestamp=candles[-1].timestamp,
        close=candles[-1].close,
        sma_fast=sma_fast[-1],
        sma_slow=sma_slow[-1],
        ema_fast=ema_fast[-1],
        ema_slow=ema_slow[-1],
        rsi=rsi_values[-1],
        macd=macd_line[-1],
        macd_signal=macd_signal[-1],
        macd_histogram=macd_histogram[-1],
        bollinger_upper=upper[-1],
        bollinger_middle=middle[-1],
        bollinger_lower=lower[-1],
        atr=atr_values[-1],
        stochastic_k=stochastic_k[-1],
        stochastic_d=stochastic_d[-1],
        obv=obv_values[-1],
        volume_ratio=volume_ratio,
        adx=adx_values[-1],
        plus_di=plus_di[-1],
        minus_di=minus_di[-1],
        mfi=mfi_values[-1],
        roc=roc_values[-1],
        vwap=vwap_values[-1],
    )
