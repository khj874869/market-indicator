from __future__ import annotations

from collections.abc import Sequence

from .engine import UnifiedIndicatorEngine
from .models import AssetClass, BacktestResult, Candle, Signal


class Backtester:
    def __init__(
        self,
        engine: UnifiedIndicatorEngine | None = None,
        *,
        initial_capital: float = 10_000.0,
        fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if fee_bps < 0 or slippage_bps < 0:
            raise ValueError("costs cannot be negative")
        self.engine = engine or UnifiedIndicatorEngine()
        self.initial_capital = initial_capital
        self.fee_rate = fee_bps / 10_000
        self.slippage_rate = slippage_bps / 10_000

    def run(
        self,
        symbol: str,
        asset_class: AssetClass,
        candles: Sequence[Candle],
    ) -> BacktestResult:
        ordered = sorted(candles, key=lambda candle: candle.timestamp)
        if len(ordered) <= self.engine.minimum_candles:
            raise ValueError("not enough candles for backtesting")

        cash = self.initial_capital
        quantity = 0.0
        entry_cost = 0.0
        wins = 0
        losses = 0
        trades = 0
        peak = self.initial_capital
        max_drawdown = 0.0
        equity_curve: list[dict[str, object]] = []

        for index in range(self.engine.minimum_candles, len(ordered)):
            history = ordered[: index + 1]
            candle = history[-1]
            decision = self.engine.analyze(symbol, asset_class, history)

            if quantity == 0 and decision.signal in {Signal.BUY, Signal.STRONG_BUY}:
                fill_price = candle.close * (1 + self.slippage_rate)
                fee = cash * self.fee_rate
                spendable = cash - fee
                quantity = spendable / fill_price
                entry_cost = cash
                cash = 0.0
                trades += 1
            elif quantity > 0 and decision.signal in {Signal.SELL, Signal.STRONG_SELL}:
                fill_price = candle.close * (1 - self.slippage_rate)
                gross = quantity * fill_price
                cash = gross * (1 - self.fee_rate)
                if cash > entry_cost:
                    wins += 1
                else:
                    losses += 1
                quantity = 0.0
                entry_cost = 0.0

            equity = cash + quantity * candle.close
            peak = max(peak, equity)
            drawdown = 0.0 if peak == 0 else (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
            equity_curve.append(
                {
                    "timestamp": candle.timestamp.isoformat(),
                    "equity": round(equity, 4),
                    "signal": decision.signal.value,
                    "score": decision.score,
                }
            )

        if quantity > 0:
            final_candle = ordered[-1]
            cash = quantity * final_candle.close * (1 - self.fee_rate - self.slippage_rate)
            if cash > entry_cost:
                wins += 1
            else:
                losses += 1

        completed_trades = wins + losses
        return BacktestResult(
            symbol=symbol.upper(),
            asset_class=asset_class,
            initial_capital=self.initial_capital,
            final_equity=round(cash, 4),
            total_return_pct=round((cash / self.initial_capital - 1) * 100, 4),
            max_drawdown_pct=round(max_drawdown * 100, 4),
            trades=trades,
            winning_trades=wins,
            losing_trades=losses,
            win_rate_pct=round((wins / completed_trades * 100) if completed_trades else 0.0, 4),
            equity_curve=equity_curve,
        )
