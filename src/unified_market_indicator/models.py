from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class AssetClass(StrEnum):
    STOCK = "stock"
    CRYPTO = "crypto"


class Signal(StrEnum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class MarketRegime(StrEnum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRANSITION = "TRANSITION"


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        prices = (self.open, self.high, self.low, self.close)
        values = (*prices, self.volume)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("OHLCV values must be finite")
        if any(value <= 0 for value in prices):
            raise ValueError("OHLC prices must be positive")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be the largest OHLC value")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be the smallest OHLC value")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Candle":
        raw_timestamp = value["timestamp"]
        if isinstance(raw_timestamp, datetime):
            timestamp = raw_timestamp
        elif isinstance(raw_timestamp, (int, float)):
            seconds = raw_timestamp / 1000 if raw_timestamp > 10_000_000_000 else raw_timestamp
            timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
        else:
            timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return cls(
            timestamp=timestamp.astimezone(timezone.utc),
            open=float(value["open"]),
            high=float(value["high"]),
            low=float(value["low"]),
            close=float(value["close"]),
            volume=float(value.get("volume", 0)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    timestamp: datetime
    close: float
    sma_fast: float | None
    sma_slow: float | None
    ema_fast: float | None
    ema_slow: float | None
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bollinger_upper: float | None
    bollinger_middle: float | None
    bollinger_lower: float | None
    atr: float | None
    stochastic_k: float | None
    stochastic_d: float | None
    obv: float | None
    volume_ratio: float | None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            result[item.name] = value.isoformat() if isinstance(value, datetime) else value
        return result


@dataclass(frozen=True, slots=True)
class SignalDecision:
    symbol: str
    asset_class: AssetClass
    signal: Signal
    score: float
    confidence: float
    snapshot: IndicatorSnapshot
    components: dict[str, float]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "signal": self.signal.value,
            "score": self.score,
            "confidence": self.confidence,
            "components": self.components,
            "reasons": list(self.reasons),
            "snapshot": self.snapshot.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class RiskPlan:
    symbol: str
    asset_class: AssetClass
    direction: str
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    position_size: float
    position_value: float
    risk_amount: float
    risk_per_unit: float
    reward_risk_ratio: float
    account_risk_pct: float
    allocation_pct: float
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "position_value": self.position_value,
            "risk_amount": self.risk_amount,
            "risk_per_unit": self.risk_per_unit,
            "reward_risk_ratio": self.reward_risk_ratio,
            "account_risk_pct": self.account_risk_pct,
            "allocation_pct": self.allocation_pct,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ScanItem:
    rank: int
    opportunity_score: float
    decision: SignalDecision
    risk_plan: RiskPlan

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "opportunity_score": self.opportunity_score,
            "decision": self.decision.as_dict(),
            "risk_plan": self.risk_plan.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ScanResult:
    generated_at: datetime
    total_markets: int
    matched_markets: int
    items: tuple[ScanItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_markets": self.total_markets,
            "matched_markets": self.matched_markets,
            "items": [item.as_dict() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    candle_count: int
    start: datetime | None
    end: datetime | None
    inferred_interval_seconds: float | None
    duplicate_timestamps: int
    out_of_order_records: int
    gap_events: int
    missing_candles_estimate: int
    max_gap_multiple: float
    zero_volume_records: int
    suspicious_price_jumps: int
    interval_regularity_pct: float
    quality_score: float
    grade: str
    issues: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "candle_count": self.candle_count,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "inferred_interval_seconds": self.inferred_interval_seconds,
            "duplicate_timestamps": self.duplicate_timestamps,
            "out_of_order_records": self.out_of_order_records,
            "gap_events": self.gap_events,
            "missing_candles_estimate": self.missing_candles_estimate,
            "max_gap_multiple": self.max_gap_multiple,
            "zero_volume_records": self.zero_volume_records,
            "suspicious_price_jumps": self.suspicious_price_jumps,
            "interval_regularity_pct": self.interval_regularity_pct,
            "quality_score": self.quality_score,
            "grade": self.grade,
            "issues": list(self.issues),
        }


@dataclass(frozen=True, slots=True)
class RegimeReport:
    regime: MarketRegime
    confidence: float
    trend_spread_pct: float
    trend_slope_pct: float
    momentum_pct: float
    atr_pct: float
    realized_volatility_pct: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "trend_spread_pct": self.trend_spread_pct,
            "trend_slope_pct": self.trend_slope_pct,
            "momentum_pct": self.momentum_pct,
            "atr_pct": self.atr_pct,
            "realized_volatility_pct": self.realized_volatility_pct,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class TimeframeAnalysisItem:
    timeframe: str
    candle_count: int
    weight: float
    decision: SignalDecision

    def as_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "candle_count": self.candle_count,
            "weight": self.weight,
            "decision": self.decision.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class MultiTimeframeResult:
    symbol: str
    asset_class: AssetClass
    consensus_signal: Signal
    consensus_score: float
    confidence: float
    agreement_pct: float
    regime: RegimeReport
    quality: DataQualityReport
    timeframes: tuple[TimeframeAnalysisItem, ...]
    skipped_timeframes: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "consensus_signal": self.consensus_signal.value,
            "consensus_score": self.consensus_score,
            "confidence": self.confidence,
            "agreement_pct": self.agreement_pct,
            "regime": self.regime.as_dict(),
            "quality": self.quality.as_dict(),
            "timeframes": [item.as_dict() for item in self.timeframes],
            "skipped_timeframes": self.skipped_timeframes,
        }


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold: int
    start: datetime
    end: datetime
    test_candles: int
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trades: int
    positive: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "fold": self.fold,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "test_candles": self.test_candles,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "trades": self.trades,
            "positive": self.positive,
        }


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    symbol: str
    asset_class: AssetClass
    fold_count: int
    positive_folds: int
    total_trades: int
    average_trades_per_fold: float
    consistency_pct: float
    average_return_pct: float
    worst_return_pct: float
    average_sharpe_ratio: float
    worst_drawdown_pct: float
    robustness_score: float
    rating: str
    folds: tuple[WalkForwardFold, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "fold_count": self.fold_count,
            "positive_folds": self.positive_folds,
            "total_trades": self.total_trades,
            "average_trades_per_fold": self.average_trades_per_fold,
            "consistency_pct": self.consistency_pct,
            "average_return_pct": self.average_return_pct,
            "worst_return_pct": self.worst_return_pct,
            "average_sharpe_ratio": self.average_sharpe_ratio,
            "worst_drawdown_pct": self.worst_drawdown_pct,
            "robustness_score": self.robustness_score,
            "rating": self.rating,
            "folds": [fold.as_dict() for fold in self.folds],
        }


@dataclass(frozen=True, slots=True)
class StressTestResult:
    baseline_return_pct: float
    paths: int
    horizon: int
    block_size: int
    seed: int
    median_return_pct: float
    p05_return_pct: float
    p95_return_pct: float
    expected_shortfall_pct: float
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float
    probability_of_loss_pct: float
    probability_of_50pct_ruin_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_return_pct": self.baseline_return_pct,
            "paths": self.paths,
            "horizon": self.horizon,
            "block_size": self.block_size,
            "seed": self.seed,
            "median_return_pct": self.median_return_pct,
            "p05_return_pct": self.p05_return_pct,
            "p95_return_pct": self.p95_return_pct,
            "expected_shortfall_pct": self.expected_shortfall_pct,
            "median_max_drawdown_pct": self.median_max_drawdown_pct,
            "p95_max_drawdown_pct": self.p95_max_drawdown_pct,
            "probability_of_loss_pct": self.probability_of_loss_pct,
            "probability_of_50pct_ruin_pct": self.probability_of_50pct_ruin_pct,
        }


@dataclass(frozen=True, slots=True)
class PortfolioAllocation:
    symbol: str
    asset_class: AssetClass
    signal: Signal
    score: float
    confidence: float
    volatility_pct: float
    correlation_penalty: float
    weight_pct: float
    allocation_amount: float
    risk_contribution_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "signal": self.signal.value,
            "score": self.score,
            "confidence": self.confidence,
            "volatility_pct": self.volatility_pct,
            "correlation_penalty": self.correlation_penalty,
            "weight_pct": self.weight_pct,
            "allocation_amount": self.allocation_amount,
            "risk_contribution_pct": self.risk_contribution_pct,
        }


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    account_equity: float
    invested_pct: float
    cash_pct: float
    average_correlation: float
    diversification_score: float
    allocations: tuple[PortfolioAllocation, ...]
    rejected: dict[str, str]
    correlation_matrix: dict[str, dict[str, float]]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_equity": self.account_equity,
            "invested_pct": self.invested_pct,
            "cash_pct": self.cash_pct,
            "average_correlation": self.average_correlation,
            "diversification_score": self.diversification_score,
            "allocations": [item.as_dict() for item in self.allocations],
            "rejected": self.rejected,
            "correlation_matrix": self.correlation_matrix,
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class BacktestResult:
    symbol: str
    asset_class: AssetClass
    initial_capital: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    profit_factor: float | None
    average_trade_return_pct: float
    exposure_pct: float
    stop_loss_exits: int
    take_profit_exits: int
    equity_curve: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "trades": self.trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": self.win_rate_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "excess_return_pct": self.excess_return_pct,
            "annualized_return_pct": self.annualized_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "profit_factor": self.profit_factor,
            "average_trade_return_pct": self.average_trade_return_pct,
            "exposure_pct": self.exposure_pct,
            "stop_loss_exits": self.stop_loss_exits,
            "take_profit_exits": self.take_profit_exits,
            "equity_curve": self.equity_curve,
        }
