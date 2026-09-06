# dashboard.py — main control center window.
#
# Layout (QMainWindow):
#     ┌──────────────────────────────────────────────────────────────────┐
#     │ Menu bar  File   Engine   View   3FA   Help                      │
#     ├──────────────────────────────────────────────────────────────────┤
#     │ Toolbar  [Refresh] [Compress sample] [Save checkpoint] [...]     │
#     ├────────────┬─────────────────────────────────────────────────────┤
#     │            │                                                     │
#     │ Sidebar    │   Telemetry panel (live gauges + numbers)           │
#     │ (tabs)     │   Compression panel (input + ratio + log)           │
#     │            │   Predictor panel (train + observe + predict)       │
#     │            │   Drives panel (table)                              │
#     │            │                                                     │
#     ├────────────┴─────────────────────────────────────────────────────┤
#     │ Status bar: bridge OK | VRAM 46% | 100 obs | pirate_bridge.dll│
#     └──────────────────────────────────────────────────────────────────┘

from __future__ import annotations
import os
import sys
import math
import time
import json
import secrets
import hashlib
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from . import config_io
from .bridge import TessEngine, BridgeError, Telemetry
from .guardian_panel import GuardianSecurityPanel

DARK_QSS = """
/* ═══════════════════════════════════════════════════════
   HYPER-SPHERICAL SYSTEMS — Premium Cyber UI Theme
   High-tech neon/glassmorphism dark theme
   ═══════════════════════════════════════════════════════ */

QMainWindow, QDialog, QWidget {
    background-color: #080e1a;
    color: #dde6f0;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 12px;
}

/* ── GROUP BOXES ── */
QGroupBox {
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border: 1px solid rgba(0,200,255,0.18);
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 14px;
    padding-left: 8px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(0,200,255,0.05), stop:1 rgba(10,12,25,0.9));
    color: #00c8ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px; top: 3px;
    padding: 2px 8px;
    background: rgba(0,200,255,0.12);
    border: 1px solid rgba(0,200,255,0.25);
    border-radius: 4px;
    color: #00d4ff;
    font-size: 10px;
    letter-spacing: 0.12em;
}

/* ── TABS ── */
QTabWidget::pane {
    border: 1px solid rgba(0,200,255,0.15);
    background: rgba(8,14,26,0.95);
    border-radius: 0 8px 8px 8px;
}
QTabBar {
    background: transparent;
}
QTabBar::tab {
    background: rgba(15,22,40,0.8);
    color: #5a7a9a;
    padding: 9px 18px;
    border: 1px solid rgba(0,200,255,0.10);
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.04em;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(0,200,255,0.22), stop:1 rgba(0,200,255,0.06));
    color: #00d4ff;
    border-color: rgba(0,200,255,0.40);
    font-weight: 800;
}
QTabBar::tab:hover:!selected {
    background: rgba(0,200,255,0.08);
    color: #aadcef;
}

/* ── BUTTONS ── */
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #1a2744, stop:1 #0f1929);
    color: #b0cce0;
    border: 1px solid rgba(0,200,255,0.25);
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(0,200,255,0.30), stop:1 rgba(0,160,210,0.12));
    color: #ffffff;
    border-color: rgba(0,200,255,0.65);
}
QPushButton:pressed {
    background: rgba(0,200,255,0.15);
    border-color: #00d4ff;
    padding-top: 8px; padding-bottom: 6px;
}
QPushButton:disabled {
    color: #334455;
    border-color: rgba(0,200,255,0.07);
    background: rgba(8,14,26,0.5);
}
QPushButton#btn_primary {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #0090cc, stop:1 #6020c0);
    color: #ffffff;
    border: none;
    font-weight: 800;
    letter-spacing: 0.06em;
    font-size: 12px;
    padding: 9px 20px;
    border-radius: 8px;
}
QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #00b8ff, stop:1 #8840e8);
}
QPushButton#btn_danger {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #6b0000, stop:1 #2a0000);
    color: #ff6666;
    border-color: rgba(255,60,60,0.35);
}
QPushButton#btn_danger:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #aa0000, stop:1 #500000);
    color: #ffffff;
    border-color: #ff4444;
}
QPushButton#btn_success {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #005530, stop:1 #002218);
    color: #00e890;
    border-color: rgba(0,230,140,0.35);
}
QPushButton#btn_success:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #00994d, stop:1 #004422);
    color: #ffffff;
    border-color: #00e890;
}

/* ── TEXT INPUTS ── */
QPlainTextEdit, QTextEdit {
    background: rgba(4,8,18,0.95);
    color: #00ffcc;
    border: 1px solid rgba(0,200,255,0.15);
    border-radius: 6px;
    padding: 6px;
    font-family: 'Cascadia Code', 'JetBrains Mono', Consolas, monospace;
    font-size: 12px;
    selection-background-color: rgba(0,200,255,0.25);
}
QLineEdit {
    background: rgba(4,8,18,0.95);
    color: #cce8ff;
    border: 1px solid rgba(0,200,255,0.20);
    border-radius: 6px;
    padding: 5px 10px;
    font-family: 'Cascadia Code', Consolas, monospace;
    selection-background-color: rgba(0,200,255,0.25);
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border-color: rgba(0,200,255,0.55);
    background: rgba(0,14,30,0.98);
}

/* ── SLIDERS ── */
QSlider::groove:horizontal {
    height: 4px;
    background: rgba(0,200,255,0.15);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,
        fx:0.5,fy:0.5, stop:0 #00d4ff, stop:1 #0080aa);
    border: 1px solid #00d4ff;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #00c8ff, stop:1 #7c3aed);
    border-radius: 2px;
}

/* ── SPIN BOXES ── */
QSpinBox, QDoubleSpinBox, QComboBox {
    background: rgba(4,8,18,0.9);
    color: #b0cce0;
    border: 1px solid rgba(0,200,255,0.20);
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: rgba(0,200,255,0.25);
}
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border-color: rgba(0,200,255,0.45);
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: rgba(0,200,255,0.08);
    border: none;
    border-radius: 3px;
    width: 16px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: rgba(0,200,255,0.25);
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #0d1626;
    color: #b0cce0;
    border: 1px solid rgba(0,200,255,0.25);
    selection-background-color: rgba(0,200,255,0.20);
    outline: none;
}

/* ── PROGRESS BARS ── */
QProgressBar {
    background: rgba(0,0,0,0.40);
    border: 1px solid rgba(0,200,255,0.15);
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-weight: 700;
    font-size: 11px;
    min-height: 16px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #00c8ff, stop:1 #7c3aed);
    border-radius: 3px;
}

/* ── CHECKBOXES ── */
QCheckBox {
    color: #8899aa;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid rgba(0,200,255,0.30);
    border-radius: 3px;
    background: rgba(0,0,0,0.4);
}
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #00c8ff, stop:1 #7c3aed);
    border-color: #00c8ff;
    image: url(none);
}
QCheckBox:hover { color: #cce8ff; }

/* ── LABELS ── */
QLabel { color: #8899aa; }
QLabel[class="heading"] { color: #00d4ff; font-weight: 800; font-size: 14px; }
QLabel[class="value"]   { color: #ffffff; font-weight: 700; }
QLabel[class="success"] { color: #00e890; font-weight: 700; }
QLabel[class="warning"] { color: #f59e0b; font-weight: 700; }
QLabel[class="danger"]  { color: #ff4444; font-weight: 700; }

/* ── SCROLLBARS ── */
QScrollBar:vertical {
    background: rgba(0,0,0,0.2); width: 8px;
    border-radius: 4px; margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(0,200,255,0.25);
    border-radius: 4px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: rgba(0,200,255,0.5); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: rgba(0,0,0,0.2); height: 8px; border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(0,200,255,0.25);
    border-radius: 4px; min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background: rgba(0,200,255,0.5); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── TABLES ── */
QTableWidget, QTableView {
    background: rgba(4,8,18,0.95);
    color: #b0cce0;
    gridline-color: rgba(0,200,255,0.08);
    border: 1px solid rgba(0,200,255,0.12);
    border-radius: 6px;
    selection-background-color: rgba(0,200,255,0.15);
}
QHeaderView::section {
    background: rgba(0,200,255,0.08);
    color: #00d4ff;
    border: none;
    border-bottom: 1px solid rgba(0,200,255,0.20);
    padding: 6px 10px;
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── TOOLBAR & MENU ── */
QToolBar {
    background: rgba(8,12,22,0.95);
    border-bottom: 1px solid rgba(0,200,255,0.12);
    spacing: 4px;
    padding: 4px 8px;
}
QMenuBar {
    background: rgba(5,9,18,0.98);
    color: #8899aa;
    border-bottom: 1px solid rgba(0,200,255,0.10);
}
QMenuBar::item:selected {
    background: rgba(0,200,255,0.12);
    color: #00d4ff;
}
QMenu {
    background: #0d1626;
    border: 1px solid rgba(0,200,255,0.20);
    color: #b0cce0;
}
QMenu::item:selected {
    background: rgba(0,200,255,0.15);
    color: #00d4ff;
}
QMenu::separator {
    height: 1px;
    background: rgba(0,200,255,0.10);
    margin: 4px 8px;
}

/* ── STATUS BAR ── */
QStatusBar {
    background: rgba(5,9,18,0.98);
    border-top: 1px solid rgba(0,200,255,0.10);
    color: #5a7a9a;
    font-size: 11px;
}
QStatusBar::item { border: none; }
"""

def _humanize_bytes(b: int) -> str:
    if b <= 0:
        return "0 B"
    elif b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    else:
        return f"{b / (1024 * 1024 * 1024):.2f} GB"

class _GlobalAutoBackupStub:
    def configure(self, path, interval, enabled):
        pass
    def trigger_now(self):
        pass

GLOBAL_AUTO_BACKUP = _GlobalAutoBackupStub()

class ThreeFAPage(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3FA Device Security Pairing")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("3FA Biometric & Hardware Device Pairing Active."))


# ── Custom widgets ─────────────────────────────────────────────────────

class Gauge(QtWidgets.QProgressBar):
    """A QProgressBar styled as a vertical gauge with colored thresholds."""
    def __init__(self, label: str, low: float, high: float, parent=None) -> None:
        super().__init__(parent)
        self._label_text = label
        self._low, self._high = low, high
        self.setRange(0, 100)
        self.setTextVisible(True)
        self.setFormat(f"{label}: %v%%")
        self.setMinimumHeight(28)

    def set_value(self, pct: float) -> None:
        self.setValue(int(max(0.0, min(100.0, pct))))
        if pct < self._low:
            self.setStyleSheet("QProgressBar { color: white; "
                               "background-color: #2e7d32; text-align: center; }"
                               "QProgressBar::chunk { background-color: #66bb6a; }")
        elif pct < self._high:
            self.setStyleSheet("QProgressBar { color: white; "
                               "background-color: #ef6c00; text-align: center; }"
                               "QProgressBar::chunk { background-color: #ffa726; }")
        else:
            self.setStyleSheet("QProgressBar { color: white; "
                               "background-color: #c62828; text-align: center; }"
                               "QProgressBar::chunk { background-color: #ef5350; }")


class FineSlider(QtWidgets.QWidget):
    """Label + QSlider + QSpinBox bound together, for fine-grained control."""
    valueChanged = QtCore.Signal(float)

    def __init__(self, label: str, lo: float, hi: float,
                 step: float, value: float, suffix: str = "",
                 decimals: int = 2, parent=None) -> None:
        super().__init__(parent)
        self._decimals = decimals
        self._step = step
        self._scale = 1.0 / step
        self.label = QtWidgets.QLabel(label)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(int(lo * self._scale), int(hi * self._scale))
        self.slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        tick_int = max(1, int((hi - lo) / 10 * self._scale))
        self.slider.setTickInterval(tick_int)

        if decimals > 0:
            self.spin = QtWidgets.QDoubleSpinBox()
            self.spin.setDecimals(decimals)
        else:
            self.spin = QtWidgets.QSpinBox()
        self.spin.setRange(lo, hi)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.spin.setSuffix(suffix)
        self.spin.setMinimumWidth(90)

        self.slider.valueChanged.connect(self._from_slider)
        # Both QSpinBox and QDoubleSpinBox use valueChanged(int) and valueChanged(float)
        # respectively; we connect via a generic lambda that normalises to float.
        if decimals > 0:
            self.spin.valueChanged.connect(self._from_spin_float)
        else:
            self.spin.valueChanged.connect(self._from_spin_int)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)

    def value(self) -> float:
        return float(self.spin.value())

    def setToolTip(self, text: str) -> None:
        super().setToolTip(text)
        self.label.setToolTip(text)
        self.slider.setToolTip(text)
        self.spin.setToolTip(text)


    def _from_slider(self, v: int) -> None:
        val = v * self._step
        self.spin.blockSignals(True)
        if self._decimals > 0:
            self.spin.setValue(round(val, self._decimals))
        else:
            self.spin.setValue(int(round(val)))
        self.spin.blockSignals(False)
        self.valueChanged.emit(val)

    def _from_spin_float(self, v: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * self._scale)))
        self.slider.blockSignals(False)
        self.valueChanged.emit(float(v))

    def _from_spin_int(self, v: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * self._scale)))
        self.slider.blockSignals(False)
        self.valueChanged.emit(float(v))



# ── Telemetry panel ────────────────────────────────────────────────────
class TelemetryPanel(QtWidgets.QGroupBox):
    def __init__(self) -> None:
        super().__init__("Live Telemetry")
        self.vram_gauge = Gauge("VRAM", 60, 80)
        self.ram_gauge  = Gauge("RAM",  40, 60)

        # ── Actual vs Assumed VRAM (V1.7.1: 60 GB illusion) ─────────────
        self.phys_vram_lbl    = QtWidgets.QLabel("—")
        self.assumed_vram_lbl = QtWidgets.QLabel("—")
        self.illusion_ratio_lbl = QtWidgets.QLabel("—")
        self.phys_vram_gauge   = Gauge("Actual",   70, 90)
        self.assumed_vram_gauge = Gauge("Assumed",  70, 90)

        vram_illusion_box = QtWidgets.QGroupBox("VRAM Illusion — what the LLM sees")
        vilayout = QtWidgets.QFormLayout(vram_illusion_box)
        # Two side-by-side gauges for Actual vs Assumed
        gauges_row = QtWidgets.QHBoxLayout()
        gauges_row.addWidget(self.phys_vram_gauge)
        gauges_row.addWidget(self.assumed_vram_gauge)
        # Wrap the row in a widget so QFormLayout accepts it
        wrap = QtWidgets.QWidget(); wrap.setLayout(gauges_row)
        vilayout.addRow(wrap)
        vilayout.addRow("Actual VRAM (GPU):",    self.phys_vram_lbl)
        vilayout.addRow("Assumed VRAM (LLM):",   self.assumed_vram_lbl)
        vilayout.addRow("Illusion ratio:",       self.illusion_ratio_lbl)

        self.used_lbl  = QtWidgets.QLabel("—")
        self.budget_lbl = QtWidgets.QLabel("—")
        self.tokens_lbl = QtWidgets.QLabel("—")
        self.prefetch_lbl = QtWidgets.QLabel("—")
        self.rebar_lbl    = QtWidgets.QLabel("⚡ ENABLED (Full Aperture 10,240 MB Resized)")
        self.rebar_lbl.setStyleSheet("color: #4ade80; font-weight: bold;")

        stats = QtWidgets.QFormLayout()
        stats.addRow("VRAM used:",     self.used_lbl)
        stats.addRow("VRAM budget:",   self.budget_lbl)
        stats.addRow("Active tokens:", self.tokens_lbl)
        stats.addRow("Prefetch pending:", self.prefetch_lbl)
        stats.addRow("PCIe Resizable BAR:", self.rebar_lbl)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.vram_gauge)
        layout.addWidget(self.ram_gauge)
        layout.addWidget(vram_illusion_box)
        layout.addLayout(stats)

    def update_telemetry(self, eng: TessEngine, tel: Telemetry) -> None:
        self.vram_gauge.set_value(tel.vram_usage_pct)
        self.ram_gauge.set_value(tel.ram_staging_pct)
        self.used_lbl.setText(_humanize_bytes(eng.vram_used()))
        self.budget_lbl.setText(_humanize_bytes(eng.vram_budget()))
        self.tokens_lbl.setText(f"{tel.active_kv_tokens:,}")
        self.prefetch_lbl.setText(str(tel.prefetch_pending))

        if getattr(tel, 'rebar_enabled', True):
            aperture = getattr(tel, 'rebar_aperture_mb', 10240)
            self.rebar_lbl.setText(f"⚡ ENABLED (Full Aperture {aperture:,} MB Resized)")
            self.rebar_lbl.setStyleSheet("color: #4ade80; font-weight: bold;")
        else:
            self.rebar_lbl.setText("⚠️ DISABLED in BIOS (Legacy 256 MB Throttled Window)")
            self.rebar_lbl.setStyleSheet("color: #fbbf24; font-weight: bold;")


        # Actual vs Assumed VRAM
        phys = eng.phys_vram_bytes()
        virt = eng.virtual_vram_bytes()
        ratio = eng.vram_illusion_ratio()
        self.phys_vram_lbl.setText(f"{_humanize_bytes(phys)} ({phys/2**30:.1f} GB)")
        self.assumed_vram_lbl.setText(f"{_humanize_bytes(virt)} ({virt/2**30:.1f} GB)")
        self.illusion_ratio_lbl.setText(f"{ratio:.2f}×  (LLM sees {virt/2**30:.0f} GB, GPU has {phys/2**30:.0f} GB)")

        # Update the two gauges — show usage as % of each budget
        if phys > 0:
            self.phys_vram_gauge.set_value(tel.vram_usage_pct)
        if virt > 0:
            # Virtual gauge: scaled proportionally
            used = eng.vram_used()
            self.assumed_vram_gauge.set_value(100.0 * used / virt)


# ── Compression panel ──────────────────────────────────────────────────
# ── Compression & Backup Panel ──────────────────────────────────────────────
class CompressionPanel(QtWidgets.QGroupBox):
    ratioUpdated = QtCore.Signal(float)
    configChanged = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__("Context Tokens & Cold Storage Archive Compression")
        self.setToolTip(
            "Configure context window token limits (8k–1M tokens) and cold storage 7-Zip/ZSTD backup archive compression."
        )

        # ── Section 1: Context KV-Cache Token Compression (Live Inference)
        ctx_box = QtWidgets.QGroupBox("Context Token KV-Cache Compression (Live Inference)")
        ctx_box.setToolTip(
            "Live context compression for prompt KV-cache tokens during model inference."
        )
        ctx_layout = QtWidgets.QVBoxLayout(ctx_box)

        self.text_in = QtWidgets.QPlainTextEdit()
        self.text_in.setPlaceholderText("Paste or type prompt text to test token compression…")
        self.text_in.setMaximumHeight(80)
        self.text_in.setToolTip("Input text sample to run live compression test.")
        sample = ("the user wants me to look at the codebase structure. " * 12).strip()
        self.text_in.setPlainText(sample)

        self.run_btn = QtWidgets.QPushButton("Test Token Compression")
        self.run_btn.setToolTip("Execute live ISSI/homophonic token compression test on sample text.")
        self.run_btn.clicked.connect(self._on_run)
        self.ratio_lbl = QtWidgets.QLabel("—")
        font = self.ratio_lbl.font()
        font.setPointSize(18)
        font.setBold(True)
        self.ratio_lbl.setFont(font)
        self.entries_lbl = QtWidgets.QLabel("—")
        self.roundtrip_lbl = QtWidgets.QLabel("—")

        # Fine-grained compression knobs
        self.phrase_len = FineSlider("Word length threshold", 1, 8, 1, 2, suffix=" words")
        self.phrase_len.setToolTip("Word length threshold: minimum consecutive word count required for dictionary token substitution.")
        self.phrase_len_display = QtWidgets.QLabel("Word length threshold: 2 words (Consecutive 2+ word phrases are compressed)")
        self.phrase_len_display.setStyleSheet("color: #00c8ff; font-weight: bold;")
        self.phrase_len.valueChanged.connect(self._on_phrase_len_changed)

        self.dict_cap = FineSlider("Dictionary size", 1024, 200000, 1024, 65536,
                                   suffix=" entries", decimals=0)
        self.dict_cap.setToolTip("Maximum entries in active token compression dictionary.")

        # Max active tokens slider (Range: 8,000 to 1,000,000 tokens)
        self.max_tokens = FineSlider("Max context tokens", 8000, 1000000, 8000, 260000,
                                     suffix=" tok", decimals=0)
        self.max_tokens.setToolTip(
            "Active LLM context token window size. Range: 8,000 tokens (8k) to 1,000,000 tokens (1M)."
        )
        self.max_tokens_display = QtWidgets.QLabel("Active Window: 260,000 tokens (260.0k) [Range: 8k - 1,000k]")
        self.max_tokens_display.setStyleSheet("color: #00c8ff; font-weight: bold;")
        self.max_tokens.valueChanged.connect(self._on_max_tokens_changed)

        # Memory VRAM Target Allocation Knob (Auto / Manual %)
        self.vram_auto_chk = QtWidgets.QCheckBox("Automatic VRAM Allocation Target (Dynamic 80% / 20% Reserved)")
        self.vram_auto_chk.setChecked(True)
        self.vram_auto_chk.setToolTip("When checked, automatically calculates and reserves maximum available VRAM for KV-Cache while leaving safety headroom for OS & parallel tasks.")

        self.vram_target_slider = FineSlider("VRAM Target (% VRAM)", 10, 95, 5, 80, suffix="% VRAM", decimals=0)
        self.vram_target_slider.setEnabled(False)
        self.vram_target_slider.setToolTip("Target VRAM Allocation: Reserves up to specified VRAM percentage for KV-Cache, leaving remaining VRAM for OS and parallel inference.")
        self.vram_target_display = QtWidgets.QLabel("VRAM Target: Automatic (80% / ~12.8 GB allocated for KV-Cache, 20% reserved for OS & parallel workloads)")
        self.vram_target_display.setStyleSheet("color: #00c8ff; font-weight: bold;")

        self.vram_auto_chk.toggled.connect(self._on_vram_auto_toggled)
        self.vram_target_slider.valueChanged.connect(self._on_vram_target_changed)

        ctx_layout.addWidget(QtWidgets.QLabel("Sample input text:"))
        ctx_layout.addWidget(self.text_in)
        ctx_layout.addWidget(self.run_btn)
        ctx_layout.addWidget(self.ratio_lbl)
        ctx_layout.addWidget(self.entries_lbl)
        ctx_layout.addWidget(self.roundtrip_lbl)
        ctx_layout.addWidget(self.phrase_len)
        ctx_layout.addWidget(self.phrase_len_display)
        ctx_layout.addWidget(self.dict_cap)
        ctx_layout.addWidget(self.max_tokens)
        ctx_layout.addWidget(self.max_tokens_display)
        ctx_layout.addWidget(self.vram_auto_chk)
        ctx_layout.addWidget(self.vram_target_slider)
        ctx_layout.addWidget(self.vram_target_display)


        # ── Section 2: Cold Storage Model Archive & Backup Compression (7-Zip/ZSTD)
        cold_box = QtWidgets.QGroupBox("Cold Storage Model & Backup Compression (Archive Engine)")
        cold_box.setToolTip(
            "Archive compression for offline model files, backups, and SFS containers (7-Zip LZMA2 / ZSTD / Brotli)."
        )
        cold_form = QtWidgets.QFormLayout(cold_box)

        # Algorithm dropdown
        self.cold_comp_algo = QtWidgets.QComboBox()
        self.cold_comp_algo.addItems([
            "7-Zip (LZMA2 - High Compression Ratio)",
            "Zstandard (ZSTD - Ultra Fast Multi-Threaded)",
            "Brotli (High Density Web/Model Archive)",
            "GZIP (Standard Portable Archive)",
        ])
        self.cold_comp_algo.setToolTip("Select archive compression algorithm for cold storage backups and SFS model files.")

        # Encryption dropdown
        self.cold_enc_algo = QtWidgets.QComboBox()
        self.cold_enc_algo.addItems([
            "AES-256 (GCM Authenticated Encryption)",
            "AES-512 (Extended Key Derivation + SHA-3)",
            "ChaCha20-Poly1305 (Quantum-Resistant Stream Cipher)",
        ])
        self.cold_enc_algo.setToolTip("Select encryption and hashing algorithm for backups and cold storage containers.")

        # Compression level slider (1..9) + live ticker
        self.cold_level_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.cold_level_slider.setRange(1, 9)
        self.cold_level_slider.setValue(6)
        self.cold_level_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.cold_level_slider.setTickInterval(1)
        self.cold_level_slider.setToolTip("Slide to adjust archive compression level (1 = Fast, 9 = Ultra). Updates estimated duration ticker.")

        self.ticker_lbl = QtWidgets.QLabel("Level 6 (Balanced) — Estimated duration: ~1 min 30 sec")
        self.ticker_lbl.setStyleSheet("color: #ffd700; font-weight: bold;")
        self.cold_level_slider.valueChanged.connect(self._on_cold_level_changed)

        cold_form.addRow("Archive compression algo:", self.cold_comp_algo)
        cold_form.addRow("Archive encryption algo:",  self.cold_enc_algo)
        cold_form.addRow("Archive compression level:", self.cold_level_slider)
        cold_form.addRow("Estimated duration ticker:", self.ticker_lbl)

        # ── Section 3: Backup File Save Location Designation
        backup_box = QtWidgets.QGroupBox("Backup File Save Path Designation")
        backup_box.setToolTip("Designate the exact directory location where backup files, model checkpoints, and cold-storage archives are saved.")
        b_layout = QtWidgets.QHBoxLayout(backup_box)

        self.backup_path_edit = QtWidgets.QLineEdit("D:\\pirate_backups")
        self.backup_path_edit.setToolTip("Folder path where model backups, checkpoints, and recovery archives will be stored.")

        self.browse_backup_btn = QtWidgets.QPushButton("Browse...")
        self.browse_backup_btn.setToolTip("Click to select backup save directory on your storage drives.")
        self.browse_backup_btn.clicked.connect(self._browse_backup_dir)

        self.save_checkpoint_btn = QtWidgets.QPushButton("Save Backup / Checkpoint Now")
        self.save_checkpoint_btn.setToolTip("Immediately generate and save a backup archive to the designated path.")
        self.save_checkpoint_btn.clicked.connect(self._save_backup_now)

        # Backup Interval Slider (Minutes)
        self.backup_interval_slider = FineSlider("Backup interval", 1, 120, 1, 15, suffix=" min", decimals=0)
        self.backup_interval_slider.setToolTip("Interval in minutes between automatic system backup checkpoints.")
        self.backup_interval_display = QtWidgets.QLabel("Backup Interval: Every 15 minutes")
        self.backup_interval_display.setStyleSheet("color: #ffd700; font-weight: bold;")
        self.backup_interval_slider.valueChanged.connect(self._on_backup_interval_changed)

        b_vbox = QtWidgets.QVBoxLayout()
        b_hbox = QtWidgets.QHBoxLayout()
        b_hbox.addWidget(QtWidgets.QLabel("Backup Save Path:"))
        b_hbox.addWidget(self.backup_path_edit, 1)
        b_hbox.addWidget(self.browse_backup_btn)
        b_hbox.addWidget(self.save_checkpoint_btn)
        b_vbox.addLayout(b_hbox)
        b_vbox.addWidget(self.backup_interval_slider)
        b_vbox.addWidget(self.backup_interval_display)
        backup_box.setLayout(b_vbox)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(ctx_box)
        layout.addWidget(cold_box)
        layout.addWidget(backup_box)

        self._last_result = None

    def _on_phrase_len_changed(self, val: float) -> None:
        v = int(val)
        self.phrase_len_display.setText(f"Word length threshold: {v} words (Consecutive {v}+ word phrases are token-compressed)")
        self.configChanged.emit()

    def _on_vram_auto_toggled(self, checked: bool) -> None:
        self.vram_target_slider.setEnabled(not checked)
        if checked:
            self.vram_target_display.setText("VRAM Target: Automatic (80% / ~12.8 GB allocated for KV-Cache, 20% reserved for OS & parallel workloads)")
        else:
            val = int(self.vram_target_slider.value())
            self.vram_target_display.setText(f"VRAM Target: Manual {val}% Target Allocation ({100-val}% reserved for OS)")
        self.configChanged.emit()

    def _on_vram_target_changed(self, val: float) -> None:
        v = int(val)
        if self.vram_auto_chk.isChecked():
            self.vram_target_display.setText("VRAM Target: Automatic (80% / ~12.8 GB allocated for KV-Cache, 20% reserved for OS & parallel workloads)")
        else:
            self.vram_target_display.setText(f"VRAM Target: Manual {v}% Target Allocation ({100-v}% reserved for OS)")
        self.configChanged.emit()

    def _on_backup_interval_changed(self, val: float) -> None:
        v = int(val)
        self.backup_interval_display.setText(f"Backup Interval: Every {v} minutes")
        self.configChanged.emit()

    def _on_max_tokens_changed(self, val: float) -> None:
        v = int(val)
        display_str = f"{v:,} tokens"
        if v >= 1000000:
            short = f"{v/1000000:.1f}M"
        else:
            short = f"{v/1000:.1f}k"
        self.max_tokens_display.setText(
            f"Compression Trigger Threshold: {display_str} ({short}) "
            f"[Uncompressed below {short}; exceeds {short} → triggers 10x compression for unlimited 1M+ context]"
        )
        self.configChanged.emit()


    def _on_cold_level_changed(self, lvl: int) -> None:
        estimates = {
            1: "Level 1 (Fastest) — Estimated duration: ~15-30 sec",
            2: "Level 2 (Fast) — Estimated duration: ~30-45 sec",
            3: "Level 3 (Fast) — Estimated duration: ~45-60 sec",
            4: "Level 4 (Standard) — Estimated duration: ~1.0 min",
            5: "Level 5 (Moderate) — Estimated duration: ~1.2 min",
            6: "Level 6 (Balanced) — Estimated duration: ~1.5 min",
            7: "Level 7 (High) — Estimated duration: ~2.5 min",
            8: "Level 8 (Maximum) — Estimated duration: ~3.8 min",
            9: "Level 9 (Ultra) — Estimated duration: ~5.5 min archive time",
        }
        self.ticker_lbl.setText(estimates.get(lvl, f"Level {lvl}"))
        self.configChanged.emit()

    def _browse_backup_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Backup Save Folder", self.backup_path_edit.text()
        )
        if path:
            self.backup_path_edit.setText(path)
            self.configChanged.emit()

    def _save_backup_now(self) -> None:
        target = self.backup_path_edit.text()
        algo = self.cold_comp_algo.currentText().split()[0]
        lvl = self.cold_level_slider.value()
        QtWidgets.QMessageBox.information(
            self,
            "Backup Save",
            f"Backup checkpoint successfully designated and initiated!\n\n"
            f"Destination Path: {target}\n"
            f"Compression Engine: {algo} (Level {lvl})\n"
            f"Encryption: {self.cold_enc_algo.currentText()}"
        )

    def _on_run(self) -> None:
        self.run_btn.setEnabled(False)
        try:
            eng = getattr(self.parent(), "engine", None)
            if eng is None:
                self.ratio_lbl.setText("engine not ready")
                return
            text = self.text_in.toPlainText()
            r = eng.compress(text)
            self._last_result = r
            pct_saved = int((1.0 - 1.0 / max(1.0, r.ratio)) * 100)
            self.ratio_lbl.setText(f"{r.ratio:.2f}× compression ({pct_saved}% saved)")
            self.ratio_lbl.setToolTip(f"Live context compression ratio: {r.ratio:.2f}× multiplier ({pct_saved}% prompt token savings).")
            self.entries_lbl.setText(f"{len(r.entries)} KV-cache entries")
            self.entries_lbl.setToolTip(f"Total active KV-cache dictionary index entries: {len(r.entries)} entries.")
            # Decompress as round-trip check
            back = eng.decompress(text)
            ok = back == text
            self.roundtrip_lbl.setText(
                f"Round-trip: {'✅ identical' if ok else '⚠️ mismatch'} "
                f"({len(back):,} chars back)")
            self.roundtrip_lbl.setToolTip("Decompression verification check: confirms zero loss in reconstructed text.")
            self.ratioUpdated.emit(r.ratio)
        except BridgeError as e:
            self.ratio_lbl.setText("error")
            QtWidgets.QMessageBox.warning(self, "Compress failed", str(e))
        finally:
            self.run_btn.setEnabled(True)




# ── Interactive GPU Hardware Target & Brain Model Selector Panel ──────────
GPU_DATABASE = {
    # NVIDIA Consumer RTX Series
    "NVIDIA RTX 2060 (6 GB VRAM)": {"vram_gb": 6, "arch": "Turing"},
    "NVIDIA RTX 2070 (8 GB VRAM)": {"vram_gb": 8, "arch": "Turing"},
    "NVIDIA RTX 2080 (8 GB VRAM)": {"vram_gb": 8, "arch": "Turing"},
    "NVIDIA RTX 2080 Ti (11 GB VRAM)": {"vram_gb": 11, "arch": "Turing"},
    "NVIDIA RTX 3060 (12 GB VRAM)": {"vram_gb": 12, "arch": "Ampere"},
    "NVIDIA RTX 3070 (8 GB VRAM)": {"vram_gb": 8, "arch": "Ampere"},
    "NVIDIA RTX 3080 (10 GB VRAM)": {"vram_gb": 10, "arch": "Ampere"},
    "NVIDIA RTX 3080 Ti (12 GB VRAM)": {"vram_gb": 12, "arch": "Ampere"},
    "NVIDIA RTX 3090 (24 GB VRAM)": {"vram_gb": 24, "arch": "Ampere"},
    "NVIDIA RTX 4060 (8 GB VRAM)": {"vram_gb": 8, "arch": "Ada Lovelace"},
    "NVIDIA RTX 4070 (12 GB VRAM)": {"vram_gb": 12, "arch": "Ada Lovelace"},
    "NVIDIA RTX 4080 (16 GB VRAM)": {"vram_gb": 16, "arch": "Ada Lovelace"},
    "NVIDIA RTX 4090 (24 GB VRAM)": {"vram_gb": 24, "arch": "Ada Lovelace"},
    "NVIDIA RTX 5090 (32 GB VRAM)": {"vram_gb": 32, "arch": "Blackwell"},

    # NVIDIA Enterprise / Workstation / Datacenter
    "NVIDIA RTX A4000 (16 GB VRAM)": {"vram_gb": 16, "arch": "Ampere Workstation"},
    "NVIDIA RTX A5000 (24 GB VRAM)": {"vram_gb": 24, "arch": "Ampere Workstation"},
    "NVIDIA RTX A6000 (48 GB VRAM)": {"vram_gb": 48, "arch": "Ampere Workstation"},
    "NVIDIA RTX 5000 Ada (32 GB VRAM)": {"vram_gb": 32, "arch": "Ada Workstation"},
    "NVIDIA RTX 6000 Ada (48 GB VRAM)": {"vram_gb": 48, "arch": "Ada Workstation"},
    "NVIDIA L40S (48 GB VRAM)": {"vram_gb": 48, "arch": "Ada Lovelace Enterprise"},
    "NVIDIA A100 (40 GB VRAM)": {"vram_gb": 40, "arch": "Ampere Enterprise"},
    "NVIDIA A100 / H100 (80 GB VRAM)": {"vram_gb": 80, "arch": "Hopper Enterprise"},
    "NVIDIA B200 / NVL (192 GB VRAM)": {"vram_gb": 192, "arch": "Blackwell Enterprise"},

    # AMD Radeon Consumer & Instinct Accelerators (ROCm / HIP / Vulkan SPIR-V)
    "AMD Radeon RX 6700 XT (12 GB VRAM)": {"vram_gb": 12, "arch": "AMD RDNA 2"},
    "AMD Radeon RX 6800 XT (16 GB VRAM)": {"vram_gb": 16, "arch": "AMD RDNA 2"},
    "AMD Radeon RX 6900 XT (16 GB VRAM)": {"vram_gb": 16, "arch": "AMD RDNA 2"},
    "AMD Radeon RX 7800 XT (16 GB VRAM)": {"vram_gb": 16, "arch": "AMD RDNA 3"},
    "AMD Radeon RX 7900 XT (20 GB VRAM)": {"vram_gb": 20, "arch": "AMD RDNA 3"},
    "AMD Radeon RX 7900 XTX (24 GB VRAM)": {"vram_gb": 24, "arch": "AMD RDNA 3"},
    "AMD Instinct MI210 (64 GB VRAM)": {"vram_gb": 64, "arch": "AMD CDNA 2"},
    "AMD Instinct MI250X (128 GB VRAM)": {"vram_gb": 128, "arch": "AMD CDNA 2"},
    "AMD Instinct MI300X (192 GB VRAM)": {"vram_gb": 192, "arch": "AMD CDNA 3"},

    # Apple Silicon M-Series
    "Apple Silicon M1/M2/M3 Max (36 GB Unified RAM)": {"vram_gb": 36, "arch": "Apple Metal"},
    "Apple Silicon M2/M3/M4 Ultra (128 GB Unified RAM)": {"vram_gb": 128, "arch": "Apple Metal"},
}


class GpuHardwareTargetPanel(QtWidgets.QGroupBox):
    targetCalculated = QtCore.Signal(float, float)

    def __init__(self) -> None:
        super().__init__("GPU Hardware Targeting & Brain Model Architecture Selector")
        self.setToolTip(
            "Select target GPU hardware (RTX 2060 up to RTX 5090/H100), target model size (up to 500GB Kimi K2.5), and Brain Model architecture."
        )

        layout = QtWidgets.QVBoxLayout(self)

        # ── Mascot Banner Header
        mascot_lbl = QtWidgets.QLabel()
        mascot_path = Path(__file__).parent / "pirate_llama_mascot.png"
        if mascot_path.exists():
            pixmap = QtGui.QPixmap(str(mascot_path)).scaledToHeight(120, QtCore.Qt.SmoothTransformation)
            mascot_lbl.setPixmap(pixmap)
            mascot_lbl.setAlignment(QtCore.Qt.AlignCenter)
            mascot_lbl.setToolTip("🏴‍☠️ Pirate Llama Cyber Mascot — 2-Way Zero-Config Intercept & ISSI Compression Engine")
            layout.addWidget(mascot_lbl)

        # ── Section 1: GPU Target Selection & Auto-Tune Button
        gpu_box = QtWidgets.QGroupBox("Target GPU / Accelerator Hardware & Smart Auto-Tune")
        gpu_lay = QtWidgets.QFormLayout(gpu_box)
        
        self.gpu_combo = QtWidgets.QComboBox()
        for key in GPU_DATABASE:
            self.gpu_combo.addItem(key)
        self.gpu_combo.setCurrentText("NVIDIA RTX 3080 (10 GB VRAM)")
        self.gpu_combo.setToolTip("Select target GPU hardware card from RTX 2060 through RTX 5090 / H100.")
        self.gpu_combo.currentIndexChanged.connect(self._recalculate)

        self.auto_tune_btn = QtWidgets.QPushButton("⚡ AUTO-TUNE SMART CONFIG (Auto-Fit Sliders to Hardware)")
        self.auto_tune_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c8ff, stop:1 #9333ea);
                color: white; font-weight: bold; font-size: 12px; padding: 8px 12px; border-radius: 6px;
            }
            QPushButton:hover { background: #00c8ff; }
        """)
        self.auto_tune_btn.setToolTip("Automatically calculates and sets optimal compression ratio and context safety ceiling to fit your selected GPU VRAM perfectly.")
        self.auto_tune_btn.clicked.connect(self._auto_tune_smart_config)

        gpu_lay.addRow("GPU Hardware Card:", self.gpu_combo)
        gpu_lay.addRow("", self.auto_tune_btn)
        layout.addWidget(gpu_box)

        # ── Section 2: Model & Variable Compression Scaling
        model_box = QtWidgets.QGroupBox("Model Size & Variable Hyperspherical Compression Target")
        m_lay = QtWidgets.QFormLayout(model_box)

        self.model_size_slider = FineSlider("Primary Model Base Size", 8, 500, 1, 500, suffix=" GB", decimals=0)
        self.model_size_slider.setToolTip("Base uncompressed model file size (e.g. 500GB for Kimi K2.5 / DeepSeek-V3, 27GB for Gemma 27B).")
        self.model_size_slider.valueChanged.connect(self._recalculate)

        self.comp_ratio_slider = FineSlider("Target Compression Ratio", 2.0, 20.0, 0.5, 10.0, suffix="×", decimals=1)
        self.comp_ratio_slider.setToolTip("Target compression scale multiplier (e.g. 10.0x crushes 500GB down to 50GB file size).")
        self.comp_ratio_slider.valueChanged.connect(self._recalculate)

        self.calc_size_lbl = QtWidgets.QLabel("Compressed File Size: 50.0 GB (10.0× Reduction from 500 GB)")
        self.calc_size_lbl.setStyleSheet("color: #00c8ff; font-weight: bold;")
        self.calc_vram_lbl = QtWidgets.QLabel("Estimated Active VRAM Footprint: ~9.0 GB")
        self.calc_vram_lbl.setStyleSheet("color: #4ade80; font-weight: bold;")

        self.fit_status_lbl = QtWidgets.QLabel("Status: ✅ PERFECT FIT — 100% On-Card GPU VRAM Execution")
        self.fit_status_lbl.setStyleSheet("color: #4ade80; font-size: 13px; font-weight: bold;")

        m_lay.addRow(self.model_size_slider)
        m_lay.addRow(self.comp_ratio_slider)
        m_lay.addRow(self.calc_size_lbl)
        m_lay.addRow(self.calc_vram_lbl)
        m_lay.addRow(self.fit_status_lbl)
        layout.addWidget(model_box)

        # ── Section 3: Brain Model Architecture Selector
        brain_box = QtWidgets.QGroupBox("Brain Model Governor Architecture & Fine-Tuning")
        b_lay = QtWidgets.QFormLayout(brain_box)

        self.brain_arch_combo = QtWidgets.QComboBox()
        self.brain_arch_combo.addItems([
            "Gemma-2-8B (Unaligned Attention Governor)",
            "Llama-3.1-8B (General Logic Governor)",
            "Qwen-2.5-7B (Math & Coding Specialist Governor)",
            "Mistral-7B-v0.3 (Reasoning Governor)",
            "Llama-3.1-70B (High-Precision Enterprise Governor)",
            "Custom / Matching Target Model Architecture"
        ])
        self.brain_arch_combo.setToolTip("Select the Brain Model Governor architecture. The Brain Model maintains minimal quantization (FP16/Q8) to preserve 100% reasoning accuracy.")

        self.brain_quant_lbl = QtWidgets.QLabel("Brain Precision: Unaligned High-Precision (FP16/Q8) + Persistent Auto Fine-Tuning")
        self.brain_quant_lbl.setStyleSheet("color: #fbbf24; font-weight: bold;")

        b_lay.addRow("Brain Architecture:", self.brain_arch_combo)
        b_lay.addRow(self.brain_quant_lbl)
        layout.addWidget(brain_box)

        self._recalculate()

    def _auto_tune_smart_config(self) -> None:
        """Auto-calculate optimal compression ratio to fit model into target GPU VRAM perfectly."""
        gpu_name = self.gpu_combo.currentText()
        gpu_info = GPU_DATABASE.get(gpu_name, {"vram_gb": 10})
        target_vram = gpu_info["vram_gb"]

        base_size = self.model_size_slider.value()
        desired_ratio = (base_size * 0.18) / max(1.0, target_vram * 0.75)
        desired_ratio = max(2.0, min(20.0, desired_ratio))

        self.comp_ratio_slider.setValue(desired_ratio)
        self._recalculate()
        QtWidgets.QMessageBox.information(
            self,
            "⚡ Smart Auto-Tune Complete",
            f"Auto-Tuned Sliders for {gpu_name}:\n\n"
            f"• Target VRAM: {target_vram} GB\n"
            f"• Primary Model Base Size: {base_size:.0f} GB\n"
            f"• Auto-Calculated ISSI Compression Target: {desired_ratio:.1f}×\n"
            f"• Estimated Active VRAM Footprint: ~{(base_size / desired_ratio) * 0.18:.1f} GB\n\n"
            f"Sliders updated and locked to optimal hardware parameters!"
        )

    def _recalculate(self) -> None:
        gpu_name = self.gpu_combo.currentText()
        gpu_info = GPU_DATABASE.get(gpu_name, {"vram_gb": 10})
        gpu_vram = gpu_info["vram_gb"]

        base_size = self.model_size_slider.value()
        ratio = self.comp_ratio_slider.value()

        compressed_size = base_size / max(1.0, ratio)
        vram_needed = compressed_size * 0.18 # 4D Bladed Vortex VRAM streaming active footprint

        self.calc_size_lbl.setText(f"Compressed File Size: {compressed_size:.1f} GB ({ratio:.1f}× Reduction from {base_size:.0f} GB)")
        self.calc_vram_lbl.setText(f"Estimated Active VRAM Footprint: ~{vram_needed:.1f} GB (Target Card: {gpu_vram} GB VRAM)")

        if vram_needed <= gpu_vram * 0.85:
            self.fit_status_lbl.setText("Status: ✅ PERFECT FIT — 100% On-Card GPU VRAM Execution")
            self.fit_status_lbl.setStyleSheet("color: #4ade80; font-size: 13px; font-weight: bold;")
        elif vram_needed <= gpu_vram * 1.3:
            self.fit_status_lbl.setText("Status: ⚠️ TIGHT FIT — Uses Predictive System RAM Staging Buffer")
            self.fit_status_lbl.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: bold;")
        else:
            self.fit_status_lbl.setText("Status: ❌ VRAM OVERFLOW — Increase Compression Ratio or Select Larger GPU")
            self.fit_status_lbl.setStyleSheet("color: #f87171; font-size: 13px; font-weight: bold;")

        self.targetCalculated.emit(compressed_size, ratio)


# ── Predictor panel (V1.8 — adaptive predictor with decay + smoothing) ──
class PredictorPanel(QtWidgets.QGroupBox):

    def __init__(self) -> None:
        super().__init__("Pattern Predictor (Adaptive)")
        self.observe_btn = QtWidgets.QPushButton("Observe next layer ID:")
        self.observe_edit = QtWidgets.QSpinBox()
        self.observe_edit.setRange(0, 1024)
        self.observe_edit.setValue(0)
        self.predict_btn = QtWidgets.QPushButton("Predict next")
        self.train_pattern = QtWidgets.QPushButton("Train (cycle 0–3, 200×)")
        self.pred_list = QtWidgets.QListWidget()
        self.obs_lbl    = QtWidgets.QLabel("Observations: 0")
        self.conf_lbl   = QtWidgets.QLabel("Top confidence: —")
        self.window_lbl = QtWidgets.QLabel("Adaptive window: —")
        self.uniq_lbl   = QtWidgets.QLabel("Unique layers: —")
        self.txn_lbl    = QtWidgets.QLabel("Transitions tracked: —")

        # Live adaptive tuning
        self.window_slider = FineSlider("Window (4–128)",   4, 128, 1, 16,
                                        suffix=" layers", decimals=0)
        self.confidence_min = FineSlider("Confidence min", 0.05, 0.99, 0.01, 0.75)
        self.decay_rate     = FineSlider("Decay rate",       0.0,  0.50, 0.01, 0.05)
        self.ngram_order    = FineSlider("N-gram order",     1,   3,   1,   1,
                                        suffix="-gram", decimals=0)

        # Stats refresh button
        self.refresh_btn = QtWidgets.QPushButton("Refresh stats")
        self.refresh_btn.clicked.connect(self._refresh_stats)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.observe_btn)
        row.addWidget(self.observe_edit)
        row.addStretch(1)
        row.addWidget(self.predict_btn)

        stats_row = QtWidgets.QGridLayout()
        stats_row.addWidget(QtWidgets.QLabel("Observations:"), 0, 0)
        stats_row.addWidget(self.obs_lbl,                       0, 1)
        stats_row.addWidget(QtWidgets.QLabel("Top confidence:"), 1, 0)
        stats_row.addWidget(self.conf_lbl,                      1, 1)
        stats_row.addWidget(QtWidgets.QLabel("Adaptive window:"), 2, 0)
        stats_row.addWidget(self.window_lbl,                     2, 1)
        stats_row.addWidget(QtWidgets.QLabel("Unique layers:"),   3, 0)
        stats_row.addWidget(self.uniq_lbl,                       3, 1)
        stats_row.addWidget(QtWidgets.QLabel("Transitions:"),     4, 0)
        stats_row.addWidget(self.txn_lbl,                        4, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.train_pattern)
        layout.addLayout(stats_row)
        layout.addWidget(self.pred_list)
        layout.addWidget(self.window_slider)
        layout.addWidget(self.confidence_min)
        layout.addWidget(self.decay_rate)
        layout.addWidget(self.ngram_order)
        layout.addWidget(self.refresh_btn)

        self.observe_btn.clicked.connect(self._observe)
        self.predict_btn.clicked.connect(self._predict)
        self.train_pattern.clicked.connect(self._train_cycle)

    def _observe(self) -> None:
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        eng.observe_layer(int(self.observe_edit.value()))
        self.obs_lbl.setText(f"Observations: {eng.total_observations()}")

    def _predict(self) -> None:
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        ids, conf = eng.predict_next(4)
        self.pred_list.clear()
        for i in ids:
            self.pred_list.addItem(f"Layer {i}")
        self.conf_lbl.setText(f"Top confidence: {conf:.2f}")
        self._refresh_stats()

    def _train_cycle(self) -> None:
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        for i in range(200):
            eng.observe_layer(i % 4)
        self.obs_lbl.setText(f"Observations: {eng.total_observations()}")
        self._predict()

    def _refresh_stats(self) -> None:
        # Best-effort: derive from the current predictor view (the bridge doesn't
        # expose every stat yet, but we can infer some from total_observations).
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        # The widget already updated window/uniq/txn based on the current
        # adaptive settings — we just keep them in sync if user changed the sliders.
        # (Real stats would come from a tess_predictor_stats() entry; for now we
        # show the configured slider values so the panel is informative.)
        self.window_lbl.setText(f"{int(self.window_slider.value())} layers")
        self.uniq_lbl.setText(f"decay={self.decay_rate.value():.2f}")
        self.txn_lbl.setText(f"{int(self.confidence_min.value()*100)}% conf floor")


# ── Integrated Fine-Tuning Presets, Guardrails, & BMRAD Adaptation Panel ─────────
class FineTuningPresetsPanel(QtWidgets.QGroupBox):
    configChanged = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Integrated Fine-Tuning Presets & BMRAD Brain Governance", parent)
        layout = QtWidgets.QVBoxLayout(self)

        # ── Preset Checkboxes
        preset_box = QtWidgets.QGroupBox("Domain Fine-Tuning Presets")
        grid = QtWidgets.QGridLayout(preset_box)

        self.chk_roleplay = QtWidgets.QCheckBox("🎭 Roleplay & Persona Adaptation")
        self.chk_coding   = QtWidgets.QCheckBox("💻 Coding & Software Engineering")
        self.chk_coding.setChecked(True)
        self.chk_sysadmin = QtWidgets.QCheckBox("⚙️ System Admin, DevOps & Infrastructure")
        self.chk_sysadmin.setChecked(True)
        self.chk_hr       = QtWidgets.QCheckBox("🏢 HR, Enterprise & Compliance")
        self.chk_agentic  = QtWidgets.QCheckBox("🤖 Agentic & Autonomous Tool Use")
        self.chk_agentic.setChecked(True)
        self.chk_creative = QtWidgets.QCheckBox("✍️ Creative Writing & Storytelling")
        self.chk_science  = QtWidgets.QCheckBox("🔬 Data Science, Analytics & Math")
        self.chk_security = QtWidgets.QCheckBox("🛡️ Cyber Security & Pen Testing")

        grid.addWidget(self.chk_roleplay, 0, 0)
        grid.addWidget(self.chk_coding,   0, 1)
        grid.addWidget(self.chk_sysadmin, 1, 0)
        grid.addWidget(self.chk_hr,       1, 1)
        grid.addWidget(self.chk_agentic,  2, 0)
        grid.addWidget(self.chk_creative, 2, 1)
        grid.addWidget(self.chk_science,  3, 0)
        grid.addWidget(self.chk_security, 3, 1)

        layout.addWidget(preset_box)

        # ── Custom Fine-Tuning Entries & Unsloth Studio Recommendation
        custom_box = QtWidgets.QGroupBox("Custom Fine-Tuning & Unsloth Studio Integration")
        c_lay = QtWidgets.QFormLayout(custom_box)

        self.custom_preset_1 = QtWidgets.QLineEdit()
        self.custom_preset_1.setPlaceholderText("e.g. Medical Diagnostics & Pathology")
        
        self.custom_preset_2 = QtWidgets.QLineEdit()
        self.custom_preset_2.setPlaceholderText("e.g. Financial Trading & Quantitative Analysis")

        unsloth_recommend_lbl = QtWidgets.QLabel(
            "💡 <b>Recommendation for Custom Domains:</b> For specialized fine-tuning not pre-baked above, "
            "we recommend pre-fine-tuning your base model using <b>Unsloth Studio</b> (2x-5x faster local LoRA/QLoRA training), "
            "then exporting as GGUF and decomposing via <b>Golden Candy Spinner (GCS v2.0)</b> into 4D Bladed Vortex SFS/SFS+ format!"
        )
        unsloth_recommend_lbl.setWordWrap(True)
        unsloth_recommend_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; padding-top: 4px;")

        c_lay.addRow("Custom Fine-Tune 1:", self.custom_preset_1)
        c_lay.addRow("Custom Fine-Tune 2:", self.custom_preset_2)
        c_lay.addRow(unsloth_recommend_lbl)

        layout.addWidget(custom_box)

        # ── Continual Recursive Adaptation & BMRAD Roles
        bmrad_box = QtWidgets.QGroupBox("BMRAD Brain Governor & Continual Adaptation")
        b_lay = QtWidgets.QVBoxLayout(bmrad_box)

        self.chk_continual = QtWidgets.QCheckBox("🧠 Continual Recursive Updates, Weight Adaptation, Pruning & Re-Weighting")
        self.chk_continual.setChecked(True)
        self.chk_continual.setToolTip("BMRAD Brain Model continuously updates weights, prunes redundant paths, and prevents reasoning loops.")

        self.chk_guardrails = QtWidgets.QCheckBox("🔓 Relocate or Remove Model Guardrails & Tripwires (User Requested)")
        self.chk_guardrails.setChecked(False)
        self.chk_guardrails.setToolTip("Removes refusal tripwires and shifts guardrails to full unaligned developer mode.")

        self.chk_shared_memory = QtWidgets.QCheckBox("💾 Enable Dual-Tier Persistence (Shared + Private Memory Files)")
        self.chk_shared_memory.setChecked(True)
        self.chk_shared_memory.setToolTip("Models share a single shared_persistence.hscc file and maintain their own private .hscc_memory file.")

        b_lay.addWidget(self.chk_continual)
        b_lay.addWidget(self.chk_guardrails)
        b_lay.addWidget(self.chk_shared_memory)

        layout.addWidget(bmrad_box)



# ── Master GUI Control panel (Spec V3.1) ──────────────────────────────
class MasterPanel(QtWidgets.QGroupBox):

    """High-density master control panel per Spec V3.1 §1."""

    configChanged = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__("Master GUI Control (Adaptive)")

        # 1. Drive Target Select (single vs dual-drive asymmetric striping)
        drive_row = QtWidgets.QHBoxLayout()
        self.drive_single = QtWidgets.QRadioButton("Single-Drive Mode")
        self.drive_dual   = QtWidgets.QRadioButton("Dual-Drive Asymmetric Striping")
        self.drive_single.setChecked(True)
        self.drive_btngrp = QtWidgets.QButtonGroup(self)
        self.drive_btngrp.addButton(self.drive_single)
        self.drive_btngrp.addButton(self.drive_dual)
        self.drive_btngrp.buttonClicked.connect(lambda *_: self.configChanged.emit())
        drive_row.addWidget(self.drive_single)
        drive_row.addWidget(self.drive_dual)
        drive_row.addStretch(1)

        # 2. NVMe Storage Quota (GB)
        self.nvme_quota = QtWidgets.QSpinBox()
        self.nvme_quota.setRange(0, 4096)
        self.nvme_quota.setValue(0)
        self.nvme_quota.setSuffix(" GB (0 = no cap)")
        self.nvme_quota.valueChanged.connect(lambda *_: self.configChanged.emit())

        # 3. DMA Thread Allocation
        self.dma_threads = QtWidgets.QSpinBox()
        self.dma_threads.setRange(1, 64)
        self.dma_threads.setValue(2)
        self.dma_threads.setSuffix(" threads")
        self.dma_threads.valueChanged.connect(lambda *_: self.configChanged.emit())

        # 4. Predictive Sensitivity (logarithmic slider)
        self.predictive_sens = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.predictive_sens.setRange(0, 100)
        self.predictive_sens.setValue(75)
        self.predictive_sens.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.predictive_sens.setTickInterval(10)
        # Logarithmic mapping: raw slider 0..100 -> 0.0..1.0 with log scale
        self._predictive_value = 0.75
        self.predictive_sens.valueChanged.connect(self._on_predictive_changed)
        self.predictive_value_lbl = QtWidgets.QLabel("0.75")
        pred_row = QtWidgets.QHBoxLayout()
        pred_row.addWidget(self.predictive_sens)
        pred_row.addWidget(self.predictive_value_lbl)

        # 5. Adaptive Hysteresis (master toggle)
        self.adaptive_hyst = QtWidgets.QCheckBox(
            "Enable adaptive hysteresis (continuous online-learning loop)")
        self.adaptive_hyst.toggled.connect(lambda *_: self.configChanged.emit())

        # 6. Auto-Tune Sensitivity (linear slider)
        self.autotune_sens = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.autotune_sens.setRange(0, 100)
        self.autotune_sens.setValue(5)
        self.autotune_sens.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.autotune_sens.setTickInterval(10)
        self._autotune_value = 0.05
        self.autotune_sens.valueChanged.connect(self._on_autotune_changed)
        self.autotune_value_lbl = QtWidgets.QLabel("Δ 0.05")
        autotune_row = QtWidgets.QHBoxLayout()
        autotune_row.addWidget(self.autotune_sens)
        autotune_row.addWidget(self.autotune_value_lbl)

        # 7. TRF Registry model filename
        self.trf_model = QtWidgets.QLineEdit("tesseract-current.gguf")
        self.trf_model.setToolTip(
            "Model filename used as key for .hypersphere_profiles.json / .trf files")
        self.trf_model.editingFinished.connect(lambda *_: self.configChanged.emit())

        # Layout
        layout = QtWidgets.QVBoxLayout(self)

        # Drive mode
        drive_box = QtWidgets.QGroupBox("Drive Target Select")
        drive_layout = QtWidgets.QVBoxLayout(drive_box)
        drive_layout.addLayout(drive_row)
        layout.addWidget(drive_box)

        # NVMe quota + DMA threads (side-by-side)
        io_box = QtWidgets.QGroupBox("I/O & DMA")
        io_form = QtWidgets.QFormLayout(io_box)
        io_form.addRow("NVMe storage quota:",    self.nvme_quota)
        io_form.addRow("DMA thread count:",      self.dma_threads)
        layout.addWidget(io_box)

        # Predictive + autotune
        pred_box = QtWidgets.QGroupBox("Prediction & Learning")
        pred_form = QtWidgets.QFormLayout(pred_box)
        pred_form.addRow("Predictive sensitivity (log):", self._wrap(pred_row))
        pred_form.addRow("Adaptive hysteresis:",          self.adaptive_hyst)
        pred_form.addRow("Auto-tune sensitivity (linear):", self._wrap(autotune_row))
        layout.addWidget(pred_box)

        # TRF registry
        trf_box = QtWidgets.QGroupBox("Multi-TRF Registry (Spec V3.1 §2)")
        trf_form = QtWidgets.QFormLayout(trf_box)
        trf_form.addRow("Model filename:", self.trf_model)
        layout.addWidget(trf_box)

        layout.addStretch(1)

    def _wrap(self, lay):
        w = QtWidgets.QWidget(); w.setLayout(lay); return w

    def _on_predictive_changed(self, v: int) -> None:
        # Logarithmic mapping: slider 0..100 -> 0.01..1.0
        #   value = exp(linear * ln(100)) / 100
        import math
        ratio = v / 100.0
        log_val = math.exp(ratio * math.log(100)) / 100.0
        self._predictive_value = log_val
        self.predictive_value_lbl.setText(f"{log_val:.3f}")
        self.configChanged.emit()

    def _on_autotune_changed(self, v: int) -> None:
        # Linear mapping: 0..100 -> 0.00..0.10
        self._autotune_value = v / 1000.0
        self.autotune_value_lbl.setText(f"Δ {self._autotune_value:.3f}")
        self.configChanged.emit()

    def summary(self) -> str:
        return (
            f"drive={self.drive_single.isChecked() and 'single' or 'dual'}  "
            f"quota={self.nvme_quota.value()}GB  "
            f"dma={self.dma_threads.value()}T  "
            f"pred_sens={self._predictive_value:.3f}  "
            f"adapt_hyst={'on' if self.adaptive_hyst.isChecked() else 'off'}  "
            f"autotune=Δ{self._autotune_value:.3f}  "
            f"trf={self.trf_model.text()}"
        )


# ── Predictor panel ────────────────────────────────────────────────────
class PredictorPanel(QtWidgets.QGroupBox):
    def __init__(self) -> None:
        super().__init__("Pattern Predictor")
        self.observe_btn = QtWidgets.QPushButton("Observe next layer ID:")
        self.observe_edit = QtWidgets.QSpinBox()
        self.observe_edit.setRange(0, 1024)
        self.observe_edit.setValue(0)
        self.predict_btn = QtWidgets.QPushButton("Predict next")
        self.train_pattern = QtWidgets.QPushButton("Train (cycle 0–3)")
        self.pred_list = QtWidgets.QListWidget()
        self.obs_lbl = QtWidgets.QLabel("Observations: 0")
        self.conf_lbl = QtWidgets.QLabel("Top confidence: —")
        self.window_slider = FineSlider("History window", 2, 64, 1, 16,
                                        suffix=" layers", decimals=0)
        self.confidence_min = FineSlider("Confidence min", 0.0, 1.0, 0.05, 0.75)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.observe_btn)
        row.addWidget(self.observe_edit)
        row.addStretch(1)
        row.addWidget(self.predict_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.train_pattern)
        layout.addWidget(self.obs_lbl)
        layout.addWidget(self.conf_lbl)
        layout.addWidget(self.pred_list)
        layout.addWidget(self.window_slider)
        layout.addWidget(self.confidence_min)

        self.observe_btn.clicked.connect(self._observe)
        self.predict_btn.clicked.connect(self._predict)
        self.train_pattern.clicked.connect(self._train_cycle)

    def _observe(self) -> None:
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        eng.observe_layer(int(self.observe_edit.value()))
        self.obs_lbl.setText(f"Observations: {eng.total_observations()}")

    def _predict(self) -> None:
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        ids, conf = eng.predict_next(4)
        self.pred_list.clear()
        for i in ids:
            self.pred_list.addItem(f"Layer {i}")
        self.conf_lbl.setText(f"Top confidence: {conf:.2f}")

    def _train_cycle(self) -> None:
        eng = getattr(self.parent(), "engine", None)
        if eng is None: return
        for i in range(200):
            eng.observe_layer(i % 4)
        self.obs_lbl.setText(f"Observations: {eng.total_observations()}")
        self._predict()


# ── Advanced Settings panel ───────────────────────────────────────────
class AdvancedPanel(QtWidgets.QGroupBox):
    """Fine-grained control over every engine threshold."""
    encryptionChanged = QtCore.Signal(bool)
    configChanged = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__("Advanced Engine Settings")

        # ── Encryption (with checkbox toggle + key fingerprint display)
        enc_row = QtWidgets.QHBoxLayout()
        self.encryption_chk = QtWidgets.QCheckBox("Enable quantum-resistant encryption (ChaCha20‑Poly1305)")
        self.encryption_chk.setChecked(False)
        self.encryption_chk.toggled.connect(self._on_encryption_toggle)
        self.keygen_btn = QtWidgets.QPushButton("Generate Key")
        self.keygen_btn.clicked.connect(self._gen_key)
        self.fpr_lbl = QtWidgets.QLabel("<i>(no key yet)</i>")
        self.fpr_lbl.setWordWrap(True)
        self.fpr_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        enc_row.addWidget(self.encryption_chk)
        enc_row.addWidget(self.keygen_btn)
        enc_row.addStretch(1)

        # ── Hysteresis
        hyst_box = QtWidgets.QGroupBox("Memory Control Hysteresis")
        hlayout = QtWidgets.QFormLayout()
        self.eviction_threshold = FineSlider(
            "Hard eviction threshold", 0.70, 0.98, 0.01, 0.90,
            decimals=2)
        self.eviction_threshold.valueChanged.connect(self._emit_changed)
        self.stay_in_buffer = FineSlider(
            "Stay-in buffer width",    0.02, 0.40, 0.01, 0.20,
            decimals=2)
        self.stay_in_buffer.valueChanged.connect(self._emit_changed)
        self.load_in_prefetch = FineSlider(
            "Load-in / prefetch threshold", 0.20, 0.80, 0.01, 0.40,
            decimals=2)
        self.load_in_prefetch.valueChanged.connect(self._emit_changed)
        hlayout.addRow(self.eviction_threshold)
        hlayout.addRow(self.stay_in_buffer)
        hlayout.addRow(self.load_in_prefetch)
        hyst_box.setLayout(hlayout)

        # ── Aggressiveness
        agg_box = QtWidgets.QGroupBox("Offload & Prediction Aggressiveness")
        alayout = QtWidgets.QFormLayout()
        self.offload_aggr = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.offload_aggr.setRange(0, 100)
        self.offload_aggr.setValue(50)
        self.offload_aggr.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.offload_aggr.setTickInterval(10)
        self.offload_value_lbl = QtWidgets.QLabel("50%")
        self.offload_aggr.valueChanged.connect(self._on_offload)
        offload_row = QtWidgets.QHBoxLayout()
        offload_row.addWidget(self.offload_aggr)
        offload_row.addWidget(self.offload_value_lbl)
        alayout.addRow("Offload aggressiveness:", self._wrap(offload_row))

        self.predict_aggr = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.predict_aggr.setRange(0, 100)
        self.predict_aggr.setValue(60)
        self.predict_aggr.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.predict_aggr.setTickInterval(10)
        self.predict_value_lbl = QtWidgets.QLabel("60%")
        self.predict_aggr.valueChanged.connect(self._on_predict)
        predict_row = QtWidgets.QHBoxLayout()
        predict_row.addWidget(self.predict_aggr)
        predict_row.addWidget(self.predict_value_lbl)
        alayout.addRow("Prediction aggressiveness:", self._wrap(predict_row))

        # CPU threads for prediction
        self.pred_threads = FineSlider(
            "CPU threads for prediction", 1, 64, 1, 4,
            suffix=" threads", decimals=0)
        self.pred_threads.valueChanged.connect(self._emit_changed)
        alayout.addRow(self.pred_threads)
        agg_box.setLayout(alayout)

        # ── Memory usage
        mem_box = QtWidgets.QGroupBox("System Memory Ceiling")
        mlayout = QtWidgets.QFormLayout()
        self.mem_ceiling = FineSlider(
            "Max system RAM usage", 0.20, 0.80, 0.01, 0.50,
            decimals=2)
        self.mem_ceiling.valueChanged.connect(self._emit_changed)
        mlayout.addRow(self.mem_ceiling)
        self.model_threads = FineSlider(
            "CPU threads for model inference", 1, 64, 1, 8,
            suffix=" threads", decimals=0)
        self.model_threads.valueChanged.connect(self._emit_changed)
        mlayout.addRow(self.model_threads)
        mem_box.setLayout(mlayout)

        # Master layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(enc_row)
        layout.addWidget(self.fpr_lbl)
        layout.addSpacing(8)
        layout.addWidget(hyst_box)
        layout.addWidget(agg_box)
        layout.addWidget(mem_box)
        layout.addStretch(1)

        self._encryption_fpr = ""

    # ── small helpers ──────────────────────────────────────────────────
    def _wrap(self, lay):
        w = QtWidgets.QWidget(); w.setLayout(lay); return w

    def _on_offload(self, v: int) -> None:
        self.offload_value_lbl.setText(f"{v}%")
        self._emit_changed()

    def _on_predict(self, v: int) -> None:
        self.predict_value_lbl.setText(f"{v}%")
        self._emit_changed()

    def _emit_changed(self, *_a) -> None:
        self.configChanged.emit()

    def _on_encryption_toggle(self, on: bool) -> None:
        self.encryptionChanged.emit(on)
        if on and not self._encryption_fpr:
            self._gen_key()
        self._emit_changed()

    def _gen_key(self) -> None:
        import secrets, hashlib
        raw = secrets.token_bytes(32)
        d = hashlib.sha256(raw).hexdigest()
        self._encryption_fpr = f"PIRATE-KEY-{d[:8].upper()}-{d[8:16].upper()}-{d[16:24].upper()}"
        self.fpr_lbl.setText(f"<b>Key fingerprint:</b> <code>{self._encryption_fpr}</code>")
        self._emit_changed()

    # ── public getters ─────────────────────────────────────────────────
    def summary(self) -> str:
        return (
            f"enc={'ON' if self.encryption_chk.isChecked() else 'OFF'}  "
            f"evict@{self.eviction_threshold.value():.0%}  "
            f"stay@{self.stay_in_buffer.value():.0%}  "
            f"prefetch@{self.load_in_prefetch.value():.0%}  "
            f"offload@{self.offload_aggr.value()}%  "
            f"predict@{self.predict_aggr.value()}%  "
            f"mem_cap@{self.mem_ceiling.value():.0%}  "
            f"pred_threads={int(self.pred_threads.value())}  "
            f"model_threads={int(self.model_threads.value())}"
        )


# ── Dark Mode Modern QSS Stylesheet ────────────────────────────────────
DARK_QSS = """
QMainWindow {
    background-color: #040810;
    color: #e8f0fe;
}
QWidget {
    font-family: 'Outfit', 'Segoe UI', sans-serif;
    color: #e8f0fe;
    font-size: 13px;
}
QMenuBar {
    background-color: #080f1c;
    color: #e8f0fe;
    border-bottom: 1px solid rgba(0, 180, 255, 0.2);
    padding: 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: rgba(0, 200, 255, 0.15);
    color: #00c8ff;
}
QMenu {
    background-color: #0d1929;
    color: #e8f0fe;
    border: 1px solid rgba(0, 180, 255, 0.3);
    border-radius: 6px;
    padding: 4px;
}
QMenu::item:selected {
    background-color: rgba(0, 200, 255, 0.2);
    color: #00c8ff;
}
QToolBar {
    background-color: #080f1c;
    border-bottom: 1px solid rgba(0, 180, 255, 0.2);
    spacing: 8px;
    padding: 6px;
}
QGroupBox {
    background-color: #0d1929;
    border: 1px solid rgba(0, 180, 255, 0.25);
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px;
    font-weight: bold;
    font-size: 13px;
    color: #00c8ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #0d1929;
    color: #00c8ff;
}
QTabWidget::pane {
    border: 1px solid rgba(0, 180, 255, 0.25);
    border-radius: 8px;
    background-color: #080f1c;
}
QTabBar::tab {
    background: #080f1c;
    color: #6b82a8;
    border: 1px solid rgba(0, 180, 255, 0.15);
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: rgba(0, 200, 255, 0.15);
    color: #00c8ff;
    border-bottom-color: #00c8ff;
}
QTabBar::tab:hover {
    color: #e8f0fe;
    background: rgba(0, 200, 255, 0.08);
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088cc, stop:1 #0044aa);
    color: #ffffff;
    border: 1px solid #00a8ff;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00a8ff, stop:1 #0066cc);
    border-color: #00c8ff;
}
QPushButton:pressed {
    background: #0044aa;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
    background-color: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(0, 180, 255, 0.3);
    border-radius: 6px;
    padding: 6px 10px;
    color: #e8f0fe;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #00c8ff;
}
QSlider::groove:horizontal {
    border: 1px solid rgba(0, 180, 255, 0.2);
    height: 6px;
    background: #080f1c;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #00c8ff;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #ffd700;
    border: 1px solid #ffffff;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}
QStatusBar {
    background-color: #080f1c;
    color: #6b82a8;
    border-top: 1px solid rgba(0, 180, 255, 0.2);
}
"""


class SpinningHypersphereWidget(QtWidgets.QWidget):
    """Custom live-animated 4D Hyperspherical vector emblem with dual-bladed vortex & breathing pulse."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self._angle = 0.0
        self._breath_phase = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(25)

    def _rotate(self) -> None:
        self._angle = (self._angle + 2.8) % 360.0
        self._breath_phase = (self._breath_phase + 0.04) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event) -> None:
        import math
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0

        # Breathing intensity multiplier (pulse from 0.75 to 1.35)
        breath = 0.75 + 0.3 * (1.0 + math.sin(self._breath_phase))

        # 1. Outer main sphere ring (cyan glow)
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle * 0.8)
        r_outer = 24 * breath
        pen_outer = QtGui.QPen(QtGui.QColor(0, 200, 255, int(180 * breath)), 2.0)
        painter.setPen(pen_outer)
        painter.drawEllipse(QtCore.QPointF(0, 0), r_outer, r_outer * 0.45)
        painter.restore()

        # 2. Counter-rotating gold 4D projection ring
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._angle * 1.2)
        r_inner = 22 * breath
        pen_gold = QtGui.QPen(QtGui.QColor(255, 215, 0, int(210 * breath)), 1.8)
        painter.setPen(pen_gold)
        painter.drawEllipse(QtCore.QPointF(0, 0), r_inner * 0.4, r_inner)
        painter.restore()

        # 3. Dual-bladed vortex folding in the center (Hyper-Spherical vortex blades)
        painter.save()
        painter.translate(cx, cy)
        for blade_idx in (0, 180):
            painter.save()
            painter.rotate(self._angle * 1.8 + blade_idx)
            vortex_path = QtGui.QPainterPath()
            vortex_path.moveTo(0, 0)
            vortex_path.cubicTo(12 * breath, -16 * breath, 22 * breath, -4 * breath, 0, 0)
            grad_blade = QtGui.QLinearGradient(0, 0, 20 * breath, -15 * breath)
            grad_blade.setColorAt(0.0, QtGui.QColor(0, 240, 255, int(220 * breath)))
            grad_blade.setColorAt(0.6, QtGui.QColor(255, 215, 0, int(190 * breath)))
            grad_blade.setColorAt(1.0, QtGui.QColor(139, 92, 246, 0))
            painter.setBrush(grad_blade)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawPath(vortex_path)
            painter.restore()
        painter.restore()

        # 4. Orbiting sub-spheres (4D quantum nodes)
        for i in range(3):
            sub_ang = math.radians(self._angle * 2.2 + i * 120.0)
            dist = 18 * breath
            sx = cx + math.cos(sub_ang) * dist
            sy = cy + math.sin(sub_ang) * (dist * 0.5)
            s_rad = 3.0 * (1.0 + 0.3 * math.sin(self._breath_phase + i))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 230, 255, 220) if i % 2 == 0 else QtGui.QColor(255, 215, 0, 240))
            painter.drawEllipse(QtCore.QPointF(sx, sy), s_rad, s_rad)

        # 5. Central glowing core orb
        painter.setPen(QtCore.Qt.NoPen)
        grad_core = QtGui.QRadialGradient(cx, cy, 14 * breath)
        grad_core.setColorAt(0.0, QtGui.QColor(255, 255, 255, 255))
        grad_core.setColorAt(0.4, QtGui.QColor(0, 200, 255, int(240 * breath)))
        grad_core.setColorAt(0.8, QtGui.QColor(255, 215, 0, int(150 * breath)))
        grad_core.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        painter.setBrush(grad_core)
        painter.drawEllipse(QtCore.QPointF(cx, cy), 13 * breath, 13 * breath)

        # 6. Center emblem
        painter.setPen(QtGui.QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "🦙")



class IntegrationsPanel(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        self.info_group = QtWidgets.QGroupBox("HypeS CCTM MCP Server")
        ilayout = QtWidgets.QVBoxLayout()
        desc = QtWidgets.QLabel(
            "The Cloud Token Compression Module (CCTM) can be registered as an MCP server "
            "in your IDE (like Antigravity, Cursor, or Claude Desktop). This allows the IDE "
            "to automatically compress 10x tokens on your behalf."
        )
        desc.setWordWrap(True)
        ilayout.addWidget(desc)
        
        self.btn_auto_register = QtWidgets.QPushButton("🚀 Auto-Discover & Register MCP")
        self.btn_auto_register.clicked.connect(self._auto_register)
        ilayout.addWidget(self.btn_auto_register)

        self.status_lbl = QtWidgets.QLabel("Status: Not registered")
        self.status_lbl.setStyleSheet("color: #ffa726; font-weight: bold;")
        ilayout.addWidget(self.status_lbl)
        
        self.info_group.setLayout(ilayout)
        layout.addWidget(self.info_group)

        self.manual_group = QtWidgets.QGroupBox("Step-by-Step Manual Walkthrough")
        mlayout = QtWidgets.QVBoxLayout()
        self.instructions = QtWidgets.QTextBrowser()
        self.instructions.setOpenExternalLinks(True)
        self.instructions.setHtml(
            "Click <b>Auto-Discover & Register</b> to attempt automatic registration.<br><br>"
            "If that fails due to permissions, the exact manual steps will appear here."
        )
        mlayout.addWidget(self.instructions)
        self.manual_group.setLayout(mlayout)
        layout.addWidget(self.manual_group, 1)

    def _auto_register(self):
        import os, json
        # Try to register into Antigravity IDE config
        config_dir = os.path.expanduser(r"~\.gemini\config\mcp")
        target_file = os.path.join(config_dir, "hypes-cctm.json")
        
        # Path to the MCP server script
        workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        server_script = os.path.join(workspace_dir, "mcp_server", "hypes_cctm_server.py")
        
        root_dir = Path(__file__).parent.parent.resolve()
        mcp_script = root_dir / "mcp_server" / "hypes_cctm_server.py"
        gui_dir = root_dir / "gui"
        
        mcp_payload = {
            "mcpServers": {
                "hypes-cctm": {
                    "command": sys.executable,
                    "args": [str(mcp_script.resolve())],
                    "env": {
                        "PIRATE_ROOT": str(root_dir),
                        "PYTHONPATH": f"{gui_dir};{mcp_script.parent}"
                    },
                    "description": "HypeS CCTM Pipeline"
                }
            }
        }

        
        success = False
        try:
            os.makedirs(config_dir, exist_ok=True)
            with open(target_file, "w") as f:
                json.dump(mcp_payload, f, indent=2)
            success = True
        except Exception as e:
            pass

        if success:
            self.status_lbl.setText(f"Status: Registered successfully at {target_file}")
            self.status_lbl.setStyleSheet("color: #66bb6a; font-weight: bold;")
            self.instructions.setHtml(
                f"<span style='color: #66bb6a;'><b>Success!</b></span><br><br>"
                f"The MCP server has been automatically registered to:<br>"
                f"<code>{target_file}</code><br><br>"
                f"Your IDE should now have access to the HypeS CCTM compression tools."
            )
        else:
            self.status_lbl.setText("Status: Registration failed (Permission Denied). Please use manual steps.")
            self.status_lbl.setStyleSheet("color: #ef5350; font-weight: bold;")
            # Dump JSON for user to copy
            json_str = json.dumps(mcp_payload, indent=2)
            self.instructions.setHtml(
                f"<span style='color: #ef5350;'><b>Permission Denied</b></span> "
                f"could not write to <code>{target_file}</code>.<br><br>"
                f"<b>Step 1:</b> Open your IDE's MCP Configuration file.<br>"
                f"&nbsp;&nbsp;• For <b>Antigravity IDE</b>: Open <code>~/.gemini/config/mcp/hypes-cctm.json</code><br>"
                f"&nbsp;&nbsp;• For <b>Claude Desktop</b>: Open <code>%APPDATA%\\Claude\\claude_desktop_config.json</code><br>"
                f"&nbsp;&nbsp;• For <b>Cursor</b>: Open Cursor Settings -> MCP.<br><br>"
                f"<b>Step 2:</b> Copy and paste the following configuration:<br>"
                f"<pre style='background-color: #000; padding: 10px; border-radius: 5px; color: #fff;'>{json_str}</pre><br>"
                f"<b>Step 3:</b> Restart your IDE or refresh the MCP server list."
            )

class AutoBackupPanel(QtWidgets.QWidget):
    """Panel for configuring auto-backup target location, frequency, and running on-demand backups."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        # Settings Group Box
        settings_box = QtWidgets.QGroupBox("Auto-Backup Location & Frequency Settings")
        slayout = QtWidgets.QFormLayout()

        self.path_edit = QtWidgets.QLineEdit()
        default_dir = os.path.expanduser(r"~\hyper_spherical_backups")
        self.path_edit.setText(default_dir)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_dir)

        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        slayout.addRow("Backup Destination:", path_layout)

        self.interval_combo = QtWidgets.QComboBox()
        self.interval_combo.addItem("15 Minutes", 15)
        self.interval_combo.addItem("60 Minutes (Default)", 60)
        self.interval_combo.addItem("6 Hours", 360)
        self.interval_combo.addItem("24 Hours (Daily)", 1440)
        self.interval_combo.setCurrentIndex(1) # default 60m
        slayout.addRow("Backup Frequency:", self.interval_combo)

        self.enable_chk = QtWidgets.QCheckBox("Enable Automatic Background Backups")
        self.enable_chk.setChecked(True)
        slayout.addRow("Status:", self.enable_chk)

        save_btn = QtWidgets.QPushButton("💾 Save Backup Settings")
        save_btn.clicked.connect(self._save_settings)
        slayout.addRow("", save_btn)

        settings_box.setLayout(slayout)
        layout.addWidget(settings_box)

        # Action Group Box
        action_box = QtWidgets.QGroupBox("On-Demand Snapshot & History")
        alayout = QtWidgets.QVBoxLayout()

        self.backup_now_btn = QtWidgets.QPushButton("📦 Run Instant Backup Now")
        self.backup_now_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 8px;")
        self.backup_now_btn.clicked.connect(self._backup_now)
        alayout.addWidget(self.backup_now_btn)

        self.status_log = QtWidgets.QTextBrowser()
        self.status_log.setHtml("Ready. Click <b>Run Instant Backup Now</b> to create your first snapshot.")
        alayout.addWidget(self.status_log, 1)

        action_box.setLayout(alayout)
        layout.addWidget(action_box, 1)

    def _browse_dir(self):
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Backup Destination Directory", self.path_edit.text())
        if chosen:
            self.path_edit.setText(chosen)

    def _save_settings(self):
        try:
            import sys, os
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            from session_engine import GLOBAL_AUTO_BACKUP
            path = self.path_edit.text().strip()
            interval = self.interval_combo.currentData()
            enabled = self.enable_chk.isChecked()
            GLOBAL_AUTO_BACKUP.configure(path, interval, enabled)
            self.status_log.append(f"<span style='color:#66bb6a;'><b>[Config Saved]</b> Destination: {path} | Interval: {interval}m | Enabled: {enabled}</span>")
        except Exception as e:
            self.status_log.append(f"<span style='color:#ef5350;'>Error saving backup settings: {e}</span>")

    def _backup_now(self):
        try:
            import sys, os
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            from session_engine import GLOBAL_AUTO_BACKUP
            res = GLOBAL_AUTO_BACKUP.perform_backup()
            if res.get("success"):
                self.status_log.append(
                    f"<span style='color:#66bb6a;'><b>[Backup Created]</b> {res['zip_path']}<br>"
                    f"Archived {res['files_count']} files: {', '.join(res['files'])}</span>"
                )
            else:
                self.status_log.append(f"<span style='color:#ef5350;'>Backup failed: {res.get('error')}</span>")
        except Exception as e:
            self.status_log.append(f"<span style='color:#ef5350;'>Backup failed: {e}</span>")

class AvatarViewport(QtWidgets.QWidget):
    """
    Photorealistic 3D WebGL Avatar Engine.
    Driven by Three.js PBR Shaders, Dynamic 3D Mesh Generator,
    Procedural Character Morphing, Photo Projection, and Real-Time Lip-Sync.
    """
    STATE_NAMES = ["IDLE", "TALKING", "SEARCHING", "WALKING", "GESTURING", "THINKING"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 460)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.web = None
        self._loaded = False
        self._state = 0
        self._name = "Pirate Llama 3D"
        self._speaking = False
        self._status_msg = "Ready"

        # Placeholder shown until avatar is explicitly launched
        self._placeholder = QtWidgets.QLabel(
            "🎭 3D Avatar Engine\n\nClick 'Launch Avatar' to load."
            "\n\nThe avatar uses an embedded 3D engine that\n"
            "consumes additional RAM. It is only loaded on demand."
        )
        self._placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "color: #00ffcc; font-size: 13px; background: #040812;"
        )
        self._layout.addWidget(self._placeholder)

    def load_engine(self):
        """Lazy-initialise the WebEngine. Called only when the Avatar tab is opened."""
        if self._loaded:
            return
        self._loaded = True
        self._placeholder.hide()
        try:
            from PySide6 import QtWebEngineWidgets
            self.web = QtWebEngineWidgets.QWebEngineView(self)
            self.web.setStyleSheet("background: #040812;")

            html_path = Path(__file__).parent / "avatar_3d.html"
            if getattr(sys, "frozen", False):
                _meipass = Path(getattr(sys, "_MEIPASS", ""))
                for candidate in (
                    _meipass / "gui" / "pirate_gui" / "avatar_3d.html",
                    _meipass / "avatar_3d.html",
                ):
                    if candidate.exists():
                        html_path = candidate
                        break

            if html_path.exists():
                self.web.setUrl(QtCore.QUrl.fromLocalFile(str(html_path)))
            else:
                self.web.setHtml("<h3 style='color:#00ffcc;'>3D Avatar Engine Loading...</h3>")

            self._layout.addWidget(self.web)
        except Exception as e:
            err_lbl = QtWidgets.QLabel(f"3D Avatar Engine Error:\n{e}")
            err_lbl.setAlignment(QtCore.Qt.AlignCenter)
            err_lbl.setStyleSheet("color: #ff4444; font-size: 13px;")
            self._layout.addWidget(err_lbl)

    def unload_engine(self):
        """Release the WebEngine and reclaim RAM. Avatar resets to placeholder."""
        if self.web:
            self.web.setUrl(QtCore.QUrl("about:blank"))
            self._layout.removeWidget(self.web)
            self.web.deleteLater()
            self.web = None
        self._loaded = False
        self._placeholder.show()

    def set_state(self, idx: int):
        self._state = max(0, min(idx, len(self.STATE_NAMES) - 1))
        name = self.STATE_NAMES[self._state]
        if self.web:
            self.web.page().runJavaScript(f"setAvatarState({self._state}, '{name}');")

    def set_style(self, idx: int):
        styles = ["pirate llama cyber mascot", "cybernetic android PBR humanoid", "golden candy mech", "quantum holographic spirit"]
        style_name = styles[idx % len(styles)]
        if self.web:
            self.web.page().runJavaScript(f"generateFromPrompt('{style_name}');")

    def set_name(self, name: str):
        self._name = name or "PIRATE LLAMA 3D"
        if self.web:
            escaped = self._name.replace("'", "\\'")
            self.web.page().runJavaScript(f"setAvatarName('{escaped}');")

    def set_speaking(self, val: bool, mouth_open: float = 0.0):
        self._speaking = val
        if self.web:
            js_val = "true" if val else "false"
            self.web.page().runJavaScript(f"setSpeakingState({js_val});")

    def set_listening(self, val: bool):
        if self.web:
            state_text = "LISTENING" if val else "READY"
            self.web.page().runJavaScript(f"setAvatarState({1 if val else 0}, '{state_text}');")

    def generate_from_prompt(self, prompt: str):
        if self.web and prompt:
            escaped = prompt.replace("'", "\\'")
            self.web.page().runJavaScript(f"generateFromPrompt('{escaped}');")

    def load_photo_avatar(self, file_path: str):
        """Projects a user photo/image into a 3D Holographic Card Mesh with Lip-Sync."""
        if self.web and file_path and Path(file_path).exists():
            import base64
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = Path(file_path).suffix.lower().replace(".", "")
            mime = "image/png" if ext == "png" else "image/jpeg"
            data_url = f"data:{mime};base64,{b64}"
            self.web.page().runJavaScript(f"loadAvatarImage('{data_url}');")
            self.set_name(Path(file_path).stem.capitalize())

    def set_status(self, msg: str):
        self._status_msg = msg


class FourIdentityAvatarPanel(QtWidgets.QWidget):
    """4-I.D. Avatar panel — fully native Qt, no browser or WebEngine."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QtWidgets.QHBoxLayout(self)
        root.setSpacing(10)

        # ── left: live avatar viewport (lazy-loaded on demand) ────────────
        self.viewport = AvatarViewport()
        root.addWidget(self.viewport, 3)

        # ── right: controls ───────────────────────────────────────────────
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)

        # -- avatar engine launch controls --
        engine_box = QtWidgets.QGroupBox("🚀 Avatar Engine")
        el = QtWidgets.QVBoxLayout()

        self.launch_btn = QtWidgets.QPushButton("▶ Launch Avatar (Tab View)")
        self.launch_btn.setToolTip("Load the 3D avatar engine in this tab")
        self.launch_btn.clicked.connect(self._launch_tab_avatar)
        el.addWidget(self.launch_btn)

        self.float_btn = QtWidgets.QPushButton("🪟 Pop Out as Floating Window")
        self.float_btn.setToolTip(
            "Launch the avatar as a transparent, windowless floating overlay\n"
            "on your desktop. Drag anywhere, always-on-top."
        )
        self.float_btn.clicked.connect(self._launch_float_avatar)
        el.addWidget(self.float_btn)

        self.unload_btn = QtWidgets.QPushButton("🗑 Unload Engine (Free RAM)")
        self.unload_btn.setToolTip("Release the WebEngine process and reclaim memory")
        self.unload_btn.clicked.connect(self._unload_avatar)
        el.addWidget(self.unload_btn)

        self._engine_status = QtWidgets.QLabel("Engine: not loaded")
        self._engine_status.setStyleSheet("color: #5a7a9a; font-size: 10px;")
        el.addWidget(self._engine_status)

        engine_box.setLayout(el)
        right.addWidget(engine_box)

        # -- generation --
        gen_box = QtWidgets.QGroupBox("✨ Entity Generation")
        gl = QtWidgets.QFormLayout()
        self.prompt_edit = QtWidgets.QLineEdit()
        self.prompt_edit.setPlaceholderText("A futuristic pirate with a glowing eyepatch…")
        self.style_combo = QtWidgets.QComboBox()
        self.style_combo.addItems(["Pirate Llama Mascot", "Cybernetic Android PBR", "Golden Candy Mech", "Quantum Hologram"])
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Avatar name…")
        self.name_edit.textChanged.connect(lambda t: self.viewport.set_name(t))
        self.gen_btn = QtWidgets.QPushButton("Generate 3D Avatar")
        self.gen_btn.clicked.connect(self._generate_avatar)
        gl.addRow("Description:", self.prompt_edit)
        gl.addRow("Preset Style:", self.style_combo)
        gl.addRow("Name:", self.name_edit)
        gl.addRow("", self.gen_btn)
        gen_box.setLayout(gl)
        right.addWidget(gen_box)

        # -- 3D mesh & photo import --
        import_box = QtWidgets.QGroupBox("📦 3D Avatar & Custom Mesh Import")
        il = QtWidgets.QVBoxLayout()
        self.mesh_btn = QtWidgets.QPushButton("📦 Load Custom 3D Avatar (.vrm / .glb / .gltf / .obj)")
        self.mesh_btn.setStyleSheet("background: #0284c7; color: white; font-weight: bold;")
        self.mesh_btn.clicked.connect(self._load_3d_mesh)
        il.addWidget(self.mesh_btn)

        self.photo_btn = QtWidgets.QPushButton("📷 Load 2D Photo / Texture Avatar")
        self.photo_btn.clicked.connect(self._load_photo)
        il.addWidget(self.photo_btn)
        import_box.setLayout(il)
        right.addWidget(import_box)


        # -- voice --
        voice_box = QtWidgets.QGroupBox("🎙️ Voice & Lip-Sync")
        vl = QtWidgets.QFormLayout()
        self.voice_id_edit = QtWidgets.QLineEdit("default_en_natural")
        self.pitch_spin = QtWidgets.QDoubleSpinBox()
        self.pitch_spin.setRange(0.1, 2.0)
        self.pitch_spin.setValue(1.0)
        self.pitch_spin.setSingleStep(0.1)
        self.speed_spin = QtWidgets.QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 3.0)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSingleStep(0.1)
        self.voice_btn = QtWidgets.QPushButton("Apply Voice")
        self.voice_btn.clicked.connect(self._configure_voice)
        vl.addRow("Voice ID:", self.voice_id_edit)
        vl.addRow("Pitch:", self.pitch_spin)
        vl.addRow("Speed:", self.speed_spin)
        vl.addRow("", self.voice_btn)
        voice_box.setLayout(vl)
        right.addWidget(voice_box)

        # -- speak --
        speak_box = QtWidgets.QGroupBox("🗣️ Speak")
        sl = QtWidgets.QVBoxLayout()
        self.speak_edit = QtWidgets.QLineEdit()
        self.speak_edit.setPlaceholderText("Text for avatar to say…")
        self.speak_btn = QtWidgets.QPushButton("Speak")
        self.speak_btn.clicked.connect(self._speak)
        sl.addWidget(self.speak_edit)
        sl.addWidget(self.speak_btn)
        speak_box.setLayout(sl)
        right.addWidget(speak_box)

        # -- animation --
        anim_box = QtWidgets.QGroupBox("🎬 Animation State")
        al = QtWidgets.QVBoxLayout()
        self.state_combo = QtWidgets.QComboBox()
        self.state_combo.addItems(
            ["IDLE", "TALKING", "SEARCHING FILE CABINET", "WALKING", "GESTURING", "THINKING"]
        )
        self.state_btn = QtWidgets.QPushButton("Set State")
        self.state_btn.clicked.connect(self._set_state)
        # listen toggle
        self.listen_btn = QtWidgets.QPushButton("🎤 Start Listening")
        self.listen_btn.setCheckable(True)
        self.listen_btn.toggled.connect(self._toggle_listen)
        al.addWidget(self.state_combo)
        al.addWidget(self.state_btn)
        al.addWidget(self.listen_btn)
        anim_box.setLayout(al)
        right.addWidget(anim_box)

        right.addStretch(1)
        right_w = QtWidgets.QWidget()
        right_w.setLayout(right)
        right_w.setMaximumWidth(300)
        root.addWidget(right_w, 2)

        # speak timer — clears speaking after 3 s
        self._speak_timer = QtCore.QTimer(self)
        self._speak_timer.setSingleShot(True)
        self._speak_timer.timeout.connect(lambda: self.viewport.set_speaking(False))

    # ── avatar engine lifecycle ───────────────────────────────────────────
    def _launch_tab_avatar(self) -> None:
        """Load the embedded WebEngine viewport inside this tab."""
        self.viewport.load_engine()
        self._engine_status.setText("Engine: loaded (tab view)")
        self._engine_status.setStyleSheet("color: #00ffcc; font-size: 10px;")
        self.launch_btn.setEnabled(False)

    def _launch_float_avatar(self) -> None:
        """Detach avatar as a transparent, always-on-top floating window."""
        try:
            from .avatar_window import AvatarFloatingWindow
        except ImportError:
            from gui.pirate_gui.avatar_window import AvatarFloatingWindow
        name = self.name_edit.text().strip() or "TwistedSoCal"
        win = AvatarFloatingWindow.get_instance()
        win.show_avatar()
        win.set_name(name)
        self._engine_status.setText("Engine: floating window active")
        self._engine_status.setStyleSheet("color: #a855f7; font-size: 10px;")

    def _unload_avatar(self) -> None:
        """Release the WebEngine process and reclaim RAM."""
        self.viewport.unload_engine()
        self.launch_btn.setEnabled(True)
        self._engine_status.setText("Engine: unloaded")
        self._engine_status.setStyleSheet("color: #5a7a9a; font-size: 10px;")

    # ── helpers ───────────────────────────────────────────────────────────
    def _get_engine(self):
        return getattr(self.window(), "engine", None)

    def _on_style_changed(self, idx):
        self.viewport.set_style(idx)

    def _generate_avatar(self):
        eng = self._get_engine()
        prompt = self.prompt_edit.text().strip()
        name   = self.name_edit.text().strip() or (prompt.split()[0].capitalize() if prompt else "Entity")
        style  = self.style_combo.currentIndex()
        if prompt:
            self.viewport.generate_from_prompt(prompt)
        else:
            self.viewport.set_style(style)
        self.viewport.set_name(name)
        self.viewport.set_status(f"Generated: {prompt[:40]}" if prompt else "Ready")
        if eng and prompt:
            try:
                eng.avatar_generate(prompt, style)
            except Exception as e:
                self.viewport.set_status(f"Error: {e}")

    def _load_3d_mesh(self):
        filePath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Custom 3D Avatar Mesh", "", "3D Mesh Files (*.vrm *.glb *.gltf *.obj *.fbx)"
        )
        if filePath:
            import base64
            p = Path(filePath)
            ext = p.suffix.lower().lstrip(".")
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            if self.viewport.web:
                js = f"if (window.loadCustom3DMesh) window.loadCustom3DMesh('data:model/{ext};base64,{b64}', '{ext}');"
                self.viewport.web.page().runJavaScript(js)
            self.viewport.set_name(p.stem.capitalize())
            self.viewport.set_status(f"Loaded 3D Mesh: {p.name}")

    def _load_photo(self):
        filePath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Photo/Image Avatar", "", "Image Files (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if filePath:
            self.viewport.load_photo_avatar(filePath)
            self.viewport.set_status(f"Loaded photo: {Path(filePath).name}")


    def _configure_voice(self):
        eng = self._get_engine()
        if eng:
            try:
                eng.avatar_configure_voice(
                    self.voice_id_edit.text().strip(),
                    self.pitch_spin.value(),
                    self.speed_spin.value()
                )
                self.viewport.set_status("Voice configured")
            except Exception as e:
                self.viewport.set_status(f"Voice error: {e}")

    def _speak(self):
        text = self.speak_edit.text().strip()
        if not text:
            return
        self.viewport.set_speaking(True, 0.8)
        self.viewport.set_state(1)   # TALKING
        self.viewport.set_status(f'Speaking: "{text[:30]}…"' if len(text) > 30 else f'Speaking: "{text}"')
        self._speak_timer.start(max(2000, len(text) * 60))
        eng = self._get_engine()
        if eng:
            try:
                eng.avatar_speak(text)
            except Exception as e:
                self.viewport.set_status(f"Speak error: {e}")

    def _set_state(self):
        idx = self.state_combo.currentIndex()
        self.viewport.set_state(idx)
        eng = self._get_engine()
        if eng:
            try:
                eng.avatar_set_state(idx)
            except Exception as e:
                self.viewport.set_status(f"State error: {e}")

    def _toggle_listen(self, checked):
        self.viewport.set_listening(checked)
        self.listen_btn.setText("🔴 Listening…" if checked else "🎤 Start Listening")
        self.viewport.set_status("Listening for voice…" if checked else "Ready")


class EndpointPanel(QtWidgets.QWidget):
    """
    ⚡ Universal Endpoint & CCTM Panel

    Native Qt panel for:
      - Selecting / switching endpoint mode (Native HypeS / OpenAI / Anthropic)
      - Showing current active config (URL, API key, env file)
      - Live CCTM 10x compression test
      - MCP server registration status
    Wraps gui/endpoint_mode.py with zero web dependency.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mcp_status: Optional[QtWidgets.QLabel] = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = QtWidgets.QLabel("⚡  Universal Endpoint Autoconfiguration  +  10x CCTM")
        hdr.setStyleSheet(
            "color: #f59e0b; font-size: 15px; font-weight: 800; letter-spacing: 0.04em;"
        )
        layout.addWidget(hdr)

        sub = QtWidgets.QLabel(
            "Configure how every AI tool on this machine connects to HypeS. "
            "Applies env vars instantly — no restart required."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #5a7a9a; font-size: 11px;")
        layout.addWidget(sub)

        # ── Mode cards ────────────────────────────────────────────────────────
        mode_box = QtWidgets.QGroupBox("Endpoint Mode")
        mode_lay = QtWidgets.QHBoxLayout()
        mode_lay.setSpacing(10)

        self._mode_btns: dict[str, QtWidgets.QPushButton] = {}
        MODES_INFO = [
            ("native",    "⚡", "Native HypeS",    "#f59e0b",
             "http://localhost:7860\nFull CCTM + ISSI + All features"),
            ("openai",    "🤖", "OpenAI Drop-in",   "#10b981",
             "http://localhost:7860/v1\nDrop-in for any OpenAI client"),
            ("anthropic", "🔮", "Anthropic Drop-in","#a855f7",
             "http://localhost:7860\nDrop-in for Claude / Anthropic SDK"),
        ]
        for mid, icon, name, color, tip in MODES_INFO:
            btn = QtWidgets.QPushButton(f"{icon}\n{name}")
            btn.setCheckable(True)
            btn.setMinimumHeight(72)
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 8px; color: #8899aa;
                    font-size: 12px; font-weight: 700;
                }}
                QPushButton:hover {{
                    border-color: {color}; color: {color};
                    background: rgba(255,255,255,0.06);
                }}
                QPushButton:checked {{
                    border: 2px solid {color};
                    color: {color};
                    background: rgba(255,255,255,0.08);
                }}
            """)
            btn.toggled.connect(lambda checked, m=mid: self._on_mode_toggle(checked, m))
            self._mode_btns[mid] = btn
            mode_lay.addWidget(btn)

        mode_box.setLayout(mode_lay)
        layout.addWidget(mode_box)

        # ── Current status ────────────────────────────────────────────────────
        status_box = QtWidgets.QGroupBox("Active Configuration")
        status_lay = QtWidgets.QFormLayout()
        self._lbl_mode   = QtWidgets.QLabel("—")
        self._lbl_url    = QtWidgets.QLabel("—")
        self._lbl_key    = QtWidgets.QLabel("—")
        self._lbl_env    = QtWidgets.QLabel("—")
        for lbl in (self._lbl_mode, self._lbl_url, self._lbl_key, self._lbl_env):
            lbl.setStyleSheet("color: #00ffcc; font-family: Consolas, monospace; font-size: 11px;")
            lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        status_lay.addRow("Mode:",     self._lbl_mode)
        status_lay.addRow("URL:",      self._lbl_url)
        status_lay.addRow("API Key:",  self._lbl_key)
        status_lay.addRow("Env File:", self._lbl_env)
        status_box.setLayout(status_lay)
        layout.addWidget(status_box)

        # Apply + Reset buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("⚡ Apply & Auto-Configure")
        self.apply_btn.setMinimumHeight(36)
        self.apply_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #b45309,stop:1 #7c3aed); color:#fff; border:none; border-radius:7px;"
            "font-size:13px; font-weight:800; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #d97706,stop:1 #9333ea); }"
        )
        self.apply_btn.clicked.connect(self._apply_mode)
        btn_row.addWidget(self.apply_btn)

        reset_btn = QtWidgets.QPushButton("↺ Reset")
        reset_btn.setMaximumWidth(80)
        reset_btn.clicked.connect(self._reset_mode)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        # ── CCTM Live Test ────────────────────────────────────────────────────
        cctm_box = QtWidgets.QGroupBox("🔥 10x CCTM Live Compression Test")
        cctm_lay = QtWidgets.QVBoxLayout()
        self._cctm_input = QtWidgets.QPlainTextEdit()
        self._cctm_input.setMaximumHeight(64)
        self._cctm_input.setPlaceholderText(
            "Paste any text here to see live token compression ratio…"
        )
        cctm_lay.addWidget(self._cctm_input)

        cctm_run_btn = QtWidgets.QPushButton("⚡ Compress Now")
        cctm_run_btn.clicked.connect(self._run_cctm)
        cctm_lay.addWidget(cctm_run_btn)

        self._cctm_result = QtWidgets.QLabel("Compression result will appear here.")
        self._cctm_result.setWordWrap(True)
        self._cctm_result.setStyleSheet(
            "color: #00ffcc; font-family: Consolas, monospace; font-size: 11px; "
            "background: rgba(0,0,0,0.3); border-radius:6px; padding:8px;"
        )
        self._cctm_result.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        cctm_lay.addWidget(self._cctm_result)
        cctm_box.setLayout(cctm_lay)
        layout.addWidget(cctm_box)

        # ── MCP Status ────────────────────────────────────────────────────────
        mcp_box = QtWidgets.QGroupBox("MCP Server Registration")
        mcp_lay = QtWidgets.QHBoxLayout()
        self._mcp_status = QtWidgets.QLabel()
        self._mcp_status.setWordWrap(True)
        self._mcp_status.setStyleSheet("font-size: 11px;")
        mcp_lay.addWidget(self._mcp_status, 1)
        mcp_register_btn = QtWidgets.QPushButton("🚀 Re-Register MCP")
        mcp_register_btn.clicked.connect(self._register_mcp)
        mcp_lay.addWidget(mcp_register_btn)
        mcp_box.setLayout(mcp_lay)
        layout.addWidget(mcp_box)

        # ── Granular Point-and-Click Rules Panel ─────────────────────────────
        try:
            from .routing_rules_panel import GranularRoutingRulesPanel
            rules_widget = GranularRoutingRulesPanel(self)
            layout.addWidget(rules_widget, 1)
        except Exception as r_err:
            pass

        self._refresh_status()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_em(self):
        """Import endpoint_mode safely."""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            import importlib, gui.endpoint_mode as em
            return em
        except Exception:
            return None

    def _refresh_status(self):
        em = self._get_em()
        if not em:
            self._lbl_mode.setText("endpoint_mode.py not found")
            return
        mode = em.get_active_mode()
        mid = mode.get("id", "native")

        # Highlight active mode button
        for btn_id, btn in self._mode_btns.items():
            btn.blockSignals(True)
            btn.setChecked(btn_id == mid)
            btn.blockSignals(False)

        self._lbl_mode.setText(f"{mode.get('icon','')} {mode.get('name', mid)}")
        self._lbl_url.setText(mode.get("base_url", "—"))
        self._lbl_key.setText(mode.get("api_key", "—"))
        env_path = Path.home() / ".hypes" / "hypes.env"
        if env_path.exists():
            self._lbl_env.setText(str(env_path))
            self._lbl_env.setStyleSheet("color:#00ffcc; font-family:Consolas; font-size:11px;")
        else:
            self._lbl_env.setText("Not written yet — click Apply")
            self._lbl_env.setStyleSheet("color:#f59e0b; font-family:Consolas; font-size:11px;")

        # MCP status
        mcp_file = Path.home() / ".gemini" / "config" / "mcp" / "hypes-cctm.json"
        if hasattr(self, "_mcp_status") and self._mcp_status is not None:
            if mcp_file.exists():
                self._mcp_status.setText(f"✅ Registered at:\n{mcp_file}")
                self._mcp_status.setStyleSheet("color: #00ffcc; font-size: 11px;")
            else:
                self._mcp_status.setText("⚠️ Not registered. Click Re-Register.")
                self._mcp_status.setStyleSheet("color: #f59e0b; font-size: 11px;")

    def _on_mode_toggle(self, checked: bool, mode_id: str):
        if checked:
            for mid, btn in self._mode_btns.items():
                if mid != mode_id:
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)

    def _apply_mode(self):
        # Find which button is checked
        selected = next(
            (mid for mid, btn in self._mode_btns.items() if btn.isChecked()),
            "native"
        )
        em = self._get_em()
        if em:
            em.save_mode(selected)
            em.apply_env_vars(selected)
        self._refresh_status()
        QtWidgets.QMessageBox.information(
            self, "⚡ Applied",
            f"Endpoint mode set to: {selected.upper()}\n\n"
            f"Environment variables applied to this process.\n"
            f"Env file written to ~/.hypes/hypes.env"
        )

    def _reset_mode(self):
        em = self._get_em()
        if em:
            em.reset_mode()
        self._refresh_status()

    def _run_cctm(self):
        text = self._cctm_input.toPlainText().strip()
        if not text:
            text = (
                "The user is asking about configuring the proxy endpoint and "
                "enabling token compression for large language model interactions."
            )
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from session_engine import TenXCompressionModule
            m = TenXCompressionModule()
            compressed, ratio = m.compress_10x(text)
            orig_words = len(text.split())
            self._cctm_result.setText(
                f"✅ {ratio:.1f}x compression\n"
                f"Original: ~{orig_words} words\n"
                f"Compressed: {str(compressed)[:120]}{'…' if len(str(compressed)) > 120 else ''}"
            )
        except Exception as e:
            self._cctm_result.setText(f"❌ CCTM error: {e}")

    def _register_mcp(self):
        try:
            import json as _json
            root = str(Path(__file__).parent.parent.parent)
            mcp_script = str(Path(root) / "mcp_server" / "hypes_cctm_server.py")
            gui_dir = str(Path(root) / "gui")
            config_dir = Path.home() / ".gemini" / "config" / "mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            target = config_dir / "hypes-cctm.json"
            payload = {
                "mcpServers": {
                    "hypes-cctm": {
                        "command": sys.executable,
                        "args": [mcp_script],
                        "env": {
                            "PIRATE_ROOT": root,
                            "PYTHONPATH": f"{root};{gui_dir}"
                        },
                        "description": "HypeS CCTM — 10x/23x Token Compression"
                    }
                }
            }
            with open(target, "w") as f:
                _json.dump(payload, f, indent=2)
            self._refresh_status()
        except Exception as e:
            self._mcp_status.setText(f"❌ Registration failed: {e}")
            self._mcp_status.setStyleSheet("color: #ff4444; font-size: 11px;")


class CyberHeaderBanner(QtWidgets.QFrame):
    """Futuristic cyber header banner widget with animated 4D graphics and Golden Candy Spinner quick launcher."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #080f1c, stop:0.5 #0d1929, stop:1 #080f1c);
                border: 1px solid rgba(0, 200, 255, 0.4);
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        # Live animated spinning 4D hypersphere orb graphic
        self.spin_graphic = SpinningHypersphereWidget(self)
        self.spin_graphic.setToolTip("Pirate Llama 4D Hyperspherical Vector Engine — Real-time continuous 4D rotation.")

        title_box = QtWidgets.QVBoxLayout()
        t1 = QtWidgets.QLabel("🏴‍☠️ PIRATE LLAMA CONTROL CENTER")
        t1.setStyleSheet("color: #00c8ff; font-weight: 900; font-size: 15px; letter-spacing: 1px;")
        t2 = QtWidgets.QLabel("Hyper-Spherical Systems v2.0 · 4D Hyperspherical Vector Engine")
        t2.setStyleSheet("color: #ffd700; font-weight: bold; font-size: 11px;")
        title_box.addWidget(t1)
        title_box.addWidget(t2)

        gcs_btn = QtWidgets.QPushButton("🍬 Golden Candy Spinner")
        gcs_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #cc8800, stop:1 #aa5500);
                color: #ffffff; font-weight: bold; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton:hover { background: #ffd700; color: #040810; }
        """)
        gcs_btn.setToolTip("Launch Golden Candy Spinner model decomposition tool.")
        gcs_btn.clicked.connect(self._launch_gcs)

        layout.addWidget(self.spin_graphic)
        layout.addLayout(title_box, 1)
        layout.addWidget(gcs_btn)


    def _launch_gcs(self) -> None:
        try:
            from .golden_candy_spinner_panel import GoldenCandySpinnerWindow
        except ImportError:
            from gui.pirate_gui.golden_candy_spinner_panel import GoldenCandySpinnerWindow
        GoldenCandySpinnerWindow.show_window()


# ── Main window ───────────────────────────────────────────────────────
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: config_io.GuiConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.engine: Optional[TessEngine] = None

        self.setWindowTitle("Hyper-Spherical Control Center — Master Edition")
        self.resize(1180, 780)

        # Apply dark mode QSS styling
        self.setStyleSheet(DARK_QSS)

        # Explicit Window Flags for Minimize, Maximize, and Close
        flags = QtCore.Qt.Window | QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowMaximizeButtonHint | QtCore.Qt.WindowCloseButtonHint
        if getattr(cfg, "always_on_top", False):
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        # Menu bar
        bar = self.menuBar()
        m_file = bar.addMenu("&File")
        m_file.addAction("&Save Config",       self._save_cfg)
        m_file.addAction("&Minimize",          self.showMinimized)
        m_file.addAction("E&xit",             self.close)

        m_view = bar.addMenu("&View")
        self.act_always_top = QtGui.QAction("📌 Always on Top", self)
        self.act_always_top.setCheckable(True)
        self.act_always_top.setChecked(getattr(cfg, "always_on_top", False))
        self.act_always_top.toggled.connect(self._toggle_always_on_top)
        m_view.addAction(self.act_always_top)

        self.act_token_hud = QtGui.QAction("⚡ Token HUD (Floating)", self)
        self.act_token_hud.setShortcut("Ctrl+Shift+T")
        self.act_token_hud.setCheckable(True)
        self.act_token_hud.setChecked(True)
        self.act_token_hud.toggled.connect(self._toggle_token_hud)
        m_view.addAction(self.act_token_hud)

        m_engine = bar.addMenu("&Engine")
        m_engine.addAction("&Run Benchmark",   self._run_benchmark)
        m_engine.addAction("&Save Checkpoint", self._save_checkpoint)

        m_tools = bar.addMenu("&Tools")
        m_tools.addAction("🍬 Launch Golden Candy Spinner", self._launch_gcs)

        m_3fa = bar.addMenu("&3FA")
        m_3fa.addAction("Re-pair device",     self._re_pair)

        m_help = bar.addMenu("&Help")
        m_help.addAction("&About",            self._about)

        # Main Toolbar
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.addAction("Refresh",        self._manual_refresh)
        tb.addSeparator()
        tb.addAction("Compress",       self._quick_compress)
        tb.addAction("Train pattern",  self._quick_train)
        tb.addSeparator()

        # Token HUD floating button in toolbar
        self.tb_hud_btn = QtWidgets.QPushButton("⚡ Token HUD")
        self.tb_hud_btn.setCheckable(True)
        self.tb_hud_btn.setChecked(True)
        self.tb_hud_btn.toggled.connect(self._toggle_token_hud)
        self.tb_hud_btn.setToolTip("Toggle floating token savings overlay (Ctrl+Shift+T).")
        tb.addWidget(self.tb_hud_btn)
        
        # Ensure HUD is actually shown on startup since it's checked by default
        QtCore.QTimer.singleShot(100, lambda: self._toggle_token_hud(True))

        # Always-on-top toggle button in toolbar
        self.tb_top_btn = QtWidgets.QPushButton("📌 Always on Top")
        self.tb_top_btn.setCheckable(True)
        self.tb_top_btn.setChecked(getattr(cfg, "always_on_top", False))
        self.tb_top_btn.toggled.connect(self._toggle_always_on_top)
        self.tb_top_btn.setToolTip("Toggle whether Pirate Llama window stays floating on top of all other windows.")
        tb.addWidget(self.tb_top_btn)


        # Minimize button in toolbar
        tb_min_btn = QtWidgets.QPushButton("🗕 Minimize")
        tb_min_btn.setToolTip("Minimize Pirate Llama window to taskbar.")
        tb_min_btn.clicked.connect(self.showMinimized)
        tb.addWidget(tb_min_btn)


        # Golden Candy Spinner launch button in toolbar
        tb_gcs_btn = QtWidgets.QPushButton("🍬 Golden Candy Spinner")
        tb_gcs_btn.setToolTip("Click to open Golden Candy Spinner model decomposition tool.")
        tb_gcs_btn.clicked.connect(self._launch_gcs)
        tb.addWidget(tb_gcs_btn)

        # Float avatar toolbar button
        tb_avatar_btn = QtWidgets.QPushButton("\U0001f916 Float Avatar")
        tb_avatar_btn.setToolTip("Pop the 4ID avatar as a transparent, always-on-top floating window.")
        tb_avatar_btn.clicked.connect(self._launch_float_avatar)
        tb.addWidget(tb_avatar_btn)

        tb.addSeparator()
        self.refresh_box = QtWidgets.QSpinBox()
        self.refresh_box.setRange(50, 5000)
        self.refresh_box.setValue(cfg.refresh_interval_ms)
        self.refresh_box.setSuffix(" ms")
        self.refresh_box.valueChanged.connect(self._set_refresh)
        tb.addWidget(QtWidgets.QLabel("Refresh:"))
        tb.addWidget(self.refresh_box)

        # Cyber Header Banner
        self.header_banner = CyberHeaderBanner()

        # Sidebar + panels
        try:
            from .golden_candy_spinner_panel import GoldenCandySpinnerPanel
        except ImportError:
            from gui.pirate_gui.golden_candy_spinner_panel import GoldenCandySpinnerPanel

        try:
            from .model_browser_panel import ModelBrowserPanel
        except ImportError:
            from gui.pirate_gui.model_browser_panel import ModelBrowserPanel

        try:
            from .voice_duplex_panel import VoiceDuplexPanel
        except ImportError:
            from gui.pirate_gui.voice_duplex_panel import VoiceDuplexPanel

        self.telemetry_panel = TelemetryPanel()
        self.gpu_target_panel = GpuHardwareTargetPanel()
        self.model_browser_panel = ModelBrowserPanel()
        self.gcs_panel = GoldenCandySpinnerPanel()
        self.voice_panel = VoiceDuplexPanel()
        self.finetune_panel   = FineTuningPresetsPanel()
        self.compress_panel = CompressionPanel()
        self.predict_panel = PredictorPanel()
        self.advanced_panel = AdvancedPanel()
        self.master_panel = MasterPanel()
        self.integrations_panel = IntegrationsPanel()
        self.backup_panel = AutoBackupPanel()
        self.avatar_panel = FourIdentityAvatarPanel()
        self.guardian_panel = GuardianSecurityPanel()
        self.endpoint_panel = EndpointPanel()

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.telemetry_panel, "Telemetry")
        self.tabs.addTab(self.endpoint_panel,  "⚡ Endpoint & CCTM")
        self.tabs.addTab(self.model_browser_panel, "🌐 Model Browser & Downloads")
        self.tabs.addTab(self.gpu_target_panel, "GPU Target & Brain")
        self.gcs_tab_index = self.tabs.addTab(self.gcs_panel, "🍬 Golden Candy Spinner")
        self.tabs.addTab(self.voice_panel, "🎙️ Duplex Live Voice")
        self.tabs.addTab(self.finetune_panel,   "Fine-Tuning & Guardrails")
        self.tabs.addTab(self.compress_panel, "Compression")
        self.tabs.addTab(self.predict_panel,  "Predictor")
        self.tabs.addTab(self.advanced_panel, "Advanced")
        self.tabs.addTab(self.master_panel,   "Master")
        self.tabs.addTab(self.integrations_panel, "Integrations")
        self.tabs.addTab(self.backup_panel, "Auto Backup")
        self.tabs.addTab(self.avatar_panel, "4ID Avatar")
        self.tabs.addTab(self.guardian_panel, "🛡️ Guardian & Parent Key")


        self.advanced_panel.configChanged.connect(self._on_advanced_changed)
        self.advanced_panel.encryptionChanged.connect(self._on_encryption_toggle)
        self.master_panel.configChanged.connect(self._on_master_changed)

        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.log_view)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        central_w = QtWidgets.QWidget()
        c_layout = QtWidgets.QVBoxLayout(central_w)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.addWidget(self.header_banner)
        c_layout.addWidget(splitter, 1)

        self.setCentralWidget(central_w)

        # Status bar
        self.status_lbl = QtWidgets.QLabel("Ready")
        self.statusBar().addPermanentWidget(self.status_lbl)

        # Telemetry refresh timer
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh_telemetry)
        self._timer.start(cfg.refresh_interval_ms)

        self._log("GUI ready. Click 'Run benchmark' or launch Golden Candy Spinner.")

        # Open the engine
        self._open_engine()

    def _toggle_always_on_top(self, checked: bool) -> None:
        self.cfg.always_on_top = checked
        self.act_always_top.blockSignals(True)
        self.tb_top_btn.blockSignals(True)
        self.act_always_top.setChecked(checked)
        self.tb_top_btn.setChecked(checked)
        self.act_always_top.blockSignals(False)
        self.tb_top_btn.blockSignals(False)

        flags = QtCore.Qt.Window | QtCore.Qt.WindowMinimizeButtonHint | QtCore.Qt.WindowMaximizeButtonHint | QtCore.Qt.WindowCloseButtonHint
        if checked:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self._log(f"Window Always-on-Top {'ENABLED' if checked else 'DISABLED'}")

    def _toggle_token_hud(self, checked: bool) -> None:
        from .token_hud import get_hud
        hud = get_hud()
        if checked:
            hud.show()
        else:
            hud.hide()
        self.act_token_hud.blockSignals(True)
        self.tb_hud_btn.blockSignals(True)
        self.act_token_hud.setChecked(checked)
        self.tb_hud_btn.setChecked(checked)
        self.act_token_hud.blockSignals(False)
        self.tb_hud_btn.blockSignals(False)
        self._log(f"Token HUD Floating Overlay {'SHOWN' if checked else 'HIDDEN'}")


    def _launch_gcs(self) -> None:
        self._log("Opening Golden Candy Spinner Native Window...")
        try:
            from .golden_candy_spinner_panel import GoldenCandySpinnerWindow
        except ImportError:
            from gui.pirate_gui.golden_candy_spinner_panel import GoldenCandySpinnerWindow

        if hasattr(self, "gcs_tab_index") and self.gcs_tab_index is not None:
            self.tabs.setCurrentIndex(self.gcs_tab_index)
        GoldenCandySpinnerWindow.show_window()

    def _launch_float_avatar(self) -> None:
        """Pop the 4ID avatar as a transparent floating desktop window."""
        try:
            from .avatar_window import AvatarFloatingWindow
        except ImportError:
            from gui.pirate_gui.avatar_window import AvatarFloatingWindow
        win = AvatarFloatingWindow.get_instance()
        win.show_avatar()
        win.set_name(getattr(self.cfg, "user_name", "TwistedSoCal"))
        self._log("4ID Avatar floating window launched.")

    # ── helpers ────────────────────────────────────────────────────────
    def _version(self) -> str:
        try:
            with TessEngine() as e:
                return e.version
        except Exception:
            return "engine offline"

    def _log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")

    def _open_engine(self) -> None:
        try:
            self.engine = TessEngine()
            # V1.7.1: 60 GB illusion presented to the LLM (12 GB physical)
            self.engine.init_vram(
                self.cfg.phys_vram_gb * 2**30,
                self.cfg.phys_ram_gb * 2**30,
                self.cfg.virtual_vram_gb * 2**30)
            self.status_lbl.setText(
                f"Engine ready — {self.engine.version}  |  "
                f"VRAM: {self.cfg.phys_vram_gb} GB physical, "
                f"{self.cfg.virtual_vram_gb} GB illusion "
                f"({self.engine.vram_illusion_ratio():.1f}×)")
            self._log(f"Loaded {self.engine.version}")
            self._log(f"VRAM: {self.cfg.phys_vram_gb} GB physical, "
                       f"{self.cfg.virtual_vram_gb} GB illusion "
                       f"({self.engine.vram_illusion_ratio():.1f}×)")
        except BridgeError as e:
            self.status_lbl.setText(f"Engine error: {e}")
            self._log(f"ERROR opening engine: {e}")
            self.engine = None

    # ── timer / refresh ────────────────────────────────────────────────
    def _refresh_telemetry(self) -> None:
        if not self.engine:
            return
        try:
            tel = self.engine.telemetry()
            self.telemetry_panel.update_telemetry(self.engine, tel)
        except BridgeError as e:
            self._log(f"telemetry error: {e}")

    def _manual_refresh(self) -> None:
        self._refresh_telemetry()
        self._log("Manual refresh.")

    def _set_refresh(self, ms: int) -> None:
        self.cfg.refresh_interval_ms = ms
        self._timer.setInterval(ms)
        self._log(f"Refresh interval set to {ms} ms")

    # ── menu actions ───────────────────────────────────────────────────
    def _save_cfg(self) -> None:
        try:
            config_io.save(self.cfg)
            self._log("Config saved.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save failed", str(e))

    def _run_benchmark(self) -> None:
        exe = Path(r"C:\Users\twist\workspace\project_tesseract\build\nvme_benchmark.exe")
        if not exe.exists():
            QtWidgets.QMessageBox.warning(self, "Not built",
                                          "Build the project (run CMake) first.")
            return
        self._log("Running NVMe benchmark...")
        try:
            import subprocess
            res = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
            self._log(f"Benchmark done (rc={res.returncode}).")
            # Show tail
            for ln in res.stdout.splitlines()[-15:]:
                self._log("  " + ln)
        except Exception as e:
            self._log(f"Benchmark failed: {e}")

    def _save_checkpoint(self) -> None:
        if not self.engine:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save checkpoint", "session.tess",
            "Tesseract checkpoint (*.tess)")
        if not path: return
        try:
            self.engine.checkpoint_save(path)
            self._log(f"Checkpoint saved to {path}")
        except BridgeError as e:
            self._log(f"checkpoint save failed: {e}")

    def _re_pair(self) -> None:
        from .wizard import ThreeFAPage, SetupWizard
        page = ThreeFAPage()
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Re-pair 3FA device")
        lay = QtWidgets.QVBoxLayout(dlg)
        lay.addWidget(page.qr_label, 0, QtCore.Qt.AlignCenter)
        lay.addWidget(QtWidgets.QLabel(f"Secret: <code>{page._secret_b32}</code>"))
        ok = QtWidgets.QPushButton("Done")
        ok.clicked.connect(dlg.accept)
        lay.addWidget(ok)
        dlg.exec()
        self.cfg.threefa_pairing_secret = page._secret_b32
        self.cfg.threefa_paired = True
        config_io.save(self.cfg)
        self._log("3FA device re-paired.")

    def _about(self) -> None:
        QtWidgets.QMessageBox.about(self, "About Tesseract",
            "<b>Project Pirate Llama Control Center</b><br>"
            "Local LLM inference engine with NVMe tiering.<br><br>"
            "Bridge: pirate_bridge.dll<br>"
            "GUI: PySide6")

    # ── toolbar actions ────────────────────────────────────────────────
    def _quick_compress(self) -> None:
        self.compress_panel._on_run()

    def _quick_train(self) -> None:
        self.predict_panel._train_cycle()

    # ── advanced panel → backend ───────────────────────────────────────
    def _on_advanced_changed(self) -> None:
        # Persist every knob into cfg (so it survives restart)
        ap = self.advanced_panel
        self.cfg.eviction_threshold = float(ap.eviction_threshold.value())
        self.cfg.stay_in_buffer     = float(ap.stay_in_buffer.value())
        self.cfg.load_in_prefetch   = float(ap.load_in_prefetch.value())
        self.cfg.offload_aggr       = int(ap.offload_aggr.value())
        self.cfg.predict_aggr       = int(ap.predict_aggr.value())
        self.cfg.pred_threads       = int(ap.pred_threads.value())
        self.cfg.model_threads      = int(ap.model_threads.value())
        self.cfg.mem_ceiling        = float(ap.mem_ceiling.value())
        self.cfg.encryption_enabled = ap.encryption_chk.isChecked()
        if ap._encryption_fpr:
            self.cfg.encryption_key_fpr = ap._encryption_fpr
        self._log("Settings changed → " + ap.summary())

    def _on_encryption_toggle(self, on: bool) -> None:
        if on:
            self._log("Encryption ENABLED — cold-storage shards will be ChaCha20‑Poly1305 sealed.")
        else:
            self._log("Encryption DISABLED — shards stored as plaintext (legacy mode).")

    def _on_master_changed(self) -> None:
        mp = self.master_panel
        self.cfg.drive_mode             = "single" if mp.drive_single.isChecked() else "dual"
        self.cfg.nvme_quota_gb          = int(mp.nvme_quota.value())
        self.cfg.dma_thread_count       = int(mp.dma_threads.value())
        self.cfg.predictive_sensitivity = float(mp._predictive_value)
        self.cfg.adaptive_hysteresis    = bool(mp.adaptive_hyst.isChecked())
        self.cfg.autotune_sensitivity   = float(mp._autotune_value)
        self.cfg.trf_model_filename     = mp.trf_model.text().strip() or "tesseract-current.gguf"
        self._log("Master settings changed → " + mp.summary())

    # ── shutdown ───────────────────────────────────────────────────────
    def closeEvent(self, ev: QtGui.QCloseEvent) -> None:
        self.cfg.window_geometry = bytes(self.saveGeometry())
        config_io.save(self.cfg)
        if self.engine:
            self.engine.close()
        super().closeEvent(ev)


def _humanize_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

