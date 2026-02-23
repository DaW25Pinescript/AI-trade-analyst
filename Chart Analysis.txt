<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Trade Analyst — Intake Form</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0b0e;
    --surface: #111318;
    --surface2: #181c24;
    --border: #1e2430;
    --border2: #2a3040;
    --gold: #d4a843;
    --gold2: #f0c060;
    --green: #22c55e;
    --red: #ef4444;
    --text: #e8eaf0;
    --muted: #6b7385;
    --accent: #3b6fff;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    padding: 0;
  }

  /* Scanline texture */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,0.08) 2px,
      rgba(0,0,0,0.08) 4px
    );
    pointer-events: none;
    z-index: 1000;
  }

  .header {
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    font-weight: 600;
    color: var(--gold);
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  .logo span {
    color: var(--muted);
    font-weight: 400;
  }

  .status-pill {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 2px;
    background: rgba(212,168,67,0.1);
    border: 1px solid rgba(212,168,67,0.3);
    color: var(--gold);
    letter-spacing: 0.1em;
  }

  .main {
    max-width: 820px;
    margin: 0 auto;
    padding: 48px 24px 80px;
  }

  .page-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.2em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  h1 {
    font-size: 28px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 6px;
    line-height: 1.2;
  }

  .subtitle {
    color: var(--muted);
    font-size: 14px;
    margin-bottom: 40px;
    font-weight: 300;
  }

  /* Steps progress */
  .steps {
    display: flex;
    gap: 0;
    margin-bottom: 40px;
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
  }

  .step {
    flex: 1;
    padding: 12px 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.1em;
    color: var(--muted);
    background: var(--surface);
    border-right: 1px solid var(--border);
    cursor: pointer;
    transition: all 0.2s;
    text-transform: uppercase;
  }

  .step:last-child { border-right: none; }

  .step .step-num {
    display: block;
    font-size: 16px;
    font-weight: 600;
    color: var(--border2);
    margin-bottom: 2px;
    transition: color 0.2s;
  }

  .step.active {
    background: var(--surface2);
    color: var(--gold);
  }

  .step.active .step-num { color: var(--gold); }

  .step.done {
    color: var(--green);
  }

  .step.done .step-num { color: var(--green); }

  /* Sections */
  .section {
    display: none;
    animation: fadeIn 0.3s ease;
  }

  .section.active { display: block; }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 24px;
    margin-bottom: 16px;
  }

  .card-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.15em;
    color: var(--gold);
    text-transform: uppercase;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .card-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  label {
    display: block;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 6px;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  input[type="text"], select, textarea {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 3px;
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    padding: 10px 14px;
    outline: none;
    transition: border-color 0.2s;
    margin-bottom: 16px;
    -webkit-appearance: none;
  }

  input[type="text"]:focus, select:focus, textarea:focus {
    border-color: var(--gold);
  }

  select {
    cursor: pointer;
  }

  select option {
    background: var(--surface2);
  }

  textarea {
    resize: vertical;
    min-height: 80px;
  }

  .row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  /* Upload zones */
  .tf-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 0;
  }

  .upload-zone {
    border: 1px dashed var(--border2);
    border-radius: 4px;
    padding: 20px 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: var(--bg);
    position: relative;
    overflow: hidden;
  }

  .upload-zone:hover {
    border-color: var(--gold);
    background: rgba(212,168,67,0.03);
  }

  .upload-zone.has-file {
    border-color: var(--green);
    border-style: solid;
    background: rgba(34,197,94,0.04);
  }

  .upload-zone input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
  }

  .upload-tf-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--gold);
    text-transform: uppercase;
    display: block;
    margin-bottom: 4px;
  }

  .upload-desc {
    font-size: 11px;
    color: var(--muted);
    display: block;
    margin-bottom: 8px;
  }

  .upload-icon {
    font-size: 24px;
    margin-bottom: 4px;
    display: block;
  }

  .upload-filename {
    font-size: 11px;
    color: var(--green);
    font-family: 'IBM Plex Mono', monospace;
    word-break: break-all;
    display: none;
  }

  .upload-zone.has-file .upload-filename { display: block; }
  .upload-zone.has-file .upload-icon { display: none; }
  .upload-zone.has-file .upload-desc { display: none; }

  /* Preview thumbnails */
  .preview-img {
    width: 100%;
    height: 80px;
    object-fit: cover;
    border-radius: 2px;
    margin-bottom: 6px;
    display: none;
  }

  .upload-zone.has-file .preview-img { display: block; }

  /* Checkboxes */
  .checkbox-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .checkbox-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    background: var(--bg);
  }

  .checkbox-item:hover {
    border-color: var(--border2);
  }

  .checkbox-item.checked {
    border-color: var(--gold);
    background: rgba(212,168,67,0.06);
  }

  .checkbox-item input { display: none; }

  .check-box {
    width: 14px;
    height: 14px;
    border: 1px solid var(--border2);
    border-radius: 2px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    transition: all 0.15s;
  }

  .checkbox-item.checked .check-box {
    background: var(--gold);
    border-color: var(--gold);
    color: #000;
  }

  .check-text {
    font-size: 13px;
    color: var(--muted);
    transition: color 0.15s;
  }

  .checkbox-item.checked .check-text { color: var(--text); }

  /* Buttons */
  .btn-row {
    display: flex;
    gap: 12px;
    margin-top: 24px;
    justify-content: flex-end;
  }

  .btn {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 12px 24px;
    border-radius: 3px;
    border: none;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border2);
    color: var(--muted);
  }

  .btn-ghost:hover {
    border-color: var(--text);
    color: var(--text);
  }

  .btn-primary {
    background: var(--gold);
    color: #000;
    font-weight: 600;
  }

  .btn-primary:hover {
    background: var(--gold2);
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Output panel */
  .output-panel {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 20px;
    margin-top: 24px;
  }

  .output-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .output-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.15em;
    color: var(--green);
    text-transform: uppercase;
  }

  .copy-btn {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    padding: 6px 14px;
    background: transparent;
    border: 1px solid var(--border2);
    color: var(--muted);
    border-radius: 2px;
    cursor: pointer;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    transition: all 0.15s;
  }

  .copy-btn:hover {
    border-color: var(--green);
    color: var(--green);
  }

  #outputText {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    line-height: 1.7;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 24px 0;
  }

  /* Ticker suggestions */
  .suggestions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: -8px;
    margin-bottom: 16px;
  }

  .sug-pill {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
    border: 1px solid var(--border2);
    border-radius: 2px;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.15s;
    letter-spacing: 0.05em;
  }

  .sug-pill:hover {
    border-color: var(--gold);
    color: var(--gold);
  }

  /* Bias selector */
  .bias-row {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }

  .bias-btn {
    flex: 1;
    padding: 10px;
    border-radius: 3px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--muted);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.15s;
    text-align: center;
  }

  .bias-btn[data-val="BULLISH"]:hover,
  .bias-btn[data-val="BULLISH"].selected {
    border-color: var(--green);
    background: rgba(34,197,94,0.08);
    color: var(--green);
  }

  .bias-btn[data-val="BEARISH"]:hover,
  .bias-btn[data-val="BEARISH"].selected {
    border-color: var(--red);
    background: rgba(239,68,68,0.08);
    color: var(--red);
  }

  .bias-btn[data-val="NEUTRAL"]:hover,
  .bias-btn[data-val="NEUTRAL"].selected {
    border-color: var(--gold);
    background: rgba(212,168,67,0.08);
    color: var(--gold);
  }

  @media (max-width: 600px) {
    .row { grid-template-columns: 1fr; }
    .tf-grid { grid-template-columns: 1fr; }
    .checkbox-grid { grid-template-columns: 1fr; }
    .steps { flex-direction: column; }
    .step { border-right: none; border-bottom: 1px solid var(--border); }
    .step:last-child { border-bottom: none; }
  }
</style>
</head>
<body>

<header class="header">
  <div class="logo">AI Trade <span>/ Analyst</span></div>
  <div class="status-pill">V1 · INTAKE FORM</div>
</header>

<main class="main">
  <div class="page-title">Market Analysis Request</div>
  <h1>Build Your Analysis Brief</h1>
  <p class="subtitle">Fill in each step — the form generates a structured prompt you send to Claude with your screenshots.</p>

  <!-- Steps nav -->
  <div class="steps">
    <div class="step active" onclick="goTo(0)">
      <span class="step-num">01</span>Setup
    </div>
    <div class="step" onclick="goTo(1)">
      <span class="step-num">02</span>Charts
    </div>
    <div class="step" onclick="goTo(2)">
      <span class="step-num">03</span>Context
    </div>
    <div class="step" onclick="goTo(3)">
      <span class="step-num">04</span>Output
    </div>
  </div>

  <!-- STEP 1: Setup -->
  <div class="section active" id="section-0">
    <div class="card">
      <div class="card-label">Asset & Session</div>

      <label>Asset / Ticker</label>
      <input type="text" id="asset" placeholder="e.g. XAUUSD, EURUSD, BTCUSDT" oninput="syncOutput()">
      <div class="suggestions">
        <span class="sug-pill" onclick="setAsset('XAUUSD')">XAUUSD</span>
        <span class="sug-pill" onclick="setAsset('EURUSD')">EURUSD</span>
        <span class="sug-pill" onclick="setAsset('GBPUSD')">GBPUSD</span>
        <span class="sug-pill" onclick="setAsset('BTCUSDT')">BTCUSDT</span>
        <span class="sug-pill" onclick="setAsset('US30')">US30</span>
        <span class="sug-pill" onclick="setAsset('NAS100')">NAS100</span>
      </div>

      <div class="row">
        <div>
          <label>Session</label>
          <select id="session" onchange="syncOutput()">
            <option value="">— Select —</option>
            <option>London Open</option>
            <option>London Mid</option>
            <option>NY Open</option>
            <option>NY AM</option>
            <option>NY PM / Close</option>
            <option>Asia Session</option>
            <option>Swing / Multi-day</option>
          </select>
        </div>
        <div>
          <label>Trade Style</label>
          <select id="style" onchange="syncOutput()">
            <option value="">— Select —</option>
            <option>Scalp only</option>
            <option>Intraday only</option>
            <option>Swing only</option>
            <option>All ideas</option>
          </select>
        </div>
      </div>

      <label>My Current Bias (optional)</label>
      <div class="bias-row">
        <div class="bias-btn" data-val="BULLISH" onclick="setBias(this)">▲ Bullish</div>
        <div class="bias-btn" data-val="BEARISH" onclick="setBias(this)">▼ Bearish</div>
        <div class="bias-btn" data-val="NEUTRAL" onclick="setBias(this)">— Neutral</div>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" onclick="goTo(1)">Next: Charts →</button>
    </div>
  </div>

  <!-- STEP 2: Charts -->
  <div class="section" id="section-1">
    <div class="card">
      <div class="card-label">Chart Screenshots</div>
      <p style="font-size:13px;color:var(--muted);margin-bottom:20px;">Attach a screenshot for each timeframe. You'll send these directly in the Claude chat alongside the generated prompt.</p>

      <div class="tf-grid">
        <div class="upload-zone" id="zone-htf" onclick="triggerUpload('upload-htf')">
          <input type="file" id="upload-htf" accept="image/*" onchange="handleUpload(this,'zone-htf','label-htf')">
          <span class="upload-icon">📈</span>
          <span class="upload-tf-label">HTF</span>
          <span class="upload-desc">Daily / Weekly</span>
          <img class="preview-img" id="prev-htf">
          <span class="upload-filename" id="label-htf"></span>
        </div>

        <div class="upload-zone" id="zone-mid" onclick="triggerUpload('upload-mid')">
          <input type="file" id="upload-mid" accept="image/*" onchange="handleUpload(this,'zone-mid','label-mid')">
          <span class="upload-icon">📊</span>
          <span class="upload-tf-label">MID TF</span>
          <span class="upload-desc">4H / 1H</span>
          <img class="preview-img" id="prev-mid">
          <span class="upload-filename" id="label-mid"></span>
        </div>

        <div class="upload-zone" id="zone-ltf" onclick="triggerUpload('upload-ltf')">
          <input type="file" id="upload-ltf" accept="image/*" onchange="handleUpload(this,'zone-ltf','label-ltf')">
          <span class="upload-icon">🔍</span>
          <span class="upload-tf-label">LTF</span>
          <span class="upload-desc">15m / 5m</span>
          <img class="preview-img" id="prev-ltf">
          <span class="upload-filename" id="label-ltf"></span>
        </div>

        <div class="upload-zone" id="zone-exec" onclick="triggerUpload('upload-exec')">
          <input type="file" id="upload-exec" accept="image/*" onchange="handleUpload(this,'zone-exec','label-exec')">
          <span class="upload-icon">⚡</span>
          <span class="upload-tf-label">EXEC TF</span>
          <span class="upload-desc">1m / 3m (optional)</span>
          <img class="preview-img" id="prev-exec">
          <span class="upload-filename" id="label-exec"></span>
        </div>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-ghost" onclick="goTo(0)">← Back</button>
      <button class="btn btn-primary" onclick="goTo(2)">Next: Context →</button>
    </div>
  </div>

  <!-- STEP 3: Context -->
  <div class="section" id="section-2">
    <div class="card">
      <div class="card-label">Market Context</div>

      <label>Indicators on chart</label>
      <input type="text" id="indicators" placeholder="e.g. EMA 50/200, ICT FVG, Fibonacci, SR Zones" oninput="syncOutput()">

      <label>Key levels you already see</label>
      <textarea id="levels" placeholder="e.g. Resistance at 5,200 — previous swing high. Support at 4,987 (HTF demand zone). Trendline from Feb lows." oninput="syncOutput()"></textarea>

      <label>Upcoming news / events</label>
      <input type="text" id="news" placeholder="e.g. CPI tomorrow 8:30 ET, FOMC next week" oninput="syncOutput()">

      <label>Any open positions?</label>
      <input type="text" id="position" placeholder="e.g. Long XAUUSD from 5,050, SL at 4,950" oninput="syncOutput()">
    </div>

    <div class="card">
      <div class="card-label">Analysis Requests</div>
      <div class="checkbox-grid" id="requests">
        <label class="checkbox-item checked" onclick="toggleCheck(this)">
          <input type="checkbox" checked>
          <div class="check-box">✓</div>
          <span class="check-text">Trend & key levels per TF</span>
        </label>
        <label class="checkbox-item checked" onclick="toggleCheck(this)">
          <input type="checkbox" checked>
          <div class="check-box">✓</div>
          <span class="check-text">Scalp idea</span>
        </label>
        <label class="checkbox-item checked" onclick="toggleCheck(this)">
          <input type="checkbox" checked>
          <div class="check-box">✓</div>
          <span class="check-text">Intraday idea</span>
        </label>
        <label class="checkbox-item checked" onclick="toggleCheck(this)">
          <input type="checkbox" checked>
          <div class="check-box">✓</div>
          <span class="check-text">Swing idea</span>
        </label>
        <label class="checkbox-item checked" onclick="toggleCheck(this)">
          <input type="checkbox" checked>
          <div class="check-box">✓</div>
          <span class="check-text">No-trade conditions</span>
        </label>
        <label class="checkbox-item" onclick="toggleCheck(this)">
          <input type="checkbox">
          <div class="check-box"></div>
          <span class="check-text">Liquidity analysis</span>
        </label>
        <label class="checkbox-item" onclick="toggleCheck(this)">
          <input type="checkbox">
          <div class="check-box"></div>
          <span class="check-text">HTF/LTF confluence</span>
        </label>
        <label class="checkbox-item" onclick="toggleCheck(this)">
          <input type="checkbox">
          <div class="check-box"></div>
          <span class="check-text">Invalidation scenarios</span>
        </label>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-ghost" onclick="goTo(1)">← Back</button>
      <button class="btn btn-primary" onclick="buildAndShow()">Generate Prompt →</button>
    </div>
  </div>

  <!-- STEP 4: Output -->
  <div class="section" id="section-3">
    <div class="card">
      <div class="card-label">Your Analysis Prompt</div>
      <p style="font-size:13px;color:var(--muted);margin-bottom:16px;">
        Copy this prompt and paste it into Claude. <strong style="color:var(--text);">Attach your chart screenshots in the same message.</strong>
      </p>

      <div class="output-panel">
        <div class="output-header">
          <span class="output-title">● Generated prompt</span>
          <button class="copy-btn" onclick="copyPrompt()">Copy Prompt</button>
        </div>
        <div id="outputText">Fill in the form to generate your prompt...</div>
      </div>
    </div>

    <div class="card">
      <div class="card-label">Charts to Attach</div>
      <div id="attachChecklist" style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);line-height:2;">
        No charts uploaded yet.
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-ghost" onclick="goTo(2)">← Edit</button>
      <button class="btn btn-primary" onclick="resetForm()">New Analysis</button>
    </div>
  </div>

</main>

<script>
let currentStep = 0;
let currentBias = '';
const uploads = { htf: null, mid: null, ltf: null, exec: null };

function goTo(step) {
  document.querySelectorAll('.section').forEach((s,i) => {
    s.classList.toggle('active', i === step);
  });
  document.querySelectorAll('.step').forEach((s,i) => {
    s.classList.remove('active','done');
    if (i === step) s.classList.add('active');
    if (i < step) s.classList.add('done');
  });
  currentStep = step;
  if (step === 3) buildPrompt();
}

function setAsset(val) {
  document.getElementById('asset').value = val;
  syncOutput();
}

function setBias(el) {
  document.querySelectorAll('.bias-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  currentBias = el.dataset.val;
}

function triggerUpload(id) {
  document.getElementById(id).click();
}

function handleUpload(input, zoneId, labelId) {
  const file = input.files[0];
  if (!file) return;
  const zone = document.getElementById(zoneId);
  const label = document.getElementById(labelId);
  const key = zoneId.replace('zone-','');
  uploads[key] = file.name;
  zone.classList.add('has-file');
  label.textContent = file.name;

  // Preview
  const reader = new FileReader();
  reader.onload = e => {
    const img = document.getElementById('prev-' + key);
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function toggleCheck(el) {
  el.classList.toggle('checked');
  const box = el.querySelector('.check-box');
  box.textContent = el.classList.contains('checked') ? '✓' : '';
}

function getChecked() {
  const items = document.querySelectorAll('#requests .checkbox-item.checked .check-text');
  return Array.from(items).map(i => i.textContent);
}

function buildPrompt() {
  const asset = document.getElementById('asset').value || '[ASSET NOT SET]';
  const session = document.getElementById('session').value || 'Not specified';
  const style = document.getElementById('style').value || 'All ideas';
  const indicators = document.getElementById('indicators').value;
  const levels = document.getElementById('levels').value;
  const news = document.getElementById('news').value;
  const position = document.getElementById('position').value;
  const checked = getChecked();

  const tfs = [];
  if (uploads.htf) tfs.push('  • HTF (Daily/Weekly) — ✓ screenshot attached');
  else tfs.push('  • HTF (Daily/Weekly) — ⚠ NO SCREENSHOT');
  if (uploads.mid) tfs.push('  • Mid TF (4H/1H) — ✓ screenshot attached');
  else tfs.push('  • Mid TF (4H/1H) — ⚠ NO SCREENSHOT');
  if (uploads.ltf) tfs.push('  • LTF (15m/5m) — ✓ screenshot attached');
  else tfs.push('  • LTF (15m/5m) — ⚠ NO SCREENSHOT');
  if (uploads.exec) tfs.push('  • Execution TF (1m/3m) — ✓ screenshot attached');

  const requests = checked.length > 0 ? checked.map(c => `  ☑ ${c}`).join('\n') : '  (none selected)';

  const prompt = `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 AI TRADE ANALYSIS REQUEST — V1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ASSET:    ${asset}
SESSION:  ${session}
STYLE:    ${style}${currentBias ? `\nBIAS:     ${currentBias} (my current read)` : ''}

─── CHARTS PROVIDED ───────────────
${tfs.join('\n')}
(Screenshots attached to this message)

─── INDICATORS ON CHART ───────────
${indicators || 'None specified'}

─── KEY LEVELS I ALREADY SEE ──────
${levels || 'None — please identify from charts'}

─── NEWS / EVENTS ─────────────────
${news || 'None known'}

─── OPEN POSITIONS ────────────────
${position || 'None'}

─── WHAT I WANT BACK ──────────────
${requests}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS FOR CLAUDE:

Please analyse each timeframe systematically:
1. Trend state (Bullish / Bearish / Range / Transition)
2. Market structure (HH/HL, LH/LL, MSS/BOS)
3. Key demand/supply zones and high-impact levels
4. Risk notes (choppy, extended, news-sensitive)

Then cross-reference timeframes for alignment.

For each trade idea requested above, provide:
  • Entry zone (not a single price)
  • Invalidation level
  • Logical target(s)
  • "Do not trade if…" conditions

Always include what would prove the idea wrong.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

  document.getElementById('outputText').textContent = prompt;

  // Checklist
  const attachEl = document.getElementById('attachChecklist');
  const list = ['htf','mid','ltf','exec'].map(k => {
    const name = uploads[k];
    return `${name ? '✓' : '○'}  ${k.toUpperCase()} chart${name ? ' — ' + name : ' (not uploaded)'}`;
  }).join('\n');
  attachEl.style.whiteSpace = 'pre';
  attachEl.textContent = list;
}

function syncOutput() {
  if (currentStep === 3) buildPrompt();
}

function buildAndShow() {
  buildPrompt();
  goTo(3);
}

function copyPrompt() {
  const text = document.getElementById('outputText').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.copy-btn');
    btn.textContent = 'Copied ✓';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => {
      btn.textContent = 'Copy Prompt';
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 2000);
  });
}

function resetForm() {
  document.getElementById('asset').value = '';
  document.getElementById('session').value = '';
  document.getElementById('style').value = '';
  document.getElementById('indicators').value = '';
  document.getElementById('levels').value = '';
  document.getElementById('news').value = '';
  document.getElementById('position').value = '';
  currentBias = '';
  document.querySelectorAll('.bias-btn').forEach(b => b.classList.remove('selected'));
  Object.keys(uploads).forEach(k => uploads[k] = null);
  ['htf','mid','ltf','exec'].forEach(k => {
    const zone = document.getElementById('zone-' + k);
    zone.classList.remove('has-file');
    document.getElementById('label-' + k).textContent = '';
    document.getElementById('prev-' + k).src = '';
    document.getElementById('upload-' + k).value = '';
  });
  goTo(0);
}
</script>
</body>
</html>