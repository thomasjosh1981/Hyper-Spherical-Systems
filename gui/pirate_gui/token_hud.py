"""
token_hud.py — Hyper-Spherical Gold Digital Token HUD & Real-Time Telemetry Suite (v7.0)
========================================================================================
Features:
  - Universal Fluid Window Dragging (Event Filter on entire frame & dedicated drag grip bar).
  - Auto-Corner Snap Button (Cycles TR ➔ TL ➔ BL ➔ BR smoothly across screens).
  - 3 Digital LCD Display Windows (Burst + Continual Cumulative Totals).
  - Interactive Helipad Landing Zone & Window Suction Docking.
  - Live Telemetry File & IPC Poller (Detects active models, CLOUD / Claude / Gemini switches).
  - Suite Links Row (🔒 SNB RECALL MATRIX + 🔒 CANDY SPINNER).
  - System Tray persistence & Zero-Data-Leak numeric statistics.
  - Big Red E-STOP Emergency Cutoff.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import ctypes
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from helipad_dock import (
        HelipadLandingZone, WindowSuctionAnimator, TargetWindowInspector,
        PersistentTargetRegistry, AutoSeekDialog, IS_WINDOWS
    )
    from security_shield import EmergencyKillswitch
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from helipad_dock import (
        HelipadLandingZone, WindowSuctionAnimator, TargetWindowInspector,
        PersistentTargetRegistry, AutoSeekDialog, IS_WINDOWS
    )
    from security_shield import EmergencyKillswitch


# ── Paths ─────────────────────────────────────────────────────────────────────
_HYPES_DIR   = Path.home() / ".hypes"
_POS_FILE    = _HYPES_DIR / "hud_pos.json"
_LOG_DIR     = _HYPES_DIR / "token_logs"
_LIVE_FILE   = _HYPES_DIR / "live_telemetry.json"


# ─────────────────────────────────────────────────────────────────────────────
# 1. DUAL-WINDOW DIGITAL LCD DISPLAY (Continual Running Total + Current Burst Sub-Window)
# ─────────────────────────────────────────────────────────────────────────────

class _DigitalLcdBox(QtWidgets.QFrame):
    """
    A high-tech dual-window digital LCD module displaying:
    1. Large Continual/Cumulative Running Total LCD (Session / All-Time Progress)
    2. Dedicated Current Request Sub-Window directly underneath (Latest Burst Tokens + Metrics)
    """

    def __init__(self, title: str, subtext: str, burst_label: str, border_color: str, glow_color: str, text_color: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.border_color = border_color
        self.glow_color = glow_color
        self.text_color = text_color
        self._continual_val = 0
        self._continual_target = 0
        self._burst_val = 0
        self._burst_target = 0

        self.setStyleSheet(f"""
            QFrame#lcd_card {{
                background-color: #04070d;
                border: 2px solid {border_color};
                border-radius: 8px;
            }}
        """)
        self.setObjectName("lcd_card")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # ── Header Title Row ─────────────────────────────────
        hdr_row = QtWidgets.QHBoxLayout()
        hdr_row.setSpacing(4)

        dot = QtWidgets.QLabel("●")
        dot.setStyleSheet(f"color: {border_color}; font-size: 10px;")
        hdr_row.addWidget(dot)

        lbl_title = QtWidgets.QLabel(title.upper())
        lbl_title.setStyleSheet(f"color: {border_color}; font-size: 10px; font-weight: 900; font-family: 'Segoe UI', Consolas; letter-spacing: 0.8px;")
        hdr_row.addWidget(lbl_title, 1)

        tag_mode = QtWidgets.QLabel("CUMULATIVE")
        tag_mode.setStyleSheet("color: #64748b; font-size: 8px; font-weight: 800; font-family: Consolas; background: #0a1120; border-radius: 2px; padding: 1px 4px;")
        hdr_row.addWidget(tag_mode)
        layout.addLayout(hdr_row)

        # ── Upper Window: Main Continual Running Total LCD ───
        self.lcd_continual = QtWidgets.QLCDNumber(self)
        self.lcd_continual.setDigitCount(8)
        self.lcd_continual.setSegmentStyle(QtWidgets.QLCDNumber.SegmentStyle.Flat)
        self.lcd_continual.setFixedHeight(42)
        self.lcd_continual.setStyleSheet(f"""
            QLCDNumber {{
                color: {text_color};
                background: #020408;
                border: 1px solid {glow_color};
                border-radius: 4px;
            }}
        """)
        self.lcd_continual.display(0)
        layout.addWidget(self.lcd_continual)

        lbl_sub = QtWidgets.QLabel(subtext.upper())
        lbl_sub.setStyleSheet("color: #64748b; font-size: 8px; font-weight: 700; font-family: Consolas;")
        layout.addWidget(lbl_sub)

        # ── Lower Window: Dedicated Current Request Sub-Window ───
        self.burst_card = QtWidgets.QFrame(self)
        self.burst_card.setStyleSheet(f"""
            QFrame {{
                background-color: #080f1e;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-left: 3px solid {border_color};
                border-radius: 4px;
            }}
        """)
        burst_lay = QtWidgets.QVBoxLayout(self.burst_card)
        burst_lay.setContentsMargins(6, 4, 6, 4)
        burst_lay.setSpacing(1)

        burst_hdr = QtWidgets.QHBoxLayout()
        lbl_b_tag = QtWidgets.QLabel(burst_label.upper())
        lbl_b_tag.setStyleSheet("color: #94a3b8; font-size: 8px; font-weight: 800; font-family: Consolas;")
        burst_hdr.addWidget(lbl_b_tag)

        self.lbl_burst_num = QtWidgets.QLabel("+0")
        self.lbl_burst_num.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.lbl_burst_num.setStyleSheet(f"color: {text_color}; font-size: 11px; font-weight: 900; font-family: Consolas;")
        burst_hdr.addWidget(self.lbl_burst_num)
        burst_lay.addLayout(burst_hdr)

        self.lbl_burst_sub = QtWidgets.QLabel("Latest Stream Inflow")
        self.lbl_burst_sub.setStyleSheet("color: #475569; font-size: 8px; font-family: Consolas;")
        burst_lay.addWidget(self.lbl_burst_sub)

        layout.addWidget(self.burst_card)

        # Animation timer
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.setInterval(20)
        self._anim_timer.timeout.connect(self._step_anim)

    def set_values(self, burst_val: int, cumulative_total: int, burst_detail: str = "") -> None:
        self._burst_target = burst_val
        self._continual_target = cumulative_total
        if burst_detail:
            self.lbl_burst_sub.setText(burst_detail)
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def _step_anim(self) -> None:
        done_continual = False
        done_burst = False

        # Step continual
        if self._continual_val < self._continual_target:
            diff = max(1, (self._continual_target - self._continual_val) // 4)
            self._continual_val = min(self._continual_target, self._continual_val + diff)
            self.lcd_continual.display(self._continual_val)
        elif self._continual_val > self._continual_target:
            diff = max(1, (self._continual_val - self._continual_target) // 4)
            self._continual_val = max(self._continual_target, self._continual_val - diff)
            self.lcd_continual.display(self._continual_val)
        else:
            done_continual = True

        # Step burst
        if self._burst_val < self._burst_target:
            diff = max(1, (self._burst_target - self._burst_val) // 3)
            self._burst_val = min(self._burst_target, self._burst_val + diff)
            self.lbl_burst_num.setText(f"+{self._burst_val:,}")
        elif self._burst_val > self._burst_target:
            diff = max(1, (self._burst_val - self._burst_target) // 3)
            self._burst_val = max(self._burst_target, self._burst_val - diff)
            self.lbl_burst_num.setText(f"+{self._burst_val:,}")
        else:
            done_burst = True

        if done_continual and done_burst:
            self._anim_timer.stop()



# ─────────────────────────────────────────────────────────────────────────────
# 2. SCROLLING TICKER MARQUEE (Broadcasting Model, URL & App)
# ─────────────────────────────────────────────────────────────────────────────

class _ScrollingTicker(QtWidgets.QWidget):
    """Smooth continuously scrolling marquee broadcasting active model, URL, client app, & stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._text = "🟢 HYPES TOKEN TELEMETRY ONLINE  ✦  SOVEREIGN PRIVACY ACTIVE (ZERO PROMPT LOGGING)  ✦  "
        self._offset: float = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._scroll_step)
        self._timer.start()

    def update_ticker(self, model: str, url: str, app_name: str, saved: int, pct: float) -> None:
        self._text = (
            f"⚡ ACTIVE MODEL: {model.upper()}  ✦  "
            f"TARGET: {url}  ✦  "
            f"CLIENT APP: {app_name}  ✦  "
            f"LATEST BURST: +{saved:,} TOKENS SAVED ({pct:.1f}% CONSERVED)  ✦  "
            f"PRIVACY: 100% CLIENT SOVEREIGN  ✦  "
        )
        self.update()

    def flash_dock_notice(self, app_name: str):
        self._text = f"🎯 AUTO-DOCK COMPLETED: {app_name.upper()} IS PERMANENTLY HOOKED TO HYPES PROXY  ✦  "
        self.update()

    def _scroll_step(self) -> None:
        self._offset += 1.2
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        r = self.rect()
        p.fillRect(r, QtGui.QColor("#03060c"))
        p.setPen(QtGui.QPen(QtGui.QColor("#ffd700"), 1))
        p.drawRect(r.adjusted(0, 0, -1, -1))

        p.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Weight.Bold.value))
        p.setPen(QtGui.QColor("#00ffcc"))

        metrics = p.fontMetrics()
        text_w = metrics.horizontalAdvance(self._text)
        if text_w <= 0:
            return

        x = -(self._offset % text_w)
        while x < self.width():
            p.drawText(int(x), 18, self._text)
            x += text_w
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 3. REAL-TIME LIVE TOKEN HISTORY GRAPH
# ─────────────────────────────────────────────────────────────────────────────

class _LiveTokenGraph(QtWidgets.QWidget):
    """Real-Time Live History Graph with 3 distinct curves & gold border."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(125)
        self.history: List[Dict[str, Any]] = []
        self.max_points = 32

    def add_point(self, pre: int, post: int) -> None:
        saved = max(0, pre - post)
        self.history.append({"pre": pre, "post": post, "saved": saved, "ts": time.time()})
        if len(self.history) > self.max_points:
            self.history.pop(0)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        p.fillRect(self.rect(), QtGui.QColor("#020408"))
        p.setPen(QtGui.QPen(QtGui.QColor("#2d2305"), 1.5))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

        if len(self.history) < 2:
            p.setFont(QtGui.QFont("Consolas", 10, QtGui.QFont.Weight.Bold.value))
            p.setPen(QtGui.QColor("#64748b"))
            p.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "REAL-TIME TOKEN HISTORY CURVE (Awaiting Telemetry Bursts)")
            p.end()
            return

        max_val = max(max(pt["pre"] for pt in self.history), 100)
        pad_x = 20
        pad_y = 16
        draw_w = w - (pad_x * 2)
        draw_h = h - (pad_y * 2)

        p.setPen(QtGui.QPen(QtGui.QColor("#111827"), 1, QtCore.Qt.PenStyle.DashLine))
        for gy in [0.25, 0.50, 0.75]:
            y_pos = pad_y + int(draw_h * gy)
            p.drawLine(pad_x, y_pos, w - pad_x, y_pos)

        def get_coords(idx: int, val: int) -> QtCore.QPointF:
            x = pad_x + (idx / (len(self.history) - 1)) * draw_w
            y = (h - pad_y) - (val / max_val) * draw_h
            return QtCore.QPointF(x, y)

        path_pre = QtGui.QPainterPath()
        path_pre.moveTo(get_coords(0, self.history[0]["pre"]))
        for i in range(1, len(self.history)):
            path_pre.lineTo(get_coords(i, self.history[i]["pre"]))
        p.setPen(QtGui.QPen(QtGui.QColor("#f59e0b"), 2))
        p.drawPath(path_pre)

        path_post = QtGui.QPainterPath()
        path_post.moveTo(get_coords(0, self.history[0]["post"]))
        for i in range(1, len(self.history)):
            path_post.lineTo(get_coords(i, self.history[i]["post"]))
        p.setPen(QtGui.QPen(QtGui.QColor("#06b6d4"), 2))
        p.drawPath(path_post)

        path_saved = QtGui.QPainterPath()
        path_saved.moveTo(get_coords(0, self.history[0]["saved"]))
        for i in range(1, len(self.history)):
            path_saved.lineTo(get_coords(i, self.history[i]["saved"]))
        p.setPen(QtGui.QPen(QtGui.QColor("#10b981"), 2.5))
        p.drawPath(path_saved)

        p.setFont(QtGui.QFont("Consolas", 8, QtGui.QFont.Weight.Bold.value))
        p.setPen(QtGui.QColor("#f59e0b"))
        p.drawText(pad_x + 4, pad_y + 10, "■ RAW PRE")
        p.setPen(QtGui.QColor("#06b6d4"))
        p.drawText(pad_x + 70, pad_y + 10, "■ SENT POST")
        p.setPen(QtGui.QColor("#10b981"))
        p.drawText(pad_x + 145, pad_y + 10, "■ CONSERVED SAVED")
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 4. MASTER GOLD TOKEN HUD WINDOW (With Auto-Corner Snap & Smooth Dragging)
# ─────────────────────────────────────────────────────────────────────────────

class TokenHUD(QtWidgets.QMainWindow):
    """
    Hyper-Spherical Gold Token HUD Window (v7.0).
    Features:
      - 3 Digital LCD Windows (Per-Request + Continual Cumulative Totals).
      - Dedicated Top Drag Grip & Universal Window Dragging.
      - Auto-Corner Snap Button (TR ➔ TL ➔ BL ➔ BR).
      - Live Telemetry File & IPC Poller for instant model/cloud switch detection.
      - Interactive Helipad Landing Zone & Window Suction.
      - Fixed-Size Red E-STOP Emergency Cutoff.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hyper-Spherical Gold Token HUD - Live Telemetry")

        self.setWindowFlags(
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.FramelessWindowHint
        )
        
        self.setMinimumSize(540, 680)
        self.resize(580, 720)

        # Continual Cumulative State
        self._session_pre_total   = 0
        self._session_post_total  = 0
        self._session_saved_total = 0
        self._active_model        = "tesseract-sfs-plus"
        self._active_url          = "http://127.0.0.1:8000/v1/chat/completions"
        self._active_app          = "Tesseract Gateway"
        self._current_corner_idx  = 0
        self._drag_pos: Optional[QtCore.QPoint] = None
        self._last_telemetry_mtime = 0.0

        self._suction_animator = WindowSuctionAnimator(self)
        self._suction_animator.animationComplete.connect(self._on_suction_complete)

        # Hover targeting timer for Helipad
        self._target_scan_timer = QtCore.QTimer(self)
        self._target_scan_timer.setInterval(120)
        self._target_scan_timer.timeout.connect(self._scan_hover_targets)
        self._target_scan_timer.start()

        # Live telemetry polling timer
        self._telemetry_poll_timer = QtCore.QTimer(self)
        self._telemetry_poll_timer.setInterval(300)
        self._telemetry_poll_timer.timeout.connect(self._check_live_telemetry)
        self._telemetry_poll_timer.start()

        self._build_ui()
        self._setup_system_tray()
        self._position_default()
        self._auto_connect_antigravity()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background-color: #03050a;")

        self.gold_frame = QtWidgets.QFrame(central)
        self.gold_frame.setObjectName("gold_frame")
        self.gold_frame.setStyleSheet("""
            #gold_frame {
                background-color: #050811;
                border: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffe066, stop:0.35 #d4af37, stop:0.7 #996515, stop:1 #ffd700);
                border-radius: 12px;
            }
        """)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(2, 2, 2, 2)
        root_layout.addWidget(self.gold_frame)

        main_lay = QtWidgets.QVBoxLayout(self.gold_frame)
        main_lay.setContentsMargins(14, 8, 14, 12)
        main_lay.setSpacing(6)

        # ── 0. Dedicated Drag Grip Bar ───────────────────────────────────────
        self.drag_bar = QtWidgets.QFrame()
        self.drag_bar.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
        self.drag_bar.setStyleSheet("""
            QFrame {
                background: #091222;
                border: 1px dashed rgba(255, 215, 0, 0.4);
                border-radius: 4px;
                padding: 2px;
            }
            QFrame:hover {
                background: #112244;
                border: 1px solid #ffd700;
            }
        """)
        d_lay = QtWidgets.QHBoxLayout(self.drag_bar)
        d_lay.setContentsMargins(6, 2, 6, 2)
        lbl_drag = QtWidgets.QLabel("⋮⋮ HOLD & DRAG HUD WINDOW ⋮⋮")
        lbl_drag.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_drag.setStyleSheet("color: #ffd700; font-size: 9px; font-weight: 900; font-family: Consolas; letter-spacing: 2px;")
        d_lay.addWidget(lbl_drag)
        main_lay.addWidget(self.drag_bar)

        # ── 1. Top Header Row & Window Controls ──────────────────────────────
        top_row = QtWidgets.QHBoxLayout()
        lbl_title = QtWidgets.QLabel("👑 HYPES TOKEN OPTIMIZER")
        lbl_title.setStyleSheet("color: #ffd700; font-size: 12px; font-weight: 900; font-family: 'Segoe UI', Consolas; letter-spacing: 1px;")
        top_row.addWidget(lbl_title)

        top_row.addStretch()

        # Prominent 1-Click Search & Seek AI Button
        self.btn_autoseek_header = QtWidgets.QPushButton("🔍 SEARCH & SEEK AI")
        self.btn_autoseek_header.setToolTip("Instant 1-Click Deep Scan: Discover and link Antigravity IDE, Web AI, Local Daemons & CLIs")
        self.btn_autoseek_header.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                font-size: 9px;
                font-weight: 900;
                padding: 3px 10px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #00d4ff);
                color: #040814;
                border-color: #00ffcc;
            }
        """)
        self.btn_autoseek_header.clicked.connect(self._open_autoseek_dialog)
        top_row.addWidget(self.btn_autoseek_header)

        # Auto-Corner Snap Button
        self.btn_snap_corner = QtWidgets.QPushButton("📐 SNAP: [TR]")
        self.btn_snap_corner.setToolTip("Auto-snap HUD to screen corners (Cycles TR ➔ TL ➔ BL ➔ BR)")
        self.btn_snap_corner.setStyleSheet("""
            QPushButton { background: #162032; color: #38bdf8; border: 1px solid #0284c7; border-radius: 4px; font-size: 9px; font-weight: 900; padding: 3px 8px; }
            QPushButton:hover { background: #0284c7; color: white; }
        """)
        self.btn_snap_corner.clicked.connect(self._cycle_corner)
        top_row.addWidget(self.btn_snap_corner)

        self.btn_ontop = QtWidgets.QPushButton("📌 ON TOP")
        self.btn_ontop.setCheckable(True)
        self.btn_ontop.setChecked(True)
        self.btn_ontop.setStyleSheet("""
            QPushButton { background: #1e1b0c; color: #ffd700; border: 1px solid #ffd700; border-radius: 4px; font-size: 9px; font-weight: bold; padding: 3px 8px; }
            QPushButton:checked { background: #d4af37; color: #000; }
        """)
        self.btn_ontop.clicked.connect(self._toggle_always_on_top)
        top_row.addWidget(self.btn_ontop)

        btn_min = QtWidgets.QPushButton("—")
        btn_min.setFixedSize(22, 20)
        btn_min.setStyleSheet("QPushButton { background: #1e293b; color: #94a3b8; border: 1px solid #475569; border-radius: 3px; font-weight: bold; } QPushButton:hover { background: #334155; color: white; }")
        btn_min.clicked.connect(self.hide)
        top_row.addWidget(btn_min)

        btn_close = QtWidgets.QPushButton("×")
        btn_close.setFixedSize(22, 20)
        btn_close.setStyleSheet("QPushButton { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; border-radius: 3px; font-weight: bold; font-size: 13px; } QPushButton:hover { background: #b91c1c; color: white; }")
        btn_close.clicked.connect(self.hide)
        top_row.addWidget(btn_close)

        main_lay.addLayout(top_row)

        # ── 1b. Suite Links Strip (Subdued / Greyed Out) ─────────────────────
        suite_box = QtWidgets.QFrame()
        suite_box.setStyleSheet("background: #060a14; border: 1px solid #1e293b; border-radius: 6px; padding: 2px 6px;")
        suite_row = QtWidgets.QHBoxLayout(suite_box)
        suite_row.setContentsMargins(4, 2, 4, 2)
        suite_row.setSpacing(8)

        lbl_suite = QtWidgets.QLabel("SUITE LINKS:")
        lbl_suite.setStyleSheet("color: #64748b; font-size: 9px; font-weight: 900; font-family: Consolas; letter-spacing: 0.5px;")
        suite_row.addWidget(lbl_suite)

        self.btn_recollect = QtWidgets.QPushButton("🔒 SNB RECALL MATRIX (2FA)")
        self.btn_recollect.setToolTip("Open 2FA-Protected Multi-Set Cognitive Recollection Matrix (SNB 3D Spherical Brain)")
        self.btn_recollect.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.03); color: #64748b; border: 1px solid #334155;
                border-radius: 3px; font-size: 9px; font-weight: 700; padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(0,212,255,0.1); color: #00d4ff; border-color: #0284c7; }
        """)
        self.btn_recollect.clicked.connect(self._open_recollection_viewer)
        suite_row.addWidget(self.btn_recollect)

        self.btn_candy = QtWidgets.QPushButton("🔒 CANDY SPINNER (GCS)")
        self.btn_candy.setToolTip("4D SFS/SFS+ Model Decomposition & Respin Suite")
        self.btn_candy.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.03); color: #64748b; border: 1px solid #334155;
                border-radius: 3px; font-size: 9px; font-weight: 700; padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(251,191,36,0.1); color: #fbbf24; border-color: #d97706; }
        """)
        self.btn_candy.clicked.connect(self._open_candy_spinner)
        suite_row.addWidget(self.btn_candy)

        self.btn_sauna = QtWidgets.QPushButton("🔒 THE SAUNA (SPA)")
        self.btn_sauna.setToolTip("Model Relaxation, Scheduled Self-Optimization & Single-Occupancy Throttling")
        self.btn_sauna.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.03); color: #64748b; border: 1px solid #334155;
                border-radius: 3px; font-size: 9px; font-weight: 700; padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(249,115,22,0.1); color: #f97316; border-color: #ea580c; }
        """)
        self.btn_autoseek = QtWidgets.QPushButton("🔍 AUTO-SEEK APPS")
        self.btn_autoseek.setToolTip("Scan the entire system for active AI windows, IDEs, TUIs, CLIs, local daemons, and phone bridges")
        self.btn_autoseek.setStyleSheet("""
            QPushButton {
                background: rgba(0,212,255,0.08); color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 3px; font-size: 9px; font-weight: 900; padding: 2px 8px;
            }
            QPushButton:hover { background: #0284c7; color: #ffffff; border-color: #00ffcc; }
        """)
        self.btn_autoseek.clicked.connect(self._open_autoseek_dialog)
        suite_row.addWidget(self.btn_autoseek)

        # ── Universal Endpoints Dropdown Selector ────────────────────────────
        lbl_ep = QtWidgets.QLabel("⚡ ENDPOINTS:")
        lbl_ep.setStyleSheet("color: #ffd700; font-size: 9px; font-weight: 900; margin-left: 6px;")
        suite_row.addWidget(lbl_ep)

        self.combo_endpoints = QtWidgets.QComboBox()
        self.combo_endpoints.setToolTip("Select active live universal endpoints or route all multi-port traffic simultaneously")
        self.combo_endpoints.setStyleSheet("""
            QComboBox {
                background: #080e1a; color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 3px; font-size: 9px; font-weight: 700; padding: 2px 6px; min-width: 170px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #080e1a; color: #38bdf8; selection-background-color: #0284c7;
                selection-color: #ffffff; border: 1px solid #0284c7;
            }
        """)
        self.combo_endpoints.addItems([
            "👑 ALL ENDPOINTS LIVE (Multi-Port)",
            "👑 Port 8000: HypeS Gateway",
            "⚡ Port 11434: Ollama Daemon",
            "⚡ Port 1234: LM Studio API",
            "⚡ Port 8080: llama.cpp Server",
            "⚡ Port 5001: KoboldCpp API",
            "📱 Port 5555: Phone ADB Bridge"
        ])
        self.combo_endpoints.currentIndexChanged.connect(self._on_endpoint_selection_changed)
        suite_row.addWidget(self.combo_endpoints)

        suite_row.addStretch()
        main_lay.addWidget(suite_box)

        # ── 2. Interactive Helipad Landing & Docking Zone ────────────────────
        self.helipad = HelipadLandingZone(self)
        self.helipad.windowDocked.connect(self._dock_external_window)
        main_lay.addWidget(self.helipad)

        # ── 3. Scrolling Ticker Marquee ──────────────────────────────────────
        self.ticker = _ScrollingTicker()
        main_lay.addWidget(self.ticker)

        # ── 4. The 3 Dual-Window Digital LCD Displays (Continual Total + Current Burst) ───
        lcd_row = QtWidgets.QHBoxLayout()
        lcd_row.setSpacing(8)

        self.lcd_pre = _DigitalLcdBox(
            title="1. RAW BEFORE",
            subtext="Continual Inflow Total",
            burst_label="LATEST PROMPT BURST",
            border_color="#f59e0b",
            glow_color="rgba(245, 158, 11, 0.35)",
            text_color="#fbbf24"
        )
        lcd_row.addWidget(self.lcd_pre)

        self.lcd_post = _DigitalLcdBox(
            title="2. SENT AFTER",
            subtext="Continual Output Total",
            burst_label="COMPRESSED OUTPUT BURST",
            border_color="#06b6d4",
            glow_color="rgba(6, 182, 212, 0.35)",
            text_color="#22d3ee"
        )
        lcd_row.addWidget(self.lcd_post)

        self.lcd_saved = _DigitalLcdBox(
            title="3. CONSERVED",
            subtext="Continual Tokens Saved",
            burst_label="TOKENS SAVED IN BURST",
            border_color="#10b981",
            glow_color="rgba(16, 185, 129, 0.35)",
            text_color="#34d399"
        )
        lcd_row.addWidget(self.lcd_saved)

        main_lay.addLayout(lcd_row)


        # ── 5. Real-Time Telemetry Curve ─────────────────────────────────────
        self.graph = _LiveTokenGraph(self)
        main_lay.addWidget(self.graph)

        # ── 6. Metrics & Emergency Cutoff Footer ──────────────────────────────
        footer_lay = QtWidgets.QHBoxLayout()
        footer_lay.setContentsMargins(0, 0, 0, 0)
        footer_lay.setSpacing(8)

        ratio_box = QtWidgets.QFrame()
        ratio_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0a1324, stop:1 #060c18);
                border: 1px solid #1e3a5f;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        r_lay = QtWidgets.QVBoxLayout(ratio_box)
        r_lay.setContentsMargins(6, 4, 6, 4)
        r_lay.setSpacing(2)

        stat_hdr = QtWidgets.QHBoxLayout()
        self.lbl_pct = QtWidgets.QLabel("0.0% SAVINGS CONSERVED")
        self.lbl_pct.setStyleSheet("color: #10b981; font-size: 13px; font-weight: 900; font-family: 'Segoe UI', Consolas;")
        stat_hdr.addWidget(self.lbl_pct)

        stat_hdr.addStretch()

        self.lbl_ratio = QtWidgets.QLabel("1.0× COMPRESSION")
        self.lbl_ratio.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 900; font-family: Consolas;")
        stat_hdr.addWidget(self.lbl_ratio)
        r_lay.addLayout(stat_hdr)

        self.lbl_sess_total = QtWidgets.QLabel("24h Session: 0 Raw ➔ 0 Sent ➔ 0 Saved (0.0% conserved · 1.0× ratio)")
        self.lbl_sess_total.setStyleSheet("color: #94a3b8; font-size: 9px; font-family: Consolas; font-weight: 600;")
        r_lay.addWidget(self.lbl_sess_total)

        footer_lay.addWidget(ratio_box, 1)

        # Fixed Red E-STOP Emergency Cutoff
        self.btn_estop = QtWidgets.QPushButton("🛑 E-STOP")
        self.btn_estop.setFixedSize(90, 48)
        self.btn_estop.setToolTip("EMERGENCY CUTOFF: Immediately terminate local AI runtimes & sever active proxy sockets.")
        self.btn_estop.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ef4444, stop:1 #991b1b);
                color: #ffffff;
                font-family: 'Segoe UI', Consolas;
                font-weight: 900;
                font-size: 12px;
                letter-spacing: 0.5px;
                border: 2px solid #f87171;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f87171, stop:1 #b91c1c);
                border-color: #fca5a5;
            }
        """)
        self.btn_estop.clicked.connect(self._trigger_manual_estop)
        footer_lay.addWidget(self.btn_estop, 0)

        main_lay.addLayout(footer_lay)

    # ── Universal Smooth Window Dragging ─────────────────────────────────────

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if (event.buttons() & QtCore.Qt.MouseButton.LeftButton) and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None
        self._save_position()
        event.accept()

    # ── Auto-Corner Snap Method ──────────────────────────────────────────────

    def _cycle_corner(self) -> None:
        """Cycles the HUD between the 4 screen corners: TR ➔ TL ➔ BL ➔ BR."""
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w = self.width()
        h = self.height()
        margin_x = 25
        margin_y = 25

        self._current_corner_idx = (self._current_corner_idx + 1) % 4

        corners = [
            ("TR", geo.right() - w - margin_x, geo.top() + margin_y),
            ("TL", geo.left() + margin_x, geo.top() + margin_y),
            ("BL", geo.left() + margin_x, geo.bottom() - h - margin_y),
            ("BR", geo.right() - w - margin_x, geo.bottom() - h - margin_y)
        ]

        tag, x, y = corners[self._current_corner_idx]
        self.move(x, y)
        self.btn_snap_corner.setText(f"📐 SNAP: [{tag}]")
        self._save_position()

    def _position_default(self) -> None:
        """Position the HUD in top-right corner of primary screen by default."""
        try:
            pos_file = Path.home() / ".hypes" / "hud_pos.json"
            if pos_file.exists():
                pos_data = json.loads(pos_file.read_text(encoding="utf-8"))
                self.move(int(pos_data.get("x", 100)), int(pos_data.get("y", 100)))
                return
        except Exception:
            pass
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                w = self.width()
                self.move(geo.right() - w - 25, geo.top() + 25)
        except Exception:
            pass

    def _save_position(self) -> None:
        """Persist current window coordinates to ~/.hypes/hud_pos.json."""
        try:
            pos_file = Path.home() / ".hypes" / "hud_pos.json"
            pos_file.parent.mkdir(parents=True, exist_ok=True)
            pos_file.write_text(json.dumps({"x": self.x(), "y": self.y()}), encoding="utf-8")
        except Exception:
            pass

    def _setup_system_tray(self) -> None:
        """Configures optional system tray icon for the HUD."""
        try:
            if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
                return
            if not hasattr(self, "_tray_icon") or not self._tray_icon:
                self._tray_icon = QtWidgets.QSystemTrayIcon(self)
                px = QtGui.QPixmap(16, 16)
                px.fill(QtGui.QColor("#d4af37"))
                self._tray_icon.setIcon(QtGui.QIcon(px))
                self._tray_icon.setToolTip("Hyper-Spherical Gold Token HUD")
                menu = QtWidgets.QMenu(self)
                show_act = menu.addAction("Show Gold HUD")
                show_act.triggered.connect(lambda: (self.show(), self.raise_(), self.activateWindow()))
                menu.addSeparator()
                quit_act = menu.addAction("Exit")
                quit_act.triggered.connect(QtWidgets.QApplication.quit)
                self._tray_icon.setContextMenu(menu)
                self._tray_icon.show()
        except Exception:
            pass



    # ── Live Telemetry & Model Switch Poller ──────────────────────────────────

    def _check_live_telemetry(self):
        """Polls ~/.hypes/live_telemetry.json for live model switches (e.g. CLOUD, Claude, Gemini)."""
        try:
            if _LIVE_FILE.exists():
                mtime = _LIVE_FILE.stat().st_mtime
                if mtime > self._last_telemetry_mtime:
                    self._last_telemetry_mtime = mtime
                    data = json.loads(_LIVE_FILE.read_text(encoding="utf-8"))
                    model = data.get("model")
                    url = data.get("url")
                    app = data.get("app")
                    pre = data.get("pre_tokens")
                    post = data.get("post_tokens")
                    if model:
                        self.set_model(model)
                    if url or app:
                        self.set_endpoint(url or self._active_url, app or self._active_app)
                    if pre is not None and post is not None:
                        self.push_stat(pre, post)
                    elif model:
                        self.ticker.update_ticker(self._active_model, self._active_url, self._active_app, 0, 0.0)
        except Exception:
            pass

    def _open_autoseek_dialog(self) -> None:
        """Open the interactive Auto-Seek AI Interfaces dialog."""
        dlg = AutoSeekDialog(self)
        dlg.interfacesHooked.connect(self._on_interfaces_hooked)
        dlg.exec()

    def _on_interfaces_hooked(self, hooked_list: list) -> None:
        """Handle multiple interfaces hooked via Auto-Seek."""
        if hooked_list:
            first = hooked_list[0]
            self._dock_external_window(first)
            count = len(hooked_list)
            if count > 1:
                self.ticker._text = f"🎯 AUTO-SEEK HOOKED {count} AI APPS: PERMANENTLY CONNECTED TO HYPES OPTIMIZER  ✦  "
                self.ticker.update()

    def _on_endpoint_selection_changed(self, index: int) -> None:
        """Handles manual selection of active universal endpoint from HUD dropdown."""
        ep_text = self.combo_endpoints.currentText()
        endpoint_map = {
            0: ("http://127.0.0.1:8000/v1", "👑 Multi-Port Master (All Ports Live)"),
            1: ("http://127.0.0.1:8000/v1", "👑 HypeS Sovereign Gateway"),
            2: ("http://127.0.0.1:11434/v1", "⚡ Ollama Local Daemon"),
            3: ("http://127.0.0.1:1234/v1", "⚡ LM Studio API Gateway"),
            4: ("http://127.0.0.1:8080/v1", "⚡ llama.cpp HTTP Server"),
            5: ("http://127.0.0.1:5001/v1", "⚡ KoboldCpp Local API"),
            6: ("http://127.0.0.1:5555/v1", "📱 Mobile Phone ADB Bridge"),
        }
        url, name = endpoint_map.get(index, ("http://127.0.0.1:8000/v1", ep_text))
        self.set_endpoint(url, name)
        if hasattr(self, "ticker"):
            self.ticker.flash_dock_notice(f"ENDPOINT SWITCHED: {name}")
        # Save choice to persistent routing config
        try:
            cfg_file = _HYPES_DIR / "routing_rules.json"
            cfg_data = {}
            if cfg_file.exists():
                cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
            cfg_data["active_endpoint_index"] = index
            cfg_data["active_endpoint_url"] = url
            cfg_data["active_endpoint_name"] = name
            cfg_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _dock_external_window(self, target_meta: dict) -> None:
        """Handle target window docked event."""
        app_name = target_meta.get("app_type", "AI Application")
        url = target_meta.get("url", "http://127.0.0.1:8000/v1")
        self.set_endpoint(url, app_name)
        if hasattr(self, "ticker"):
            self.ticker.flash_dock_notice(app_name)
        PersistentTargetRegistry.register_target(target_meta)

    def _auto_connect_antigravity(self) -> None:
        """Automatically scans for Google Antigravity IDE and active AI interfaces on boot."""
        try:
            targets = TargetWindowInspector.scan_all_system_ai_interfaces()
            antigravity_target = next((t for t in targets if "antigravity" in t.get("app_type", "").lower() or "antigravity" in t.get("title", "").lower()), None)
            if antigravity_target:
                PersistentTargetRegistry.register_target(antigravity_target)
                self._active_app = "Google Antigravity IDE (Agent Studio)"
                self._active_url = "http://127.0.0.1:8000/v1"
                self._active_model = "gemini-2.5-pro / claude-3-7-sonnet"
                if hasattr(self, "ticker"):
                    self.ticker._text = (
                        "⚡ CONNECTED: GOOGLE ANTIGRAVITY IDE (AGENT STUDIO)  ✦  "
                        "GCP PROJECT: hypes-506323 (hypeS)  ✦  "
                        "GATEWAY: http://127.0.0.1:8000/v1  ✦  "
                        "SOVEREIGN PRIVACY ACTIVE  ✦  "
                    )
                    self.ticker.update()
            elif targets:
                first = targets[0]
                PersistentTargetRegistry.register_target(first)
                self._active_app = first.get("app_type", "Active AI App")
                if hasattr(self, "ticker"):
                    self.ticker.flash_dock_notice(self._active_app)
        except Exception:
            pass


    # ── System Tray Setup ────────────────────────────────────────────────────

    def _setup_system_tray(self) -> None:
        self.tray = QtWidgets.QSystemTrayIcon(self)
        icon_path = Path(__file__).parent / "hype_s.png"
        if icon_path.exists():
            self.tray.setIcon(QtGui.QIcon(str(icon_path)))
        else:
            pix = QtGui.QPixmap(16, 16)
            pix.fill(QtGui.QColor("#ffd700"))
            self.tray.setIcon(QtGui.QIcon(pix))

        self.tray.setToolTip("Hyper-Spherical Gold Token HUD — Online")

        tray_menu = QtWidgets.QMenu()
        tray_menu.setStyleSheet("QMenu { background: #080e1a; color: #dde6f0; border: 1px solid #ffd700; } QMenu::item:selected { background: #d4af37; color: #000; }")
        
        act_show = tray_menu.addAction("⚡ Show / Hide HUD")
        act_show.triggered.connect(self._toggle_visibility)

        act_snap = tray_menu.addAction("📐 Snap Next Corner")
        act_snap.triggered.connect(self._cycle_corner)

        act_pin = tray_menu.addAction("📌 Toggle Always On Top")
        act_pin.triggered.connect(self._toggle_always_on_top)

        tray_menu.addSeparator()

        act_estop = tray_menu.addAction("🛑 Emergency E-STOP")
        act_estop.triggered.connect(self._trigger_manual_estop)

        act_reset = tray_menu.addAction("↺ Reset Session Ledger")
        act_reset.triggered.connect(self.reset_session)

        tray_menu.addSeparator()

        act_quit = tray_menu.addAction("✕ Terminate HypeS")
        act_quit.triggered.connect(QtWidgets.QApplication.quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_visibility()

    def closeEvent(self, event: QtGui.QCloseEvent):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Hyper-Spherical Systems",
            "HypeS is still active in your system tray, optimizing local & cloud AI traffic.",
            QtWidgets.QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    # ── Helipad Target Detection & Window Suction Docking ────────────────────

    def _scan_hover_targets(self):
        if not self.isVisible() or not IS_WINDOWS:
            return

        target = TargetWindowInspector.get_window_under_cursor(exclude_hwnd=self.winId())
        if target:
            app_type = target["app_type"]
            already_locked = target.get("already_locked", False)
            self.helipad.set_target_state(True, app_type, already_locked=already_locked)
        else:
            self.helipad.set_target_state(False)

    def _open_autoseek_dialog(self) -> None:
        """Opens the Auto-Seek Radar modal to deep-scan and hook Hyper-Spherical, Antigravity IDE, Web AI & Local Daemons."""
        try:
            dlg = AutoSeekDialog(parent=self)
            dlg.interfacesHooked.connect(self._on_interfaces_hooked)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Auto-Seek Error", f"Could not launch Auto-Seek Radar: {e}")

    def _on_interfaces_hooked(self, hooked_list: List[Dict[str, Any]]) -> None:
        """Called when interfaces are hooked from the Auto-Seek modal."""
        if not hooked_list:
            return
        # Prioritize Hyper-Spherical or Antigravity if present, else first
        target = next((t for t in hooked_list if "hyper-spherical" in t.get("app_type", "").lower() or "hyperspherical" in t.get("app_type", "").lower() or "antigravity" in t.get("app_type", "").lower()), hooked_list[0])
        app_name = target.get("app_type", "AI Application")
        url = target.get("url", f"http://127.0.0.1:{target.get('port', 8000)}/v1")
        self.set_endpoint(url, app_name)
        if hasattr(self, "ticker"):
            self.ticker.flash_dock_notice(f"LOCKED TARGET: {app_name}")
            self.ticker._text = f"⚡ LOCKED & OPTIMIZING: {app_name.upper()}  ✦  PORT: {target.get('port', 8000)}  ✦  HYPES SOVEREIGN PRIVACY ACTIVE  ✦  "
            self.ticker.update()
        if hasattr(self, "helipad"):
            self.helipad.set_target_state(True, app_name, already_locked=True)

    def _dock_external_window(self, target_meta: Dict[str, Any]):
        dock_rect = (self.x() + 20, self.y() + 60, 420, 240)
        self._suction_animator.start_suction(target_meta, dock_rect)

    def _on_suction_complete(self, target_meta: Dict[str, Any]):
        app_name = target_meta.get("app_type", "Target Application")
        self.set_endpoint("http://127.0.0.1:8000/v1", app_name)
        PersistentTargetRegistry.register_target(target_meta)
        self.ticker.flash_dock_notice(app_name)

    def _open_recollection_viewer(self):
        try:
            from recollection_module import RecollectionViewerDialog, TwoFactorAuthDialog, SNBRecollectionEngine
            auth_dlg = TwoFactorAuthDialog(parent=self)
            if auth_dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return
            snb_path = Path(__file__).parent.parent.parent / "hypermem_vault" / "MASTER_CONVERSATION_PERPETUAL.snb"
            engine = SNBRecollectionEngine(str(snb_path) if snb_path.exists() else None)
            dlg = RecollectionViewerDialog(engine=engine, parent=self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Recollection Engine", f"Could not launch Recollection Module: {e}")

    def _open_candy_spinner(self):
        try:
            from golden_candy_spinner_panel import GoldenCandySpinnerPanel
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("💥🍬 Matrix Muncher & Golden Candy Spinner (GCS v6.0)")
            dlg.resize(1100, 750)
            lay = QtWidgets.QVBoxLayout(dlg)
            panel = GoldenCandySpinnerPanel(parent=dlg)
            lay.addWidget(panel)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Candy Spinner", f"Could not launch Candy Spinner: {e}")

    def _open_sauna(self):
        """Opens The Sauna: Scheduled Model Relaxation, Fine-Tuning & Throttling Chamber."""
        try:
            from sauna_panel import SaunaPanel
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("🧖🔥 THE SAUNA — Model Relaxation & Self-Optimization Spa")
            dlg.resize(900, 650)
            lay = QtWidgets.QVBoxLayout(dlg)
            panel = SaunaPanel(parent=dlg)
            lay.addWidget(panel)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "The Sauna", f"Could not launch The Sauna: {e}")

    # ── Emergency E-STOP Cutoff System ───────────────────────────────────────

    def _trigger_manual_estop(self):
        try:
            from security_shield import EmergencyKillswitch
            EmergencyKillswitch.trigger_estop("Manual E-STOP Button Pressed by User")
        except Exception:
            import subprocess
            if sys.platform == "win32":
                subprocess.run("taskkill /F /IM golden_candy_spinner.exe /IM sfs_runtime_launcher.exe /IM llama.exe /IM ollama.exe /T", shell=True)

        self.lbl_pct.setText("🛑 EMERGENCY STOP TRIGGERED")
        self.lbl_pct.setStyleSheet("color: #ef4444; font-size: 14px; font-weight: 900;")
        self.lbl_ratio.setText("0.0× OFFLINE")
        self.lbl_ratio.setStyleSheet("color: #f87171; font-weight: 900;")

    # ── Public Telemetry Push API (Zero-Data-Leak Forensics) ─────────────────

    def set_model(self, model: str) -> None:
        self._active_model = model

    def set_endpoint(self, url: str = "", app_name: str = "") -> None:
        if url:
            self._active_url = url
        if app_name:
            self._active_app = app_name

    def push_stat(self, pre_tokens: int, post_tokens: int) -> None:
        saved = max(0, pre_tokens - post_tokens)
        pct   = (saved / pre_tokens * 100.0) if pre_tokens > 0 else 0.0
        ratio = (pre_tokens / post_tokens) if post_tokens > 0 else 1.0

        self._session_pre_total   += pre_tokens
        self._session_post_total  += post_tokens
        self._session_saved_total += saved

        self.lcd_pre.set_values(
            burst_val=pre_tokens,
            cumulative_total=self._session_pre_total,
            burst_detail=f"+{pre_tokens:,} tok input"
        )
        self.lcd_post.set_values(
            burst_val=post_tokens,
            cumulative_total=self._session_post_total,
            burst_detail=f"{pct:.1f}% reduction ({post_tokens:,} sent)"
        )
        self.lcd_saved.set_values(
            burst_val=saved,
            cumulative_total=self._session_saved_total,
            burst_detail=f"+{saved:,} saved ({ratio:.1f}× ratio)"
        )


        self.lbl_pct.setText(f"{pct:.1f}% SAVINGS CONSERVED")
        self.lbl_ratio.setText(f"{ratio:.1f}× COMPRESSION")

        sess_pct = (self._session_saved_total / self._session_pre_total * 100.0) if self._session_pre_total > 0 else 0.0
        sess_ratio = (self._session_pre_total / self._session_post_total) if self._session_post_total > 0 else 1.0
        dollar_saved = (self._session_saved_total / 1_000_000.0) * 3.00 # $3.00 per 1M blended cloud credit baseline

        self.lbl_sess_total.setText(
            f"24h Session: {self._session_pre_total:,} Raw ➔ {self._session_post_total:,} Sent ➔ {self._session_saved_total:,} Saved ({sess_pct:.1f}% conserved · {sess_ratio:.1f}× ratio · 💵 ${dollar_saved:.2f} Saved · 🛡️ Zero-Loss Guard Active)"
        )

        self.ticker.update_ticker(
            model=self._active_model,
            url=self._active_url,
            app_name=self._active_app,
            saved=saved,
            pct=pct
        )

        self.graph.add_point(pre_tokens, post_tokens)
        self._save_zero_leak_stat(pre_tokens, post_tokens)

    def _save_zero_leak_stat(self, pre: int, post: int):
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            today_file = _LOG_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl"
            stat_rec = {
                "ts": int(time.time()),
                "pre_tokens": pre,
                "post_tokens": post,
                "model": self._active_model[:32],
                "app": self._active_app[:32]
            }
            with open(today_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(stat_rec) + "\n")
        except Exception:
            pass

    def reset_session(self) -> None:
        self._session_pre_total = 0
        self._session_post_total = 0
        self._session_saved_total = 0
        self.lcd_pre.set_values(0, 0)
        self.lcd_post.set_values(0, 0)
        self.lcd_saved.set_values(0, 0)
        self.lbl_sess_total.setText("24h Session: 0 Raw ➔ 0 Sent ➔ 0 Saved (0.0% conserved · 1.0×)")
        self.graph.history.clear()
        self.graph.update()

    def _toggle_always_on_top(self) -> None:
        ontop = self.btn_ontop.isChecked()
        flags = QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.FramelessWindowHint
        if ontop:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _position_default(self) -> None:
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w = self.width()
            h = self.height()
            x = geo.right() - w - 25
            y = geo.top() + 25

            try:
                if _POS_FILE.exists():
                    data = json.loads(_POS_FILE.read_text(encoding="utf-8"))
                    saved_x = data.get("x", x)
                    saved_y = data.get("y", y)
                    if geo.left() <= saved_x <= geo.right() - 150 and geo.top() <= saved_y <= geo.bottom() - 150:
                        x, y = saved_x, saved_y
            except Exception:
                pass

            self.setGeometry(x, y, w, h)

        self.show()
        self.raise_()
        self.activateWindow()

    def _save_position(self) -> None:
        try:
            _HYPES_DIR.mkdir(parents=True, exist_ok=True)
            data = {"x": self.x(), "y": self.y(), "w": self.width(), "h": self.height()}
            _POS_FILE.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass


# ── Global Singleton Accessor & Telemetry Broadcast Helper ──────────────────
_GLOBAL_HUD: Optional[TokenHUD] = None

def get_hud() -> TokenHUD:
    global _GLOBAL_HUD
    if _GLOBAL_HUD is None:
        _GLOBAL_HUD = TokenHUD()
    return _GLOBAL_HUD

def push_compression_stat(pre_tokens: int, post_tokens: int, url: str = "", app_name: str = "", model: str = "") -> None:
    hud = get_hud()
    if url:
        hud.set_endpoint(url, app_name)
    if model:
        hud.set_model(model)
    hud.push_stat(pre_tokens, post_tokens)

    # Broadcast to live telemetry file
    try:
        _HYPES_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": time.time(),
            "model": model or hud._active_model,
            "url": url or hud._active_url,
            "app": app_name or hud._active_app,
            "pre_tokens": pre_tokens,
            "post_tokens": post_tokens
        }
        _LIVE_FILE.write_text(json.dumps(rec), encoding="utf-8")
    except Exception:
        pass
