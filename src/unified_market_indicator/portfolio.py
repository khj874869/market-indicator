from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from statistics import mean, pstdev

from .engine import UnifiedIndicatorEngine
from .models import PortfolioAllocation, PortfolioResult, Signal, SignalDecision
from .scanner import MarketSeries


class PortfolioAllocator:
    def __init__(self, engine: UnifiedIndicatorEngine | None = None) -> None:
        self.engine = engine or UnifiedIndicatorEngine()

    def allocate(
        self,
        markets: Sequence[MarketSeries],
        *,
        account_equity: float = 10_000.0,
        total_allocation_pct: float = 80.0,
        max_asset_pct: float = 25.0,
        lookback: int = 60,
    ) -> PortfolioResult:
        if account_equity <= 0:
            raise ValueError("account_equity must be positive")
        if not 0 < total_allocation_pct <= 100:
            raise ValueError("total_allocation_pct must be between 0 and 100")
        if not 0 < max_asset_pct <= 100:
            raise ValueError("max_asset_pct must be between 0 and 100")
        if lookback < 20:
            raise ValueError("lookback must be at least 20")
        symbols = [market.symbol.upper() for market in markets]
        if len(symbols) != len(set(symbols)):
            raise ValueError("market symbols must be unique")

        rejected: dict[str, str] = {}
        warnings: list[str] = []
        candidates: dict[
            str, tuple[MarketSeries, SignalDecision, dict[datetime, float], float]
        ] = {}
        bullish = {Signal.BUY, Signal.STRONG_BUY}
        for market in markets:
            symbol = market.symbol.upper()
            decision = self.engine.analyze(symbol, market.asset_class, market.candles)
            if decision.signal not in bullish:
                rejected[symbol] = f"Signal is {decision.signal.value}, not BUY or STRONG_BUY"
                continue
            returns = _returns_by_timestamp(market, lookback)
            if len(returns) < 20:
                rejected[symbol] = "Fewer than 20 usable returns"
                continue
            volatility = pstdev(returns.values()) * 100
            candidates[symbol] = (market, decision, returns, volatility)

        matrix: dict[str, dict[str, float]] = {symbol: {} for symbol in candidates}
        pair_values: list[float] = []
        candidate_symbols = list(candidates)
        for left in candidate_symbols:
            for right in candidate_symbols:
                if left == right:
                    correlation = 1.0
                elif right in matrix and left in matrix[right]:
                    correlation = matrix[right][left]
                else:
                    left_returns = candidates[left][2]
                    right_returns = candidates[right][2]
                    shared = sorted(set(left_returns).intersection(right_returns))
                    if len(shared) < 10:
                        correlation = 0.0
                        warnings.append(
                            f"{left}/{right}: fewer than 10 aligned returns; correlation assumed zero"
                        )
                    else:
                        correlation = _correlation(
                            [left_returns[key] for key in shared],
                            [right_returns[key] for key in shared],
                        )
                        pair_values.append(correlation)
                matrix[left][right] = round(correlation, 4)

        raw_weights: dict[str, float] = {}
        penalties: dict[str, float] = {}
        for symbol, (_, decision, _, volatility) in candidates.items():
            peers = [max(0.0, matrix[symbol][peer]) for peer in candidate_symbols if peer != symbol]
            average_positive_correlation = mean(peers) if peers else 0.0
            penalty = 1 / (1 + average_positive_correlation)
            conviction = max(0.0, decision.score) * decision.confidence / 100
            raw_weights[symbol] = conviction / max(volatility, 0.01) * penalty
            penalties[symbol] = penalty
        weights = _capped_weights(raw_weights, total_allocation_pct, max_asset_pct)
        risk_units = {
            symbol: weights.get(symbol, 0.0) * candidates[symbol][3]
            for symbol in candidates
        }
        total_risk_units = sum(risk_units.values())
        allocations = tuple(
            sorted(
                (
                    PortfolioAllocation(
                        symbol=symbol,
                        asset_class=candidates[symbol][0].asset_class,
                        signal=candidates[symbol][1].signal,
                        score=candidates[symbol][1].score,
                        confidence=candidates[symbol][1].confidence,
                        volatility_pct=round(candidates[symbol][3], 4),
                        correlation_penalty=round(penalties[symbol], 4),
                        weight_pct=round(weight, 4),
                        allocation_amount=round(account_equity * weight / 100, 2),
                        risk_contribution_pct=round(
                            risk_units[symbol] / total_risk_units * 100, 4
                        )
                        if total_risk_units
                        else 0.0,
                    )
                    for symbol, weight in weights.items()
                    if weight > 0
                ),
                key=lambda item: item.weight_pct,
                reverse=True,
            )
        )
        invested = sum(item.weight_pct for item in allocations)
        average_correlation = mean(pair_values) if pair_values else 0.0
        diversification = (
            max(0.0, min(100.0, (1 - max(0.0, average_correlation)) * 100))
            if len(candidate_symbols) >= 2
            else 0.0
        )
        if not allocations:
            warnings.append("No bullish market qualified; portfolio remains in cash")
        elif invested < total_allocation_pct:
            warnings.append("Asset caps or rejected signals left part of the target allocation in cash")
        return PortfolioResult(
            account_equity=account_equity,
            invested_pct=round(invested, 4),
            cash_pct=round(100 - invested, 4),
            average_correlation=round(average_correlation, 4),
            diversification_score=round(diversification, 2),
            allocations=allocations,
            rejected=rejected,
            correlation_matrix=matrix,
            warnings=tuple(dict.fromkeys(warnings)),
        )


def _returns_by_timestamp(market: MarketSeries, lookback: int) -> dict[datetime, float]:
    ordered = sorted(market.candles, key=lambda candle: candle.timestamp)[-(lookback + 1) :]
    return {
        current.timestamp: current.close / previous.close - 1
        for previous, current in zip(ordered, ordered[1:])
        if previous.close
    }


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left)
        * sum((value - right_mean) ** 2 for value in right)
    )
    return numerator / denominator if denominator else 0.0


def _capped_weights(
    raw_weights: dict[str, float],
    total_allocation_pct: float,
    max_asset_pct: float,
) -> dict[str, float]:
    active = {symbol for symbol, value in raw_weights.items() if value > 0}
    weights: dict[str, float] = {}
    remaining = total_allocation_pct
    while active and remaining > 0:
        raw_total = sum(raw_weights[symbol] for symbol in active)
        if raw_total <= 0:
            break
        tentative = {
            symbol: remaining * raw_weights[symbol] / raw_total for symbol in active
        }
        capped = {symbol for symbol, value in tentative.items() if value > max_asset_pct}
        if not capped:
            weights.update(tentative)
            break
        for symbol in capped:
            weights[symbol] = max_asset_pct
            remaining -= max_asset_pct
        active -= capped
    return weights
