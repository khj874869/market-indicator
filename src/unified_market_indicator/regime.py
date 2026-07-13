from __future__ import annotations

from collections.abc import Sequence
from statistics import pstdev

from .indicators import atr, sma
from .models import AssetClass, Candle, MarketRegime, RegimeReport


class MarketRegimeDetector:
    minimum_candles = 60

    def detect(self, candles: Sequence[Candle], asset_class: AssetClass) -> RegimeReport:
        if len(candles) < self.minimum_candles:
            raise ValueError(f"at least {self.minimum_candles} candles are required")
        ordered = sorted(candles, key=lambda candle: candle.timestamp)
        closes = [candle.close for candle in ordered]
        fast = sma(closes, 20)
        slow = sma(closes, 50)
        latest_fast = fast[-1]
        previous_fast = fast[-10]
        latest_slow = slow[-1]
        latest_close = closes[-1]
        assert latest_fast is not None and previous_fast is not None and latest_slow is not None

        trend_spread = (latest_fast - latest_slow) / latest_close * 100
        trend_slope = (latest_fast - previous_fast) / latest_close * 100
        momentum = (latest_close / closes[-20] - 1) * 100 if closes[-20] else 0.0
        atr_value = atr(ordered)[-1] or 0.0
        atr_pct = atr_value / latest_close * 100 if latest_close else 0.0
        returns = [
            current / previous - 1
            for previous, current in zip(closes[-21:], closes[-20:])
            if previous
        ]
        realized_volatility = pstdev(returns) * (len(returns) ** 0.5) * 100 if len(returns) > 1 else 0.0
        high_atr = 4.5 if asset_class == AssetClass.STOCK else 7.5
        reasons: list[str] = []

        if atr_pct >= high_atr:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = min(100.0, 55 + (atr_pct / high_atr - 1) * 45)
            reasons.append("ATR is above the asset-class volatility threshold")
        elif trend_spread > 0.5 and trend_slope > 0:
            regime = MarketRegime.BULL_TREND
            confidence = min(100.0, 50 + trend_spread * 12 + max(0.0, momentum) * 2)
            reasons.extend(("20-period average is above the 50-period average", "Short trend slope is positive"))
        elif trend_spread < -0.5 and trend_slope < 0:
            regime = MarketRegime.BEAR_TREND
            confidence = min(100.0, 50 + abs(trend_spread) * 12 + max(0.0, -momentum) * 2)
            reasons.extend(("20-period average is below the 50-period average", "Short trend slope is negative"))
        elif abs(trend_spread) <= 0.5 and abs(momentum) <= 3:
            regime = MarketRegime.RANGE_BOUND
            confidence = min(100.0, 55 + (0.5 - abs(trend_spread)) * 40 + (3 - abs(momentum)) * 4)
            reasons.append("Trend averages and 20-period momentum are compressed")
        else:
            regime = MarketRegime.TRANSITION
            confidence = min(100.0, 45 + abs(trend_spread) * 8 + abs(momentum) * 2)
            reasons.append("Trend direction and momentum are not yet aligned")

        return RegimeReport(
            regime=regime,
            confidence=round(confidence, 2),
            trend_spread_pct=round(trend_spread, 4),
            trend_slope_pct=round(trend_slope, 4),
            momentum_pct=round(momentum, 4),
            atr_pct=round(atr_pct, 4),
            realized_volatility_pct=round(realized_volatility, 4),
            reasons=tuple(reasons),
        )
