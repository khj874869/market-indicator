from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any

from .backtest import Backtester
from .engine import UnifiedIndicatorEngine
from .models import AssetClass, BacktestResult, Candle, SignalDecision
from .portfolio import PortfolioAllocator
from .quality import DataQualityAnalyzer
from .regime import MarketRegimeDetector
from .risk import RiskManager
from .scanner import MarketScanner, MarketSeries
from .timeframe import MultiTimeframeAnalyzer
from .validation import MonteCarloStressTester, WalkForwardValidator


def _candles(payload: dict[str, Any]) -> list[Candle]:
    return [Candle.from_mapping(row) for row in payload["candles"]]


def _decision_object(payload: dict[str, Any]) -> SignalDecision:
    return UnifiedIndicatorEngine().analyze(
        payload["symbol"],
        AssetClass(payload["asset_class"]),
        _candles(payload),
    )


def _decision(payload: dict[str, Any]) -> dict[str, Any]:
    return _decision_object(payload).as_dict()


def _quality(payload: dict[str, Any]) -> dict[str, Any]:
    return DataQualityAnalyzer().analyze(
        _candles(payload), AssetClass(payload["asset_class"])
    ).as_dict()


def _regime(payload: dict[str, Any]) -> dict[str, Any]:
    return MarketRegimeDetector().detect(
        _candles(payload), AssetClass(payload["asset_class"])
    ).as_dict()


def _multi_timeframe(payload: dict[str, Any]) -> dict[str, Any]:
    raw_timeframes = payload.get("timeframes", ["1h", "4h", "1d"])
    timeframes = (
        [item.strip() for item in raw_timeframes.split(",") if item.strip()]
        if isinstance(raw_timeframes, str)
        else [str(item) for item in raw_timeframes]
    )
    return MultiTimeframeAnalyzer().analyze(
        payload["symbol"],
        AssetClass(payload["asset_class"]),
        _candles(payload),
        timeframes,
    ).as_dict()


def _risk_plan(payload: dict[str, Any]) -> dict[str, Any]:
    result = RiskManager(
        account_equity=float(payload.get("account_equity", 10_000)),
        risk_pct=float(payload.get("risk_pct", 1)),
        atr_stop_multiple=float(payload.get("atr_stop_multiple", 2)),
        reward_risk_ratio=float(payload.get("reward_risk_ratio", 2)),
        max_allocation_pct=float(payload.get("max_allocation_pct", 25)),
    ).plan(_decision_object(payload))
    return result.as_dict()


def _scan(payload: dict[str, Any]) -> dict[str, Any]:
    markets = [
        MarketSeries(
            symbol=item["symbol"],
            asset_class=AssetClass(item["asset_class"]),
            candles=_candles(item),
        )
        for item in payload["markets"]
    ]
    risk_manager = RiskManager(
        account_equity=float(payload.get("account_equity", 10_000)),
        risk_pct=float(payload.get("risk_pct", 1)),
        max_allocation_pct=float(payload.get("max_allocation_pct", 25)),
    )
    result = MarketScanner(risk_manager=risk_manager).scan(
        markets,
        direction=str(payload.get("direction", "all")),
        min_confidence=float(payload.get("min_confidence", 0)),
        limit=int(payload["limit"]) if payload.get("limit") is not None else None,
    )
    return result.as_dict()


def _portfolio(payload: dict[str, Any]) -> dict[str, Any]:
    markets = [
        MarketSeries(
            symbol=item["symbol"],
            asset_class=AssetClass(item["asset_class"]),
            candles=_candles(item),
        )
        for item in payload["markets"]
    ]
    return PortfolioAllocator().allocate(
        markets,
        account_equity=float(payload.get("account_equity", 10_000)),
        total_allocation_pct=float(payload.get("total_allocation_pct", 80)),
        max_asset_pct=float(payload.get("max_asset_pct", 25)),
        lookback=int(payload.get("lookback", 60)),
    ).as_dict()


def _backtest_object(payload: dict[str, Any]) -> BacktestResult:
    return Backtester(
        initial_capital=float(payload.get("initial_capital", 10_000)),
        fee_bps=float(payload.get("fee_bps", 10)),
        slippage_bps=float(payload.get("slippage_bps", 5)),
        risk_per_trade_pct=float(payload.get("risk_per_trade_pct", 1)),
        max_allocation_pct=float(payload.get("max_allocation_pct", 25)),
        atr_stop_multiple=float(payload.get("atr_stop_multiple", 2)),
        reward_risk_ratio=float(payload.get("reward_risk_ratio", 2)),
    ).run(payload["symbol"], AssetClass(payload["asset_class"]), _candles(payload))


def _backtest(payload: dict[str, Any]) -> dict[str, Any]:
    return _backtest_object(payload).as_dict()


def _walk_forward(payload: dict[str, Any]) -> dict[str, Any]:
    return WalkForwardValidator(
        initial_capital=float(payload.get("initial_capital", 10_000)),
        fee_bps=float(payload.get("fee_bps", 10)),
        slippage_bps=float(payload.get("slippage_bps", 5)),
        risk_per_trade_pct=float(payload.get("risk_per_trade_pct", 1)),
        max_allocation_pct=float(payload.get("max_allocation_pct", 25)),
        atr_stop_multiple=float(payload.get("atr_stop_multiple", 2)),
        reward_risk_ratio=float(payload.get("reward_risk_ratio", 2)),
    ).run(
        payload["symbol"],
        AssetClass(payload["asset_class"]),
        _candles(payload),
        test_size=int(payload.get("test_size", 60)),
    ).as_dict()


def _stress(payload: dict[str, Any]) -> dict[str, Any]:
    return MonteCarloStressTester().run(
        _backtest_object(payload),
        paths=int(payload.get("paths", 1_000)),
        horizon=int(payload["horizon"]) if payload.get("horizon") is not None else None,
        block_size=int(payload.get("block_size", 5)),
        seed=int(payload.get("seed", 42)),
    ).as_dict()


class IndicatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "UnifiedMarketIndicator/0.4"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "version": "0.4.0"})
        elif self.path == "/":
            self._send_asset("index.html", "text/html; charset=utf-8")
        elif self.path == "/assets/styles.css":
            self._send_asset("styles.css", "text/css; charset=utf-8")
        elif self.path == "/assets/context.css":
            self._send_asset("context.css", "text/css; charset=utf-8")
        elif self.path == "/assets/robustness.css":
            self._send_asset("robustness.css", "text/css; charset=utf-8")
        elif self.path == "/assets/app.js":
            self._send_asset("app.js", "text/javascript; charset=utf-8")
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 10_000_000:
                raise ValueError("request body must be between 1 byte and 10 MB")
            payload = json.loads(self.rfile.read(length))
            handlers = {
                "/analyze": _decision,
                "/quality": _quality,
                "/regime": _regime,
                "/multi-timeframe": _multi_timeframe,
                "/risk-plan": _risk_plan,
                "/scan": _scan,
                "/portfolio": _portfolio,
                "/backtest": _backtest,
                "/walk-forward": _walk_forward,
                "/stress": _stress,
            }
            handler = handlers.get(self.path)
            if handler is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            self._send_json(HTTPStatus.OK, handler(payload))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal server error"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_asset(self, name: str, content_type: str) -> None:
        body = files("unified_market_indicator.static").joinpath(name).read_bytes()
        self._send_bytes(HTTPStatus.OK, body, content_type)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
        )
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), IndicatorRequestHandler)
    print(f"Unified Market Indicator listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
