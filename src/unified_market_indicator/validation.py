from __future__ import annotations

import math
import random
from collections.abc import Sequence
from statistics import mean

from .backtest import Backtester
from .models import (
    AssetClass,
    BacktestResult,
    Candle,
    StressTestResult,
    WalkForwardFold,
    WalkForwardResult,
)


class WalkForwardValidator:
    def __init__(
        self,
        *,
        initial_capital: float = 10_000.0,
        fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
        risk_per_trade_pct: float = 1.0,
        max_allocation_pct: float = 25.0,
        atr_stop_multiple: float = 2.0,
        reward_risk_ratio: float = 2.0,
    ) -> None:
        self.settings = {
            "initial_capital": initial_capital,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "risk_per_trade_pct": risk_per_trade_pct,
            "max_allocation_pct": max_allocation_pct,
            "atr_stop_multiple": atr_stop_multiple,
            "reward_risk_ratio": reward_risk_ratio,
        }

    def run(
        self,
        symbol: str,
        asset_class: AssetClass,
        candles: Sequence[Candle],
        *,
        test_size: int = 60,
    ) -> WalkForwardResult:
        if test_size < 20:
            raise ValueError("test_size must be at least 20 candles")
        ordered = sorted(candles, key=lambda candle: candle.timestamp)
        warmup = Backtester().engine.minimum_candles
        if len(ordered) < warmup + test_size:
            raise ValueError(f"at least {warmup + test_size} candles are required")

        folds: list[WalkForwardFold] = []
        test_start = warmup
        while test_start < len(ordered):
            test_end = min(len(ordered), test_start + test_size)
            actual_test_size = test_end - test_start
            if actual_test_size < max(20, test_size // 2):
                break
            segment = ordered[test_start - warmup : test_end]
            result = Backtester(**self.settings).run(symbol, asset_class, segment)
            folds.append(
                WalkForwardFold(
                    fold=len(folds) + 1,
                    start=ordered[test_start].timestamp,
                    end=ordered[test_end - 1].timestamp,
                    test_candles=actual_test_size,
                    total_return_pct=result.total_return_pct,
                    max_drawdown_pct=result.max_drawdown_pct,
                    sharpe_ratio=result.sharpe_ratio,
                    trades=result.trades,
                    positive=result.total_return_pct > 0,
                )
            )
            test_start = test_end

        if not folds:
            raise ValueError("no complete walk-forward fold could be created")
        returns = [fold.total_return_pct for fold in folds]
        sharpes = [fold.sharpe_ratio for fold in folds]
        positive = sum(fold.positive for fold in folds)
        total_trades = sum(fold.trades for fold in folds)
        consistency = positive / len(folds) * 100
        average_sharpe = mean(sharpes)
        worst_drawdown = max(fold.max_drawdown_pct for fold in folds)
        sharpe_score = max(0.0, min(100.0, 50 + average_sharpe * 12))
        drawdown_score = max(0.0, min(100.0, 100 - worst_drawdown * 4))
        sample_score = min(100.0, total_trades / (len(folds) * 5) * 100)
        robustness = (
            consistency * 0.30
            + sharpe_score * 0.20
            + drawdown_score * 0.20
            + sample_score * 0.30
        )
        rating = (
            "ROBUST"
            if robustness >= 80
            else "STABLE"
            if robustness >= 60
            else "FRAGILE"
            if robustness >= 40
            else "WEAK"
        )
        return WalkForwardResult(
            symbol=symbol.upper(),
            asset_class=asset_class,
            fold_count=len(folds),
            positive_folds=positive,
            total_trades=total_trades,
            average_trades_per_fold=round(total_trades / len(folds), 4),
            consistency_pct=round(consistency, 2),
            average_return_pct=round(mean(returns), 4),
            worst_return_pct=round(min(returns), 4),
            average_sharpe_ratio=round(average_sharpe, 4),
            worst_drawdown_pct=round(worst_drawdown, 4),
            robustness_score=round(robustness, 2),
            rating=rating,
            folds=tuple(folds),
        )


class MonteCarloStressTester:
    def run(
        self,
        backtest: BacktestResult,
        *,
        paths: int = 1_000,
        horizon: int | None = None,
        block_size: int = 5,
        seed: int = 42,
    ) -> StressTestResult:
        if not 100 <= paths <= 10_000:
            raise ValueError("paths must be between 100 and 10000")
        if block_size <= 0:
            raise ValueError("block_size must be positive")
        equities = [float(point["equity"]) for point in backtest.equity_curve]
        returns = [current / previous - 1 for previous, current in zip(equities, equities[1:]) if previous]
        if len(returns) < 10:
            raise ValueError("at least 11 equity points are required for stress testing")
        simulation_horizon = horizon or len(returns)
        if not 10 <= simulation_horizon <= 5_000:
            raise ValueError("horizon must be between 10 and 5000")
        effective_block = min(block_size, len(returns))
        randomizer = random.Random(seed)
        final_returns: list[float] = []
        max_drawdowns: list[float] = []
        for _ in range(paths):
            sampled: list[float] = []
            while len(sampled) < simulation_horizon:
                start = randomizer.randrange(0, len(returns) - effective_block + 1)
                sampled.extend(returns[start : start + effective_block])
            equity = peak = 1.0
            max_drawdown = 0.0
            for value in sampled[:simulation_horizon]:
                equity *= 1 + value
                peak = max(peak, equity)
                max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
            final_returns.append((equity - 1) * 100)
            max_drawdowns.append(max_drawdown * 100)
        final_returns.sort()
        max_drawdowns.sort()
        tail_count = max(1, math.ceil(paths * 0.05))
        return StressTestResult(
            baseline_return_pct=backtest.total_return_pct,
            paths=paths,
            horizon=simulation_horizon,
            block_size=effective_block,
            seed=seed,
            median_return_pct=round(_percentile(final_returns, 50), 4),
            p05_return_pct=round(_percentile(final_returns, 5), 4),
            p95_return_pct=round(_percentile(final_returns, 95), 4),
            expected_shortfall_pct=round(mean(final_returns[:tail_count]), 4),
            median_max_drawdown_pct=round(_percentile(max_drawdowns, 50), 4),
            p95_max_drawdown_pct=round(_percentile(max_drawdowns, 95), 4),
            probability_of_loss_pct=round(sum(value < 0 for value in final_returns) / paths * 100, 2),
            probability_of_50pct_ruin_pct=round(
                sum(value <= -50 for value in final_returns) / paths * 100, 2
            ),
        )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("values cannot be empty")
    position = (len(values) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction
