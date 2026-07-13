from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backtest import Backtester
from .engine import UnifiedIndicatorEngine
from .io import read_candles, write_candles
from .models import AssetClass
from .providers import PROVIDERS
from .server import serve


def _asset_class(value: str) -> AssetClass:
    return AssetClass(value.lower())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unified-indicator",
        description="Unified technical indicator engine for stocks and crypto.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser("analyze", help="Analyze a local OHLCV file")
    analyze.add_argument("--symbol", required=True)
    analyze.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    analyze.add_argument("--input", type=Path, required=True)

    backtest = commands.add_parser("backtest", help="Backtest the unified signal")
    backtest.add_argument("--symbol", required=True)
    backtest.add_argument("--asset-class", type=_asset_class, choices=list(AssetClass), required=True)
    backtest.add_argument("--input", type=Path, required=True)
    backtest.add_argument("--initial-capital", type=float, default=10_000)
    backtest.add_argument("--fee-bps", type=float, default=10)
    backtest.add_argument("--slippage-bps", type=float, default=5)

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
    elif args.command == "backtest":
        result = Backtester(
            initial_capital=args.initial_capital,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
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
