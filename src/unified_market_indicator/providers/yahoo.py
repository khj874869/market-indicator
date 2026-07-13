from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from ..models import Candle
from .http import get_json


class YahooFinanceProvider:
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    def fetch(self, symbol: str, interval: str = "1d", limit: int = 300) -> list[Candle]:
        ranges = {
            "1m": "7d",
            "5m": "60d",
            "15m": "60d",
            "30m": "60d",
            "60m": "2y",
            "1h": "2y",
            "1d": "5y",
            "1wk": "10y",
        }
        normalized_interval = "60m" if interval == "1h" else interval
        payload = get_json(
            f"{self.base_url}/{quote(symbol)}",
            {"interval": normalized_interval, "range": ranges.get(normalized_interval, "5y")},
        )
        return self.parse(payload)[-limit:]

    @staticmethod
    def parse(payload: dict[str, Any]) -> list[Candle]:
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote_values = result["indicators"]["quote"][0]
        candles: list[Candle] = []
        for index, timestamp in enumerate(timestamps):
            values = {
                key: quote_values.get(key, [None] * len(timestamps))[index]
                for key in ("open", "high", "low", "close", "volume")
            }
            if any(values[key] is None for key in ("open", "high", "low", "close")):
                continue
            candles.append(
                Candle(
                    timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                    open=float(values["open"]),
                    high=float(values["high"]),
                    low=float(values["low"]),
                    close=float(values["close"]),
                    volume=float(values["volume"] or 0),
                )
            )
        return candles
