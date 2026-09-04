/**
 * electron_hud/renderer.js
 * Frontend rendering logic for the Hyper-Spherical Electron Token HUD.
 *
 * Features:
 *   - 3 Digital LCD Windows (RAW BEFORE, SENT AFTER, CONSERVED)
 *   - Gold banner with savings % and compression ratio
 *   - 24h session ledger
 *   - Scrolling ticker with URL, model, log path, compression stats
 *   - Real-time live history graph (canvas)
 *   - Hooked applications telemetry table
 */

let sessionPre = 0;
let sessionPost = 0;
let sessionSaved = 0;
let isPinned = true;

// Current active model & endpoint info (updated on each telemetry burst)
let activeModel = 'Awaiting first request…';
let activeUrl = 'http://127.0.0.1:8000/v1';
let activeApp = 'Tesseract Gateway';
let logFilePath = '';

// Graph history buffer (up to 60 data points for smoother curves)
const historyData = [];
const maxHistoryPoints = 60;

// DOM Elements
const elValPre = document.getElementById('valPre');
const elValPost = document.getElementById('valPost');
const elValSaved = document.getElementById('valSaved');
const elPctSaved = document.getElementById('pctSaved');
const elRatioBadge = document.getElementById('ratioBadge');
const elSessionText = document.getElementById('sessionText');
const elTickerText = document.getElementById('tickerText');
const elTableBody = document.getElementById('tableBody');
const elBtnPin = document.getElementById('btnPin');
const elBtnTest = document.getElementById('btnTest');
const elBtnMin = document.getElementById('btnMin');
const elBtnClose = document.getElementById('btnClose');
const elBtnReset = document.getElementById('btnReset');
const canvas = document.getElementById('tokenGraphCanvas');
const ctx = canvas.getContext('2d');

// ── Window Controls ─────────────────────────────────────────────────────────

elBtnClose.addEventListener('click', () => {
  try { if (window.electronAPI) window.electronAPI.closeWindow(); } catch (e) { console.error('Close failed:', e); }
});

elBtnMin.addEventListener('click', () => {
  try { if (window.electronAPI) window.electronAPI.minimizeWindow(); } catch (e) { console.error('Minimize failed:', e); }
});

elBtnPin.addEventListener('click', () => {
  isPinned = !isPinned;
  if (isPinned) {
    elBtnPin.classList.remove('unpinned');
    elBtnPin.textContent = '📌 PINNED';
  } else {
    elBtnPin.classList.add('unpinned');
    elBtnPin.textContent = '📍 UNPINNED';
  }
  try { if (window.electronAPI) window.electronAPI.toggleAlwaysOnTop(isPinned); } catch (e) { console.error('Pin toggle failed:', e); }
});

elBtnReset.addEventListener('click', () => {
  sessionPre = 0;
  sessionPost = 0;
  sessionSaved = 0;
  historyData.length = 0;
  elTableBody.innerHTML = '';
  updateSessionDisplay();
  drawGraph();
});

elBtnTest.addEventListener('click', () => {
  const mockPre = Math.floor(Math.random() * 2200) + 1600;
  const mockPost = Math.floor(Math.random() * 320) + 180;
  handleNewStat({
    pre_tokens: mockPre,
    post_tokens: mockPost,
    model: 'tesseract-sfs-plus (burst test)',
    url: 'http://127.0.0.1:8000/v1/chat/completions',
    app: 'Interactive Pulse',
    log_path: 'C:\\Users\\twist\\.hypes\\token_logs\\' + new Date().toISOString().slice(0, 10) + '.jsonl',
  });
});

// ── Scrolling Ticker — Continuously broadcasts current state ────────────────

function buildTickerString() {
  const sessPct = sessionPre > 0 ? ((sessionSaved / sessionPre) * 100).toFixed(1) : '0.0';
  const sessRatio = sessionPost > 0 ? (sessionPre / sessionPost).toFixed(1) : '1.0';

  const today = new Date().toISOString().slice(0, 10);
  const logPath = logFilePath || `C:\\Users\\twist\\.hypes\\token_logs\\${today}.jsonl`;

  const parts = [
    `⚡ MODEL: ${activeModel.toUpperCase()}`,
    `✦`,
    `TARGET: ${activeUrl}`,
    `✦`,
    `APP: ${activeApp}`,
    `✦`,
    `SESSION: ${sessionSaved.toLocaleString()} TOKENS SAVED (${sessPct}% · ${sessRatio}×)`,
    `✦`,
    `LOG: ${logPath}`,
    `✦`,
    `COMPRESSION: ${sessRatio}× ACTIVE`,
    `✦`,
    sessionPre > 0 ? `STATUS: LIVE OPTIMIZING` : `STATUS: AWAITING TRAFFIC`,
    `✦`,
  ];

  return parts.join(' \u00A0');
}

// Refresh ticker every 2 seconds so it stays current even without new bursts
setInterval(() => {
  if (elTickerText) {
    elTickerText.textContent = buildTickerString();
  }
}, 2000);

// ── Telemetry Update Handler ────────────────────────────────────────────────

function handleNewStat(data) {
  try {
    const pre = parseInt(data.pre_tokens || 0, 10);
    const post = parseInt(data.post_tokens || 0, 10);
    const saved = Math.max(0, pre - post);
    const model = data.model || 'tesseract-sfs-plus';
    const url = data.url || 'http://127.0.0.1:8000/v1';
    const app = data.app || 'Tesseract Gateway';

    // Update global state for ticker
    activeModel = model;
    activeUrl = url;
    activeApp = app;
    if (data.log_path) logFilePath = data.log_path;

    const pct = pre > 0 ? (saved / pre) * 100 : 0;
    const ratio = post > 0 ? pre / post : 1;

    // 1. Update 3 Digital Windows
    animateCounter(elValPre, pre);
    animateCounter(elValPost, post);
    animateCounter(elValSaved, saved);

    // 2. Update Golden Banner
    elPctSaved.textContent = `${pct.toFixed(1)}% SAVINGS`;
    elRatioBadge.textContent = `${ratio.toFixed(1)}× COMPRESSION`;

    // 3. Update Session Totals
    sessionPre += pre;
    sessionPost += post;
    sessionSaved += saved;
    updateSessionDisplay();

    // 4. Update Scrolling Ticker immediately
    elTickerText.textContent = buildTickerString();

    // 5. Add to Graph History
    historyData.push({ pre, post, saved, ts: Date.now() });
    if (historyData.length > maxHistoryPoints) {
      historyData.shift();
    }
    drawGraph();

    // 6. Append to Table Log
    appendTableRow(app, model, pre, post, saved, pct);
  } catch (err) {
    console.error('[HUD] Error processing telemetry:', err);
  }
}

function updateSessionDisplay() {
  const sessPct = sessionPre > 0 ? (sessionSaved / sessionPre) * 100 : 0;
  const sessRatio = sessionPost > 0 ? sessionPre / sessionPost : 1;
  elSessionText.textContent = `24h Session: ${sessionSaved.toLocaleString()} tokens saved (${sessPct.toFixed(1)}% conserved · ${sessRatio.toFixed(1)}× total)`;
}

function animateCounter(elem, targetVal) {
  if (!elem) return;
  const startVal = parseInt(elem.textContent.replace(/,/g, ''), 10) || 0;
  const diff = targetVal - startVal;
  if (diff === 0) { elem.textContent = targetVal.toLocaleString(); return; }
  const steps = 15;
  let cur = 0;

  const timer = setInterval(() => {
    cur++;
    const val = Math.round(startVal + (diff * (cur / steps)));
    elem.textContent = val.toLocaleString();
    if (cur >= steps) {
      clearInterval(timer);
      elem.textContent = targetVal.toLocaleString();
    }
  }, 16);
}

function appendTableRow(app, model, pre, post, saved, pct) {
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${timeStr}</td>
    <td style="color: #38bdf8;">${escapeHtml(app.slice(0, 20))}</td>
    <td style="color: #c084fc;">${escapeHtml(model.slice(0, 18))}</td>
    <td style="color: #fb923c;">${pre.toLocaleString()}</td>
    <td style="color: #38bdf8;">${post.toLocaleString()}</td>
    <td class="saved-cell">+${saved.toLocaleString()} (${pct.toFixed(0)}%)</td>
  `;

  elTableBody.insertBefore(tr, elTableBody.firstChild);

  // Keep table bounded to last 50 entries
  while (elTableBody.children.length > 50) {
    elTableBody.removeChild(elTableBody.lastChild);
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Canvas Graph Renderer ───────────────────────────────────────────────────

function resizeCanvas() {
  try {
    const rect = canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform before scaling
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    drawGraph();
  } catch (err) {
    console.error('[HUD] Canvas resize error:', err);
  }
}

window.addEventListener('resize', resizeCanvas);

function drawGraph() {
  try {
    const rect = canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;
    if (w <= 0 || h <= 0) return;

    ctx.clearRect(0, 0, w, h);

    // Background Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (const yPct of [0.25, 0.5, 0.75]) {
      const y = h * yPct;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    if (historyData.length < 2) {
      ctx.fillStyle = '#64748b';
      ctx.font = '10px Consolas, monospace';
      ctx.textAlign = 'center';
      ctx.fillText('⚡ REAL-TIME GRAPH — CLICK TEST OR AWAIT LIVE TRAFFIC', w / 2, h / 2 + 3);
      return;
    }

    const maxVal = Math.max(...historyData.map((d) => d.pre), 100);
    const padX = 16;
    const padY = 12;
    const plotW = w - padX * 2;
    const plotH = h - padY * 2;

    function getX(idx) {
      return padX + (idx / (historyData.length - 1)) * plotW;
    }
    function getY(val) {
      return h - padY - (val / maxVal) * plotH;
    }

    // 1. Saved Area Gradient Fill  (FIXED: was setColorAt, must be addColorStop)
    const grad = ctx.createLinearGradient(0, padY, 0, h - padY);
    grad.addColorStop(0, 'rgba(16, 185, 129, 0.45)');
    grad.addColorStop(1, 'rgba(16, 185, 129, 0.02)');

    ctx.beginPath();
    ctx.moveTo(getX(0), h - padY);
    for (let i = 0; i < historyData.length; i++) {
      ctx.lineTo(getX(i), getY(historyData[i].saved));
    }
    ctx.lineTo(getX(historyData.length - 1), h - padY);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // 2. Raw Curve (Amber Line)
    drawCurve(historyData.map(d => d.pre), '#f59e0b', 2);

    // 3. Sent Curve (Cyan Line)
    drawCurve(historyData.map(d => d.post), '#06b6d4', 2);

    // 4. Conserved Curve (Green Line)
    drawCurve(historyData.map(d => d.saved), '#10b981', 2.5);

    // 5. Draw data point dots on the latest point
    const lastIdx = historyData.length - 1;
    drawDot(getX(lastIdx), getY(historyData[lastIdx].pre), '#f59e0b');
    drawDot(getX(lastIdx), getY(historyData[lastIdx].post), '#06b6d4');
    drawDot(getX(lastIdx), getY(historyData[lastIdx].saved), '#10b981');

    function drawCurve(values, color, lineWidth) {
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(values[0]));
      for (let i = 1; i < values.length; i++) {
        ctx.lineTo(getX(i), getY(values[i]));
      }
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }

    function drawDot(x, y, color) {
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      // Glow
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fillStyle = color.replace(')', ', 0.3)').replace('rgb', 'rgba');
      ctx.fill();
    }
  } catch (err) {
    console.error('[HUD] Graph draw error:', err);
  }
}

// ── Startup & Initialization ────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  try {
    resizeCanvas();

    // Set initial ticker
    elTickerText.textContent = buildTickerString();

    // Initialize from live telemetry IPC
    if (window.electronAPI) {
      window.electronAPI.onTelemetryUpdate((data) => {
        handleNewStat(data);
      });

      try {
        const initial = await window.electronAPI.getInitialState();
        if (initial && initial.totalPre > 0) {
          sessionPre = initial.totalPre;
          sessionPost = initial.totalPost;
          sessionSaved = initial.totalSaved;
          if (initial.logPath) logFilePath = initial.logPath;
          updateSessionDisplay();
          elTickerText.textContent = buildTickerString();
          if (initial.lastRecord) {
            handleNewStat(initial.lastRecord);
          }
        }
      } catch (err) {
        console.warn('[HUD] Could not load initial state:', err);
      }
    } else {
      console.log('[HUD] No electronAPI — running in standalone browser mode');
    }
  } catch (err) {
    console.error('[HUD] Startup error:', err);
  }
});
