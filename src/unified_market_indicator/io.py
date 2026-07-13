from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Candle


def read_candles(path: str | Path) -> list[Candle]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        rows = payload["candles"] if isinstance(payload, dict) else payload
    elif source.suffix.lower() == ".csv":
        with source.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        raise ValueError("input must be a .csv or .json file")
    candles = [Candle.from_mapping(row) for row in rows]
    return sorted(candles, key=lambda candle: candle.timestamp)


def write_candles(path: str | Path, candles: list[Candle]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        target.write_text(
            json.dumps([candle.as_dict() for candle in candles], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return
    if target.suffix.lower() != ".csv":
        raise ValueError("output must be a .csv or .json file")
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(candle.as_dict() for candle in candles)
