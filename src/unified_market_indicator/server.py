from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any

from .backtest import Backtester
from .engine import UnifiedIndicatorEngine
from .models import AssetClass, Candle
from .risk import RiskManager
from .scanner import MarketScanner, MarketSeries


def _candles(payload: dict[str, Any]) -> list[Candle]:
    return [Candle.from_mapping(row) for row in payload["candles"]]


def _decision_object(payload: dict[str, Any]):
    return UnifiedIndicatorEngine().analyze(
        payload["symbol"],
        AssetClass(payload["asset_class"]),
        _candles(payload),
    )


def _decision(payload: dict[str, Any]) -> dict[str, Any]:
    return _decision_object(payload).as_dict()


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


def _backtest(payload: dict[str, Any]) -> dict[str, Any]:
    result = Backtester(
        initial_capital=float(payload.get("initial_capital", 10_000)),
        fee_bps=float(payload.get("fee_bps", 10)),
        slippage_bps=float(payload.get("slippage_bps", 5)),
        risk_per_trade_pct=float(payload.get("risk_per_trade_pct", 1)),
        max_allocation_pct=float(payload.get("max_allocation_pct", 25)),
        atr_stop_multiple=float(payload.get("atr_stop_multiple", 2)),
        reward_risk_ratio=float(payload.get("reward_risk_ratio", 2)),
    ).run(payload["symbol"], AssetClass(payload["asset_class"]), _candles(payload))
    return result.as_dict()


class IndicatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "UnifiedMarketIndicator/0.2"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "version": "0.2.0"})
        elif self.path == "/":
            self._send_asset("index.html", "text/html; charset=utf-8")
        elif self.path == "/assets/styles.css":
            self._send_asset("styles.css", "text/css; charset=utf-8")
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
                "/risk-plan": _risk_plan,
                "/scan": _scan,
                "/backtest": _backtest,
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
