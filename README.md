# Unified Market Indicator

주식과 코인을 같은 OHLCV 모델로 분석하는 기술적 지표·복합 시그널·리스크 관리·백테스트 플랫폼입니다.

하나의 지표만 맹신하지 않고 추세, 모멘텀, 변동성, 거래량을 각각 계산한 뒤 자산군별
프로필로 합산합니다. 주식과 24시간 거래되는 코인의 변동성 차이는 서로 다른 임계값으로
처리합니다.

## 주요 기능

- 공통 OHLCV 데이터 모델
- SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, OBV, 거래량 비율
- 추세·모멘텀·변동성·거래량 4개 구성 점수
- `STRONG_BUY`, `BUY`, `HOLD`, `SELL`, `STRONG_SELL` 판정
- 주식·코인별 임계값과 고변동성 감점
- ATR 기반 손절·익절, 거래당 위험예산, 최대 배분 한도를 포함한 포지션 계획
- 여러 주식·코인을 신뢰도와 신호 강도로 정렬하는 통합 스캐너
- 중복·시간 공백·순서 오류·거래량 누락·비정상 급등락 OHLCV 품질 진단
- 상승·하락·횡보·고변동·전환 시장 국면 탐지
- `15m`, `1h`, `4h`, `1d` 등 다중 시간대 가중 합의와 불일치 감점
- 수수료·슬리피지·MDD·Sharpe·Profit Factor·벤치마크 초과수익 백테스트
- Yahoo Finance, Binance, Upbit 공개 시세 어댑터
- CSV/JSON CLI, 의존성 없는 JSON HTTP API, 반응형 웹 대시보드
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

대시보드는 별도 프론트엔드 설치 없이 실행됩니다.

```bash
unified-indicator serve --host 127.0.0.1 --port 8080
# 브라우저에서 http://127.0.0.1:8080 접속
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
  --slippage-bps 5 \
  --risk-per-trade-pct 1 \
  --max-allocation-pct 25 \
  --atr-stop-multiple 2 \
  --reward-risk-ratio 2
```

백테스트는 각 시점에서 그때까지 확정된 캔들만 사용해 미래 데이터 참조를 피합니다.
매수·매도 체결 가격에 슬리피지를 적용하고 거래 수수료를 차감합니다.

추가 결과에는 Buy & Hold 벤치마크, 초과수익, 연환산 수익률, Sharpe Ratio,
Profit Factor, 평균 거래수익률, 시장 노출도와 손절·익절 횟수가 포함됩니다.

## 포지션 리스크 계획

```bash
unified-indicator risk \
  --symbol BTCUSDT \
  --asset-class crypto \
  --input data/btc.csv \
  --account-equity 10000000 \
  --risk-pct 1 \
  --max-allocation-pct 25
```

현재 ATR과 계좌 평가액을 기준으로 진입 기준가, 손절가, 목표가, 수량, 실제 위험액을
계산합니다. `HOLD`인 경우 포지션 수량은 0으로 반환됩니다.

## 데이터 품질과 시장 국면

```bash
unified-indicator quality \
  --asset-class crypto \
  --input data/btc.csv

unified-indicator regime \
  --asset-class crypto \
  --input data/btc.csv
```

품질 진단은 추정 데이터 간격, 정규성, 중복 시각, 누락 추정 봉, 0 거래량과 자산군별
비정상 가격 점프를 평가해 `A`부터 `F`까지 등급을 반환합니다. 시장 국면은 이동평균
스프레드·기울기, 20기간 모멘텀, ATR, 실현변동성으로 분류합니다.

## 다중 시간대 합의

```bash
unified-indicator multi \
  --symbol BTCUSDT \
  --asset-class crypto \
  --input data/btc.csv \
  --timeframes 1h,4h,1d
```

장기 시간대에 더 높은 가중치를 부여하고 시간대별 방향 일치율을 최종 신뢰도에 반영합니다.
상승 국면의 하락 신호, 하락 국면의 상승 신호, 고변동성 구간의 신호는 자동 감점됩니다.
리샘플링 후 60봉을 확보하지 못한 시간대는 오류 대신 제외 사유와 함께 반환됩니다.

## 다중 종목 스캔

스캔 매니페스트는 분석할 로컬 데이터 파일을 나열합니다.

```json
[
  {"symbol": "AAPL", "asset_class": "stock", "input": "sample_ohlcv.csv"},
  {"symbol": "BTCUSDT", "asset_class": "crypto", "input": "sample_ohlcv.csv"}
]
```

```bash
unified-indicator scan \
  --manifest examples/scan_manifest.json \
  --direction all \
  --min-confidence 30 \
  --limit 10
```

`opportunity_score = abs(signal score) × confidence / 100`으로 계산해 강한 양방향 기회를
우선 정렬하며 `bullish`, `bearish` 필터를 지원합니다.

## HTTP API

```bash
unified-indicator serve --host 127.0.0.1 --port 8080
curl http://127.0.0.1:8080/health
```

- `POST /analyze`
- `POST /quality`
- `POST /regime`
- `POST /multi-timeframe`
- `POST /risk-plan`
- `POST /scan`
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
├── risk.py              # ATR 포지션·손절·목표 계획
├── scanner.py           # 다중 자산 랭킹
├── quality.py           # OHLCV 무결성·시간 간격 진단
├── regime.py            # 시장 국면 분류
├── timeframe.py         # 리샘플링·다중 시간대 합의
├── cli.py               # analyze/quality/regime/multi/risk/scan 등
├── server.py            # HTTP API와 대시보드 서버
├── static/              # 의존성 없는 반응형 대시보드
└── providers/           # Yahoo/Binance/Upbit
```

## 안전 고지

이 프로젝트의 결과는 연구·교육·포트폴리오 목적이며 투자 권유나 자동 주문 승인이 아닙니다.
기술적 지표는 급격한 장세 변화, 유동성 부족, 거래소 장애, 상장폐지 및 뉴스 이벤트를
예측하지 못합니다. 실거래 전에 별도 리스크 한도, 포지션 크기, 손절 정책, 장기간의
아웃오브샘플 검증이 필요합니다.
