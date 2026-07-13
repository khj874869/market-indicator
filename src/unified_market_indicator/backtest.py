from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import mean, median, pstdev

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
        risk_per_trade_pct: float = 1.0,
        max_allocation_pct: float = 25.0,
        atr_stop_multiple: float = 2.0,
        reward_risk_ratio: float = 2.0,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if fee_bps < 0 or slippage_bps < 0:
            raise ValueError("costs cannot be negative")
        if not 0 < risk_per_trade_pct <= 100:
            raise ValueError("risk_per_trade_pct must be between 0 and 100")
        if not 0 < max_allocation_pct <= 100:
            raise ValueError("max_allocation_pct must be between 0 and 100")
        if atr_stop_multiple <= 0 or reward_risk_ratio <= 0:
            raise ValueError("ATR and reward multiples must be positive")
        self.engine = engine or UnifiedIndicatorEngine()
        self.initial_capital = initial_capital
        self.fee_rate = fee_bps / 10_000
        self.slippage_rate = slippage_bps / 10_000
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_allocation_pct = max_allocation_pct
        self.atr_stop_multiple = atr_stop_multiple
        self.reward_risk_ratio = reward_risk_ratio

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
        entry_price = 0.0
        stop_price = 0.0
        target_price = 0.0
        wins = losses = trades = 0
        stop_exits = target_exits = exposure_bars = 0
        peak = self.initial_capital
        max_drawdown = 0.0
        trade_returns: list[float] = []
        trade_profits: list[float] = []
        equity_curve: list[dict[str, object]] = []

        for index in range(self.engine.minimum_candles, len(ordered)):
            history = ordered[: index + 1]
            candle = history[-1]
            decision = self.engine.analyze(symbol, asset_class, history)
            exit_reason: str | None = None

            if quantity > 0:
                if candle.low <= stop_price:
                    fill_price = stop_price * (1 - self.slippage_rate)
                    exit_reason = "stop_loss"
                    stop_exits += 1
                elif candle.high >= target_price:
                    fill_price = target_price * (1 - self.slippage_rate)
                    exit_reason = "take_profit"
                    target_exits += 1
                elif decision.signal in {Signal.SELL, Signal.STRONG_SELL}:
                    fill_price = candle.close * (1 - self.slippage_rate)
                    exit_reason = "signal"
                else:
                    fill_price = 0.0
                if exit_reason:
                    gross = quantity * fill_price
                    proceeds = gross * (1 - self.fee_rate)
                    profit = proceeds - entry_cost
                    cash += proceeds
                    trade_return = profit / entry_cost if entry_cost else 0.0
                    trade_returns.append(trade_return)
                    trade_profits.append(profit)
                    if profit > 0:
                        wins += 1
                    else:
                        losses += 1
                    quantity = entry_cost = entry_price = stop_price = target_price = 0.0

            if quantity == 0 and exit_reason is None and decision.signal in {Signal.BUY, Signal.STRONG_BUY}:
                fill_price = candle.close * (1 + self.slippage_rate)
                atr = decision.snapshot.atr or fill_price * 0.02
                risk_per_unit = max(atr * self.atr_stop_multiple, fill_price * 0.001)
                equity = cash
                risk_budget = equity * self.risk_per_trade_pct / 100
                allocation_budget = equity * self.max_allocation_pct / 100
                risk_quantity = risk_budget / risk_per_unit
                allocation_quantity = allocation_budget / fill_price
                affordable_quantity = cash / (fill_price * (1 + self.fee_rate))
                quantity = min(risk_quantity, allocation_quantity, affordable_quantity)
                if quantity > 0:
                    cost = quantity * fill_price
                    entry_fee = cost * self.fee_rate
                    entry_cost = cost + entry_fee
                    cash -= entry_cost
                    entry_price = fill_price
                    stop_price = max(0.0, fill_price - risk_per_unit)
                    target_price = fill_price + risk_per_unit * self.reward_risk_ratio
                    trades += 1

            if quantity > 0:
                exposure_bars += 1
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
                    "position": round(quantity, 8),
                    "stop_loss": round(stop_price, 8) if quantity else None,
                    "take_profit": round(target_price, 8) if quantity else None,
                    "exit_reason": exit_reason,
                }
            )

        if quantity > 0:
            final_candle = ordered[-1]
            fill_price = final_candle.close * (1 - self.slippage_rate)
            proceeds = quantity * fill_price * (1 - self.fee_rate)
            profit = proceeds - entry_cost
            cash += proceeds
            trade_returns.append(profit / entry_cost if entry_cost else 0.0)
            trade_profits.append(profit)
            if profit > 0:
                wins += 1
            else:
                losses += 1
            if equity_curve:
                equity_curve[-1]["equity"] = round(cash, 4)
                equity_curve[-1]["position"] = 0.0
                equity_curve[-1]["exit_reason"] = "end_of_data"

        total_return = (cash / self.initial_capital - 1) * 100
        start_candle = ordered[self.engine.minimum_candles]
        benchmark = (
            ordered[-1].close * (1 - self.fee_rate - self.slippage_rate)
            / (start_candle.close * (1 + self.slippage_rate))
            - 1
        ) * 100
        annualized = self._annualized_return(cash, start_candle, ordered[-1])
        sharpe = self._sharpe_ratio(equity_curve, ordered, asset_class)
        gross_profit = sum(value for value in trade_profits if value > 0)
        gross_loss = abs(sum(value for value in trade_profits if value < 0))
        profit_factor = round(gross_profit / gross_loss, 4) if gross_loss else None
        completed_trades = wins + losses
        return BacktestResult(
            symbol=symbol.upper(),
            asset_class=asset_class,
            initial_capital=self.initial_capital,
            final_equity=round(cash, 4),
            total_return_pct=round(total_return, 4),
            max_drawdown_pct=round(max_drawdown * 100, 4),
            trades=trades,
            winning_trades=wins,
            losing_trades=losses,
            win_rate_pct=round((wins / completed_trades * 100) if completed_trades else 0.0, 4),
            benchmark_return_pct=round(benchmark, 4),
            excess_return_pct=round(total_return - benchmark, 4),
            annualized_return_pct=round(annualized, 4),
            sharpe_ratio=round(sharpe, 4),
            profit_factor=profit_factor,
            average_trade_return_pct=round(mean(trade_returns) * 100, 4) if trade_returns else 0.0,
            exposure_pct=round(exposure_bars / len(equity_curve) * 100, 4) if equity_curve else 0.0,
            stop_loss_exits=stop_exits,
            take_profit_exits=target_exits,
            equity_curve=equity_curve,
        )

    def _annualized_return(self, final_equity: float, start: Candle, end: Candle) -> float:
        years = (end.timestamp - start.timestamp).total_seconds() / (365.25 * 24 * 3600)
        if years <= 0 or final_equity <= 0:
            return 0.0
        return ((final_equity / self.initial_capital) ** (1 / years) - 1) * 100

    @staticmethod
    def _sharpe_ratio(
        equity_curve: list[dict[str, object]],
        candles: Sequence[Candle],
        asset_class: AssetClass,
    ) -> float:
        equities = [float(point["equity"]) for point in equity_curve]
        returns = [current / previous - 1 for previous, current in zip(equities, equities[1:]) if previous]
        if len(returns) < 2 or pstdev(returns) == 0:
            return 0.0
        deltas = [
            (current.timestamp - previous.timestamp).total_seconds()
            for previous, current in zip(candles, candles[1:])
            if current.timestamp > previous.timestamp
        ]
        seconds = median(deltas) if deltas else 86_400
        if seconds >= 20 * 3600:
            periods_per_year = 252 if asset_class == AssetClass.STOCK else 365.25
        else:
            annual_seconds = 252 * 6.5 * 3600 if asset_class == AssetClass.STOCK else 365.25 * 24 * 3600
            periods_per_year = annual_seconds / seconds
        return mean(returns) / pstdev(returns) * math.sqrt(periods_per_year)
