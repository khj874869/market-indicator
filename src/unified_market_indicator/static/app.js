const $ = (id) => document.getElementById(id);
const number = (value, digits = 2) => value == null ? "--" : Number(value).toLocaleString(undefined, {maximumFractionDigits: digits});
const percent = (value) => value == null ? "--" : `${number(value)}%`;

function sampleCandles() {
  const candles = [];
  let previous = 100;
  const start = Date.now() - 239 * 3600000;
  for (let i = 0; i < 240; i += 1) {
    const close = 100 + i * 0.12 + Math.sin(i / 6) * 2.5;
    candles.push({timestamp: new Date(start + i * 3600000).toISOString(), open: previous, high: Math.max(previous, close) + 1.2, low: Math.min(previous, close) - 1.2, close, volume: 1000 + (i % 24) * 35});
    previous = close;
  }
  $("candles").value = JSON.stringify(candles, null, 2);
  updateCount();
}

function payload() {
  const candles = JSON.parse($("candles").value || "[]");
  const timeframes = $("timeframes").value.split(",").map((value) => value.trim()).filter(Boolean);
  return {symbol: $("symbol").value.trim(), asset_class: $("asset-class").value, account_equity: Number($("equity").value), risk_pct: Number($("risk").value), timeframes, candles};
}

async function request(path, body) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function showDecision(decision, risk) {
  $("hero-score").textContent = number(decision.score, 0);
  $("signal").textContent = decision.signal.replaceAll("_", " ");
  $("signal").className = `signal ${decision.score > 0 ? "buy" : decision.score < 0 ? "sell" : "neutral"}`;
  $("confidence").textContent = `${number(decision.confidence, 0)}%`;
  $("reason").textContent = decision.reasons.slice(0, 2).join(" · ") || "중립 구간입니다.";
  $("asset-label").textContent = decision.asset_class.toUpperCase();
  const components = Object.entries(decision.components).map(([name, value]) => {
    const width = Math.min(50, Math.abs(value) / 72 * 100);
    return `<div class="bar-row"><span>${name}</span><div class="bar-track"><i class="bar-fill ${value < 0 ? "negative" : ""}" style="width:${width}%"></i></div><b>${value > 0 ? "+" : ""}${number(value)}</b></div>`;
  }).join("");
  $("components").innerHTML = components;
  $("direction").textContent = risk.direction;
  $("entry").textContent = number(risk.entry_price, 6);
  $("stop").textContent = number(risk.stop_loss, 6);
  $("target").textContent = number(risk.take_profit, 6);
  $("size").textContent = number(risk.position_size, 6);
  $("risk-amount").textContent = number(risk.risk_amount);
  $("allocation").textContent = percent(risk.allocation_pct);
  $("warning").textContent = risk.warnings.join(" · ") || `Risk / Reward 1 : ${risk.reward_risk_ratio}`;
}

function showContext(context) {
  $("hero-score").textContent = number(context.consensus_score, 0);
  $("regime").textContent = context.regime.regime.replaceAll("_", " ");
  $("regime-confidence").textContent = percent(context.regime.confidence);
  $("quality-grade").textContent = context.quality.grade;
  $("quality-grade").className = `quality-${context.quality.grade.toLowerCase()}`;
  $("quality-score").textContent = number(context.quality.quality_score, 0);
  $("agreement").textContent = percent(context.agreement_pct);
  $("consensus").textContent = context.consensus_signal.replaceAll("_", " ");
  $("quality-issue").textContent = context.quality.issues.join(" · ");
  $("timeframe-summary").textContent = `${context.timeframes.length} ACTIVE · ${Object.keys(context.skipped_timeframes).length} SKIPPED`;
  const header = '<div class="timeframe-row header"><span>TIMEFRAME</span><span>SIGNAL</span><span>SCORE</span><span>CONFIDENCE</span><span>WEIGHT</span></div>';
  const rows = context.timeframes.map((item) => {
    const negative = item.decision.score < 0 ? "negative" : "";
    return `<div class="timeframe-row"><b>${item.timeframe}</b><span>${item.decision.signal.replaceAll("_", " ")}</span><span class="${negative}">${number(item.decision.score)}</span><span>${percent(item.decision.confidence)}</span><span>${percent(item.weight * 100)}</span></div>`;
  }).join("");
  $("timeframe-table").innerHTML = header + rows;
}

async function analyze() {
  setBusy(true); clearError();
  try {
    const body = payload();
    const [decision, risk, context] = await Promise.all([request("/analyze", body), request("/risk-plan", body), request("/multi-timeframe", body)]);
    showDecision(decision, risk);
    showContext(context);
  } catch (error) { showError(error); } finally { setBusy(false); }
}

async function backtest() {
  setBusy(true); clearError();
  try {
    const body = {...payload(), initial_capital: Number($("equity").value), risk_per_trade_pct: Number($("risk").value)};
    const result = await request("/backtest", body);
    $("return").textContent = percent(result.total_return_pct);
    $("excess").textContent = percent(result.excess_return_pct);
    $("drawdown").textContent = percent(result.max_drawdown_pct);
    $("sharpe").textContent = number(result.sharpe_ratio);
    $("win-rate").textContent = percent(result.win_rate_pct);
    $("profit-factor").textContent = number(result.profit_factor);
    $("curve-label").textContent = `${result.trades} TRADES · ${percent(result.exposure_pct)} EXPOSED`;
    drawChart(result.equity_curve.map((point) => point.equity));
  } catch (error) { showError(error); } finally { setBusy(false); }
}

function drawChart(values) {
  const canvas = $("chart"), ctx = canvas.getContext("2d"), ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth, height = canvas.clientHeight;
  canvas.width = width * ratio; canvas.height = height * ratio; ctx.scale(ratio, ratio); ctx.clearRect(0, 0, width, height);
  if (values.length < 2) return;
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1, pad = 18;
  ctx.strokeStyle = "#21342e"; ctx.lineWidth = 1;
  for (let i = 1; i < 5; i += 1) { const y = i * height / 5; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke(); }
  const points = values.map((value, i) => [pad + i / (values.length - 1) * (width - pad * 2), pad + (1 - (value - min) / range) * (height - pad * 2)]);
  const gradient = ctx.createLinearGradient(0, 0, 0, height); gradient.addColorStop(0, "rgba(82,242,162,.35)"); gradient.addColorStop(1, "rgba(82,242,162,0)");
  ctx.beginPath(); ctx.moveTo(points[0][0], height); points.forEach(([x, y]) => ctx.lineTo(x, y)); ctx.lineTo(points.at(-1)[0], height); ctx.fillStyle = gradient; ctx.fill();
  ctx.beginPath(); points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.strokeStyle = "#52f2a2"; ctx.lineWidth = 2; ctx.stroke();
}

function updateCount() { try { $("candle-count").textContent = `${JSON.parse($("candles").value || "[]").length} CANDLES`; } catch { $("candle-count").textContent = "INVALID JSON"; } }
function setBusy(value) { [$("analyze"), $("backtest")].forEach((button) => { button.disabled = value; }); }
function clearError() { $("error").textContent = ""; }
function showError(error) { $("error").textContent = error.message; }
$("sample").addEventListener("click", sampleCandles); $("analyze").addEventListener("click", analyze); $("backtest").addEventListener("click", backtest); $("candles").addEventListener("input", updateCount); window.addEventListener("resize", () => {});
sampleCandles();
