from __future__ import annotations

import unittest

from unified_market_indicator.providers.binance import BinanceProvider
from unified_market_indicator.providers.upbit import UpbitProvider
from unified_market_indicator.providers.yahoo import YahooFinanceProvider


class ProviderParserTest(unittest.TestCase):
    def test_binance_parser(self) -> None:
        candles = BinanceProvider.parse([[1_700_000_000_000, "10", "12", "9", "11", "42"]])
        self.assertEqual(candles[0].close, 11)

    def test_upbit_parser_sorts_oldest_first(self) -> None:
        payload = [
            {
                "candle_date_time_utc": "2025-01-02T00:00:00",
                "opening_price": 10,
                "high_price": 12,
                "low_price": 9,
                "trade_price": 11,
                "candle_acc_trade_volume": 42,
            },
            {
                "candle_date_time_utc": "2025-01-01T00:00:00",
                "opening_price": 9,
                "high_price": 11,
                "low_price": 8,
                "trade_price": 10,
                "candle_acc_trade_volume": 30,
            },
        ]
        candles = UpbitProvider.parse(payload)
        self.assertLess(candles[0].timestamp, candles[1].timestamp)

    def test_yahoo_parser_skips_null_rows(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1_700_000_000, 1_700_003_600],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10, None],
                                    "high": [12, None],
                                    "low": [9, None],
                                    "close": [11, None],
                                    "volume": [42, None],
                                }
                            ]
                        },
                    }
                ]
            }
        }
        self.assertEqual(len(YahooFinanceProvider.parse(payload)), 1)


if __name__ == "__main__":
    unittest.main()
