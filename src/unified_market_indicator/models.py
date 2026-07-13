from __future__ import annotations

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


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        values = (self.open, self.high, self.low, self.close, self.volume)
        if any(value < 0 for value in values):
            raise ValueError("OHLCV values cannot be negative")
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
