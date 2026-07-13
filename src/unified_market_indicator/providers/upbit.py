from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import Candle
from .http import get_json


class UpbitProvider:
    base_url = "https://api.upbit.com/v1/candles"

    def fetch(self, symbol: str, interval: str = "60", limit: int = 200) -> list[Candle]:
        if not 1 <= limit <= 200:
            raise ValueError("Upbit limit must be between 1 and 200")
        if interval in {"day", "days"}:
            url = f"{self.base_url}/days"
        else:
            minutes = int(interval.removesuffix("m"))
            if minutes not in {1, 3, 5, 10, 15, 30, 60, 240}:
                raise ValueError("unsupported Upbit minute interval")
            url = f"{self.base_url}/minutes/{minutes}"
        payload = get_json(url, {"market": symbol.upper(), "count": limit})
        return self.parse(payload)

    @staticmethod
    def parse(payload: list[dict[str, Any]]) -> list[Candle]:
        candles = [
            Candle.from_mapping(
                {
                    "timestamp": row["candle_date_time_utc"] + "+00:00",
                    "open": row["opening_price"],
                    "high": row["high_price"],
                    "low": row["low_price"],
                    "close": row["trade_price"],
                    "volume": row["candle_acc_trade_volume"],
                }
            )
            for row in payload
        ]
        return sorted(candles, key=lambda candle: candle.timestamp)
