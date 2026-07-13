from __future__ import annotations

import unittest

from helpers import synthetic_candles
from unified_market_indicator.indicators import (
    atr,
    bollinger_bands,
    ema,
    macd,
    obv,
    rsi,
    sma,
    snapshot,
    stochastic,
)


class IndicatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candles = synthetic_candles()
        self.closes = [candle.close for candle in self.candles]

    def test_moving_averages_have_expected_warmup(self) -> None:
        simple = sma(self.closes, 20)
        exponential = ema(self.closes, 20)
        self.assertIsNone(simple[18])
        self.assertIsNotNone(simple[19])
        self.assertIsNone(exponential[18])
        self.assertIsNotNone(exponential[19])

    def test_oscillators_stay_in_range(self) -> None:
        rsi_values = [value for value in rsi(self.closes) if value is not None]
        stochastic_k, stochastic_d = stochastic(self.candles)
        self.assertTrue(all(0 <= value <= 100 for value in rsi_values))
        self.assertTrue(all(0 <= value <= 100 for value in stochastic_k if value is not None))
        self.assertTrue(all(0 <= value <= 100 for value in stochastic_d if value is not None))

    def test_volatility_and_volume_indicators(self) -> None:
        upper, middle, lower = bollinger_bands(self.closes)
        self.assertGreater(upper[-1], middle[-1])
        self.assertGreater(middle[-1], lower[-1])
        self.assertGreater(atr(self.candles)[-1], 0)
        self.assertEqual(len(obv(self.candles)), len(self.candles))

    def test_macd_and_snapshot_are_complete_after_warmup(self) -> None:
        line, signal, histogram = macd(self.closes)
        self.assertIsNotNone(line[-1])
        self.assertIsNotNone(signal[-1])
        self.assertIsNotNone(histogram[-1])
        result = snapshot(self.candles)
        self.assertEqual(result.close, self.candles[-1].close)
        self.assertIsNotNone(result.rsi)


if __name__ == "__main__":
    unittest.main()
