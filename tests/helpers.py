from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from unified_market_indicator.models import Candle


def synthetic_candles(
    count: int = 240,
    *,
    trend: float = 0.12,
    oscillation: float = 2.5,
) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []
    previous = 100.0
    for index in range(count):
        close = 100 + index * trend + math.sin(index / 6) * oscillation
        opening = previous
        high = max(opening, close) + 1.2
        low = min(opening, close) - 1.2
        candles.append(
            Candle(
                timestamp=start + timedelta(hours=index),
                open=opening,
                high=high,
                low=low,
                close=close,
                volume=1_000 + (index % 24) * 35,
            )
        )
        previous = close
    return candles
