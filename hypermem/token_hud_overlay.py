"""
Hyper-Spherical Systems - Floating Token Counter HUD & Control Center v5.0
==========================================================================
Features:
- Pure real data (ZERO mock/dummy data on startup; clean 0 state or true IPC log).
- 3 Tabs / Views:
    1. [MAIN HUD]: 3-Card Metrics, Large Rolling Counter, Sparkline Trend Graph, Live Ticker.
    2. [⚙️ SETTINGS]: Preposition Aggressiveness Slider, Verb/Syntax Compaction, Conversational Mode, Safety Fallbacks.
    3. [📜 HISTORY]: Hierarchical Tree of Intercepted URLs -> Models -> Token Breakdowns.
- Always-On-Top, Frameless, Inertial Glide Physics, Magnetic Edge Snapping.
- Live Bidirectional IPC: Reads ~/.hypes/intercept_events.jsonl & writes ~/.hypes/compression_config.json.
"""

import sys
import os
import json
import time
import math
import ctypes
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets

# ── Paths & Configuration ─────────────────────────────────────────────────────
HYPES_DIR = Path.home() / ".hypes"
POS_FILE = HYPES_DIR / "hud_pos.json"
EVENTS_LOG = HYPES_DIR / "intercept_events.jsonl"
CONFIG_FILE = HYPES_DIR / "compression_config.json"
HYPES_DIR.mkdir(parents=True, exist_ok=True)

# Default Compression Config
DEFAULT_CONFIG = {
    "preposition_stripping": "standard",  # "off", "light", "standard", "aggressive"
    "v_verbs_optimization": True,
    "syntax_compaction": True,
    "conversational_filter": True,
    "auto_explore_routes": True,
    "safety_fallback_threshold": 0.98,
    "drop_fillers": True,
    "m2m_caching": True
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ── Mini Sparkline / Token Graph Widget ───────────────────────────────────────
class SparklineGraph(QtWidgets.QWidget):
    """Draws a live neon-cyan area chart of recent token compression events."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.history = []  # list of (raw, comp, saved)

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
        painter.fillRect(rect, QtGui.QColor(20, 20, 20))

        # Subtle grid lines
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 1, QtCore.Qt.PenStyle.DotLine))
        painter.drawLine(0, rect.height() // 2, rect.width(), rect.height() // 2)

        if not self.history or len(self.history) < 2:
            painter.setFont(QtGui.QFont("Segoe UI", 8))
            painter.setPen(QtGui.QColor(80, 80, 80))
            painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, "Awaiting live AI stream data for graph...")
            return

        max_val = max(max(pt[0] for pt in self.history), 100)
        w = rect.width()
        h = rect.height() - 6
        step = w / max(1, len(self.history) - 1)

        # Build Points for Raw (dim gray) and Saved (neon cyan)
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

        # Draw Raw line
        painter.setPen(QtGui.QPen(QtGui.QColor(100, 100, 100), 1))
        painter.drawPath(raw_path)

        # Draw Saved area + line
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 204), 2))
        painter.drawPath(saved_path)

        # Fill under saved curve
        fill_path = QtGui.QPainterPath(saved_path)
        fill_path.lineTo(w, h + 3)
        fill_path.lineTo(0, h + 3)
        fill_path.closeSubpath()
        painter.fillPath(fill_path, QtGui.QColor(0, 255, 204, 30))


# ── Scrolling Marquee Ticker ──────────────────────────────────────────────────
class TickerMarquee(QtWidgets.QWidget):
    """Smooth horizontal marquee scrolling active URL, Model, Tokens, and compression stats."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._text = "⚡ HYPERMEM MITM LISTENING • READY FOR AI TRAFFIC (Ollama / LM Studio / OpenAI / Cursor) • "
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


# ── Main Multi-Tab Token Counter Window ───────────────────────────────────────
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

        # Real initial stats (zeroed unless real history log exists)
        self._total_saved = 0
        self._orig_tokens = 0
        self._comp_tokens = 0
        self._ratio = 1.0
        self._cur_disp = 0.0
        self._tgt_disp = 0.0
        self._evt_offset = 0
        self._history_records = []  # list of dicts

        self._apply_flags()
        self.setWindowTitle("HypeS Token Counter HUD")
        self.setMinimumSize(380, 200)
        self.resize(400, 225)

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
                background: #1e1e1e;
                color: #888888;
                font-family: 'Segoe UI';
                font-size: 10px;
                font-weight: bold;
                padding: 4px 10px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #00FFCC;
                color: #121212;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #333333;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #00FFCC;
                border: 1px solid #ffffff;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QCheckBox {
                color: #cccccc;
                font-family: 'Segoe UI';
                font-size: 10px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border-radius: 2px;
                border: 1px solid #00FFCC;
                background: #1a1a1a;
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
                font-size: 10px;
            }
            QTreeWidget::item:selected {
                background-color: #005544;
                color: #00FFCC;
            }
            QHeaderView::section {
                background-color: #202020;
                color: #00FFCC;
                padding: 2px;
                font-size: 9px;
                border: none;
            }
        """)

        self._build_ui()
        self._load_geo()
        self._load_initial_history()

        # Rolling counter animation
        self._ct = QtCore.QTimer(self)
        self._ct.timeout.connect(self._anim)
        self._ct.start(25)

        # Inertial glide physics
        self._gt = QtCore.QTimer(self)
        self._gt.timeout.connect(self._glide)

        # IPC event poll from auto_interceptor
        self._pt = QtCore.QTimer(self)
        self._pt.timeout.connect(self._poll)
        self._pt.start(500)

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

        # ── Header Title + Status Bar ─────────────────────────────────────────
        tb = QtWidgets.QHBoxLayout()
        self._hdr = QtWidgets.QLabel("TOKEN COUNTER • 3D+ISSI+5+1")
        self._hdr.setStyleSheet("color:#888888;font:bold 9px 'Segoe UI';border:none;background:transparent;")
        tb.addWidget(self._hdr)
        tb.addStretch()

        self._pin_btn = QtWidgets.QPushButton("📌 ON TOP" if self._pinned else "📍 FLOAT")
        self._pin_btn.setStyleSheet("""
            QPushButton {
                color: #00FFCC;
                font: bold 8px 'Segoe UI';
                background: transparent;
                border: 1px solid #005544;
                border-radius: 3px;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background: #003322;
            }
        """)
        self._pin_btn.clicked.connect(self._toggle_pin)
        tb.addWidget(self._pin_btn)
        fl.addLayout(tb)

        # ── Tabbed Widget ─────────────────────────────────────────────────────
        self.tabs = QtWidgets.QTabWidget()

        # TAB 1: MAIN METRICS & GRAPH
        tab_main = QtWidgets.QWidget()
        tm_l = QtWidgets.QVBoxLayout(tab_main)
        tm_l.setContentsMargins(0, 4, 0, 0)
        tm_l.setSpacing(4)

        # 3-Card Metrics
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(6)

        c1 = QtWidgets.QFrame()
        c1.setStyleSheet("QFrame{background-color:#1a1a1a;border:1px solid #333333;border-radius:4px;padding:1px;}")
        c1_l = QtWidgets.QVBoxLayout(c1)
        c1_l.setContentsMargins(3, 1, 3, 1)
        c1_l.setSpacing(1)
        c1_t = QtWidgets.QLabel("ORIGINAL")
        c1_t.setStyleSheet("color:#888888;font:bold 8px 'Segoe UI';border:none;background:transparent;")
        self._orig_lbl = QtWidgets.QLabel(f"{self._orig_tokens:,} tok")
        self._orig_lbl.setStyleSheet("color:#dddddd;font:bold 10px 'Segoe UI';border:none;background:transparent;")
        c1_l.addWidget(c1_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c1_l.addWidget(self._orig_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c1)

        c2 = QtWidgets.QFrame()
        c2.setStyleSheet("QFrame{background-color:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:1px;}")
        c2_l = QtWidgets.QVBoxLayout(c2)
        c2_l.setContentsMargins(3, 1, 3, 1)
        c2_l.setSpacing(1)
        c2_t = QtWidgets.QLabel("COMPRESSED")
        c2_t.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';border:none;background:transparent;")
        self._comp_lbl = QtWidgets.QLabel(f"{self._comp_tokens:,} tok")
        self._comp_lbl.setStyleSheet("color:#00FFCC;font:bold 10px 'Segoe UI';border:none;background:transparent;")
        c2_l.addWidget(c2_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c2_l.addWidget(self._comp_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c2)

        c3 = QtWidgets.QFrame()
        c3.setStyleSheet("QFrame{background-color:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:1px;}")
        c3_l = QtWidgets.QVBoxLayout(c3)
        c3_l.setContentsMargins(3, 1, 3, 1)
        c3_l.setSpacing(1)
        c3_t = QtWidgets.QLabel("SAVINGS")
        c3_t.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';border:none;background:transparent;")
        self._ratio_lbl = QtWidgets.QLabel(f"{self._ratio:.1f}x (-0.0%)")
        self._ratio_lbl.setStyleSheet("color:#55ffaa;font:bold 10px 'Segoe UI';border:none;background:transparent;")
        c3_l.addWidget(c3_t, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c3_l.addWidget(self._ratio_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c3)

        tm_l.addLayout(cards_layout)

        # Center Main Counter
        val_box = QtWidgets.QHBoxLayout()
        val_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v_title = QtWidgets.QLabel("SAVED:")
        v_title.setStyleSheet("color:#888888;font:bold 12px 'Segoe UI';border:none;background:transparent;padding-right:3px;")
        val_box.addWidget(v_title)

        self._val = QtWidgets.QLabel("0")
        self._val.setStyleSheet("color:#00FFCC;font:800 22px 'Segoe UI';border:none;background:transparent;")
        val_box.addWidget(self._val)

        v_unit = QtWidgets.QLabel("TOKENS")
        v_unit.setStyleSheet("color:#00FFCC;font:bold 10px 'Segoe UI';border:none;background:transparent;padding-left:3px;padding-top:4px;")
        val_box.addWidget(v_unit)
        tm_l.addLayout(val_box)

        # Live Sparkline Graph
        self.sparkline = SparklineGraph()
        tm_l.addWidget(self.sparkline)

        self.tabs.addTab(tab_main, "📊 HUD")

        # TAB 2: SETTINGS (Prepositions, Verbs, Fallbacks)
        tab_settings = QtWidgets.QWidget()
        ts_l = QtWidgets.QVBoxLayout(tab_settings)
        ts_l.setContentsMargins(4, 4, 4, 4)
        ts_l.setSpacing(4)

        # Preposition Slider
        prep_box = QtWidgets.QHBoxLayout()
        prep_lbl = QtWidgets.QLabel("Preposition Stripping:")
        prep_lbl.setStyleSheet("color:#aaaaaa;font:bold 9px 'Segoe UI';")
        self.prep_val_lbl = QtWidgets.QLabel(self._config.get("preposition_stripping", "standard").upper())
        self.prep_val_lbl.setStyleSheet("color:#00FFCC;font:bold 9px 'Segoe UI';")
        prep_box.addWidget(prep_lbl)
        prep_box.addStretch()
        prep_box.addWidget(self.prep_val_lbl)
        ts_l.addLayout(prep_box)

        self.prep_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.prep_slider.setRange(0, 3)
        prep_map = {"off": 0, "light": 1, "standard": 2, "aggressive": 3}
        self.prep_slider.setValue(prep_map.get(self._config.get("preposition_stripping", "standard"), 2))
        self.prep_slider.valueChanged.connect(self._on_prep_changed)
        ts_l.addWidget(self.prep_slider)

        # Checkboxes
        self.chk_v_verbs = QtWidgets.QCheckBox("V-Verbs & Syntax Compaction")
        self.chk_v_verbs.setChecked(self._config.get("v_verbs_optimization", True))
        self.chk_v_verbs.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_v_verbs)

        self.chk_conversational = QtWidgets.QCheckBox("Conversational Filler Pruning ('please', 'thanks')")
        self.chk_conversational.setChecked(self._config.get("drop_fillers", True))
        self.chk_conversational.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_conversational)

        self.chk_auto_routes = QtWidgets.QCheckBox("Auto-Explore Optimal Compression Routes")
        self.chk_auto_routes.setChecked(self._config.get("auto_explore_routes", True))
        self.chk_auto_routes.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_auto_routes)

        self.chk_safety = QtWidgets.QCheckBox("Safety Fallback on Reconstruction Warning")
        self.chk_safety.setChecked(True)
        self.chk_safety.toggled.connect(self._on_setting_toggled)
        ts_l.addWidget(self.chk_safety)

        self.tabs.addTab(tab_settings, "⚙️ SETTINGS")

        # TAB 3: HISTORY & MODEL INSPECTOR
        tab_hist = QtWidgets.QWidget()
        th_l = QtWidgets.QVBoxLayout(tab_hist)
        th_l.setContentsMargins(2, 2, 2, 2)
        th_l.setSpacing(2)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["URL / Model / Timestamp", "Raw", "Comp", "Saved"])
        self.tree.setColumnWidth(0, 190)
        self.tree.setColumnWidth(1, 55)
        self.tree.setColumnWidth(2, 55)
        self.tree.setColumnWidth(3, 55)
        th_l.addWidget(self.tree)

        self.tabs.addTab(tab_hist, "📜 HISTORY")

        fl.addWidget(self.tabs)

        # ── Scrolling Marquee Ticker at the Bottom ─────────────────────────────
        self._tick = TickerMarquee()
        self._tick.setStyleSheet("border:none;border-radius:4px;")
        fl.addWidget(self._tick)

    # ── Settings Handlers ─────────────────────────────────────────────────────
    def _on_prep_changed(self, val: int):
        rev_map = {0: "off", 1: "light", 2: "standard", 3: "aggressive"}
        mode = rev_map.get(val, "standard")
        self.prep_val_lbl.setText(mode.upper())
        self._config["preposition_stripping"] = mode
        save_config(self._config)
        self._tick.set_text(f"⚙️ PREPOSITION COMPRESSION SET TO: {mode.upper()}")

    def _on_setting_toggled(self):
        self._config["v_verbs_optimization"] = self.chk_v_verbs.isChecked()
        self._config["drop_fillers"] = self.chk_conversational.isChecked()
        self._config["auto_explore_routes"] = self.chk_auto_routes.isChecked()
        save_config(self._config)
        self._tick.set_text("⚙️ COMPRESSION ENGINE PARAMETERS SAVED & SYNCED")

    # ── Real Data Event Injection ─────────────────────────────────────────────
    def push(self, url: str, model: str, app: str, user: str, raw: int, comp: int, timestamp: str = ""):
        """Processes a true intercepted request."""
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

        # Update History Tree (Hierarchical by URL -> Model)
        self._add_to_history_tree(url, model, app, user, raw, comp, saved, r, timestamp)

        self._tick.set_text(
            f"⚡ [{app.upper()} | {model}]  URL: {url}  |  "
            f"Raw: {raw:,}  |  Post-3D: {comp:,}  |  "
            f"Saved: {saved:,} ({r}x)  |  TOTAL SAVED: {self._total_saved:,} TOKENS"
        )

    def _add_to_history_tree(self, url, model, app, user, raw, comp, saved, ratio, timestamp):
        # Find or create URL top-level item
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

        # Find or create Model child
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

        # Add Request turn leaf
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

    # ── IPC: Load Initial History & Poll Real Events ───────────────────────────
    def _load_initial_history(self):
        """Reads existing true log file if present on startup."""
        if not EVENTS_LOG.exists():
            return
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
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

    # ── Inertial Glide Physics ────────────────────────────────────────────────
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
        if x < d:
            x = 0
        elif screen.width() - (x + self.width()) < d:
            x = screen.width() - self.width()
        if y < d:
            y = 0
        elif screen.height() - (y + self.height()) < d:
            y = screen.height() - self.height()
        self.move(x, y)

    # ── Mouse: Drag, Resize, Glide Launch ─────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._gt.stop()
            r = self.rect()
            if (r.right() - e.position().x() < self._rm
                    and r.bottom() - e.position().y() < self._rm):
                self._resizing = True
            else:
                self._drag_pos = (
                    e.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                self._last_pt = e.globalPosition().toPoint()
                self._last_t = time.time()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._resizing:
            self.resize(
                max(self.minimumWidth(), int(e.position().x())),
                max(self.minimumHeight(), int(e.position().y())),
            )
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
            if (r.right() - e.position().x() < self._rm
                    and r.bottom() - e.position().y() < self._rm):
                self.setCursor(QtCore.Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        self._resizing = False
        if abs(self._vx) > 1.2 or abs(self._vy) > 1.2:
            self._gt.start(16)
        else:
            self._snap()
            self._save_geo()

    # ── Right-Click Context Menu ──────────────────────────────────────────────
    def contextMenuEvent(self, e):
        m = QtWidgets.QMenu(self)
        m.setStyleSheet(
            "QMenu{background:#1a1a1a;color:#00FFCC;border:1px solid #00FFCC;font:11px 'Segoe UI';}"
            "QMenu::item:selected{background:#00FFCC;color:#121212;}"
        )
        pa = m.addAction("📌 Always On Top")
        pa.setCheckable(True)
        pa.setChecked(self._pinned)
        pa.triggered.connect(self._toggle_pin)

        om = m.addMenu("🌓 Opacity")
        for lv, lb in [(0.80, "80%"), (0.96, "96% (Default)"), (1.0, "100% Solid")]:
            a = om.addAction(lb)
            a.setCheckable(True)
            a.setChecked(abs(self._opacity - lv) < 0.02)
            a.triggered.connect(lambda _, v=lv: self._set_opacity(v))

        m.addSeparator()
        m.addAction("🧹 Clear Counter & History", self._clear)
        m.addAction("🔄 Reset Position", self._reset_pos)
        m.addSeparator()
        m.addAction("❌ Close HUD", self.close)
        m.exec(e.globalPos())

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

    def _set_opacity(self, v):
        self._opacity = v
        self.setWindowOpacity(v)
        self._save_geo()

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

    def _reset_pos(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        self.resize(400, 225)
        self.move(screen.width() - 440, 80)
        self.force_win32_topmost()
        self._save_geo()

    # ── Geometry Persistence ──────────────────────────────────────────────────
    def _save_geo(self):
        try:
            with open(POS_FILE, "w") as f:
                json.dump({
                    "x": self.x(), "y": self.y(),
                    "w": self.width(), "h": self.height(),
                    "pinned": self._pinned, "opacity": self._opacity,
                }, f)
        except Exception:
            pass

    def _load_geo(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        default_x = screen.width() - 440
        default_y = 80

        if POS_FILE.exists():
            try:
                g = json.loads(POS_FILE.read_text())
                gx = g.get("x", default_x)
                gy = g.get("y", default_y)
                gw = g.get("w", 400)
                gh = g.get("h", 225)

                if gx < 0 or gx > screen.width() - 100:
                    gx = default_x
                if gy < 0 or gy > screen.height() - 80:
                    gy = default_y

                self.move(gx, gy)
                self.resize(gw, gh)
                self._pinned = g.get("pinned", True)
                self._opacity = g.get("opacity", 0.96)
                self._pin_btn.setText("📌 ON TOP" if self._pinned else "📍 FLOAT")
                self._apply_flags()
                return
            except Exception:
                pass

        self.move(default_x, default_y)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    hud = TokenHUD()
    hud.show()
    hud.raise_()
    hud.activateWindow()
    hud.force_win32_topmost()

    # Screenshot automation support
    if "--screenshot" in sys.argv:
        def capture_and_exit():
            QtWidgets.QApplication.processEvents()
            hud_pix = hud.grab()
            hud_path = "C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v5_widget.png"
            hud_pix.save(hud_path)
            print(f"HUD Widget screenshot saved: {hud_path}")

            # Switch to Settings tab and screenshot
            hud.tabs.setCurrentIndex(1)
            QtWidgets.QApplication.processEvents()
            hud_settings_pix = hud.grab()
            settings_path = "C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_v5_settings.png"
            hud_settings_pix.save(settings_path)
            print(f"HUD Settings screenshot saved: {settings_path}")

            app.quit()

        QtCore.QTimer.singleShot(600, capture_and_exit)

    sys.exit(app.exec())
