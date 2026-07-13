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
    )
