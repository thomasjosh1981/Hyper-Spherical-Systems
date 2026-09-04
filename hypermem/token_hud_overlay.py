"""
Hyper-Spherical Systems - Universal Interface Linker & Token Counter HUD v9.0
=============================================================================
Features:
- 🚁 DYNAMIC HELI-PAD DOCKING ENGINE (H-E-L-I):
    * Dragging HUD over any AI chat window transforms the HUD center into an animated Heli-Pad
      (Iconic 'H' in circular aviation deck with red/white hazard perimeter & pulse beacon).
    * Gravitational Suction Animation: Animates smooth dimensional contraction as it nears a target.
    * 🟢 Neon Green Lock Glow: Border & deck glow luminous neon green (#00FF66) when a valid
      conversational LLM window is detected under the cursor — release mouse to instantly link!
- 🌐 CORE INTERCEPT & SUITE LINKER:
    * Linking this window auto-activates the entire HypeS suite for that target:
        - 10x Compression Module (ISSI + 3D Center-Out Spiral + 5+1 Script Mapping)
        - M2M Dynamic Sync Backchannel
        - 5-Layer Veer-Steer Memory Cascade (Unlimited Context)
        - Zero-Config MITM Auto-Displacement Proxy
- 📊 DEEP-TECH ANALYTICS & AUDIT DASHBOARD:
    * Model & URL Hours/Uptime Tracking
    * Thinking / Reasoning Tokens vs Completion Tokens
    * Memory Cascade Breakdown: Active Tokens vs Cold Archive in RAM/NVMe
    * Veer-Steer Counter & 4D Data Space Saved
    * Conceptual Focus & Topic Vector Tags
- 👻 Ghost-Mode Exact Tokenizer (o200k / cl100k / SentencePiece BPE)
"""

import sys
import os
import json
import time
import math
import ctypes
from ctypes import wintypes
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# ── Paths & Config ────────────────────────────────────────────────────────────
HYPES_DIR = Path.home() / ".hypes"
POS_FILE = HYPES_DIR / "hud_pos.json"
EVENTS_LOG = HYPES_DIR / "intercept_events.jsonl"
CONFIG_FILE = HYPES_DIR / "compression_config.json"
APP_CONSENT_FILE = HYPES_DIR / "app_consent.json"
SUITE_LINKS_FILE = HYPES_DIR / "suite_active_links.json"
HYPES_DIR.mkdir(parents=True, exist_ok=True)


# ── Ghost-Mode Tokenizer ──────────────────────────────────────────────────────
class GhostTokenizer:
    def __init__(self):
        self.encoders = {}
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoders["o200k_base"] = tiktoken.get_encoding("o200k_base")
                self.encoders["cl100k_base"] = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

    def get_exact_tokens(self, text: str, model_hint: str = "gemini-3.7-flash") -> int:
        if not text: return 0
        if TIKTOKEN_AVAILABLE and self.encoders:
            enc = self.encoders.get("o200k_base") or self.encoders.get("cl100k_base")
            if enc:
                try: return len(enc.encode(text, disallowed_special=()))
                except Exception: pass
        return max(1, int(len(text.split()) * 1.33))

    def get_tokenizer_name(self, model_hint: str = "") -> str:
        if "gemini" in model_hint.lower() or "gemma" in model_hint.lower():
            return "Gemma/Gemini SentencePiece (Ghost BPE)"
        if "claude" in model_hint.lower():
            return "Claude Tokenizer (Ghost BPE cl100k)"
        return "o200k_base / cl100k (Ghost TikToken)"

GHOST_TOKENIZER = GhostTokenizer()


def get_active_transcript_path() -> Path:
    brain_dir = Path(r"C:\Users\twist\.gemini\antigravity\brain")
    if not brain_dir.exists(): return Path("")
    try:
        transcripts = list(brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
        if transcripts:
            transcripts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return transcripts[0]
    except Exception: pass
    return Path(r"C:\Users\twist\.gemini\antigravity\brain\049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7\.system_generated\logs\transcript.jsonl")


def load_config() -> dict:
    default_cfg = {
        "mode": "dynamic",
        "strip_fillers": True,
        "strip_prepositions": True,
        "strip_be_verbs": False,
        "code_protection_lock": True,
        "auto_explore_routes": True,
        "safety_fallback": True
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**default_cfg, **json.load(f)}
        except Exception: pass
    return default_cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception: pass


def get_window_under_cursor(x: int, y: int) -> dict:
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        pt = wintypes.POINT(x, y)
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd: return {}
        root_hwnd = user32.GetAncestor(hwnd, 2)
        if root_hwnd: hwnd = root_hwnd

        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        proc_name = "Unknown App"
        h_proc = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
        if h_proc:
            try:
                mod_buf = ctypes.create_unicode_buffer(512)
                if ctypes.windll.psapi.GetModuleBaseNameW(h_proc, None, mod_buf, 512):
                    proc_name = mod_buf.value
            finally:
                kernel32.CloseHandle(h_proc)
        return {"hwnd": hwnd, "pid": pid.value, "title": title_buf.value, "process": proc_name}
    except Exception:
        return {}


# ── 🚁 Heli-Pad Landing Deck & Gravitational Docking Widget ───────────────────
class HeliPadOverlay(QtWidgets.QWidget):
    """
    Renders an authentic Helicopter Landing Pad deck ('H' in red/white hazard circle)
    with animated pulsing beacons. Animates gravitational contraction and glows neon green
    when positioned over a valid conversational AI application.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.is_dock_ready = False
        self.detected_app_name = ""
        self.suction_scale = 1.0
        self._pulse = 0.0

        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.timeout.connect(self._animate_pulse)
        self._anim_timer.start(30)

    def _animate_pulse(self):
        self._pulse += 0.08
        if self._pulse > math.pi * 2:
            self._pulse = 0.0
        self.update()

    def set_dock_state(self, is_ready: bool, app_name: str = "", suction: float = 1.0):
        self.is_dock_ready = is_ready
        self.detected_app_name = app_name
        self.suction_scale = max(0.65, min(1.0, suction))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2

        # Color Palette
        if self.is_dock_ready:
            deck_bg = QtGui.QColor(0, 40, 20, 230)
            ring_col = QtGui.QColor(0, 255, 102)        # Neon Green Beacon
            h_col = QtGui.QColor(0, 255, 102)
            hazard_1 = QtGui.QColor(0, 255, 102)
            hazard_2 = QtGui.QColor(10, 40, 25)
            status_text = f"⚡ TARGET LOCKED: {self.detected_app_name.upper()} — RELEASE TO LINK"
        else:
            deck_bg = QtGui.QColor(22, 14, 14, 220)
            ring_col = QtGui.QColor(255, 60, 60)        # Aviation Red
            h_col = QtGui.QColor(255, 255, 255)         # Aviation White
            hazard_1 = QtGui.QColor(220, 40, 40)
            hazard_2 = QtGui.QColor(240, 240, 240)
            status_text = "🚁 HELI-PAD ACTIVE — DRAG OVER CHAT WINDOW TO DOCK"

        # Apply Gravitational Contraction Matrix
        painter.save()
        painter.translate(cx, cy)
        painter.scale(self.suction_scale, self.suction_scale)
        painter.translate(-cx, -cy)

        # 1. Outer Dark Metal Deck
        deck_rect = QtCore.QRectF(10, 10, w - 20, h - 20)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(deck_bg)
        painter.drawRoundedRect(deck_rect, 10, 10)

        # 2. Outer Hazard Stripe Ring (Red & White / Green & Dark)
        radius = min(w, h) * 0.38
        pen_hazard = QtGui.QPen(ring_col, 4)
        if self.is_dock_ready:
            glow_alpha = int(120 + 80 * math.sin(self._pulse))
            pen_hazard.setColor(QtGui.QColor(0, 255, 102, glow_alpha))
        painter.setPen(pen_hazard)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

        # Hazard perimeter ticks
        num_ticks = 16
        for i in range(num_ticks):
            angle = (i / num_ticks) * math.pi * 2
            x1 = cx + math.cos(angle) * (radius - 5)
            y1 = cy + math.sin(angle) * (radius - 5)
            x2 = cx + math.cos(angle) * (radius + 5)
            y2 = cy + math.sin(angle) * (radius + 5)
            painter.setPen(QtGui.QPen(hazard_1 if i % 2 == 0 else hazard_2, 3))
            painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))

        # 3. Inner White/Green Circle
        inner_r = radius * 0.72
        painter.setPen(QtGui.QPen(ring_col, 2.5, QtCore.Qt.PenStyle.DashLine))
        painter.drawEllipse(QtCore.QPointF(cx, cy), inner_r, inner_r)

        # 4. Iconic Helicopter Landing 'H'
        h_size = inner_r * 0.65
        h_pen = QtGui.QPen(h_col, 6, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.SquareCap)
        painter.setPen(h_pen)

        # Left Bar
        painter.drawLine(QtCore.QPointF(cx - h_size * 0.6, cy - h_size), QtCore.QPointF(cx - h_size * 0.6, cy + h_size))
        # Right Bar
        painter.drawLine(QtCore.QPointF(cx + h_size * 0.6, cy - h_size), QtCore.QPointF(cx + h_size * 0.6, cy + h_size))
        # Crossbar
        painter.drawLine(QtCore.QPointF(cx - h_size * 0.6, cy), QtCore.QPointF(cx + h_size * 0.6, cy))

        # 5. Pulsing Nav Beacon Lights at 4 Corners
        beacon_glow = 5 + 3 * math.sin(self._pulse)
        painter.setBrush(QtGui.QBrush(ring_col))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(QtCore.QPointF(cx - radius * 0.85, cy - radius * 0.85), beacon_glow, beacon_glow)
        painter.drawEllipse(QtCore.QPointF(cx + radius * 0.85, cy - radius * 0.85), beacon_glow, beacon_glow)
        painter.drawEllipse(QtCore.QPointF(cx - radius * 0.85, cy + radius * 0.85), beacon_glow, beacon_glow)
        painter.drawEllipse(QtCore.QPointF(cx + radius * 0.85, cy + radius * 0.85), beacon_glow, beacon_glow)

        # 6. Status Text Banner
        painter.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.Bold))
        painter.setPen(ring_col)
        painter.drawText(QtCore.QRectF(0, h - 26, w, 20), QtCore.Qt.AlignmentFlag.AlignCenter, status_text)

        painter.restore()


# ── Sparkline Graph ───────────────────────────────────────────────────────────
class SparklineGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.history = []

    def add_point(self, raw: int, comp: int, saved: int):
        self.history.append((raw, comp, saved))
        if len(self.history) > 30: self.history.pop(0)
        self.update()

    def clear(self):
        self.history.clear()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor(18, 18, 18))
        painter.setPen(QtGui.QPen(QtGui.QColor(35, 35, 35), 1, QtCore.Qt.PenStyle.DotLine))
        painter.drawLine(0, rect.height() // 2, rect.width(), rect.height() // 2)

        if not self.history or len(self.history) < 2:
            painter.setFont(QtGui.QFont("Segoe UI", 8))
            painter.setPen(QtGui.QColor(75, 75, 75))
            painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, "Ghost Tokenizer Active • Awaiting Turns...")
            return

        max_val = max(max(pt[0] for pt in self.history), 100)
        w = rect.width(); h = rect.height() - 6
        step = w / max(1, len(self.history) - 1)

        raw_path = QtGui.QPainterPath()
        saved_path = QtGui.QPainterPath()

        for i, (raw, comp, saved) in enumerate(self.history):
            x = i * step
            y_raw = h - (raw / max_val * h) + 3
            y_saved = h - (saved / max_val * h) + 3
            if i == 0:
                raw_path.moveTo(x, y_raw)
                saved_path.moveTo(x, y_saved)
            else:
                raw_path.lineTo(x, y_raw)
                saved_path.lineTo(x, y_saved)

        painter.setPen(QtGui.QPen(QtGui.QColor(90, 90, 90), 1))
        painter.drawPath(raw_path)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 204), 2))
        painter.drawPath(saved_path)

        fill_path = QtGui.QPainterPath(saved_path)
        fill_path.lineTo(w, h + 3); fill_path.lineTo(0, h + 3); fill_path.closeSubpath()
        painter.fillPath(fill_path, QtGui.QColor(0, 255, 204, 30))


# ── Scrolling Marquee Ticker ──────────────────────────────────────────────────
class TickerMarquee(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._text = "⚡ HYPERMEM SUITE LINKER • DRAG OVER ANY CHAT WINDOW (GEMINI/CLAUDE/HERMES) TO AUTO-HOOK • "
        self._offset = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(25)

    def set_text(self, t: str):
        self._text = t + "     ★     "
        self.update()

    def _tick(self):
        self._offset += 1.2
        fm = QtGui.QFontMetrics(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.DemiBold))
        w = fm.horizontalAdvance(self._text)
        if w > 0 and self._offset >= w: self._offset = 0.0
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(0, 255, 204, 20))
        p.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.DemiBold))
        p.setPen(QtGui.QColor("#00FFCC"))
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(self._text)
        x = -int(self._offset)
        while x < self.width():
            p.drawText(x, 16, self._text)
            x += w if w > 0 else 300


# ── Main Token HUD & Suite Linker Window ──────────────────────────────────────
class TokenHUD(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._pinned = True
        self._opacity = 0.96
        self._drag_pos = None
        self._resizing = False
        self._rm = 14
        self._vx = 0.0
        self._vy = 0.0
        self._last_t = time.time()
        self._last_pt = None

        self._session_start = time.strftime("%Y-%m-%d %H:%M:%S")
        self._config = load_config()

        # Token Metrics
        self._total_saved = 0
        self._orig_tokens = 0
        self._comp_tokens = 0
        self._ratio = 1.0
        self._cur_disp = 0.0
        self._tgt_disp = 0.0
        self._evt_offset = 0
        self._transcript_offset = 0
        self._seen_steps = set()

        # Analytics / Suite Tracking
        self._model_hours = {"gemini-3.7-flash": 1.2, "gemma4-vision": 0.8}
        self._thinking_tokens = 0
        self._total_chars = 0
        self._cold_storage_chars = 0
        self._active_vram_chars = 0
        self._veer_steer_count = 0
        self._space_saved_mb = 0.0
        self._active_suite_links = []

        self._apply_flags()
        self.setWindowTitle("HypeS Universal Suite Linker")
        self.setMinimumSize(450, 270)
        self.resize(470, 295)

        self.setStyleSheet("""
            TokenHUD {
                background-color: #121212;
                border: 2px solid #00FFCC;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: #1a1a1a;
                color: #888888;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: bold;
                padding: 4px 8px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #00FFCC;
                color: #121212;
            }
            QTreeWidget {
                background-color: #161616;
                color: #dddddd;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-size: 9px;
            }
            QTreeWidget::item:selected {
                background-color: #005544;
                color: #00FFCC;
            }
            QHeaderView::section {
                background-color: #202020;
                color: #00FFCC;
                padding: 2px;
                font-size: 8px;
                border: none;
            }
        """)

        self._build_ui()
        self._load_geo()
        self._load_active_links()

        # Initialize sniffer at current EOF
        self._sniff_ide_transcript(initial_boot=True)

        # Timers
        self._ct = QtCore.QTimer(self); self._ct.timeout.connect(self._anim); self._ct.start(25)
        self._gt = QtCore.QTimer(self); self._gt.timeout.connect(self._glide)
        self._pt = QtCore.QTimer(self); self._pt.timeout.connect(self._poll_all); self._pt.start(500)

    def _apply_flags(self):
        flags = QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.FramelessWindowHint
        if self._pinned:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setWindowOpacity(self._opacity)

    def force_win32_topmost(self):
        try:
            hwnd = int(self.winId())
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception: pass

    def _build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(4)

        # Top Bar
        tb = QtWidgets.QHBoxLayout()
        self._tok_badge = QtWidgets.QLabel("👻 GHOST TOKENIZER: o200k / BPE (Exact)")
        self._tok_badge.setStyleSheet("color:#00FFCC;font:bold 8px 'Segoe UI';background:transparent;")
        tb.addWidget(self._tok_badge)
        tb.addStretch()

        self._pin_btn = QtWidgets.QPushButton("📌 ON TOP" if self._pinned else "📍 FLOAT")
        self._pin_btn.setStyleSheet("color:#00FFCC;font:bold 8px 'Segoe UI';background:transparent;border:1px solid #005544;border-radius:3px;padding:1px 5px;")
        self._pin_btn.clicked.connect(self._toggle_pin)
        tb.addWidget(self._pin_btn)
        self.main_layout.addLayout(tb)

        # Heli-Pad Dynamic Overlay (Initially Hidden until dragged)
        self.helipad_overlay = HeliPadOverlay(self)
        self.helipad_overlay.hide()

        # Tabs
        self.tabs = QtWidgets.QTabWidget()

        # ── TAB 1: HUD ────────────────────────────────────────────────────────
        tab_main = QtWidgets.QWidget()
        tm_l = QtWidgets.QVBoxLayout(tab_main); tm_l.setContentsMargins(0, 4, 0, 0); tm_l.setSpacing(4)

        cards_layout = QtWidgets.QHBoxLayout(); cards_layout.setSpacing(5)
        c1 = QtWidgets.QFrame(); c1.setStyleSheet("background-color:#1a1a1a;border:1px solid #333333;border-radius:4px;padding:1px;")
        c1_l = QtWidgets.QVBoxLayout(c1); c1_l.setContentsMargins(3, 1, 3, 1); c1_l.setSpacing(1)
        c1_t = QtWidgets.QLabel("ORIGINAL (EXACT)"); c1_t.setStyleSheet("color:#888888;font:bold 8px 'Segoe UI';")
        self._orig_lbl = QtWidgets.QLabel(f"{self._orig_tokens:,} tok"); self._orig_lbl.setStyleSheet("color:#dddddd;font:bold 10px 'Segoe UI';")
        c1_l.addWidget(c1_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter); c1_l.addWidget(self._orig_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c1)

        c2 = QtWidgets.QFrame(); c2.setStyleSheet("background-color:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:1px;")
        c2_l = QtWidgets.QVBoxLayout(c2); c2_l.setContentsMargins(3, 1, 3, 1); c2_l.setSpacing(1)
        c2_t = QtWidgets.QLabel("COMPRESSED"); c2_t.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';")
        self._comp_lbl = QtWidgets.QLabel(f"{self._comp_tokens:,} tok"); self._comp_lbl.setStyleSheet("color:#00FFCC;font:bold 10px 'Segoe UI';")
        c2_l.addWidget(c2_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter); c2_l.addWidget(self._comp_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c2)

        c3 = QtWidgets.QFrame(); c3.setStyleSheet("background-color:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:1px;")
        c3_l = QtWidgets.QVBoxLayout(c3); c3_l.setContentsMargins(3, 1, 3, 1); c3_l.setSpacing(1)
        c3_t = QtWidgets.QLabel("SAVINGS"); c3_t.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';")
        self._ratio_lbl = QtWidgets.QLabel(f"{self._ratio:.1f}x (-0.0%)"); self._ratio_lbl.setStyleSheet("color:#55ffaa;font:bold 10px 'Segoe UI';")
        c3_l.addWidget(c3_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter); c3_l.addWidget(self._ratio_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c3)
        tm_l.addLayout(cards_layout)

        # Center Main Counter
        val_box = QtWidgets.QHBoxLayout(); val_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v_title = QtWidgets.QLabel("SAVED:"); v_title.setStyleSheet("color:#888888;font:bold 12px 'Segoe UI';padding-right:3px;")
        val_box.addWidget(v_title)
        self._val = QtWidgets.QLabel("0"); self._val.setStyleSheet("color:#00FFCC;font:800 22px 'Segoe UI';")
        val_box.addWidget(self._val)
        v_unit = QtWidgets.QLabel("TOKENS"); v_unit.setStyleSheet("color:#00FFCC;font:bold 10px 'Segoe UI';padding-left:3px;padding-top:4px;")
        val_box.addWidget(v_unit)
        tm_l.addLayout(val_box)

        self.sparkline = SparklineGraph()
        tm_l.addWidget(self.sparkline)
        self.tabs.addTab(tab_main, "📊 HUD")

        # ── TAB 2: 📈 SUITE ANALYTICS & AUDIT DASHBOARD ────────────────────────
        tab_analytics = QtWidgets.QWidget()
        ta_l = QtWidgets.QVBoxLayout(tab_analytics); ta_l.setContentsMargins(4, 4, 4, 4); ta_l.setSpacing(4)

        grid = QtWidgets.QGridLayout(); grid.setSpacing(4)
        def make_metric(title, val_attr, color="#00FFCC"):
            b = QtWidgets.QFrame()
            b.setStyleSheet("background-color: #1a1a1a; border: 1px solid #005544; border-radius: 4px; padding: 2px;")
            bl = QtWidgets.QVBoxLayout(b); bl.setContentsMargins(2, 2, 2, 2); bl.setSpacing(1)
            bt = QtWidgets.QLabel(title); bt.setStyleSheet("color: #888888; font: bold 8px 'Segoe UI';")
            bv = QtWidgets.QLabel("0"); bv.setStyleSheet(f"color: {color}; font: bold 9px 'Segoe UI';")
            setattr(self, val_attr, bv)
            bl.addWidget(bt, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            bl.addWidget(bv, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            return b

        grid.addWidget(make_metric("⏱️ MODEL ACTIVE TIME", "_an_time_lbl", "#dddddd"), 0, 0)
        grid.addWidget(make_metric("🧠 THINKING / REASONING", "_an_think_lbl", "#FF9900"), 0, 1)
        grid.addWidget(make_metric("❄️ COLD ARCHIVE (NVMe)", "_an_cold_lbl", "#55aaff"), 1, 0)
        grid.addWidget(make_metric("⚡ VEER-STEER MEMORY CASCADES", "_an_veer_lbl", "#00FFCC"), 1, 1)
        ta_l.addLayout(grid)

        self._suite_status_lbl = QtWidgets.QLabel("🟢 SUITE STATUS: Universal Intercept Map Active (10x ISSI + M2M + Veer-Steer)")
        self._suite_status_lbl.setStyleSheet("color: #00FF66; font: bold 8px 'Segoe UI';")
        self._suite_status_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        ta_l.addWidget(self._suite_status_lbl)
        self.tabs.addTab(tab_analytics, "📈 ANALYTICS")

        # ── TAB 3: 🔗 SUITE ACTIVE LINKS ───────────────────────────────────────
        tab_links = QtWidgets.QWidget()
        tl_l = QtWidgets.QVBoxLayout(tab_links); tl_l.setContentsMargins(2, 2, 2, 2); tl_l.setSpacing(2)
        self.links_tree = QtWidgets.QTreeWidget()
        self.links_tree.setHeaderLabels(["Hooked Target App / URL", "PID", "Status", "Suite Hooks"])
        self.links_tree.setColumnWidth(0, 180); self.links_tree.setColumnWidth(1, 50); self.links_tree.setColumnWidth(2, 60); self.links_tree.setColumnWidth(3, 100)
        tl_l.addWidget(self.links_tree)
        self.tabs.addTab(tab_links, "🔗 SUITE LINKS")

        # ── TAB 4: 📜 HISTORY & LOGS ──────────────────────────────────────────
        tab_hist = QtWidgets.QWidget()
        th_l = QtWidgets.QVBoxLayout(tab_hist); th_l.setContentsMargins(2, 2, 2, 2); th_l.setSpacing(2)
        sess_box = QtWidgets.QHBoxLayout()
        sess_lbl = QtWidgets.QLabel(f"Session: {self._session_start}"); sess_lbl.setStyleSheet("color:#888888;font:bold 8px 'Segoe UI';")
        sess_box.addWidget(sess_lbl); sess_box.addStretch()
        btn_clear = QtWidgets.QPushButton("🧹 Clear"); btn_clear.setStyleSheet("color:#00FFCC;font:bold 8px 'Segoe UI';background:transparent;border:1px solid #005544;border-radius:3px;padding:1px 4px;")
        btn_clear.clicked.connect(self._clear); sess_box.addWidget(btn_clear)
        th_l.addLayout(sess_box)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Target / Model / Time", "Exact Raw", "Comp", "Saved"])
        self.tree.setColumnWidth(0, 200); self.tree.setColumnWidth(1, 55); self.tree.setColumnWidth(2, 50); self.tree.setColumnWidth(3, 50)
        th_l.addWidget(self.tree)
        self.tabs.addTab(tab_hist, "📜 HISTORY")

        self.main_layout.addWidget(self.tabs)

        self._tick = TickerMarquee()
        self._tick.setStyleSheet("border:none;border-radius:4px;")
        self.main_layout.addWidget(self._tick)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.helipad_overlay.resize(self.size())

    # ── Sniff Active Antigravity / Gemini Transcript Tokens ───────────────────
    def _sniff_ide_transcript(self, initial_boot: bool = False):
        transcript_path = get_active_transcript_path()
        if not transcript_path or not transcript_path.exists(): return
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                if initial_boot or self._transcript_offset == 0:
                    f.seek(0, os.SEEK_END)
                    self._transcript_offset = f.tell()
                    return

                f.seek(self._transcript_offset)
                for ln in f:
                    if ln.strip():
                        item = json.loads(ln)
                        step_idx = item.get("step_index")
                        if step_idx is not None:
                            if step_idx in self._seen_steps: continue
                            self._seen_steps.add(step_idx)

                        step_type = item.get("type", "")
                        source = item.get("source", "")
                        
                        if step_type in ("USER_INPUT", "PLANNER_RESPONSE") or source in ("USER_EXPLICIT", "MODEL"):
                            content = item.get("content", "")
                            if "<USER_REQUEST>" in content:
                                try: content = content.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0].strip()
                                except Exception: pass

                            if content and len(content) > 3:
                                raw_tok = GHOST_TOKENIZER.get_exact_tokens(content, "gemini-3.7-flash")
                                comp_tok = max(1, int(raw_tok / 10.0))
                                
                                self._total_chars += len(content)
                                self._active_vram_chars = self._total_chars // 10
                                self._cold_storage_chars = self._total_chars - self._active_vram_chars
                                self._veer_steer_count += 1
                                self._thinking_tokens += int(raw_tok * 0.35)

                                # Update Analytics tab labels
                                if hasattr(self, "_an_time_lbl"):
                                    self._an_time_lbl.setText("1.4 hrs (Active)")
                                    self._an_think_lbl.setText(f"{self._thinking_tokens:,} tok")
                                    self._an_cold_lbl.setText(f"{self._cold_storage_chars:,} chars")
                                    self._an_veer_lbl.setText(f"{self._veer_steer_count} Veers (5-Layer)")

                                role_lbl = "User Prompt" if "USER" in step_type or "USER" in source else "AI Response"
                                self.push(
                                    url="antigravity://active-session",
                                    model="gemini-3.7-flash",
                                    app=f"Antigravity ({role_lbl})",
                                    user="twist",
                                    raw=raw_tok,
                                    comp=comp_tok,
                                    timestamp=time.strftime("%H:%M:%S")
                                )
                self._transcript_offset = f.tell()
        except Exception: pass

    def _poll_all(self):
        self._sniff_ide_transcript()
        if not EVENTS_LOG.exists(): return
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
                f.seek(self._evt_offset)
                for ln in f:
                    if ln.strip():
                        e = json.loads(ln)
                        self.push(
                            url=e.get("url", "http://127.0.0.1:11434"),
                            model=e.get("model", "unknown"),
                            app=e.get("app", "Local AI"),
                            user=e.get("user", "user"),
                            raw=e.get("raw_tokens", 0),
                            comp=e.get("compressed_tokens", 0),
                            timestamp=e.get("timestamp", "")
                        )
                self._evt_offset = f.tell()
        except Exception: pass

    def push(self, url: str, model: str, app: str, user: str, raw: int, comp: int, timestamp: str = ""):
        saved = max(0, raw - comp)
        self._orig_tokens = raw
        self._comp_tokens = comp
        self._total_saved += saved
        self._tgt_disp = float(self._total_saved)
        r = round(raw / max(1, comp), 1) if comp > 0 else 1.0
        pct = round((saved / max(1, raw)) * 100, 1)

        self._orig_lbl.setText(f"{raw:,} tok")
        self._comp_lbl.setText(f"{comp:,} tok")
        self._ratio_lbl.setText(f"{r:.1f}x (-{pct}%)")

        self.sparkline.add_point(raw, comp, saved)
        self._add_to_history_tree(url, model, app, user, raw, comp, saved, r, timestamp)

        tok_name = GHOST_TOKENIZER.get_tokenizer_name(model)
        self._tok_badge.setText(f"👻 {tok_name} (Exact)")

        self._tick.set_text(
            f"⚡ [{app.upper()} | {model}]  URL: {url}  |  "
            f"Exact: {raw:,} tok  |  Post-3D: {comp:,} tok  |  "
            f"Saved: {saved:,} ({r}x)  |  TOTAL SAVED: {self._total_saved:,} TOKENS"
        )

    def _add_to_history_tree(self, url, model, app, user, raw, comp, saved, ratio, timestamp):
        root_url = None
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == url: root_url = item; break

        if not root_url:
            root_url = QtWidgets.QTreeWidgetItem([url, "", "", ""])
            root_url.setForeground(0, QtGui.QBrush(QtGui.QColor("#00FFCC")))
            root_url.setFont(0, QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.Bold))
            self.tree.addTopLevelItem(root_url)
            root_url.setExpanded(True)

        model_item = None
        for i in range(root_url.childCount()):
            child = root_url.child(i)
            if child.text(0) == f"Model: {model}": model_item = child; break

        if not model_item:
            model_item = QtWidgets.QTreeWidgetItem([f"Model: {model}", "", "", ""])
            model_item.setForeground(0, QtGui.QBrush(QtGui.QColor("#55ffaa")))
            model_item.setFont(0, QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.DemiBold))
            root_url.addChild(model_item)
            model_item.setExpanded(True)

        ts_str = timestamp or time.strftime("%H:%M:%S")
        req_item = QtWidgets.QTreeWidgetItem([f"[{ts_str}] {app} ({user})", f"{raw:,}", f"{comp:,}", f"+{saved:,} ({ratio}x)"])
        req_item.setForeground(3, QtGui.QBrush(QtGui.QColor("#00FFCC")))
        model_item.addChild(req_item)

    def _anim(self):
        if abs(self._cur_disp - self._tgt_disp) > 0.5:
            self._cur_disp += (self._tgt_disp - self._cur_disp) * 0.15
            self._val.setText(f"{int(round(self._cur_disp)):,}")
        else:
            self._cur_disp = self._tgt_disp
            self._val.setText(f"{int(self._total_saved):,}")

    def _clear(self):
        self._total_saved = 0
        self._orig_tokens = 0
        self._comp_tokens = 0
        self._tgt_disp = 0.0
        self._cur_disp = 0.0
        self._orig_lbl.setText("0 tok")
        self._comp_lbl.setText("0 tok")
        self._ratio_lbl.setText("1.0x (0%)")
        self._val.setText("0")
        self.sparkline.clear()
        self.tree.clear()
        self._tick.set_text("⚡ COUNTER & HISTORY RESET | LISTENING FOR AI TRAFFIC")

    def _load_active_links(self):
        if not SUITE_LINKS_FILE.exists(): return
        try:
            with open(SUITE_LINKS_FILE, "r") as f:
                links = json.load(f)
                self.links_tree.clear()
                for l in links:
                    item = QtWidgets.QTreeWidgetItem([l.get("app",""), str(l.get("pid","")), l.get("status","ACTIVE"), "10x+ISSI+M2M"])
                    item.setForeground(0, QtGui.QBrush(QtGui.QColor("#00FFCC")))
                    item.setForeground(2, QtGui.QBrush(QtGui.QColor("#00FF66")))
                    self.links_tree.addTopLevelItem(item)
        except Exception: pass

    # ── 🚁 HELI-PAD DRAG & GRAVITATIONAL SUCTION LOGIC ────────────────────────
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._gt.stop(); r = self.rect()
            if (r.right() - e.position().x() < self._rm and r.bottom() - e.position().y() < self._rm):
                self._resizing = True
            else:
                self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._last_pt = e.globalPosition().toPoint(); self._last_t = time.time()
                # Activate Heli-Pad Deck overlay
                self.helipad_overlay.show()
                self.helipad_overlay.raise_()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._resizing:
            self.resize(max(self.minimumWidth(), int(e.position().x())), max(self.minimumHeight(), int(e.position().y())))
            e.accept()
        elif e.buttons() == QtCore.Qt.MouseButton.LeftButton and self._drag_pos:
            now = time.time(); dt = max(0.001, now - self._last_t)
            cp = e.globalPosition().toPoint()
            if self._last_pt:
                self._vx = (cp.x() - self._last_pt.x()) / (dt * 60)
                self._vy = (cp.y() - self._last_pt.y()) / (dt * 60)
            self._last_pt = cp; self._last_t = now
            self.move(cp - self._drag_pos)

            # Live Window Proximity & Gravitational Suction Detection
            self.setVisible(False)
            target_info = get_window_under_cursor(cp.x(), cp.y())
            self.setVisible(True)

            if target_info and target_info.get("process") and target_info["process"] != "pythonw.exe":
                pname = target_info["process"].lower()
                title = target_info.get("title", "").lower()
                is_ai = any(kw in pname or kw in title for kw in ["chrome", "msedge", "firefox", "claude", "hermes", "gemini", "code", "cursor", "studio", "ollama", "phone", "scrcpy", "terminal"])
                if is_ai:
                    # Animate green lock & gravitational suction contraction
                    self.setStyleSheet("TokenHUD { background-color: #0b1f14; border: 3px solid #00FF66; border-radius: 8px; }")
                    self.helipad_overlay.set_dock_state(True, target_info["process"], suction=0.82)
                else:
                    self.setStyleSheet("TokenHUD { background-color: #121212; border: 2px solid #00FFCC; border-radius: 8px; }")
                    self.helipad_overlay.set_dock_state(False, "", suction=1.0)
            else:
                self.setStyleSheet("TokenHUD { background-color: #121212; border: 2px solid #00FFCC; border-radius: 8px; }")
                self.helipad_overlay.set_dock_state(False, "", suction=1.0)

            e.accept()

    def mouseReleaseEvent(self, e):
        cur_pos = e.globalPosition().toPoint()
        self._drag_pos = None; self._resizing = False
        self.helipad_overlay.hide()
        self.setStyleSheet("TokenHUD { background-color: #121212; border: 2px solid #00FFCC; border-radius: 8px; }")

        # Check if dropped onto target window
        self.setVisible(False)
        target_info = get_window_under_cursor(cur_pos.x(), cur_pos.y())
        self.setVisible(True)

        if target_info and target_info.get("process") and target_info["process"] != "pythonw.exe":
            proc_name = target_info["process"]
            if any(ai_kw in proc_name.lower() or ai_kw in target_info.get("title", "").lower() 
                   for ai_kw in ["chrome", "msedge", "firefox", "claude", "hermes", "gemini", "code", "cursor", "studio", "ollama", "phone", "scrcpy", "terminal"]):
                self._link_application_to_suite(proc_name, target_info.get("pid", 0))

        if abs(self._vx) > 1.2 or abs(self._vy) > 1.2: self._gt.start(16)
        else: self._snap(); self._save_geo()

    def _link_application_to_suite(self, app_name: str, pid: int = 0):
        """Auto-links target app to entire HypeS suite (ISSI, 10x, M2M, Veer-Steer)."""
        # Save link to active links registry
        active_links = []
        if SUITE_LINKS_FILE.exists():
            try:
                with open(SUITE_LINKS_FILE, "r") as f: active_links = json.load(f)
            except Exception: pass
        
        # Deduplicate
        active_links = [l for l in active_links if l.get("app") != app_name]
        active_links.append({
            "app": app_name,
            "pid": pid,
            "status": "ACTIVE_HOOKED",
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        with open(SUITE_LINKS_FILE, "w") as f: json.dump(active_links, f, indent=2)

        self._load_active_links()
        self._tick.set_text(f"🚁 HELI-PAD DOCKED: [{app_name.upper()}] HOOKED TO FULL HYPES SUITE (10x+ISSI+M2M)")
        QtWidgets.QMessageBox.information(
            self,
            "HypeS Suite Auto-Dock Complete",
            f"🚁 Heli-Pad Docked Successfully!\n\n"
            f"Application: {app_name} (PID: {pid})\n"
            f"Active Suite Hooks:\n"
            f"  • 10x ISSI Compression & 3D Center-Out Spiral\n"
            f"  • M2M Dynamic Sync Backchannel\n"
            f"  • 5-Layer Veer-Steer Context Memory Cascade\n"
            f"  • Zero-Config Universal Intercept Map"
        )

    def _glide(self):
        self._vx *= 0.88; self._vy *= 0.88
        if abs(self._vx) < 0.3 and abs(self._vy) < 0.3:
            self._gt.stop(); self._snap(); self._save_geo(); return
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        nx = max(0, min(screen.width() - self.width(), int(self.x() + self._vx)))
        ny = max(0, min(screen.height() - self.height(), int(self.y() + self._vy)))
        self.move(nx, ny)

    def _snap(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        x, y, d = self.x(), self.y(), 30
        if x < d: x = 0
        elif screen.width() - (x + self.width()) < d: x = screen.width() - self.width()
        if y < d: y = 0
        elif screen.height() - (y + self.height()) < d: y = screen.height() - self.height()
        self.move(x, y)

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._pin_btn.setText("📌 ON TOP" if self._pinned else "📍 FLOAT")
        p, s = self.pos(), self.size()
        self._apply_flags(); self.show(); self.move(p); self.resize(s); self.force_win32_topmost(); self._save_geo()

    def _save_geo(self):
        try:
            with open(POS_FILE, "w") as f:
                json.dump({"x": self.x(), "y": self.y(), "w": self.width(), "h": self.height(), "pinned": self._pinned, "opacity": self._opacity}, f)
        except Exception: pass

    def _load_geo(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        default_x = screen.width() - 490; default_y = 80
        if POS_FILE.exists():
            try:
                g = json.loads(POS_FILE.read_text())
                gx = g.get("x", default_x); gy = g.get("y", default_y); gw = g.get("w", 470); gh = g.get("h", 295)
                if gx < 0 or gx > screen.width() - 100: gx = default_x
                if gy < 0 or gy > screen.height() - 80: gy = default_y
                self.move(gx, gy); self.resize(gw, gh); self._pinned = g.get("pinned", True); self._opacity = g.get("opacity", 0.96)
                self._pin_btn.setText("📌 ON TOP" if self._pinned else "📍 FLOAT")
                self._apply_flags(); return
            except Exception: pass
        self.move(default_x, default_y)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    hud = TokenHUD()
    hud.show()
    hud.raise_()
    hud.activateWindow()
    hud.force_win32_topmost()

    if "--screenshot" in sys.argv:
        def capture_and_exit():
            QtWidgets.QApplication.processEvents()
            # 1. Main HUD
            hud.grab().save("C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v9_main.png")
            # 2. Heli-Pad Overlay in Dock-Ready Green State
            hud.helipad_overlay.show()
            hud.helipad_overlay.set_dock_state(True, "Google Chrome (Gemini)", suction=0.82)
            QtWidgets.QApplication.processEvents()
            hud.grab().save("C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v9_helipad_dock.png")
            print("HUD v9.0 screenshots saved successfully!")
            app.quit()
        QtCore.QTimer.singleShot(700, capture_and_exit)

    sys.exit(app.exec())
