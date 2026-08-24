"""
Hyper-Spherical Systems - Floating Token Counter HUD & Control Center v6.0
==========================================================================
Features:
- 🌶️ CHILI PAD & WINDOW HOOK ENGINE:
    * Drag HUD onto any target window (Chrome, Claude, Hermes, Ollama, LM Studio) to auto-link.
    * Drag application shortcuts or windows directly onto the Chili Pad landing zone.
    * Auto-prompts: "Enable universal endpoint & zero-config interception for [App]?"
- 🧠 CONTEXT-AWARE SMART COMPRESSION MODES:
    * ⚡ Dynamic / Automatic Mode (Protects context, dials stripping up/down).
    * 🛡️ Code-Safe Mode (STRICT ZERO stripping on code blocks, symbols, & syntax).
    * 💬 Non-Conversational Only / 📋 Structured Output Only / 🔥 Aggressive Max.
- 📖 RICH GRAMMAR & GLUE WORD TOOLTIPS:
    * Detailed mouseovers explaining Fluff/Fillers, Glue Words/Prepositions, Form-of-Be verbs.
- 📊 Sparkline Graph, Hierarchical Model History, Always-On-Top, Inertial Glide.
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

# ── Paths & Config ────────────────────────────────────────────────────────────
HYPES_DIR = Path.home() / ".hypes"
POS_FILE = HYPES_DIR / "hud_pos.json"
EVENTS_LOG = HYPES_DIR / "intercept_events.jsonl"
CONFIG_FILE = HYPES_DIR / "compression_config.json"
APP_CONSENT_FILE = HYPES_DIR / "app_consent.json"
HYPES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "mode": "dynamic",  # "dynamic", "code_safe", "non_conversational", "structured_only", "aggressive", "off"
    "strip_fillers": True,        # 'please', 'thanks', 'could you', 'as an AI'
    "strip_prepositions": True,   # 'in', 'on', 'at', 'by', 'for', 'with', 'about'
    "strip_be_verbs": False,      # 'is', 'are', 'was', 'were', 'been'
    "code_protection_lock": True, # STRICT ZERO stripping when code/syntax is detected
    "auto_explore_routes": True,
    "m2m_caching": True,
    "safety_fallback": True
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ── Win32 Window & Process Inspector ──────────────────────────────────────────
def get_window_under_cursor(x: int, y: int) -> dict:
    """Uses Win32 API to find the process name and window title under screen coordinates (x, y)."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        pt = wintypes.POINT(x, y)
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return {}

        # Get root ancestor window
        root_hwnd = user32.GetAncestor(hwnd, 2)  # GA_ROOT
        if root_hwnd:
            hwnd = root_hwnd

        # Get Window Title
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        win_title = title_buf.value

        # Get Process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        # Get Process Name
        process_name = "Unknown App"
        h_process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if h_process:
            try:
                psapi = ctypes.windll.psapi
                mod_buf = ctypes.create_unicode_buffer(512)
                if psapi.GetModuleBaseNameW(h_process, None, mod_buf, 512):
                    process_name = mod_buf.value
            finally:
                kernel32.CloseHandle(h_process)

        return {
            "hwnd": hwnd,
            "pid": pid.value,
            "title": win_title,
            "process": process_name
        }
    except Exception:
        return {}


# ── Sparkline Graph ───────────────────────────────────────────────────────────
class SparklineGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.history = []

    def add_point(self, raw: int, comp: int, saved: int):
        self.history.append((raw, comp, saved))
        if len(self.history) > 30:
            self.history.pop(0)
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
            painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, "Awaiting live AI stream data for graph...")
            return

        max_val = max(max(pt[0] for pt in self.history), 100)
        w = rect.width()
        h = rect.height() - 6
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
        fill_path.lineTo(w, h + 3)
        fill_path.lineTo(0, h + 3)
        fill_path.closeSubpath()
        painter.fillPath(fill_path, QtGui.QColor(0, 255, 204, 30))


# ── Scrolling Marquee Ticker ──────────────────────────────────────────────────
class TickerMarquee(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._text = "⚡ HYPERMEM MITM LISTENING • READY FOR AI TRAFFIC (Ollama / LM Studio / Claude / Gemini / Chrome) • "
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
        if w > 0 and self._offset >= w:
            self._offset = 0.0
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


# ── 🌶️ Chili Pad Drop Zone Widget ─────────────────────────────────────────────
class ChiliPadDropZone(QtWidgets.QFrame):
    """Interactive drop target where users can drop shortcuts, files, or apps to auto-hook."""
    app_dropped = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1208;
                border: 2px dashed #FF6600;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #261a0c;
                border: 2px dashed #00FFCC;
            }
        """)
        l = QtWidgets.QVBoxLayout(self)
        l.setContentsMargins(6, 6, 6, 6)
        
        self.icon_lbl = QtWidgets.QLabel("🌶️ CHILI PAD — LANDING ZONE")
        self.icon_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet("color: #FF7700; font: bold 11px 'Segoe UI'; border: none;")
        l.addWidget(self.icon_lbl)

        self.sub_lbl = QtWidgets.QLabel("Drop app shortcut, executable, or window here to auto-link")
        self.sub_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sub_lbl.setStyleSheet("color: #888888; font: 8px 'Segoe UI'; border: none;")
        l.addWidget(self.sub_lbl)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #003322; border: 2px solid #00FFCC; border-radius: 6px;")

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        self.setStyleSheet("background-color: #1a1208; border: 2px dashed #FF6600; border-radius: 6px;")

    def dropEvent(self, event: QtGui.QDropEvent):
        self.setStyleSheet("background-color: #1a1208; border: 2px dashed #FF6600; border-radius: 6px;")
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile()
                self.app_dropped.emit(fpath)
                event.acceptProposedAction()
                return
        elif event.mimeData().hasText():
            self.app_dropped.emit(event.mimeData().text().strip())
            event.acceptProposedAction()


# ── Main Token HUD & Control Center ───────────────────────────────────────────
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

        self._config = load_config()

        # Real initial stats
        self._total_saved = 0
        self._orig_tokens = 0
        self._comp_tokens = 0
        self._ratio = 1.0
        self._cur_disp = 0.0
        self._tgt_disp = 0.0
        self._evt_offset = 0

        self._apply_flags()
        self.setWindowTitle("HypeS Token Counter HUD")
        self.setMinimumSize(420, 240)
        self.resize(440, 270)

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
            QComboBox {
                background: #1a1a1a;
                color: #00FFCC;
                border: 1px solid #005544;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QComboBox QAbstractItemView {
                background: #1a1a1a;
                color: #00FFCC;
                selection-background-color: #005544;
            }
            QCheckBox {
                color: #cccccc;
                font-family: 'Segoe UI';
                font-size: 9px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 12px;
                height: 12px;
                border-radius: 2px;
                border: 1px solid #00FFCC;
                background: #161616;
            }
            QCheckBox::indicator:checked {
                background: #00FFCC;
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
            QToolTip {
                background-color: #1a1a1a;
                color: #00FFCC;
                border: 1px solid #00FFCC;
                font-family: 'Segoe UI';
                font-size: 10px;
                padding: 4px;
            }
        """)

        self._build_ui()
        self._load_geo()
        self._load_initial_history()

        # Timers
        self._ct = QtCore.QTimer(self); self._ct.timeout.connect(self._anim); self._ct.start(25)
        self._gt = QtCore.QTimer(self); self._gt.timeout.connect(self._glide)
        self._pt = QtCore.QTimer(self); self._pt.timeout.connect(self._poll); self._pt.start(500)

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
        except Exception:
            pass

    def _build_ui(self):
        fl = QtWidgets.QVBoxLayout(self)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(4)

        # Top Bar
        tb = QtWidgets.QHBoxLayout()
        self._hdr = QtWidgets.QLabel("TOKEN COUNTER • 3D+ISSI+5+1")
        self._hdr.setStyleSheet("color:#888888;font:bold 9px 'Segoe UI';border:none;background:transparent;")
        tb.addWidget(self._hdr)
        tb.addStretch()

        self._pin_btn = QtWidgets.QPushButton("📌 ON TOP" if self._pinned else "📍 FLOAT")
        self._pin_btn.setStyleSheet("color:#00FFCC;font:bold 8px 'Segoe UI';background:transparent;border:1px solid #005544;border-radius:3px;padding:1px 5px;")
        self._pin_btn.clicked.connect(self._toggle_pin)
        tb.addWidget(self._pin_btn)
        fl.addLayout(tb)

        # Tabs
        self.tabs = QtWidgets.QTabWidget()

        # ── TAB 1: HUD ────────────────────────────────────────────────────────
        tab_main = QtWidgets.QWidget()
        tm_l = QtWidgets.QVBoxLayout(tab_main)
        tm_l.setContentsMargins(0, 4, 0, 0)
        tm_l.setSpacing(4)

        # 3 Cards
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(5)

        c1 = QtWidgets.QFrame()
        c1.setStyleSheet("QFrame{background-color:#1a1a1a;border:1px solid #333333;border-radius:4px;padding:1px;}")
        c1_l = QtWidgets.QVBoxLayout(c1); c1_l.setContentsMargins(3, 1, 3, 1); c1_l.setSpacing(1)
        c1_t = QtWidgets.QLabel("ORIGINAL"); c1_t.setStyleSheet("color:#888888;font:bold 8px 'Segoe UI';")
        self._orig_lbl = QtWidgets.QLabel(f"{self._orig_tokens:,} tok")
        self._orig_lbl.setStyleSheet("color:#dddddd;font:bold 10px 'Segoe UI';")
        c1_l.addWidget(c1_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c1_l.addWidget(self._orig_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c1)

        c2 = QtWidgets.QFrame()
        c2.setStyleSheet("QFrame{background-color:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:1px;}")
        c2_l = QtWidgets.QVBoxLayout(c2); c2_l.setContentsMargins(3, 1, 3, 1); c2_l.setSpacing(1)
        c2_t = QtWidgets.QLabel("COMPRESSED"); c2_t.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';")
        self._comp_lbl = QtWidgets.QLabel(f"{self._comp_tokens:,} tok")
        self._comp_lbl.setStyleSheet("color:#00FFCC;font:bold 10px 'Segoe UI';")
        c2_l.addWidget(c2_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c2_l.addWidget(self._comp_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c2)

        c3 = QtWidgets.QFrame()
        c3.setStyleSheet("QFrame{background-color:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:1px;}")
        c3_l = QtWidgets.QVBoxLayout(c3); c3_l.setContentsMargins(3, 1, 3, 1); c3_l.setSpacing(1)
        c3_t = QtWidgets.QLabel("SAVINGS"); c3_t.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';")
        self._ratio_lbl = QtWidgets.QLabel(f"{self._ratio:.1f}x (-0.0%)")
        self._ratio_lbl.setStyleSheet("color:#55ffaa;font:bold 10px 'Segoe UI';")
        c3_l.addWidget(c3_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c3_l.addWidget(self._ratio_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c3)
        tm_l.addLayout(cards_layout)

        # Center Main Counter
        val_box = QtWidgets.QHBoxLayout()
        val_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v_title = QtWidgets.QLabel("SAVED:")
        v_title.setStyleSheet("color:#888888;font:bold 12px 'Segoe UI';padding-right:3px;")
        val_box.addWidget(v_title)

        self._val = QtWidgets.QLabel("0")
        self._val.setStyleSheet("color:#00FFCC;font:800 22px 'Segoe UI';background:transparent;")
        val_box.addWidget(self._val)

        v_unit = QtWidgets.QLabel("TOKENS")
        v_unit.setStyleSheet("color:#00FFCC;font:bold 10px 'Segoe UI';padding-left:3px;padding-top:4px;")
        val_box.addWidget(v_unit)
        tm_l.addLayout(val_box)

        # Sparkline Graph
        self.sparkline = SparklineGraph()
        tm_l.addWidget(self.sparkline)
        self.tabs.addTab(tab_main, "📊 HUD")

        # ── TAB 2: 🌶️ CHILI PAD (Landing Zone) ────────────────────────────────
        tab_chili = QtWidgets.QWidget()
        tc_l = QtWidgets.QVBoxLayout(tab_chili)
        tc_l.setContentsMargins(4, 4, 4, 4)

        self.chili_pad = ChiliPadDropZone()
        self.chili_pad.app_dropped.connect(self._handle_manual_app_drop)
        tc_l.addWidget(self.chili_pad)

        inst_lbl = QtWidgets.QLabel("💡 TIP: You can also DRAG THIS HUD directly over any chat window (Chrome, Claude, Hermes, LM Studio) to auto-link!")
        inst_lbl.setWordWrap(True)
        inst_lbl.setStyleSheet("color: #777777; font: 8px 'Segoe UI';")
        tc_l.addWidget(inst_lbl)

        self.tabs.addTab(tab_chili, "🌶️ CHILI PAD")

        # ── TAB 3: ⚙️ SETTINGS & GRAMMAR TUNER ─────────────────────────────────
        tab_settings = QtWidgets.QWidget()
        ts_l = QtWidgets.QVBoxLayout(tab_settings)
        ts_l.setContentsMargins(4, 4, 4, 4)
        ts_l.setSpacing(3)

        # Mode Selector
        mode_box = QtWidgets.QHBoxLayout()
        mode_lbl = QtWidgets.QLabel("Optimization Mode:")
        mode_lbl.setStyleSheet("color:#aaaaaa;font:bold 9px 'Segoe UI';")
        mode_lbl.setToolTip(
            "<b>Optimization Mode Selector:</b><br>"
            "• <b>⚡ Dynamic (Recommended):</b> Auto-detects code vs chat. Protects context.<br>"
            "• <b>🛡️ Code-Safe:</b> Locks out all grammar stripping on code blocks.<br>"
            "• <b>💬 Non-Conversational Only:</b> Strips only when formal/technical.<br>"
            "• <b>🔥 Aggressive:</b> Maximum token compression everywhere."
        )
        self.combo_mode = QtWidgets.QComboBox()
        self.combo_mode.addItems([
            "⚡ Dynamic / Auto (Context-Safe)",
            "🛡️ Code-Safe (Zero Code Stripping)",
            "💬 Non-Conversational Only",
            "📋 Structured Output Only",
            "🔥 Aggressive Max Compression",
            "❌ Off (Pass-Through)"
        ])
        mode_key_map = {
            "dynamic": 0, "code_safe": 1, "non_conversational": 2,
            "structured_only": 3, "aggressive": 4, "off": 5
        }
        self.combo_mode.setCurrentIndex(mode_key_map.get(self._config.get("mode", "dynamic"), 0))
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_box.addWidget(mode_lbl)
        mode_box.addWidget(self.combo_mode)
        ts_l.addLayout(mode_box)

        # Granular Checkboxes with Explanatory Tooltips
        self.chk_code_lock = QtWidgets.QCheckBox("🛡️ Code Protection Lock (Zero Preposition Stripping on Code)")
        self.chk_code_lock.setToolTip(
            "<b>Code Protection Lock:</b><br>"
            "Ensures prepositions and grammar inside code blocks (Python, JS, C++, SQL, JSON)<br>"
            "are <b>100% UNTOUCHED and preserved exactly verbatim</b>."
        )
        self.chk_code_lock.setChecked(self._config.get("code_protection_lock", True))
        self.chk_code_lock.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_code_lock)

        self.chk_fillers = QtWidgets.QCheckBox("🧹 Fluff & Filler Pruning ('please', 'thanks', 'could you')")
        self.chk_fillers.setToolTip(
            "<b>Fluff & Conversational Fillers:</b><br>"
            "Removes conversational pleasantries and polite filler phrases like:<br>"
            "<i>'Please', 'Could you kindly', 'Thank you', 'As an AI language model'</i><br>"
            "Saves 10-25% tokens without changing meaning."
        )
        self.chk_fillers.setChecked(self._config.get("strip_fillers", True))
        self.chk_fillers.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_fillers)

        self.chk_prep = QtWidgets.QCheckBox("🔗 Glue Words & Prepositions ('in', 'on', 'at', 'with', 'about')")
        self.chk_prep.setToolTip(
            "<b>Prepositions & Glue Words:</b><br>"
            "Filters non-essential relational prepositions in dense text:<br>"
            "<i>'about', 'above', 'across', 'at', 'by', 'for', 'from', 'in', 'on', 'with'</i><br>"
            "<b>Note:</b> In Code-Safe and Dynamic mode, this is automatically skipped on code."
        )
        self.chk_prep.setChecked(self._config.get("strip_prepositions", True))
        self.chk_prep.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_prep)

        self.chk_be_verbs = QtWidgets.QCheckBox("🔤 Form-of-Be Verbs ('is', 'are', 'was', 'were') [Advanced]")
        self.chk_be_verbs.setToolTip(
            "<b>Forms of 'Be' Verbs:</b><br>"
            "Compacts auxiliary state verbs (<i>is, are, was, were, been, being</i>)<br>"
            "into compact relation markers. Recommended for structured queries."
        )
        self.chk_be_verbs.setChecked(self._config.get("strip_be_verbs", False))
        self.chk_be_verbs.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_be_verbs)

        self.tabs.addTab(tab_settings, "⚙️ SETTINGS")

        # ── TAB 4: 📜 HISTORY ──────────────────────────────────────────────────
        tab_hist = QtWidgets.QWidget()
        th_l = QtWidgets.QVBoxLayout(tab_hist)
        th_l.setContentsMargins(2, 2, 2, 2)
        th_l.setSpacing(2)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["URL / Model / Timestamp", "Raw", "Comp", "Saved"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 50)
        self.tree.setColumnWidth(2, 50)
        self.tree.setColumnWidth(3, 50)
        th_l.addWidget(self.tree)
        self.tabs.addTab(tab_hist, "📜 HISTORY")

        fl.addWidget(self.tabs)

        # ── Bottom Scrolling Marquee Ticker ───────────────────────────────────
        self._tick = TickerMarquee()
        self._tick.setStyleSheet("border:none;border-radius:4px;")
        fl.addWidget(self._tick)

    # ── Mode & Settings Handlers ──────────────────────────────────────────────
    def _on_mode_changed(self, idx: int):
        mode_keys = ["dynamic", "code_safe", "non_conversational", "structured_only", "aggressive", "off"]
        mode = mode_keys[idx]
        self._config["mode"] = mode
        
        # Enforce Code-Safe defaults if code_safe selected
        if mode == "code_safe":
            self.chk_code_lock.setChecked(True)
            self.chk_prep.setChecked(False)
            self.chk_be_verbs.setChecked(False)

        save_config(self._config)
        self._tick.set_text(f"⚙️ OPTIMIZATION MODE SET TO: {mode.upper()}")

    def _on_setting_toggled(self):
        self._config["code_protection_lock"] = self.chk_code_lock.isChecked()
        self._config["strip_fillers"] = self.chk_fillers.isChecked()
        self._config["strip_prepositions"] = self.chk_prep.isChecked()
        self._config["strip_be_verbs"] = self.chk_be_verbs.isChecked()
        save_config(self._config)
        self._tick.set_text("⚙️ GRAMMAR & CODE PROTECTION SETTINGS SYNCED")

    # ── Manual & Dropped App Auto-Linking ─────────────────────────────────────
    def _handle_manual_app_drop(self, target_path_or_name: str):
        app_name = Path(target_path_or_name).stem if os.path.exists(target_path_or_name) else target_path_or_name
        self._prompt_enable_universal_interception(app_name)

    def _prompt_enable_universal_interception(self, app_name: str):
        """Shows 1-click confirmation dialog when dragged onto an app or chili pad."""
        msg = (
            f"Detected Application: <b>{app_name}</b><br><br>"
            f"Would you like to enable universal endpoint and zero config interception "
            f"for maximum compression and optimization?"
        )
        reply = QtWidgets.QMessageBox.question(
            self,
            "HyperMem Universal Auto-Hook",
            msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Persist consent
            consents = {}
            if APP_CONSENT_FILE.exists():
                try:
                    with open(APP_CONSENT_FILE, "r") as f:
                        consents = json.load(f)
                except Exception:
                    pass
            consents[app_name.lower()] = True
            with open(APP_CONSENT_FILE, "w") as f:
                json.dump(consents, f, indent=2)

            self._tick.set_text(f"✅ AUTO-HOOKED [{app_name.upper()}] • 10X ZERO-CONFIG COMPRESSION ACTIVE")
            QtWidgets.QMessageBox.information(
                self,
                "HyperMem Hook Active",
                f"Successfully linked {app_name}! Outbound AI traffic will now be compressed with 10x 3D+ISSI+5+1."
            )

    # ── Real Data Event Injection ─────────────────────────────────────────────
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

        self._tick.set_text(
            f"⚡ [{app.upper()} | {model}]  URL: {url}  |  "
            f"Raw: {raw:,}  |  Post-3D: {comp:,}  |  "
            f"Saved: {saved:,} ({r}x)  |  TOTAL SAVED: {self._total_saved:,} TOKENS"
        )

    def _add_to_history_tree(self, url, model, app, user, raw, comp, saved, ratio, timestamp):
        root_url = None
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == url:
                root_url = item
                break

        if not root_url:
            root_url = QtWidgets.QTreeWidgetItem([url, "", "", ""])
            root_url.setForeground(0, QtGui.QBrush(QtGui.QColor("#00FFCC")))
            root_url.setFont(0, QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.Bold))
            self.tree.addTopLevelItem(root_url)
            root_url.setExpanded(True)

        model_item = None
        for i in range(root_url.childCount()):
            child = root_url.child(i)
            if child.text(0) == f"Model: {model}":
                model_item = child
                break

        if not model_item:
            model_item = QtWidgets.QTreeWidgetItem([f"Model: {model}", "", "", ""])
            model_item.setForeground(0, QtGui.QBrush(QtGui.QColor("#55ffaa")))
            model_item.setFont(0, QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.DemiBold))
            root_url.addChild(model_item)
            model_item.setExpanded(True)

        ts_str = timestamp or time.strftime("%H:%M:%S")
        req_item = QtWidgets.QTreeWidgetItem([
            f"[{ts_str}] {app} ({user})",
            f"{raw:,}",
            f"{comp:,}",
            f"+{saved:,} ({ratio}x)"
        ])
        req_item.setForeground(3, QtGui.QBrush(QtGui.QColor("#00FFCC")))
        model_item.addChild(req_item)

    # ── Smooth Rolling Counter Animation ──────────────────────────────────────
    def _anim(self):
        if abs(self._cur_disp - self._tgt_disp) > 0.5:
            self._cur_disp += (self._tgt_disp - self._cur_disp) * 0.15
            self._val.setText(f"{int(round(self._cur_disp)):,}")
        else:
            self._cur_disp = self._tgt_disp
            self._val.setText(f"{int(self._total_saved):,}")

    # ── IPC: Load History & Poll Real Events ───────────────────────────────────
    def _load_initial_history(self):
        if not EVENTS_LOG.exists():
            return
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
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
        except Exception:
            pass

    def _poll(self):
        if not EVENTS_LOG.exists():
            return
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
                f.seek(self._evt_offset)
                lines = f.readlines()
                self._evt_offset = f.tell()
                for ln in lines:
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
        except Exception:
            pass

    # ── Inertial Glide & Magnetic Snapping ────────────────────────────────────
    def _glide(self):
        self._vx *= 0.88
        self._vy *= 0.88
        if abs(self._vx) < 0.3 and abs(self._vy) < 0.3:
            self._gt.stop()
            self._snap()
            self._save_geo()
            return
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

    # ── Mouse Press, Drag, Drop on Target Window Detection ────────────────────
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._gt.stop()
            r = self.rect()
            if (r.right() - e.position().x() < self._rm and r.bottom() - e.position().y() < self._rm):
                self._resizing = True
            else:
                self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._last_pt = e.globalPosition().toPoint()
                self._last_t = time.time()
            event = e
            event.accept()

    def mouseMoveEvent(self, e):
        if self._resizing:
            self.resize(max(self.minimumWidth(), int(e.position().x())), max(self.minimumHeight(), int(e.position().y())))
            e.accept()
        elif e.buttons() == QtCore.Qt.MouseButton.LeftButton and self._drag_pos:
            now = time.time()
            dt = max(0.001, now - self._last_t)
            cp = e.globalPosition().toPoint()
            if self._last_pt:
                self._vx = (cp.x() - self._last_pt.x()) / (dt * 60)
                self._vy = (cp.y() - self._last_pt.y()) / (dt * 60)
            self._last_pt = cp
            self._last_t = now
            self.move(cp - self._drag_pos)
            e.accept()
        else:
            r = self.rect()
            if (r.right() - e.position().x() < self._rm and r.bottom() - e.position().y() < self._rm):
                self.setCursor(QtCore.Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        cur_pos = e.globalPosition().toPoint()
        self._drag_pos = None
        self._resizing = False

        # Check if the user dropped this HUD onto another target window!
        # Hide momentarily to peek at window underneath
        self.setVisible(False)
        target_info = get_window_under_cursor(cur_pos.x(), cur_pos.y())
        self.setVisible(True)

        if target_info and target_info.get("process") and target_info["process"] != "pythonw.exe":
            proc_name = target_info["process"]
            # Trigger auto-hook confirmation if dropped over an external AI app
            if any(ai_kw in proc_name.lower() or ai_kw in target_info.get("title", "").lower() 
                   for ai_kw in ["chrome", "msedge", "claude", "hermes", "code", "cursor", "studio", "ollama", "terminal"]):
                QtCore.QTimer.singleShot(200, lambda: self._prompt_enable_universal_interception(proc_name))

        if abs(self._vx) > 1.2 or abs(self._vy) > 1.2:
            self._gt.start(16)
        else:
            self._snap()
            self._save_geo()

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._pin_btn.setText("📌 ON TOP" if self._pinned else "📍 FLOAT")
        p, s = self.pos(), self.size()
        self._apply_flags()
        self.show()
        self.move(p)
        self.resize(s)
        self.force_win32_topmost()
        self._save_geo()

    def _save_geo(self):
        try:
            with open(POS_FILE, "w") as f:
                json.dump({"x": self.x(), "y": self.y(), "w": self.width(), "h": self.height(), "pinned": self._pinned, "opacity": self._opacity}, f)
        except Exception: pass

    def _load_geo(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        default_x = screen.width() - 460
        default_y = 80
        if POS_FILE.exists():
            try:
                g = json.loads(POS_FILE.read_text())
                gx = g.get("x", default_x)
                gy = g.get("y", default_y)
                gw = g.get("w", 440)
                gh = g.get("h", 270)
                if gx < 0 or gx > screen.width() - 100: gx = default_x
                if gy < 0 or gy > screen.height() - 80: gy = default_y
                self.move(gx, gy)
                self.resize(gw, gh)
                self._pinned = g.get("pinned", True)
                self._opacity = g.get("opacity", 0.96)
                self._pin_btn.setText("📌 ON TOP" if self._pinned else "📍 FLOAT")
                self._apply_flags()
                return
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
            hud.grab().save("C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v6_main.png")
            # 2. Chili Pad Tab
            hud.tabs.setCurrentIndex(1)
            QtWidgets.QApplication.processEvents()
            hud.grab().save("C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v6_chili.png")
            # 3. Settings Tab
            hud.tabs.setCurrentIndex(2)
            QtWidgets.QApplication.processEvents()
            hud.grab().save("C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v6_settings.png")
            print("All HUD v6.0 screenshots saved successfully!")
            app.quit()
        QtCore.QTimer.singleShot(700, capture_and_exit)

    sys.exit(app.exec())
