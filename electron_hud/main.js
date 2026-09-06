/**
 * electron_hud/main.js
 * Main process for the Hyper-Spherical Electron Desktop Token Counter HUD.
 *
 * Window configuration:
 *   - alwaysOnTop: true (screen-saver level)
 *   - frame: false (custom title bar)
 *   - resizable: true
 *   - Top-right screen corner positioning
 *
 * Telemetry:
 *   - Polls ~/.hypes/hud_live.json every 150ms for real-time token compression data
 *   - Restores 24h session totals from daily JSONL logs on startup
 *   - Sends IPC telemetry-update events to renderer for live display
 */

const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

const HYPES_DIR = path.join(os.homedir(), '.hypes');
const LIVE_STAT_FILE = path.join(HYPES_DIR, 'hud_live.json');
const LOG_DIR = path.join(HYPES_DIR, 'token_logs');

let mainWindow = null;
let lastSeq = -1;
let telemetryInterval = null;

// ── Ensure directories exist ────────────────────────────────────────────────

function ensureDirectories() {
  try {
    if (!fs.existsSync(HYPES_DIR)) {
      fs.mkdirSync(HYPES_DIR, { recursive: true });
    }
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }
  } catch (err) {
    console.error('[HUD Main] Failed to create directories:', err.message);
  }
}

// ── Seed a demo hud_live.json if none exists ────────────────────────────────

function seedDemoTelemetry() {
  try {
    if (!fs.existsSync(LIVE_STAT_FILE)) {
      const demo = {
        seq: 0,
        pre_tokens: 0,
        post_tokens: 0,
        model: 'awaiting-first-request',
        url: 'http://127.0.0.1:8000/v1',
        app: 'HypeS Gateway',
        log_path: path.join(LOG_DIR, new Date().toISOString().slice(0, 10) + '.jsonl'),
      };
      fs.writeFileSync(LIVE_STAT_FILE, JSON.stringify(demo), 'utf8');
    }
  } catch (err) {
    console.warn('[HUD Main] Could not seed demo telemetry:', err.message);
  }
}

// ── Window Creation ─────────────────────────────────────────────────────────

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth } = primaryDisplay.workAreaSize;

  const winWidth = 580;
  const winHeight = 740;

  // Position in Top-Right Corner of Screen
  const posX = Math.max(20, screenWidth - winWidth - 30);
  const posY = 30;

  mainWindow = new BrowserWindow({
    width: winWidth,
    height: winHeight,
    minWidth: 480,
    minHeight: 520,
    x: posX,
    y: posY,
    alwaysOnTop: true,
    frame: false,
    resizable: true,
    transparent: true,
    hasShadow: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false,
    },
  });

  mainWindow.loadFile('index.html');

  // Handle window drag and always-on-top
  mainWindow.setAlwaysOnTop(true, 'screen-saver');

  mainWindow.on('closed', () => {
    mainWindow = null;
    if (telemetryInterval) {
      clearInterval(telemetryInterval);
      telemetryInterval = null;
    }
  });

  // Handle renderer crashes gracefully
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    console.error('[HUD Main] Renderer crashed:', details.reason);
    // Try to reload
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.reload();
      }
    }, 2000);
  });

  startTelemetryWatcher();
}

// ── Telemetry File Watcher ──────────────────────────────────────────────────

function startTelemetryWatcher() {
  // Poll hud_live.json every 150ms for instant real-time telemetry updates
  telemetryInterval = setInterval(() => {
    try {
      if (!fs.existsSync(LIVE_STAT_FILE)) return;
      const raw = fs.readFileSync(LIVE_STAT_FILE, 'utf8');
      if (!raw.trim()) return;

      const data = JSON.parse(raw);
      if (data.seq !== lastSeq && data.pre_tokens > 0) {
        lastSeq = data.seq;

        // Attach log path if not already set
        if (!data.log_path) {
          const today = new Date().toISOString().slice(0, 10);
          data.log_path = path.join(LOG_DIR, `${today}.jsonl`);
        }

        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('telemetry-update', data);
        }
      }
    } catch (e) {
      // Ignore transient read collisions or malformed JSON
      if (e.code !== 'ENOENT' && e.name !== 'SyntaxError') {
        console.warn('[HUD Main] Telemetry poll error:', e.message);
      }
    }
  }, 150);
}

// ── IPC Listeners ─────────────────────────────────────────────────────────────

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('toggle-always-on-top', (event, shouldPin) => {
  if (mainWindow) {
    mainWindow.setAlwaysOnTop(shouldPin, 'screen-saver');
  }
});

ipcMain.handle('get-initial-state', () => {
  try {
    // Read today's log to restore session totals if any
    const today = new Date().toISOString().slice(0, 10);
    const todayFile = path.join(LOG_DIR, `${today}.jsonl`);
    let totalPre = 0;
    let totalPost = 0;
    let lastRecord = null;

    if (fs.existsSync(todayFile)) {
      const lines = fs.readFileSync(todayFile, 'utf8').split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const rec = JSON.parse(line);
          totalPre += rec.pre_tokens || 0;
          totalPost += rec.post_tokens || 0;
          lastRecord = rec;
        } catch (e) {
          // Skip malformed lines
        }
      }
    }

    return {
      totalPre,
      totalPost,
      totalSaved: Math.max(0, totalPre - totalPost),
      lastRecord,
      logPath: todayFile,
    };
  } catch (e) {
    console.warn('[HUD Main] Error loading initial state:', e.message);
    return { totalPre: 0, totalPost: 0, totalSaved: 0, lastRecord: null, logPath: '' };
  }
});

// ── App Lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(() => {
  ensureDirectories();
  seedDemoTelemetry();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Handle uncaught exceptions gracefully
process.on('uncaughtException', (err) => {
  console.error('[HUD Main] Uncaught exception:', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[HUD Main] Unhandled rejection:', reason);
});
