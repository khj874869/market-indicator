# Unified Market Indicator

주식과 코인을 같은 OHLCV 모델로 분석하는 기술적 지표·복합 시그널·백테스트 엔진입니다.

하나의 지표만 맹신하지 않고 추세, 모멘텀, 변동성, 거래량을 각각 계산한 뒤 자산군별
프로필로 합산합니다. 주식과 24시간 거래되는 코인의 변동성 차이는 서로 다른 임계값으로
처리합니다.

## 주요 기능

- 공통 OHLCV 데이터 모델
- SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, OBV, 거래량 비율
- 추세·모멘텀·변동성·거래량 4개 구성 점수
- `STRONG_BUY`, `BUY`, `HOLD`, `SELL`, `STRONG_SELL` 판정
- 주식·코인별 임계값과 고변동성 감점
- 수수료·슬리피지·MDD·승률을 포함한 롱 전용 백테스트
- Yahoo Finance, Binance, Upbit 공개 시세 어댑터
- CSV/JSON CLI 및 의존성 없는 JSON HTTP API
- Python 3.11–3.13 CI, Docker 이미지 검증

## 빠른 시작

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/generate_sample.py

unified-indicator analyze \
  --symbol AAPL \
  --asset-class stock \
  --input examples/sample_ohlcv.csv
```

Windows PowerShell에서는 가상환경 활성화 명령만 다음처럼 바꿉니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

## 공개 시장 데이터 가져오기

```bash
# 미국/한국 주식 및 ETF
unified-indicator fetch --provider yahoo --symbol AAPL --interval 1d --limit 300 --output data/aapl.csv
unified-indicator fetch --provider yahoo --symbol 005930.KS --interval 1d --limit 300 --output data/samsung.csv

# Binance
unified-indicator fetch --provider binance --symbol BTCUSDT --interval 1h --limit 300 --output data/btc.csv

# Upbit
unified-indicator fetch --provider upbit --symbol KRW-BTC --interval 60 --limit 200 --output data/upbit-btc.csv
```

공개 캔들 API만 사용하므로 기본 기능에는 API 키가 필요하지 않습니다. 향후 주문 API를
연결할 경우 키는 로컬 `.env`에만 보관해야 하며 저장소에 커밋하면 안 됩니다.

## 백테스트

```bash
unified-indicator backtest \
  --symbol BTCUSDT \
  --asset-class crypto \
  --input data/btc.csv \
  --initial-capital 10000000 \
  --fee-bps 10 \
  --slippage-bps 5
```

백테스트는 각 시점에서 그때까지 확정된 캔들만 사용해 미래 데이터 참조를 피합니다.
매수·매도 체결 가격에 슬리피지를 적용하고 거래 수수료를 차감합니다.

## HTTP API

```bash
unified-indicator serve --host 127.0.0.1 --port 8080
curl http://127.0.0.1:8080/health
```

- `POST /analyze`
- `POST /backtest`

요청 본문 예시:

```json
{
  "symbol": "BTCUSDT",
  "asset_class": "crypto",
  "candles": [
    {
      "timestamp": "2026-01-01T00:00:00+00:00",
      "open": 90000,
      "high": 91000,
      "low": 89500,
      "close": 90500,
      "volume": 1200
    }
  ]
}
```

실제 분석에는 최소 60개 캔들이 필요합니다. HTTP 본문은 최대 10 MB로 제한됩니다.

## 점수 구성

| 구성 | 핵심 입력 | 최대 방향성 |
|---|---|---:|
| Trend | SMA 20/50, EMA 12/26, MACD histogram | ±36 |
| Momentum | RSI 14, Stochastic 14/3 | ±24 |
| Volatility | Bollinger 20/2, ATR 14 | ±12 및 고변동성 감점 |
| Volume | OBV 변화, 20기간 거래량 비율 | ±14 |

최종 점수는 `-100..100` 범위로 제한됩니다. 코인은 주식보다 더 높은 매수·매도 임계값과
ATR 위험 허용치를 사용합니다.

## 개발 및 검증

```bash
make check
# 또는
python -m compileall -q src tests examples
python -m unittest discover -s tests -v
```

## 프로젝트 구조

```text
src/unified_market_indicator/
├── indicators.py        # 순수 기술지표
├── engine.py            # 통합 점수와 시그널
├── backtest.py          # 비용·MDD 포함 백테스트
├── cli.py               # analyze/fetch/backtest/serve
├── server.py            # 표준 라이브러리 HTTP API
└── providers/           # Yahoo/Binance/Upbit
```

## 안전 고지

이 프로젝트의 결과는 연구·교육·포트폴리오 목적이며 투자 권유나 자동 주문 승인이 아닙니다.
기술적 지표는 급격한 장세 변화, 유동성 부족, 거래소 장애, 상장폐지 및 뉴스 이벤트를
예측하지 못합니다. 실거래 전에 별도 리스크 한도, 포지션 크기, 손절 정책, 장기간의
아웃오브샘플 검증이 필요합니다.
