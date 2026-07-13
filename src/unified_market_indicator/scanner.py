from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .engine import UnifiedIndicatorEngine
from .models import AssetClass, Candle, RiskPlan, ScanItem, ScanResult, Signal, SignalDecision
from .risk import RiskManager


@dataclass(frozen=True, slots=True)
class MarketSeries:
    symbol: str
    asset_class: AssetClass
    candles: Sequence[Candle]


class MarketScanner:
    def __init__(
        self,
        engine: UnifiedIndicatorEngine | None = None,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self.engine = engine or UnifiedIndicatorEngine()
        self.risk_manager = risk_manager or RiskManager()

    def scan(
        self,
        markets: Iterable[MarketSeries],
        *,
        direction: str = "all",
        min_confidence: float = 0.0,
        limit: int | None = None,
    ) -> ScanResult:
        if direction not in {"all", "bullish", "bearish"}:
            raise ValueError("direction must be all, bullish, or bearish")
        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")

        series = list(markets)
        candidates: list[tuple[float, SignalDecision, RiskPlan]] = []
        bullish = {Signal.BUY, Signal.STRONG_BUY}
        bearish = {Signal.SELL, Signal.STRONG_SELL}
        for market in series:
            decision = self.engine.analyze(market.symbol, market.asset_class, market.candles)
            if decision.confidence < min_confidence:
                continue
            if direction == "bullish" and decision.signal not in bullish:
                continue
            if direction == "bearish" and decision.signal not in bearish:
                continue
            opportunity = (
                0.0
                if decision.signal == Signal.HOLD
                else round(abs(decision.score) * decision.confidence / 100, 4)
            )
            candidates.append((opportunity, decision, self.risk_manager.plan(decision)))

        candidates.sort(key=lambda item: (item[0], abs(item[1].score)), reverse=True)
        if limit is not None:
            candidates = candidates[:limit]
        items = tuple(
            ScanItem(rank=index, opportunity_score=score, decision=decision, risk_plan=risk_plan)
            for index, (score, decision, risk_plan) in enumerate(candidates, start=1)
        )
        return ScanResult(
            generated_at=datetime.now(timezone.utc),
            total_markets=len(series),
            matched_markets=len(items),
            items=items,
        )
