import { state } from '../state/model.js';

function _safeText(s) {
  return (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function _buildReportHTML() {
  const prompt = document.getElementById('outputText').textContent || '';
  const asset = document.getElementById('asset').value || 'ASSET';
  const now = new Date().toISOString().replace('T',' ').slice(0,19) + 'Z';

  const imgs = [
    { key:'htf',  title:'HTF (Daily/Weekly)',   name: state.uploads.htf,  src: state.imgSrcs.htf  },
    { key:'mid',  title:'Mid TF (4H/1H)',        name: state.uploads.mid,  src: state.imgSrcs.mid  },
    { key:'ltf',  title:'LTF (15m/5m)',          name: state.uploads.ltf,  src: state.imgSrcs.ltf  },
    { key:'exec', title:'Execution TF (1m/3m)',  name: state.uploads.exec, src: state.imgSrcs.exec },
  ].filter(x => x.name && x.src);

  const imgBlocks = imgs.length
    ? imgs.map(x => `
        <div class="ic">
          <div class="ih"><span class="it">${_safeText(x.title)}</span><span class="im">${_safeText(x.name)}</span></div>
          <img src="${x.src}" alt="${_safeText(x.title)}" style="width:100%;display:block;">
        </div>`).join('')
    : `<p style="color:#6b7385;font-size:13px;">No screenshots embedded.</p>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Trade Analysis — ${_safeText(state.ticketID)}</title>
<style>
  body{margin:0;background:#0a0b0e;color:#e8eaf0;font-family:system-ui,sans-serif;}
  .w{max-width:900px;margin:0 auto;padding:24px 16px 48px;}
  .hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;gap:12px;flex-wrap:wrap;}
  .brand{font-size:11px;letter-spacing:.15em;color:#d4a843;text-transform:uppercase;font-weight:700;margin-bottom:4px;}
  h1{font-size:20px;margin:0 0 4px;}
  .meta{font-size:12px;color:#6b7385;}
  .stamp{font-size:11px;color:#6b7385;font-family:monospace;}
  .card{background:#111318;border:1px solid #1e2430;border-radius:6px;padding:16px;margin-bottom:12px;}
  pre{white-space:pre-wrap;word-break:break-word;margin:0;font-family:ui-monospace,Menlo,Monaco,monospace;font-size:11.5px;line-height:1.7;color:#e8eaf0;}
  .ic{background:#0b0c10;border:1px solid #1e2430;border-radius:5px;overflow:hidden;margin-bottom:10px;}
  .ih{padding:10px 12px 7px;border-bottom:1px solid #1e2430;display:flex;justify-content:space-between;align-items:baseline;gap:10px;}
  .it{font-weight:600;font-size:13px;}
  .im{color:#6b7385;font-size:11px;}
  @media print{body{background:#0a0b0e!important;color:#e8eaf0!important;color-scheme:dark;}}
</style>
</head>
<body>
<div class="w">
  <div class="hdr">
    <div>
      <div class="brand">AI Trade / Analyst — V3</div>
      <h1>Analysis Brief — ${_safeText(document.getElementById('asset').value || 'ASSET')}</h1>
      <div class="meta">Ticket: ${_safeText(state.ticketID)} · ${_safeText(now)}</div>
    </div>
    <div class="stamp">${_safeText(now)}</div>
  </div>
  <div class="card">
    <div class="meta" style="margin-bottom:10px;"><strong style="color:#e8eaf0;">Generated Prompt</strong></div>
    <pre>${_safeText(prompt)}</pre>
  </div>
  <div class="card">
    <div class="meta" style="margin-bottom:10px;"><strong style="color:#e8eaf0;">Embedded Screenshots</strong></div>
    ${imgBlocks}
  </div>
</div>
</body>
</html>`;
}

export { _safeText, _buildReportHTML };
