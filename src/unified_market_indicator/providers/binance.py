from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import Candle
from .http import get_json


class BinanceProvider:
    base_url = "https://api.binance.com/api/v3/klines"

    def fetch(self, symbol: str, interval: str = "1h", limit: int = 300) -> list[Candle]:
        if not 1 <= limit <= 1000:
            raise ValueError("Binance limit must be between 1 and 1000")
        payload = get_json(
            self.base_url,
            {"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )
        return self.parse(payload)

    @staticmethod
    def parse(payload: list[list[Any]]) -> list[Candle]:
        return [
            Candle(
                timestamp=datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )
            for row in payload
        ]
