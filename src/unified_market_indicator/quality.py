from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from .models import AssetClass, Candle, DataQualityReport


class DataQualityAnalyzer:
    def analyze(self, candles: Sequence[Candle], asset_class: AssetClass) -> DataQualityReport:
        if not candles:
            return DataQualityReport(
                candle_count=0,
                start=None,
                end=None,
                inferred_interval_seconds=None,
                duplicate_timestamps=0,
                out_of_order_records=0,
                gap_events=0,
                missing_candles_estimate=0,
                max_gap_multiple=0.0,
                zero_volume_records=0,
                suspicious_price_jumps=0,
                interval_regularity_pct=0.0,
                quality_score=0.0,
                grade="F",
                issues=("Dataset is empty",),
            )

        duplicate_count = len(candles) - len({candle.timestamp for candle in candles})
        out_of_order = sum(
            current.timestamp < previous.timestamp
            for previous, current in zip(candles, candles[1:])
        )
        ordered = sorted(candles, key=lambda candle: candle.timestamp)
        deltas = [
            (current.timestamp - previous.timestamp).total_seconds()
            for previous, current in zip(ordered, ordered[1:])
            if current.timestamp > previous.timestamp
        ]
        interval = median(deltas) if deltas else None
        gap_events = missing = 0
        max_gap_multiple = 0.0
        regular = 0
        if interval and interval > 0:
            for delta in deltas:
                multiple = delta / interval
                max_gap_multiple = max(max_gap_multiple, multiple)
                expected_stock_closure = asset_class == AssetClass.STOCK and (
                    (interval < 20 * 3_600 and 8 * 3_600 <= delta <= 4 * 86_400)
                    or (interval >= 20 * 3_600 and 1.5 < multiple <= 4.1)
                )
                if 0.9 <= multiple <= 1.1 or expected_stock_closure:
                    regular += 1
                if multiple > 1.5 and not expected_stock_closure:
                    gap_events += 1
                    missing += max(1, round(multiple) - 1)
        regularity = regular / len(deltas) * 100 if deltas else 0.0
        zero_volume = sum(candle.volume == 0 for candle in ordered)
        jump_limit = 0.20 if asset_class == AssetClass.STOCK else 0.35
        jumps = sum(
            abs(current.close / previous.close - 1) > jump_limit
            for previous, current in zip(ordered, ordered[1:])
            if previous.close > 0
        )

        count = len(candles)
        deductions = min(35.0, duplicate_count * 12.0)
        deductions += min(20.0, out_of_order * 5.0)
        deductions += min(25.0, missing / max(count, 1) * 250)
        deductions += min(10.0, zero_volume / max(count, 1) * 100)
        deductions += min(20.0, jumps * 5.0)
        if count < 60:
            deductions += 20.0
        score = round(max(0.0, 100.0 - deductions), 2)
        grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
        issues: list[str] = []
        if duplicate_count:
            issues.append(f"{duplicate_count} duplicate timestamp(s) detected")
        if out_of_order:
            issues.append(f"{out_of_order} out-of-order record(s) detected")
        if gap_events:
            issues.append(f"{gap_events} time gap(s), approximately {missing} missing candle(s)")
        if zero_volume:
            issues.append(f"{zero_volume} zero-volume candle(s) detected")
        if jumps:
            issues.append(f"{jumps} suspicious close-to-close jump(s) detected")
        if count < 60:
            issues.append("Fewer than 60 candles; signal analysis is unavailable")
        if not issues:
            issues.append("No material OHLCV quality issue detected")

        return DataQualityReport(
            candle_count=count,
            start=ordered[0].timestamp,
            end=ordered[-1].timestamp,
            inferred_interval_seconds=round(interval, 4) if interval else None,
            duplicate_timestamps=duplicate_count,
            out_of_order_records=out_of_order,
            gap_events=gap_events,
            missing_candles_estimate=missing,
            max_gap_multiple=round(max_gap_multiple, 4),
            zero_volume_records=zero_volume,
            suspicious_price_jumps=jumps,
            interval_regularity_pct=round(regularity, 2),
            quality_score=score,
            grade=grade,
            issues=tuple(issues),
        )
