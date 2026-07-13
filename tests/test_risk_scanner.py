from __future__ import annotations

import unittest

from helpers import synthetic_candles
from unified_market_indicator import (
    AssetClass,
    MarketScanner,
    MarketSeries,
    RiskManager,
    UnifiedIndicatorEngine,
)


class RiskAndScannerTest(unittest.TestCase):
    def test_atr_plan_caps_allocation_and_defines_long_exits(self) -> None:
        decision = UnifiedIndicatorEngine().analyze(
            "ETHUSDT", AssetClass.CRYPTO, synthetic_candles(trend=0)
        )
        plan = RiskManager(
            account_equity=20_000,
            risk_pct=1,
            max_allocation_pct=25,
        ).plan(decision)
        self.assertEqual(plan.direction, "LONG")
        self.assertLess(plan.stop_loss, plan.entry_price)
        self.assertGreater(plan.take_profit, plan.entry_price)
        self.assertLessEqual(plan.position_value, 5_000.01)
        self.assertLessEqual(plan.risk_amount, 200.01)

    def test_hold_signal_produces_no_position(self) -> None:
        decision = UnifiedIndicatorEngine().analyze(
            "BTCUSDT", AssetClass.CRYPTO, synthetic_candles(trend=0.12)
        )
        plan = RiskManager().plan(decision)
        self.assertEqual(plan.direction, "FLAT")
        self.assertEqual(plan.position_size, 0)
        self.assertIsNone(plan.stop_loss)

    def test_scanner_ranks_and_filters_multiple_asset_classes(self) -> None:
        markets = [
            MarketSeries("BEAR", AssetClass.CRYPTO, synthetic_candles(trend=-0.12)),
            MarketSeries("BULL", AssetClass.STOCK, synthetic_candles(trend=0)),
            MarketSeries("FLAT", AssetClass.CRYPTO, synthetic_candles(trend=0.12)),
        ]
        scanner = MarketScanner()
        result = scanner.scan(markets)
        self.assertEqual(result.total_markets, 3)
        self.assertEqual([item.rank for item in result.items], [1, 2, 3])
        self.assertGreaterEqual(result.items[0].opportunity_score, result.items[-1].opportunity_score)
        flat = next(item for item in result.items if item.decision.symbol == "FLAT")
        self.assertEqual(flat.opportunity_score, 0)
        bearish = scanner.scan(markets, direction="bearish")
        self.assertEqual(bearish.matched_markets, 1)
        self.assertEqual(bearish.items[0].decision.symbol, "BEAR")

    def test_invalid_scanner_filters_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MarketScanner().scan([], direction="sideways")
        with self.assertRaises(ValueError):
            MarketScanner().scan([], min_confidence=101)


if __name__ == "__main__":
    unittest.main()
