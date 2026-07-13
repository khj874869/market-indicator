from __future__ import annotations

import math
import re
from collections.abc import Sequence
from datetime import datetime, timezone

from .engine import UnifiedIndicatorEngine
from .models import (
    AssetClass,
    Candle,
    MarketRegime,
    MultiTimeframeResult,
    SignalDecision,
    TimeframeAnalysisItem,
)
from .quality import DataQualityAnalyzer
from .regime import MarketRegimeDetector


_INTERVAL_PATTERN = re.compile(r"^([1-9][0-9]*)([mhdw])$")
_UNIT_SECONDS = {"m": 60, "h": 3_600, "d": 86_400, "w": 604_800}


def interval_seconds(interval: str) -> int:
    match = _INTERVAL_PATTERN.fullmatch(interval.lower())
    if not match:
        raise ValueError(f"invalid timeframe '{interval}'; use forms such as 15m, 1h, 4h, or 1d")
    value = int(match.group(1)) * _UNIT_SECONDS[match.group(2)]
    if value > 365 * 86_400:
        raise ValueError("timeframe cannot exceed 365 days")
    return value


def resample_candles(candles: Sequence[Candle], interval: str) -> list[Candle]:
    seconds = interval_seconds(interval)
    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    if not ordered:
        return []
    buckets: list[Candle] = []
    bucket_start: int | None = None
    opening = high = low = close = volume = 0.0
    for candle in ordered:
        current_bucket = int(candle.timestamp.timestamp()) // seconds * seconds
        if bucket_start is None or current_bucket != bucket_start:
            if bucket_start is not None:
                buckets.append(
                    Candle(
                        timestamp=datetime.fromtimestamp(bucket_start, tz=timezone.utc),
                        open=opening,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                    )
                )
            bucket_start = current_bucket
            opening = candle.open
            high = candle.high
            low = candle.low
            volume = candle.volume
        else:
            high = max(high, candle.high)
            low = min(low, candle.low)
            volume += candle.volume
        close = candle.close
    assert bucket_start is not None
    buckets.append(
        Candle(
            timestamp=datetime.fromtimestamp(bucket_start, tz=timezone.utc),
            open=opening,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
    )
    return buckets


class MultiTimeframeAnalyzer:
    def __init__(
        self,
        engine: UnifiedIndicatorEngine | None = None,
        quality_analyzer: DataQualityAnalyzer | None = None,
        regime_detector: MarketRegimeDetector | None = None,
    ) -> None:
        self.engine = engine or UnifiedIndicatorEngine()
        self.quality_analyzer = quality_analyzer or DataQualityAnalyzer()
        self.regime_detector = regime_detector or MarketRegimeDetector()

    def analyze(
        self,
        symbol: str,
        asset_class: AssetClass,
        candles: Sequence[Candle],
        timeframes: Sequence[str],
    ) -> MultiTimeframeResult:
        if not timeframes:
            raise ValueError("at least one timeframe is required")
        if len(timeframes) > 8:
            raise ValueError("at most eight timeframes are supported")
        quality = self.quality_analyzer.analyze(candles, asset_class)
        if quality.duplicate_timestamps:
            raise ValueError("duplicate timestamps must be removed before multi-timeframe analysis")
        if len(candles) < self.engine.minimum_candles:
            raise ValueError(f"at least {self.engine.minimum_candles} source candles are required")
        source_interval = quality.inferred_interval_seconds or 1.0
        raw_items: list[tuple[str, list[Candle], float, SignalDecision]] = []
        skipped: dict[str, str] = {}
        seen: set[str] = set()
        for raw_timeframe in timeframes:
            timeframe = raw_timeframe.lower()
            if timeframe in seen:
                continue
            seen.add(timeframe)
            seconds = interval_seconds(timeframe)
            if seconds < source_interval * 0.9:
                skipped[timeframe] = "Requested timeframe is smaller than the source interval"
                continue
            aggregated = resample_candles(candles, timeframe)
            if len(aggregated) < self.engine.minimum_candles:
                skipped[timeframe] = (
                    f"Only {len(aggregated)} candles after resampling; "
                    f"{self.engine.minimum_candles} are required"
                )
                continue
            decision = self.engine.analyze(symbol, asset_class, aggregated)
            ratio = max(1.0, seconds / source_interval)
            weight = min(4.0, 1.0 + math.log2(ratio))
            raw_items.append((timeframe, aggregated, weight, decision))

        if not raw_items:
            raise ValueError("none of the requested timeframes has enough data")
        total_weight = sum(item[2] for item in raw_items)
        weighted_score = sum(item[2] * item[3].score for item in raw_items) / total_weight
        regime = self.regime_detector.detect(candles, asset_class)
        if regime.regime == MarketRegime.BULL_TREND and weighted_score < 0:
            weighted_score *= 0.75
        elif regime.regime == MarketRegime.BEAR_TREND and weighted_score > 0:
            weighted_score *= 0.75
        elif regime.regime == MarketRegime.HIGH_VOLATILITY:
            weighted_score *= 0.80
        consensus_sign = 1 if weighted_score > 0 else -1 if weighted_score < 0 else 0
        aligned_weight = sum(
            weight
            for _, _, weight, decision in raw_items
            if (1 if decision.score > 0 else -1 if decision.score < 0 else 0) == consensus_sign
        )
        agreement = aligned_weight / total_weight if total_weight else 0.0
        weighted_confidence = sum(item[2] * item[3].confidence for item in raw_items) / total_weight
        quality_factor = 0.5 + quality.quality_score / 200
        confidence = weighted_confidence * (0.55 + agreement * 0.45) * quality_factor
        normalized_items = tuple(
            TimeframeAnalysisItem(
                timeframe=timeframe,
                candle_count=len(aggregated),
                weight=round(weight / total_weight, 4),
                decision=decision,
            )
            for timeframe, aggregated, weight, decision in raw_items
        )
        score = round(max(-100.0, min(100.0, weighted_score)), 2)
        return MultiTimeframeResult(
            symbol=symbol.upper(),
            asset_class=asset_class,
            consensus_signal=self.engine.signal_for_score(asset_class, score),
            consensus_score=score,
            confidence=round(min(100.0, confidence), 2),
            agreement_pct=round(agreement * 100, 2),
            regime=regime,
            quality=quality,
            timeframes=normalized_items,
            skipped_timeframes=skipped,
        )
