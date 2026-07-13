from __future__ import annotations

from .models import RiskPlan, Signal, SignalDecision


class RiskManager:
    """Build an ATR-based trade plan without placing an order."""

    def __init__(
        self,
        *,
        account_equity: float = 10_000.0,
        risk_pct: float = 1.0,
        atr_stop_multiple: float = 2.0,
        reward_risk_ratio: float = 2.0,
        max_allocation_pct: float = 25.0,
    ) -> None:
        if account_equity <= 0:
            raise ValueError("account_equity must be positive")
        if not 0 < risk_pct <= 100:
            raise ValueError("risk_pct must be between 0 and 100")
        if atr_stop_multiple <= 0 or reward_risk_ratio <= 0:
            raise ValueError("ATR and reward multiples must be positive")
        if not 0 < max_allocation_pct <= 100:
            raise ValueError("max_allocation_pct must be between 0 and 100")
        self.account_equity = account_equity
        self.risk_pct = risk_pct
        self.atr_stop_multiple = atr_stop_multiple
        self.reward_risk_ratio = reward_risk_ratio
        self.max_allocation_pct = max_allocation_pct

    def plan(self, decision: SignalDecision) -> RiskPlan:
        entry = decision.snapshot.close
        atr = decision.snapshot.atr
        warnings: list[str] = []
        if decision.signal in {Signal.BUY, Signal.STRONG_BUY}:
            direction = "LONG"
        elif decision.signal in {Signal.SELL, Signal.STRONG_SELL}:
            direction = "SHORT"
        else:
            direction = "FLAT"

        if direction == "FLAT":
            return RiskPlan(
                symbol=decision.symbol,
                asset_class=decision.asset_class,
                direction=direction,
                entry_price=round(entry, 8),
                stop_loss=None,
                take_profit=None,
                position_size=0.0,
                position_value=0.0,
                risk_amount=0.0,
                risk_per_unit=0.0,
                reward_risk_ratio=self.reward_risk_ratio,
                account_risk_pct=self.risk_pct,
                allocation_pct=0.0,
                warnings=("HOLD signal: no position is recommended",),
            )

        if atr is None or atr <= 0:
            atr = entry * 0.02
            warnings.append("ATR unavailable; a 2% price fallback was used")
        risk_per_unit = atr * self.atr_stop_multiple
        if direction == "LONG":
            stop = max(0.0, entry - risk_per_unit)
            target = entry + risk_per_unit * self.reward_risk_ratio
            risk_per_unit = entry - stop
        else:
            stop = entry + risk_per_unit
            target = max(0.0, entry - risk_per_unit * self.reward_risk_ratio)

        risk_budget = self.account_equity * self.risk_pct / 100
        max_position_value = self.account_equity * self.max_allocation_pct / 100
        risk_quantity = risk_budget / risk_per_unit if risk_per_unit else 0.0
        allocation_quantity = max_position_value / entry if entry else 0.0
        quantity = min(risk_quantity, allocation_quantity)
        position_value = quantity * entry
        actual_risk = quantity * risk_per_unit
        allocation_pct = position_value / self.account_equity * 100
        if allocation_quantity < risk_quantity:
            warnings.append("Position size was capped by the maximum allocation limit")
        if decision.confidence < 50:
            warnings.append("Signal confidence is below 50")

        return RiskPlan(
            symbol=decision.symbol,
            asset_class=decision.asset_class,
            direction=direction,
            entry_price=round(entry, 8),
            stop_loss=round(stop, 8),
            take_profit=round(target, 8),
            position_size=round(quantity, 8),
            position_value=round(position_value, 4),
            risk_amount=round(actual_risk, 4),
            risk_per_unit=round(risk_per_unit, 8),
            reward_risk_ratio=self.reward_risk_ratio,
            account_risk_pct=self.risk_pct,
            allocation_pct=round(allocation_pct, 4),
            warnings=tuple(warnings),
        )
