from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path


target = Path(__file__).with_name("sample_ohlcv.csv")
start = datetime(2025, 1, 1, tzinfo=timezone.utc)
previous = 100.0
with target.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
        lineterminator="\n",
    )
    writer.writeheader()
    for index in range(240):
        close = 100 + index * 0.1 + math.sin(index / 6) * 2.5
        writer.writerow(
            {
                "timestamp": (start + timedelta(hours=index)).isoformat(),
                "open": previous,
                "high": max(previous, close) + 1.2,
                "low": min(previous, close) - 1.2,
                "close": close,
                "volume": 1_000 + (index % 24) * 35,
            }
        )
        previous = close
print(target)
