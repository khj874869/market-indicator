from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backtest import Backtester
from .engine import UnifiedIndicatorEngine
from .io import read_candles, write_candles
from .models import AssetClass
from .portfolio import PortfolioAllocator
from .providers import PROVIDERS
from .quality import DataQualityAnalyzer
from .regime import MarketRegimeDetector
from .risk import RiskManager
from .scanner import MarketScanner, MarketSeries
from .server import serve
from .timeframe import MultiTimeframeAnalyzer
from .validation import MonteCarloStressTester, WalkForwardValidator


def _asset_class(value: str) -> AssetClass:
    return AssetClass(value.lower())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unified-indicator",
        description="Unified technical indicator engine for stocks and crypto.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.4.0")
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze", help="Analyze a local OHLCV file")
    analyze.add_argument("--symbol", required=True)
    analyze.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    analyze.add_argument("--input", type=Path, required=True)

    quality = commands.add_parser("quality", help="Audit OHLCV data integrity and regularity")
    quality.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    quality.add_argument("--input", type=Path, required=True)

    regime = commands.add_parser("regime", help="Classify the current market regime")
    regime.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    regime.add_argument("--input", type=Path, required=True)

    multi = commands.add_parser("multi", help="Build a multi-timeframe consensus signal")
    multi.add_argument("--symbol", required=True)
    multi.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    multi.add_argument("--input", type=Path, required=True)
    multi.add_argument("--timeframes", default="1h,4h,1d")

    walk_forward = commands.add_parser("walk-forward", help="Validate strategy consistency by time fold")
    walk_forward.add_argument("--symbol", required=True)
    walk_forward.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    walk_forward.add_argument("--input", type=Path, required=True)
    walk_forward.add_argument("--test-size", type=int, default=60)
    walk_forward.add_argument("--initial-capital", type=float, default=10_000)

    stress = commands.add_parser("stress", help="Run block-bootstrap Monte Carlo stress testing")
    stress.add_argument("--symbol", required=True)
    stress.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    stress.add_argument("--input", type=Path, required=True)
    stress.add_argument("--paths", type=int, default=1_000)
    stress.add_argument("--block-size", type=int, default=5)
    stress.add_argument("--seed", type=int, default=42)
    stress.add_argument("--initial-capital", type=float, default=10_000)

    risk = commands.add_parser("risk", help="Create an ATR-based position and exit plan")
    risk.add_argument("--symbol", required=True)
    risk.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    risk.add_argument("--input", type=Path, required=True)
    risk.add_argument("--account-equity", type=float, default=10_000)
    risk.add_argument("--risk-pct", type=float, default=1)
    risk.add_argument("--max-allocation-pct", type=float, default=25)
    risk.add_argument("--atr-stop-multiple", type=float, default=2)
    risk.add_argument("--reward-risk-ratio", type=float, default=2)

    scan = commands.add_parser("scan", help="Rank multiple local stock and crypto datasets")
    scan.add_argument("--manifest", type=Path, required=True)
    scan.add_argument("--direction", choices=["all", "bullish", "bearish"], default="all")
    scan.add_argument("--min-confidence", type=float, default=0)
    scan.add_argument("--limit", type=int)
    scan.add_argument("--account-equity", type=float, default=10_000)

    portfolio = commands.add_parser("portfolio", help="Build a capped correlation-aware allocation")
    portfolio.add_argument("--manifest", type=Path, required=True)
    portfolio.add_argument("--account-equity", type=float, default=10_000)
    portfolio.add_argument("--total-allocation-pct", type=float, default=80)
    portfolio.add_argument("--max-asset-pct", type=float, default=25)
    portfolio.add_argument("--lookback", type=int, default=60)

    backtest = commands.add_parser("backtest", help="Backtest the unified signal")
    backtest.add_argument("--symbol", required=True)
    backtest.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    backtest.add_argument("--input", type=Path, required=True)
    backtest.add_argument("--initial-capital", type=float, default=10_000)
    backtest.add_argument("--fee-bps", type=float, default=10)
    backtest.add_argument("--slippage-bps", type=float, default=5)
    backtest.add_argument("--risk-per-trade-pct", type=float, default=1)
    backtest.add_argument("--max-allocation-pct", type=float, default=25)
    backtest.add_argument("--atr-stop-multiple", type=float, default=2)
    backtest.add_argument("--reward-risk-ratio", type=float, default=2)

    fetch = commands.add_parser("fetch", help="Fetch public OHLCV market data")
    fetch.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    fetch.add_argument("--symbol", required=True)
    fetch.add_argument("--interval", default="1h")
    fetch.add_argument("--limit", type=int, default=200)
    fetch.add_argument("--output", type=Path, required=True)

    server = commands.add_parser("serve", help="Run the JSON HTTP API")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "analyze":
        result = UnifiedIndicatorEngine().analyze(
            args.symbol,
            args.asset_class,
            read_candles(args.input),
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "quality":
        result = DataQualityAnalyzer().analyze(read_candles(args.input), args.asset_class)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "regime":
        result = MarketRegimeDetector().detect(read_candles(args.input), args.asset_class)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "multi":
        timeframes = [item.strip() for item in args.timeframes.split(",") if item.strip()]
        result = MultiTimeframeAnalyzer().analyze(
            args.symbol,
            args.asset_class,
            read_candles(args.input),
            timeframes,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "walk-forward":
        result = WalkForwardValidator(initial_capital=args.initial_capital).run(
            args.symbol,
            args.asset_class,
            read_candles(args.input),
            test_size=args.test_size,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "stress":
        backtest_result = Backtester(initial_capital=args.initial_capital).run(
            args.symbol, args.asset_class, read_candles(args.input)
        )
        result = MonteCarloStressTester().run(
            backtest_result,
            paths=args.paths,
            block_size=args.block_size,
            seed=args.seed,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "risk":
        decision = UnifiedIndicatorEngine().analyze(
            args.symbol,
            args.asset_class,
            read_candles(args.input),
        )
        result = RiskManager(
            account_equity=args.account_equity,
            risk_pct=args.risk_pct,
            max_allocation_pct=args.max_allocation_pct,
            atr_stop_multiple=args.atr_stop_multiple,
            reward_risk_ratio=args.reward_risk_ratio,
        ).plan(decision)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "scan":
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        markets = [
            MarketSeries(
                symbol=item["symbol"],
                asset_class=AssetClass(item["asset_class"]),
                candles=read_candles(args.manifest.parent / item["input"]),
            )
            for item in manifest
        ]
        result = MarketScanner(
            risk_manager=RiskManager(account_equity=args.account_equity)
        ).scan(
            markets,
            direction=args.direction,
            min_confidence=args.min_confidence,
            limit=args.limit,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "portfolio":
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        markets = [
            MarketSeries(
                symbol=item["symbol"],
                asset_class=AssetClass(item["asset_class"]),
                candles=read_candles(args.manifest.parent / item["input"]),
            )
            for item in manifest
        ]
        result = PortfolioAllocator().allocate(
            markets,
            account_equity=args.account_equity,
            total_allocation_pct=args.total_allocation_pct,
            max_asset_pct=args.max_asset_pct,
            lookback=args.lookback,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "backtest":
        result = Backtester(
            initial_capital=args.initial_capital,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
            risk_per_trade_pct=args.risk_per_trade_pct,
            max_allocation_pct=args.max_allocation_pct,
            atr_stop_multiple=args.atr_stop_multiple,
            reward_risk_ratio=args.reward_risk_ratio,
        ).run(args.symbol, args.asset_class, read_candles(args.input))
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "fetch":
        provider = PROVIDERS[args.provider]()
        candles = provider.fetch(args.symbol, args.interval, args.limit)
        write_candles(args.output, candles)
        print(f"wrote {len(candles)} candles to {args.output}")
    elif args.command == "serve":
        serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
