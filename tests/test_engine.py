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
        self.assertEqual(
            set(stock.components),
            {"trend", "momentum", "volatility", "volume", "confirmation"},
        )
        self.assertGreaterEqual(stock.agreement_pct, 0)
        self.assertLessEqual(stock.agreement_pct, 100)
        self.assertGreaterEqual(stock.conflict_penalty, 0)

    def test_adx_adapts_trend_and_confirmation_score(self) -> None:
        strong_trend = synthetic_candles(trend=0.3, oscillation=0)
        decision = self.engine.analyze("AAPL", AssetClass.STOCK, strong_trend)
        self.assertGreater(decision.components["trend"], 28)
        self.assertGreater(decision.components["confirmation"], 0)
        self.assertGreater(decision.snapshot.adx, 25)
        self.assertGreater(decision.agreement_pct, 50)

    def test_flat_market_does_not_create_false_bearish_trend(self) -> None:
        flat = synthetic_candles(trend=0, oscillation=0)
        decision = self.engine.analyze("BTCUSDT", AssetClass.CRYPTO, flat)
        self.assertEqual(decision.components["trend"], 0)
        self.assertEqual(decision.components["confirmation"], 0)
        self.assertEqual(decision.score, 0)
        self.assertEqual(decision.signal, Signal.HOLD)
        self.assertLess(decision.confidence, 20)

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
        self.assertEqual(
            result.excess_return_pct,
            round(result.total_return_pct - result.benchmark_return_pct, 4),
        )


if __name__ == "__main__":
    unittest.main()
