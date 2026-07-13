from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .backtest import Backtester
from .engine import UnifiedIndicatorEngine
from .models import AssetClass, Candle


def _decision(payload: dict[str, Any]) -> dict[str, Any]:
    candles = [Candle.from_mapping(row) for row in payload["candles"]]
    decision = UnifiedIndicatorEngine().analyze(
        payload["symbol"],
        AssetClass(payload["asset_class"]),
        candles,
    )
    return decision.as_dict()


def _backtest(payload: dict[str, Any]) -> dict[str, Any]:
    candles = [Candle.from_mapping(row) for row in payload["candles"]]
    result = Backtester(
        initial_capital=float(payload.get("initial_capital", 10_000)),
        fee_bps=float(payload.get("fee_bps", 10)),
        slippage_bps=float(payload.get("slippage_bps", 5)),
    ).run(payload["symbol"], AssetClass(payload["asset_class"]), candles)
    return result.as_dict()


class IndicatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "UnifiedMarketIndicator/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(HTTPStatus.OK, {"status": "ok"})
        else:
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 10_000_000:
                raise ValueError("request body must be between 1 byte and 10 MB")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/analyze":
                response = _decision(payload)
            elif self.path == "/backtest":
                response = _backtest(payload)
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            self._send(HTTPStatus.OK, response)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal server error"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
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
