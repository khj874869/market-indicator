from __future__ import annotations

from typing import Protocol

from ..models import Candle


class MarketDataProvider(Protocol):
    def fetch(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        ...
