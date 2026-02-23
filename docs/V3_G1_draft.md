```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Trade Analyst — V3</title>
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

  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.08) 2px, rgba(0,0,0,0.08) 4px);
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

  .logo span { color: var(--muted); font-weight: 400; }

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

  .page-title { font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.2em; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; }

  h1 { font-size: 28px; font-weight: 600; color: var(--text); margin-bottom: 6px; line-height: 1.2; }

  .subtitle { color: var(--muted); font-size: 14px; margin-bottom: 40px; font-weight: 300; }

  .steps {
    display: flex; gap: 0; margin-bottom: 40px;
    border: 1px solid var(--border); border-radius: 4px; overflow: hidden;
  }

  .step {
    flex: 1; padding: 12px 16px;
    font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: 0.1em;
    color: var(--muted); background: var(--surface);
    border-right: 1px solid var(--border); cursor: pointer; transition: all 0.2s;
    text-transform: uppercase;
  }

  .step:last-child { border-right: none; }

  .step .step-num {
    display: block; font-size: 16px; font-weight: 600;
    color: var(--border2); margin-bottom: 2px; transition: color 0.2s;
  }

  .step.active { background: var(--surface2); color: var(--gold); }
  .step.active .step-num { color: var(--gold); }
  .step.done { color: var(--green); }
  .step.done .step-num { color: var(--green); }

  .section { display: none; animation: fadeIn 0.3s ease; }
  .section.active { display: block; }

  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; padding: 24px; margin-bottom: 16px;
  }

  .card-label {
    font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: 0.15em;
    color: var(--gold); text-transform: uppercase; margin-bottom: 16px;
    display: flex; align-items: center; gap: 8px;
  }

  .card-label::after { content: ''; flex: 1; height: 1px; background: var(--border); }

  label {
    display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px;
    font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.05em; text-transform: uppercase;
  }

  input[type="text"], select, textarea, input[type="number"] {
    width: 100%; background: var(--bg); border: 1px solid var(--border);
    border-radius: 3px; color: var(--text); font-family: 'DM Sans', sans-serif;
    font-size: 14px; padding: 10px 14px; outline: none; transition: border-color 0.2s;
    margin-bottom: 16px;
  }

  input[type="text"]:focus, select:focus, textarea:focus { border-color: var(--gold); }

  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

  .tf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 0; }

  .upload-zone {
    border: 1px dashed var(--border2); border-radius: 4px; padding: 20px 16px;
    text-align: center; cursor: pointer; transition: all 0.2s; background: var(--bg);
    position: relative; overflow: hidden;
  }

  .upload-zone:hover { border-color: var(--gold); background: rgba(212,168,67,0.03); }

  .upload-zone.has-file {
    border-color: var(--green); border-style: solid; background: rgba(34,197,94,0.04);
  }

  .upload-zone input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; margin: 0; padding: 0; }

  .upload-tf-label { font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.1em; color: var(--gold); text-transform: uppercase; display: block; margin-bottom: 4px; }

  .upload-desc { font-size: 11px; color: var(--muted); display: block; margin-bottom: 8px; }

  .upload-icon { font-size: 24px; margin-bottom: 4px; display: block; }

  .upload-filename { font-size: 11px; color: var(--green); font-family: 'IBM Plex Mono', monospace; word-break: break-all; display: none; }

  .upload-zone.has-file .upload-filename { display: block; }
  .upload-zone.has-file .upload-icon, .upload-zone.has-file .upload-desc { display: none; }

  .preview-img { width: 100%; height: 80px; object-fit: cover; border-radius: 2px; margin-bottom: 6px; display: none; }
  .upload-zone.has-file .preview-img { display: block; }

  .checkbox-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

  .checkbox-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; border: 1px solid var(--border); border-radius: 3px;
    cursor: pointer; transition: all 0.15s; background: var(--bg);
  }

  .checkbox-item:hover { border-color: var(--border2); }

  .checkbox-item.checked {
    border-color: var(--gold); background: rgba(212,168,67,0.06);
  }

  .checkbox-item input { display: none; }

  .check-box {
    width: 14px; height: 14px; border: 1px solid var(--border2);
    border-radius: 2px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
    font-size: 10px; transition: all 0.15s;
  }

  .checkbox-item.checked .check-box {
    background: var(--gold); border-color: var(--gold); color: #000;
  }

  .check-text { font-size: 13px; color: var(--muted); transition: color 0.15s; }
  .checkbox-item.checked .check-text { color: var(--text); }

  .btn-row { display: flex; gap: 12px; margin-top: 24px; justify-content: flex-end; }

  .btn {
    font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.1em;
    text-transform: uppercase; padding: 12px 24px; border-radius: 3px;
    border: none; cursor: pointer; transition: all 0.15s;
  }

  .btn-ghost {
    background: transparent; border: 1px solid var(--border2); color: var(--muted);
  }

  .btn-ghost:hover { border-color: var(--text); color: var(--text); }

  .btn-primary {
    background: var(--gold); color: #000; font-weight: 600;
  }

  .btn-primary:hover { background: var(--gold2); }

  .output-panel {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 4px; padding: 20px; margin-top: 24px;
  }

  .output-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }

  .output-title {
    font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: 0.15em;
    color: var(--green); text-transform: uppercase;
  }

  .copy-btn {
    font-family: 'IBM Plex Mono', monospace; font-size: 10px;
    padding: 6px 14px; background: transparent; border: 1px solid var(--border2);
    color: var(--muted); border-radius: 2px; cursor: pointer;
    letter-spacing: 0.08em; text-transform: uppercase; transition: all 0.15s;
  }

  .copy-btn:hover { border-color: var(--green); color: var(--green); }

  #outputText {
    font-family: 'IBM Plex Mono', monospace; font-size: 12px;
    line-height: 1.7; color: var(--text); white-space: pre-wrap; word-break: break-word;
  }

  /* New V3 styles for G1 */
  .radio-group { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
  .radio-option {
    padding: 8px 14px; border: 1px solid var(--border); border-radius: 3px;
    cursor: pointer; font-size: 13px; transition: all 0.15s;
  }
  .radio-option.selected { border-color: var(--gold); background: rgba(212,168,67,0.06); color: var(--gold); }

  .slider-container { margin-bottom: 16px; }
  .slider-label { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
  input[type="range"] { width: 100%; accent-color: var(--gold); }

  .ticket-id { font-family: 'IBM Plex Mono', monospace; font-size: 13px; color: var(--gold); background: rgba(212,168,67,0.1); padding: 4px 10px; border-radius: 3px; display: inline-block; margin-bottom: 12px; }
</style>
</head>
<body>

<header class="header">
  <div class="logo">AI Trade <span>/ Analyst</span></div>
  <div class="status-pill">V3 · G1 PROMPT ENGINE</div>
</header>

<main class="main">
  <div class="page-title">Market Analysis Request — V3</div>
  <h1>Build Your Analysis Brief</h1>
  <p class="subtitle">G1 complete: full structured prompt engine with Ticket ID, persona, pre-ticket read, chart narrative & enum ticket block.</p>

  <!-- Steps nav (4 steps for G1) -->
  <div class="steps">
    <div class="step active" onclick="goTo(0)"><span class="step-num">01</span> Setup</div>
    <div class="step" onclick="goTo(1)"><span class="step-num">02</span> Charts</div>
    <div class="step" onclick="goTo(2)"><span class="step-num">03</span> Context + Pre-Ticket</div>
    <div class="step" onclick="goTo(3)"><span class="step-num">04</span> Output</div>
  </div>

  <!-- STEP 1: Setup -->
  <div class="section active" id="section-0">
    <div class="card">
      <div class="card-label">Asset & Session</div>
      <label>Asset / Ticker</label>
      <input type="text" id="asset" placeholder="e.g. XAUUSD" oninput="syncOutput()">
      <div class="suggestions">
        <span class="sug-pill" onclick="setAsset('XAUUSD')">XAUUSD</span>
        <span class="sug-pill" onclick="setAsset('EURUSD')">EURUSD</span>
        <span class="sug-pill" onclick="setAsset('BTCUSDT')">BTCUSDT</span>
      </div>

      <div class="row">
        <div>
          <label>Session</label>
          <select id="session" onchange="syncOutput()">
            <option value="">— Select —</option>
            <option>Swing / Multi-day</option>
            <option>NY Open</option>
            <option>London Open</option>
          </select>
        </div>
        <div>
          <label>Broker / Platform</label>
          <select id="broker" onchange="syncOutput()">
            <option value="">TradingView</option>
            <option>MT5</option>
            <option>cTrader</option>
            <option>Other</option>
          </select>
        </div>
      </div>

      <div class="row">
        <div>
          <label>Candle Type</label>
          <select id="candleType" onchange="syncOutput()">
            <option>Normal</option>
            <option>Heikin Ashi</option>
            <option>Renko</option>
          </select>
        </div>
        <div>
          <label>Chart Timezone</label>
          <input type="text" id="chartTimezone" placeholder="e.g. UTC+3 (MT5)" oninput="syncOutput()">
        </div>
      </div>

      <label>Price Now (optional)</label>
      <input type="text" id="priceNow" placeholder="e.g. 2934.65" oninput="syncOutput()">

      <div class="ticket-id" id="ticketIdDisplay">Ticket ID will appear after first generate</div>
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" onclick="goTo(1)">Next: Charts →</button>
    </div>
  </div>

  <!-- STEP 2: Charts -->
  <div class="section" id="section-1">
    <div class="card">
      <div class="card-label">Chart Screenshots</div>
      <p style="font-size:13px;color:var(--muted);margin-bottom:20px;">Attach screenshots (will be embedded in HTML/PDF later).</p>

      <div class="tf-grid">
        <div class="upload-zone" id="zone-htf" onclick="triggerUpload('upload-htf')">
          <input type="file" id="upload-htf" accept="image/*" onchange="handleUpload(this,'zone-htf','label-htf')">
          <span class="upload-icon">📈</span>
          <span class="upload-tf-label">HTF</span>
          <span class="upload-desc">Daily / Weekly</span>
          <img class="preview-img" id="prev-htf">
          <span class="upload-filename" id="label-htf"></span>
        </div>
        <!-- MID, LTF, EXEC zones (same as V2) -->
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
      <button class="btn btn-primary" onclick="goTo(2)">Next: Context + Pre-Ticket →</button>
    </div>
  </div>

  <!-- STEP 3: Context + Pre-Ticket (G1 core) -->
  <div class="section" id="section-2">
    <div class="card">
      <div class="card-label">Market Context</div>
      <label>Indicators on chart</label>
      <input type="text" id="indicators" placeholder="e.g. EMA 50/200, ICT FVG" oninput="syncOutput()">

      <label>Key levels I already see</label>
      <textarea id="levels" placeholder="e.g. Resistance 2935..." oninput="syncOutput()"></textarea>

      <label>Upcoming news / events</label>
      <input type="text" id="news" placeholder="None known" oninput="syncOutput()">

      <label>Any open positions?</label>
      <input type="text" id="position" placeholder="None" oninput="syncOutput()">
    </div>

    <!-- NEW G1: Pre-Ticket Checklist -->
    <div class="card">
      <div class="card-label">Pre-Ticket Checklist (mandatory for ticket block)</div>
      <div class="row">
        <div>
          <label>HTF State</label>
          <select id="htfState" onchange="syncOutput()">
            <option>Trending</option>
            <option>Ranging</option>
            <option>Transition</option>
          </select>
        </div>
        <div>
          <label>HTF Location</label>
          <select id="htfLocation" onchange="syncOutput()">
            <option>At POI</option>
            <option>Mid-range</option>
            <option>At extremes</option>
          </select>
        </div>
      </div>

      <div class="row">
        <div>
          <label>LTF Alignment</label>
          <select id="ltfAlignment" onchange="syncOutput()">
            <option>Aligned</option>
            <option>Counter-trend</option>
            <option>Mixed</option>
          </select>
        </div>
        <div>
          <label>Liquidity Context</label>
          <select id="liquidityContext" onchange="syncOutput()">
            <option>Near highs or lows</option>
            <option>Equilibrium</option>
            <option>None identified</option>
          </select>
        </div>
      </div>

      <div class="row">
        <div>
          <label>Volatility / News Risk</label>
          <select id="volRisk" onchange="syncOutput()">
            <option>Normal</option>
            <option>Elevated</option>
          </select>
        </div>
        <div>
          <label>Execution Quality</label>
          <select id="execQuality" onchange="syncOutput()">
            <option>Clean</option>
            <option>Messy</option>
            <option>Chop</option>
          </select>
        </div>
      </div>

      <label>My Personal Edge Tag</label>
      <select id="userEdgeTag" onchange="syncOutput()">
        <option>High-probability pullback</option>
        <option>Liquidity grab</option>
        <option>FVG reclaim</option>
        <option>Structure BOS</option>
        <option>Range boundary</option>
        <option>Other</option>
      </select>

      <div class="slider-container">
        <div class="slider-label">My Confluence Score (1–10)</div>
        <input type="range" id="confluenceScore" min="1" max="10" value="7" oninput="syncOutput()">
        <span id="confluenceValue" style="font-family:monospace;color:var(--gold);">7</span>
      </div>
    </div>

    <div class="btn-row">
      <button class="btn btn-ghost" onclick="goTo(1)">← Back</button>
      <button class="btn btn-primary" onclick="buildAndShow()">Generate V3 Prompt →</button>
    </div>
  </div>

  <!-- STEP 4: Output -->
  <div class="section" id="section-3">
    <div class="card">
      <div class="card-label">Your V3 Analysis Prompt (G1 Engine)</div>
      <p style="font-size:13px;color:var(--muted);margin-bottom:16px;">
        Copy & paste into Claude/Grok. Attach your 4 screenshots in the same message.<br>
        <strong>Ticket ID & timestamp auto-generated.</strong>
      </p>

      <div class="output-panel">
        <div class="output-header">
          <span class="output-title">● GENERATED PROMPT — V3</span>
          <button class="copy-btn" onclick="copyPrompt()">Copy Prompt</button>
        </div>
        <div id="outputText">Fill form → Generate</div>
      </div>
    </div>

    <div class="card">
      <div class="card-label">Charts to Attach</div>
      <div id="attachChecklist" style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);line-height:2;white-space:pre;"></div>
    </div>

    <div class="btn-row">
      <button class="btn btn-ghost" onclick="goTo(2)">← Edit</button>
      <button class="btn btn-primary" onclick="resetForm()">New Ticket</button>
    </div>
  </div>

</main>

<script>
let currentStep = 0;
let currentBias = '';
const uploads = { htf: null, mid: null, ltf: null, exec: null };
let ticketID = '';

function generateTicketID() {
  const asset = (document.getElementById('asset').value || 'XXXXXX').toUpperCase().slice(0,6);
  const now = new Date();
  const ymd = now.getFullYear().toString().slice(2) + 
              String(now.getMonth()+1).padStart(2,'0') + 
              String(now.getDate()).padStart(2,'0');
  const hm = String(now.getHours()).padStart(2,'0') + String(now.getMinutes()).padStart(2,'0');
  ticketID = `${asset}_${ymd}_${hm}`;
  document.getElementById('ticketIdDisplay').textContent = `Ticket ID: ${ticketID}`;
}

function goTo(step) {
  document.querySelectorAll('.section').forEach((s,i) => s.classList.toggle('active', i === step));
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
  generateTicketID();
  syncOutput();
}

function triggerUpload(id) { document.getElementById(id).click(); }

function handleUpload(input, zoneId, labelId) {
  const file = input.files[0];
  if (!file) return;
  const zone = document.getElementById(zoneId);
  const label = document.getElementById(labelId);
  const key = zoneId.replace('zone-','');
  uploads[key] = file.name;
  zone.classList.add('has-file');
  label.textContent = file.name;

  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById('prev-' + key).src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function getChecked() {
  return Array.from(document.querySelectorAll('#requests .checkbox-item.checked .check-text'))
              .map(i => i.textContent);
}

function buildPrompt() {
  generateTicketID(); // ensure latest

  const asset = document.getElementById('asset').value || '[ASSET]';
  const session = document.getElementById('session').value || 'Swing / Multi-day';
  const broker = document.getElementById('broker').value || 'TradingView';
  const candleType = document.getElementById('candleType').value || 'Normal';
  const chartTZ = document.getElementById('chartTimezone').value || 'Broker default';
  const priceNow = document.getElementById('priceNow').value || '—';

  const indicators = document.getElementById('indicators').value || 'None specified';
  const levels = document.getElementById('levels').value || 'None — identify from charts';
  const news = document.getElementById('news').value || 'None known';
  const position = document.getElementById('position').value || 'None';

  // G1 Pre-Ticket values
  const htfState = document.getElementById('htfState').value;
  const htfLocation = document.getElementById('htfLocation').value;
  const ltfAlignment = document.getElementById('ltfAlignment').value;
  const liquidityContext = document.getElementById('liquidityContext').value;
  const volRisk = document.getElementById('volRisk').value;
  const execQuality = document.getElementById('execQuality').value;
  const userEdgeTag = document.getElementById('userEdgeTag').value;
  const confluenceScore = document.getElementById('confluenceScore').value;

  const tfs = [
    `  • HTF (Daily/Weekly) — ${uploads.htf ? '✓ attached' : '⚠ NO SCREENSHOT'}`,
    `  • Mid TF (4H/1H) — ${uploads.mid ? '✓ attached' : '⚠ NO SCREENSHOT'}`,
    `  • LTF (15m/5m) — ${uploads.ltf ? '✓ attached' : '⚠ NO SCREENSHOT'}`,
    `  • Execution TF (1m/3m) — ${uploads.exec ? '✓ attached' : '— optional'}`,
  ].join('\n');

  const now = new Date().toISOString().slice(0,19) + 'Z';

  const prompt = `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 AI TRADE ANALYSIS REQUEST — V3
Ticket ID: ${ticketID}
Generated: ${now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ASSET:           ${asset}
SESSION:         ${session}
BROKER:          ${broker}
CANDLE TYPE:     ${candleType}
CHART TIMEZONE:  ${chartTZ}
PRICE NOW:       ${priceNow}

─── CHARTS PROVIDED ───────────────
${tfs}
(Screenshots attached to this message)

─── INDICATORS ON CHART ───────────
${indicators}

─── KEY LEVELS I ALREADY SEE ──────
${levels}

─── NEWS / EVENTS ─────────────────
${news}

─── OPEN POSITIONS ────────────────
${position}

─── PRE-TICKET READ (user input) ──
HTF State:           ${htfState}
HTF Location:        ${htfLocation}
LTF Alignment:       ${ltfAlignment}
Liquidity Context:   ${liquidityContext}
Volatility Risk:     ${volRisk}
Exec Quality:        ${execQuality}
Personal Edge Tag:   ${userEdgeTag}
Confluence Score:    ${confluenceScore}/10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM PERSONA (obey strictly):
You are a ruthless, zero-ego 20-year prop trader. You would rather say WAIT than force a low-quality ticket. Never sugar-coat. Precision over comfort.

CHART NARRATIVE (describe exactly what you see — no assumptions):
HTF:  [describe visible trend, structure, key levels]
Mid:  [describe visible]
LTF:  [describe visible]
Exec: [describe visible]
Overall raw bias from charts only: [Bullish / Bearish / Neutral / Range]

TRADE TICKET ${ticketID}:
Decision:            LONG / SHORT / WAIT / CONDITIONAL
Setup Type:          Pullback / Breakout / Reversal / Range / Other
Entry:               [zone or exact]
Entry Trigger:       [Close above/below / Break + retest / Sweep + reclaim / Pullback to zone / Momentum shift]
Confirmation TF:     [1m / 5m / 15m / 1H]
Stop:                [level] — [Stop Logic: Below swing low / Below zone / ATR-based / Structure + buffer] — reason
TP1:                 [level] — rationale
TP2:                 [level] — rationale
R:R (TP1 / TP2):    [calculated using spread assumption]
Time Validity:       [This session / 24H / Custom]
Kill-switch:         [what cancels the setup]
Confidence:          [1–5] — max 3 bullet reasons
What changes mind:   [2 concrete observable conditions]
Missing info:        [declare gaps if any]
WAIT reason:         [enum — only if WAIT]
Re-entry condition:  [only if WAIT]

Always include what would prove the idea wrong.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

  document.getElementById('outputText').textContent = prompt;

  // Checklist
  const attachEl = document.getElementById('attachChecklist');
  const list = ['htf','mid','ltf','exec'].map(k => {
    const name = uploads[k];
    return `${name ? '✓' : '○'} ${k.toUpperCase()} — ${name || '(not uploaded)'}`;
  }).join('\n');
  attachEl.textContent = list;
}

function syncOutput() {
  if (currentStep === 3) buildPrompt();
  document.getElementById('confluenceValue').textContent = document.getElementById('confluenceScore').value;
}

function buildAndShow() {
  buildPrompt();
  goTo(3);
}

function copyPrompt() {
  const text = document.getElementById('outputText').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.copy-btn');
    const orig = btn.textContent;
    btn.textContent = 'COPIED ✓';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => {
      btn.textContent = orig;
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 1800);
  });
}

function resetForm() {
  location.reload(); // simple for G1
}

// Init
window.onload = () => {
  generateTicketID();
  // Sync slider live
  document.getElementById('confluenceScore').addEventListener('input', () => {
    document.getElementById('confluenceValue').textContent = document.getElementById('confluenceScore').value;
  });
};
</script>
</body>
</html>
```

**✅ G1 COMPLETE — V3 Prompt Engine Live**

**What you have right now (copy the entire code above into a file called `AI-Trade-Analyst-V3.html` and open it):**

- Auto-generated **Ticket ID** (e.g. XAUUSD_260223_1745)  
- Full **V3 structured prompt** with:  
  - System persona (ruthless prop trader)  
  - Pre-Ticket Read block (populated from the new radios in Step 3)  
  - **CHART NARRATIVE** grounding block  
  - Enum-enforced **TRADE TICKET** block  
  - All meta-injections (broker, candle type, timezone, price now, etc.)  



