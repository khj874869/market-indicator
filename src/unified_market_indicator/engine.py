from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Sequence

from .indicators import obv, snapshot
from .models import AssetClass, Candle, Signal, SignalDecision


@dataclass(frozen=True, slots=True)
class MarketProfile:
    buy_threshold: float
    strong_buy_threshold: float
    sell_threshold: float
    strong_sell_threshold: float
    high_volume_ratio: float
    atr_risk_ratio: float


PROFILES = {
    AssetClass.STOCK: MarketProfile(22, 52, -22, -52, 1.35, 0.045),
    AssetClass.CRYPTO: MarketProfile(25, 58, -25, -58, 1.50, 0.075),
}


class UnifiedIndicatorEngine:
    minimum_candles = 60

    def analyze(
        self,
        symbol: str,
        asset_class: AssetClass,
        candles: Sequence[Candle],
    ) -> SignalDecision:
        if len(candles) < self.minimum_candles:
            raise ValueError(f"at least {self.minimum_candles} candles are required")
        ordered = sorted(candles, key=lambda candle: candle.timestamp)
        if len({candle.timestamp for candle in ordered}) != len(ordered):
            raise ValueError("candle timestamps must be unique")

        latest = snapshot(ordered)
        profile = PROFILES[asset_class]
        components: dict[str, float] = {}
        reasons: list[str] = []

        raw_trend = self._trend_score(latest, reasons)
        components["trend"] = self._adaptive_trend_score(latest, raw_trend, reasons)
        components["momentum"] = self._momentum_score(latest, reasons)
        components["volatility"] = self._volatility_score(latest, profile, reasons)
        components["volume"] = self._volume_score(ordered, latest.volume_ratio, profile, reasons)
        components["confirmation"] = self._confirmation_score(latest, reasons)

        score = max(-100.0, min(100.0, sum(components.values())))
        signal = self._signal(score, profile)
        snapshot_fields = fields(latest)
        completeness = sum(
            getattr(latest, item.name) is not None for item in snapshot_fields
        ) / len(snapshot_fields)
        total_strength = sum(abs(value) for value in components.values())
        aligned_strength = sum(abs(value) for value in components.values() if value * score > 0)
        agreement_pct = (
            100.0 * aligned_strength / total_strength
            if score != 0 and total_strength > 0
            else 0.0
        )
        disagreement_ratio = 1 - agreement_pct / 100 if total_strength > 0 else 0.0
        component_penalty = disagreement_ratio * 24
        weak_trend_penalty = 6.0 if latest.adx is not None and latest.adx < 15 else 0.0
        conflict_penalty = component_penalty + weak_trend_penalty
        confidence = max(
            0.0,
            min(
                100.0,
                abs(score) * 0.72
                + agreement_pct * 0.18
                + completeness * 14
                - conflict_penalty,
            ),
        )
        if component_penalty >= 4:
            reasons.append("Conflicting score components reduced confidence")
        return SignalDecision(
            symbol=symbol.upper(),
            asset_class=asset_class,
            signal=signal,
            score=round(score, 2),
            confidence=round(confidence, 2),
            agreement_pct=round(agreement_pct, 2),
            conflict_penalty=round(conflict_penalty, 2),
            snapshot=latest,
            components={key: round(value, 2) for key, value in components.items()},
            reasons=tuple(reasons),
        )

    def signal_for_score(self, asset_class: AssetClass, score: float) -> Signal:
        return self._signal(score, PROFILES[asset_class])

    @staticmethod
    def _trend_score(latest, reasons: list[str]) -> float:
        score = 0.0
        if latest.sma_fast is not None and latest.sma_slow is not None:
            if latest.sma_fast > latest.sma_slow:
                score += 18
                reasons.append("20-period SMA is above the 50-period SMA")
            elif latest.sma_fast < latest.sma_slow:
                score -= 18
                reasons.append("20-period SMA is below the 50-period SMA")
        if latest.ema_fast is not None and latest.ema_slow is not None:
            if latest.ema_fast > latest.ema_slow:
                score += 10
            elif latest.ema_fast < latest.ema_slow:
                score -= 10
        if latest.macd_histogram is not None:
            macd_deadband = max(1e-10, latest.close * 1e-8)
            if latest.macd_histogram > macd_deadband:
                score += 8
                reasons.append("MACD momentum is positive")
            elif latest.macd_histogram < -macd_deadband:
                score -= 8
                reasons.append("MACD momentum is negative")
        return score

    @staticmethod
    def _adaptive_trend_score(latest, score: float, reasons: list[str]) -> float:
        if latest.adx is None:
            return score
        if latest.adx < 15:
            reasons.append("Weak ADX reduced trend weight")
            return score * 0.55
        if latest.adx < 25 or score == 0:
            return score
        directional_bias = 0
        if latest.plus_di is not None and latest.minus_di is not None:
            if latest.plus_di > latest.minus_di:
                directional_bias = 1
            elif latest.plus_di < latest.minus_di:
                directional_bias = -1
        if directional_bias * score > 0:
            reasons.append("Strong ADX and directional movement reinforced the trend")
            score *= 1.15
        elif directional_bias * score < 0:
            reasons.append("ADX directional movement conflicted with moving averages")
            score *= 0.65
        return max(-42.0, min(42.0, score))

    @staticmethod
    def _momentum_score(latest, reasons: list[str]) -> float:
        score = 0.0
        if latest.rsi is not None:
            if latest.rsi <= 30:
                score += 16
                reasons.append("RSI is oversold")
            elif latest.rsi >= 70:
                score -= 16
                reasons.append("RSI is overbought")
            elif latest.rsi >= 55:
                score += 7
            elif latest.rsi <= 45:
                score -= 7
        if latest.stochastic_k is not None and latest.stochastic_d is not None:
            if latest.stochastic_k < 25 and latest.stochastic_k > latest.stochastic_d:
                score += 8
                reasons.append("Stochastic is turning up from a low region")
            elif latest.stochastic_k > 75 and latest.stochastic_k < latest.stochastic_d:
                score -= 8
                reasons.append("Stochastic is turning down from a high region")
        return score

    @staticmethod
    def _volatility_score(latest, profile: MarketProfile, reasons: list[str]) -> float:
        score = 0.0
        has_band_range = (
            latest.bollinger_lower is not None
            and latest.bollinger_upper is not None
            and latest.bollinger_upper > latest.bollinger_lower
        )
        if has_band_range:
            if latest.close <= latest.bollinger_lower:
                score += 12
                reasons.append("Price is at or below the lower Bollinger band")
            elif latest.close >= latest.bollinger_upper:
                score -= 12
                reasons.append("Price is at or above the upper Bollinger band")
        if latest.atr is not None and latest.close > 0:
            atr_ratio = latest.atr / latest.close
            if atr_ratio > profile.atr_risk_ratio:
                score *= 0.65
                reasons.append("High ATR reduced signal strength")
        return score

    @staticmethod
    def _volume_score(
        candles: Sequence[Candle],
        volume_ratio: float | None,
        profile: MarketProfile,
        reasons: list[str],
    ) -> float:
        score = 0.0
        obv_values = obv(candles)
        if len(obv_values) >= 10:
            delta = obv_values[-1] - obv_values[-10]
            score += 7 if delta > 0 else -7 if delta < 0 else 0
        if volume_ratio is not None and volume_ratio >= profile.high_volume_ratio:
            price_direction = candles[-1].close - candles[-2].close
            score += 7 if price_direction > 0 else -7 if price_direction < 0 else 0
            reasons.append("Current volume is materially above its 20-period average")
        return score

    @staticmethod
    def _confirmation_score(latest, reasons: list[str]) -> float:
        votes: list[int] = []
        if (
            latest.adx is not None
            and latest.adx >= 20
            and latest.plus_di is not None
            and latest.minus_di is not None
        ):
            if latest.plus_di > latest.minus_di:
                votes.append(1)
            elif latest.plus_di < latest.minus_di:
                votes.append(-1)
            else:
                votes.append(0)
        if latest.mfi is not None:
            votes.append(1 if latest.mfi > 55 else -1 if latest.mfi < 45 else 0)
        if latest.roc is not None:
            votes.append(1 if latest.roc > 0.1 else -1 if latest.roc < -0.1 else 0)
        if latest.vwap is not None and latest.vwap > 0:
            distance = (latest.close / latest.vwap - 1) * 100
            votes.append(1 if distance > 0.1 else -1 if distance < -0.1 else 0)

        net_votes = sum(votes)
        if net_votes >= 2:
            reasons.append(f"{net_votes} adaptive indicators confirmed bullish conditions")
        elif net_votes <= -2:
            reasons.append(f"{abs(net_votes)} adaptive indicators confirmed bearish conditions")
        return max(-12.0, min(12.0, net_votes * 3.0))

    @staticmethod
    def _signal(score: float, profile: MarketProfile) -> Signal:
        if score >= profile.strong_buy_threshold:
            return Signal.STRONG_BUY
        if score >= profile.buy_threshold:
            return Signal.BUY
        if score <= profile.strong_sell_threshold:
            return Signal.STRONG_SELL
        if score <= profile.sell_threshold:
            return Signal.SELL
        return Signal.HOLD
