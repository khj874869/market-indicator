from __future__ import annotations

import unittest

from helpers import synthetic_candles
from unified_market_indicator import AssetClass, Backtester, Signal, UnifiedIndicatorEngine


class EngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candles = synthetic_candles()
        self.engine = UnifiedIndicatorEngine()

    def test_same_engine_supports_stock_and_crypto(self) -> None:
        stock = self.engine.analyze("AAPL", AssetClass.STOCK, self.candles)
        crypto = self.engine.analyze("BTCUSDT", AssetClass.CRYPTO, self.candles)
        self.assertIn(stock.signal, set(Signal))
        self.assertIn(crypto.signal, set(Signal))
        self.assertEqual(stock.asset_class, AssetClass.STOCK)
        self.assertEqual(crypto.asset_class, AssetClass.CRYPTO)
        self.assertGreaterEqual(stock.score, -100)
        self.assertLessEqual(stock.score, 100)
        self.assertEqual(set(stock.components), {"trend", "momentum", "volatility", "volume"})

    def test_rejects_short_or_duplicate_series(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.analyze("AAPL", AssetClass.STOCK, self.candles[:10])
        duplicate = list(self.candles)
        duplicate[-1] = duplicate[-2]
        with self.assertRaises(ValueError):
            self.engine.analyze("AAPL", AssetClass.STOCK, duplicate)

    def test_backtest_includes_costs_and_risk_metrics(self) -> None:
        result = Backtester(initial_capital=20_000, fee_bps=10, slippage_bps=5).run(
            "BTCUSDT",
            AssetClass.CRYPTO,
            self.candles,
        )
        self.assertGreater(result.final_equity, 0)
        self.assertGreaterEqual(result.max_drawdown_pct, 0)
        self.assertEqual(len(result.equity_curve), len(self.candles) - self.engine.minimum_candles)
        self.assertEqual(result.winning_trades + result.losing_trades, result.trades)
        self.assertLessEqual(result.stop_loss_exits + result.take_profit_exits, result.trades)
        self.assertIsInstance(result.sharpe_ratio, float)
        self.assertEqual(result.excess_return_pct, round(result.total_return_pct - result.benchmark_return_pct, 4))


if __name__ == "__main__":
    unittest.main()
