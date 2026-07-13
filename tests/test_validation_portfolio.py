from __future__ import annotations

import unittest

from helpers import synthetic_candles
from unified_market_indicator import (
    AssetClass,
    Backtester,
    MarketSeries,
    MonteCarloStressTester,
    PortfolioAllocator,
    WalkForwardValidator,
)


class ValidationAndPortfolioTest(unittest.TestCase):
    def test_walk_forward_reports_non_overlapping_test_folds(self) -> None:
        result = WalkForwardValidator().run(
            "BTCUSDT",
            AssetClass.CRYPTO,
            synthetic_candles(count=360, trend=0),
            test_size=60,
        )
        self.assertEqual(result.fold_count, 5)
        self.assertEqual([fold.fold for fold in result.folds], [1, 2, 3, 4, 5])
        self.assertTrue(all(fold.test_candles == 60 for fold in result.folds))
        self.assertEqual(result.total_trades, sum(fold.trades for fold in result.folds))
        self.assertGreaterEqual(result.robustness_score, 0)
        self.assertLessEqual(result.robustness_score, 100)
        self.assertIn(result.rating, {"ROBUST", "STABLE", "FRAGILE", "WEAK"})

    def test_walk_forward_rejects_insufficient_data(self) -> None:
        with self.assertRaises(ValueError):
            WalkForwardValidator().run(
                "AAPL", AssetClass.STOCK, synthetic_candles(count=100), test_size=60
            )

    def test_monte_carlo_is_deterministic_and_orders_percentiles(self) -> None:
        backtest = Backtester().run(
            "BTCUSDT", AssetClass.CRYPTO, synthetic_candles(count=300, trend=0)
        )
        tester = MonteCarloStressTester()
        first = tester.run(backtest, paths=200, seed=7)
        second = tester.run(backtest, paths=200, seed=7)
        self.assertEqual(first, second)
        self.assertLessEqual(first.p05_return_pct, first.median_return_pct)
        self.assertLessEqual(first.median_return_pct, first.p95_return_pct)
        self.assertGreaterEqual(first.probability_of_loss_pct, 0)
        self.assertLessEqual(first.probability_of_loss_pct, 100)

    def test_portfolio_applies_signal_filter_correlation_and_caps(self) -> None:
        bullish = synthetic_candles(trend=0)
        result = PortfolioAllocator().allocate(
            [
                MarketSeries("BULL1", AssetClass.CRYPTO, bullish),
                MarketSeries("BULL2", AssetClass.STOCK, bullish),
                MarketSeries("HOLD", AssetClass.CRYPTO, synthetic_candles(trend=0.12)),
            ],
            account_equity=20_000,
            total_allocation_pct=80,
            max_asset_pct=25,
        )
        self.assertEqual(len(result.allocations), 2)
        self.assertIn("HOLD", result.rejected)
        self.assertTrue(all(item.weight_pct <= 25 for item in result.allocations))
        self.assertAlmostEqual(result.invested_pct + result.cash_pct, 100, places=3)
        self.assertEqual(result.correlation_matrix["BULL1"]["BULL2"], 1)
        self.assertAlmostEqual(
            sum(item.risk_contribution_pct for item in result.allocations), 100, places=3
        )

    def test_portfolio_rejects_duplicate_symbols(self) -> None:
        market = MarketSeries("BTC", AssetClass.CRYPTO, synthetic_candles())
        with self.assertRaises(ValueError):
            PortfolioAllocator().allocate([market, market])

    def test_empty_portfolio_does_not_claim_diversification(self) -> None:
        result = PortfolioAllocator().allocate(
            [MarketSeries("HOLD", AssetClass.CRYPTO, synthetic_candles())]
        )
        self.assertEqual(result.invested_pct, 0)
        self.assertEqual(result.diversification_score, 0)


if __name__ == "__main__":
    unittest.main()
