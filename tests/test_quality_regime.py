from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from helpers import synthetic_candles
from unified_market_indicator import (
    AssetClass,
    DataQualityAnalyzer,
    MarketRegime,
    MarketRegimeDetector,
    MultiTimeframeAnalyzer,
    Candle,
    interval_seconds,
    resample_candles,
)


class QualityAndRegimeTest(unittest.TestCase):
    def test_clean_hourly_data_receives_an_a_grade(self) -> None:
        result = DataQualityAnalyzer().analyze(synthetic_candles(), AssetClass.CRYPTO)
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.inferred_interval_seconds, 3600)
        self.assertEqual(result.interval_regularity_pct, 100)
        self.assertEqual(result.gap_events, 0)
        self.assertEqual(result.duplicate_timestamps, 0)

    def test_quality_report_detects_gaps_duplicates_order_and_zero_volume(self) -> None:
        source = synthetic_candles()
        damaged = source[:80] + source[81:]
        damaged[20] = replace(damaged[20], volume=0)
        damaged.append(source[10])
        result = DataQualityAnalyzer().analyze(damaged, AssetClass.CRYPTO)
        self.assertEqual(result.duplicate_timestamps, 1)
        self.assertGreaterEqual(result.out_of_order_records, 1)
        self.assertEqual(result.gap_events, 1)
        self.assertEqual(result.zero_volume_records, 1)
        self.assertLess(result.quality_score, 90)

    def test_empty_quality_report_is_explicit(self) -> None:
        result = DataQualityAnalyzer().analyze([], AssetClass.STOCK)
        self.assertEqual(result.grade, "F")
        self.assertEqual(result.candle_count, 0)

    def test_candle_rejects_non_finite_and_zero_prices(self) -> None:
        timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            Candle(timestamp, 100, float("nan"), 99, 100, 1_000)
        with self.assertRaises(ValueError):
            Candle(timestamp, 0, 1, 0.5, 0.8, 1_000)

    def test_stock_weekends_are_not_reported_as_missing_candles(self) -> None:
        timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
        candles: list[Candle] = []
        while len(candles) < 90:
            if timestamp.weekday() < 5:
                price = 100 + len(candles) * 0.1
                candles.append(Candle(timestamp, price, price + 1, price - 1, price, 1_000))
            timestamp += timedelta(days=1)
        result = DataQualityAnalyzer().analyze(candles, AssetClass.STOCK)
        self.assertEqual(result.gap_events, 0)
        self.assertEqual(result.missing_candles_estimate, 0)
        self.assertEqual(result.interval_regularity_pct, 100)

    def test_regime_detector_distinguishes_trend_and_range(self) -> None:
        detector = MarketRegimeDetector()
        bull = detector.detect(synthetic_candles(trend=0.1, oscillation=0), AssetClass.CRYPTO)
        bear = detector.detect(synthetic_candles(trend=-0.1, oscillation=0), AssetClass.CRYPTO)
        flat = detector.detect(synthetic_candles(trend=0, oscillation=0), AssetClass.CRYPTO)
        self.assertEqual(bull.regime, MarketRegime.BULL_TREND)
        self.assertEqual(bear.regime, MarketRegime.BEAR_TREND)
        self.assertEqual(flat.regime, MarketRegime.RANGE_BOUND)

    def test_resampling_preserves_ohlcv_semantics(self) -> None:
        source = synthetic_candles(count=240)
        result = resample_candles(source, "4h")
        self.assertEqual(len(result), 60)
        self.assertEqual(result[0].open, source[0].open)
        self.assertEqual(result[0].close, source[3].close)
        self.assertEqual(result[0].high, max(item.high for item in source[:4]))
        self.assertEqual(result[0].volume, sum(item.volume for item in source[:4]))
        self.assertEqual(interval_seconds("15m"), 900)
        with self.assertRaises(ValueError):
            interval_seconds("hour")

    def test_multi_timeframe_consensus_skips_insufficient_intervals(self) -> None:
        result = MultiTimeframeAnalyzer().analyze(
            "BTCUSDT",
            AssetClass.CRYPTO,
            synthetic_candles(count=480),
            ["1h", "4h", "1d"],
        )
        self.assertEqual(len(result.timeframes), 2)
        self.assertIn("1d", result.skipped_timeframes)
        self.assertGreaterEqual(result.agreement_pct, 0)
        self.assertLessEqual(result.agreement_pct, 100)
        self.assertEqual(result.quality.grade, "A")
        self.assertAlmostEqual(sum(item.weight for item in result.timeframes), 1, places=3)

    def test_multi_timeframe_rejects_duplicate_source_data(self) -> None:
        source = synthetic_candles()
        with self.assertRaises(ValueError):
            MultiTimeframeAnalyzer().analyze(
                "AAPL", AssetClass.STOCK, source + [source[-1]], ["1h"]
            )


if __name__ == "__main__":
    unittest.main()
