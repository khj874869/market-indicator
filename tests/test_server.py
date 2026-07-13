from __future__ import annotations

import unittest
from importlib.resources import files

from helpers import synthetic_candles
from unified_market_indicator.server import _backtest, _decision, _risk_plan, _scan


class ServerContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "symbol": "BTCUSDT",
            "asset_class": "crypto",
            "candles": [candle.as_dict() for candle in synthetic_candles()],
        }

    def test_analysis_risk_and_backtest_contracts(self) -> None:
        self.assertIn("score", _decision(self.payload))
        self.assertIn("position_size", _risk_plan(self.payload))
        result = _backtest(self.payload)
        self.assertIn("sharpe_ratio", result)
        self.assertIn("benchmark_return_pct", result)
        self.assertEqual(len(result["equity_curve"]), 180)

    def test_scan_contract_and_dashboard_assets(self) -> None:
        result = _scan({"markets": [self.payload], "limit": 1})
        self.assertEqual(result["total_markets"], 1)
        self.assertEqual(len(result["items"]), 1)
        static = files("unified_market_indicator.static")
        self.assertIn("Market Signal Lab", static.joinpath("index.html").read_text(encoding="utf-8"))
        self.assertGreater(len(static.joinpath("app.js").read_bytes()), 1_000)


if __name__ == "__main__":
    unittest.main()
