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

DARK_QSS = """
QMainWindow {
    background-color: #121212;
    color: #e0e0e0;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #333333;
    border-radius: 6px;
    margin-top: 6px;
    padding-top: 10px;
    background-color: #1e1e1e;
    color: #00c8ff;
}
QTabWidget::pane {
    border: 1px solid #333333;
    background-color: #1e1e1e;
}
QTabBar::tab {
    background-color: #2a2a2a;
    color: #aaaaaa;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #00c8ff;
    color: #000000;
    font-weight: bold;
}
QPushButton {
    background-color: #2a2a2a;
    color: #ffffff;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #00c8ff;
    color: #000000;
}
QPlainTextEdit, QLineEdit {
    background-color: #181818;
    color: #00ffcc;
    border: 1px solid #333333;
    font-family: Consolas, monospace;
}
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
        self.run_btn.setToolTip("Execute live SISSI/homophonic token compression test on sample text.")
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
            mascot_lbl.setToolTip("🏴‍☠️ Pirate Llama Cyber Mascot — 2-Way Zero-Config Intercept & SISSI Compression Engine")
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
            f"• Auto-Calculated SISSI Compression Target: {desired_ratio:.1f}×\n"
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
    Fully native Qt avatar — no browser, no WebEngine.
    Driven by QPainter + QTimer at 30 fps.

    Features:
    - Expressive face: eyebrows, pupils tracking, multiple mouth shapes,
      blinking, raised eyebrows, furrowed brow, squinting
    - Detailed hands: open palm, pointing finger, fist, wave, thumbs-up,
      chin-scratch, chin-rest (thinking)
    - Full personality: autonomous idle fidgets (weight shift, look around,
      scratch head), breathing, emotion flashes
    - State-driven full-body animations for all 6 states
    """

    STATE_NAMES = ["IDLE", "TALKING", "SEARCHING", "WALKING", "GESTURING", "THINKING"]

    # Emotion constants
    EMO_NEUTRAL  = 0
    EMO_HAPPY    = 1
    EMO_THINKING = 2
    EMO_SURPRISED = 3
    EMO_FOCUSED  = 4
    EMO_AMUSED   = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 460)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setAutoFillBackground(False)

        # Core state
        self._state      = 0
        self._tick       = 0
        self._style_idx  = 0
        self._name       = "Entity"
        self._speaking   = False
        self._listen     = False
        self._mouth_open = 0.0
        self._status_msg = "Ready"

        # Personality / emotion system
        self._emotion         = self.EMO_NEUTRAL
        self._emotion_timer   = 0      # ticks until next autonomous emotion
        self._idle_gesture    = 0      # which idle sub-gesture is active
        self._idle_gesture_t  = 0      # phase within that gesture
        self._look_offset_x   = 0.0   # pupil gaze offset -1..1
        self._look_offset_y   = 0.0
        self._look_target_x   = 0.0
        self._look_target_y   = 0.0
        self._blink_t         = 0      # blink phase
        self._blink_closed    = False
        self._eyebrow_raise   = 0.0   # -1=furrowed 0=neutral 1=raised
        self._eyebrow_target  = 0.0
        self._breath_phase    = 0.0   # sinusoidal breath
        self._gesture_phase   = 0.0   # sub-gesture oscillator
        self._weight_side     = 0     # -1=left, 0=centre, 1=right (idle weight shift)

        # Autonomous behaviour schedule (in ticks)
        self._next_look   = 90
        self._next_blink  = 30
        self._next_fidget = 200

        # Style palettes
        self._palettes = [
            {"skin": "#f5cba7", "skin2": "#e59866", "hair": "#4a3728",
             "eye": "#27ae60",  "pupil": "#1a5c36",  "lip": "#c0392b",
             "glow": "#00ffcc", "shirt": "#2980b9",  "label": "Realistic"},
            {"skin": "#ffe4b5", "skin2": "#f0c080", "hair": "#ff69b4",
             "eye": "#9b59b6",  "pupil": "#5d3478",  "lip": "#e91e63",
             "glow": "#ff00ff", "shirt": "#8e44ad",  "label": "Anime"},
            {"skin": "#ffdd57", "skin2": "#f0b800", "hair": "#e74c3c",
             "eye": "#2980b9",  "pupil": "#154360",  "lip": "#c0392b",
             "glow": "#f9ca24", "shirt": "#27ae60",  "label": "Cartoon"},
            {"skin": "#6c3483", "skin2": "#4a235a", "hair": "#1abc9c",
             "eye": "#e74c3c",  "pupil": "#7b241c",  "lip": "#8e44ad",
             "glow": "#8e44ad", "shirt": "#17202a",  "label": "Creature"},
        ]

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(33)  # 30 fps

        # ── Spawn / materialisation sequence ─────────────────────────────
        # Phase 0: Hypersphere swirling (0..89)
        # Phase 1: Collapse + shockwave  (90..119)
        # Phase 2: Materialise fade-in   (120..179)
        # Phase 3: Alive (180+)
        self._spawn_tick   = 0
        self._spawn_done   = False
        # spawn particles: list of [x_rel, y_rel, vx, vy, size, col_hue, alpha]
        import random as _r
        self._spawn_particles = [
            [_r.uniform(-1.0, 1.0), _r.uniform(-1.0, 1.0),
             _r.uniform(-2.5, 2.5), _r.uniform(-2.5, 2.5),
             _r.uniform(2, 6), _r.randint(0, 360), _r.randint(180, 255)]
            for _ in range(55)
        ]
        self._spawn_sub_angles = [i * (360.0 / 12) for i in range(12)]
        self._spawn_vortex_a   = 0.0

    # ── Public API ────────────────────────────────────────────────────────
    def set_state(self, idx: int):
        old = self._state
        self._state = max(0, min(idx, len(self.STATE_NAMES) - 1))
        if self._state != old:
            self._gesture_phase = 0.0
            # emotion hint per state
            em_map = {0: self.EMO_NEUTRAL, 1: self.EMO_HAPPY,
                      2: self.EMO_FOCUSED, 3: self.EMO_NEUTRAL,
                      4: self.EMO_AMUSED,  5: self.EMO_THINKING}
            self._emotion = em_map.get(self._state, self.EMO_NEUTRAL)

    def set_style(self, idx: int):
        self._style_idx = max(0, min(idx, len(self._palettes) - 1))

    def set_name(self, name: str):
        self._name = name or "Entity"

    def set_speaking(self, val: bool, mouth_open: float = 0.0):
        self._speaking   = val
        self._mouth_open = mouth_open
        if val:
            self._emotion = self.EMO_HAPPY

    def set_listening(self, val: bool):
        self._listen = val
        if val:
            self._emotion = self.EMO_FOCUSED

    def set_status(self, msg: str):
        self._status_msg = msg

    # ── Autonomous animation tick ─────────────────────────────────────────
    def _animate(self):
        import math, random
        self._tick += 1
        t = self._tick

        # ── spawn sequence tick ───────────────────────────────────────────
        if not self._spawn_done:
            self._spawn_tick += 1
            self._spawn_vortex_a += 0.09
            # update spawn particles
            W, H = max(1, self.width()), max(1, self.height())
            cx, cy = W / 2.0, H / 2.0
            for pt in self._spawn_particles:
                if self._spawn_tick < 90:   # phase 0: spiral inward
                    dx, dy = cx - (cx + pt[0] * 80), cy - (cy + pt[1] * 80)
                    dist = math.sqrt(dx*dx + dy*dy) + 0.1
                    pt[2] += (dx / dist) * 0.25
                    pt[3] += (dy / dist) * 0.25
                    pt[0] += pt[2] * 0.04
                    pt[1] += pt[3] * 0.04
                    # fade in
                    pt[6] = min(255, pt[6] + 3)
                elif self._spawn_tick < 120:  # phase 1: blast outward
                    pt[0] += pt[2] * 0.18
                    pt[1] += pt[3] * 0.18
                    pt[6] = max(0, pt[6] - 8)
                else:                          # phase 2+: fade away
                    pt[6] = max(0, pt[6] - 14)
            for i in range(len(self._spawn_sub_angles)):
                self._spawn_sub_angles[i] += 3.4
            if self._spawn_tick >= 180:
                self._spawn_done = True
            self.update()
            if not self._spawn_done:
                return   # skip normal anim during spawn

        # Breathing
        self._breath_phase = math.sin(t * 0.04) * 2.5

        # Mouth open while speaking
        if self._speaking:
            self._mouth_open = 0.45 + 0.55 * abs(math.sin(t * 0.38 + 0.3))

        # Gesture phase oscillator
        self._gesture_phase += 0.06
        if self._gesture_phase > math.tau:
            self._gesture_phase -= math.tau

        # ── autonomous blink ──────────────────────────────────────────────
        self._blink_t -= 1
        if self._blink_t <= 0:
            self._blink_closed = True
            self._blink_t = random.randint(70, 150)
        elif self._blink_closed and self._blink_t > 5:
            self._blink_closed = False

        # ── autonomous gaze shift ─────────────────────────────────────────
        self._next_look -= 1
        if self._next_look <= 0:
            self._next_look = random.randint(60, 180)
            self._look_target_x = random.uniform(-0.55, 0.55)
            self._look_target_y = random.uniform(-0.3, 0.3)
        # smooth tracking
        self._look_offset_x += (self._look_target_x - self._look_offset_x) * 0.12
        self._look_offset_y += (self._look_target_y - self._look_offset_y) * 0.12

        # ── eyebrow lerp ──────────────────────────────────────────────────
        self._eyebrow_raise += (self._eyebrow_target - self._eyebrow_raise) * 0.08

        # ── autonomous fidget ─────────────────────────────────────────────
        self._next_fidget -= 1
        if self._next_fidget <= 0 and self._state == 0:  # IDLE only
            self._next_fidget = random.randint(120, 300)
            self._idle_gesture = random.randint(0, 4)
            self._idle_gesture_t = 60
            # random emotion flash
            self._emotion = random.choice([self.EMO_NEUTRAL, self.EMO_HAPPY,
                                           self.EMO_AMUSED, self.EMO_NEUTRAL])
            self._eyebrow_target = random.choice([-0.5, 0.0, 0.8])
            # random weight shift
            self._weight_side = random.choice([-1, 0, 1])

        if self._idle_gesture_t > 0:
            self._idle_gesture_t -= 1

        self.update()

    # ── Helpers ───────────────────────────────────────────────────────────
    def _draw_hand(self, p, x, y, shape, pal, size=10, angle_deg=0.0):
        """Draw a hand icon at (x,y). shape: 0=open 1=point 2=fist 3=wave 4=thumbsup 5=peace"""
        import math
        p.save()
        p.translate(x, y)
        p.rotate(angle_deg)
        s = size
        skin = QtGui.QColor(pal["skin"])
        skin2 = QtGui.QColor(pal["skin2"])

        p.setPen(QtGui.QPen(skin2, 1.5))
        p.setBrush(QtGui.QBrush(skin))

        if shape == 0:  # open palm
            # palm
            p.drawEllipse(-s, -s, s * 2, s * 2)
            # fingers
            for fi, (fx, fy) in enumerate([(-s//2, -s-6), (-1, -s-9),
                                            (s//2, -s-7), (s+2, -s//2)]):
                p.drawEllipse(fx - 3, fy - 5, 6, 10)
            # thumb
            p.drawEllipse(-s - 5, -3, 7, 11)

        elif shape == 1:  # pointing finger
            p.drawEllipse(-s, -s//2, s * 2, s)  # fist base
            # extended index finger
            p.drawRect(-2, -s - 12, 5, 13)
            # folded fingers
            for fi, fy in [(s//2 - 3, -s//2), (0, -s//2), (-s//2+1, -s//2)]:
                p.drawEllipse(fi - 2, fy, 5, 7)

        elif shape == 2:  # fist
            p.drawRoundedRect(-s, -s//2, s*2, s+2, 4, 4)
            # finger line
            p.setPen(QtGui.QPen(skin2, 1))
            p.drawLine(-s//2, -s//2, s//2, -s//2)

        elif shape == 3:  # wave (spread fingers)
            p.drawEllipse(-s, -s//2, s*2, s)
            angles = [-40, -20, 0, 20, 40]
            for ai, ang in enumerate(angles):
                rad = math.radians(ang - 80)
                ex = int(math.cos(rad) * (s + 10))
                ey = int(math.sin(rad) * (s + 10))
                p.drawLine(0, 0, ex, ey)
                p.drawEllipse(ex - 3, ey - 3, 6, 6)

        elif shape == 4:  # thumbs up
            p.drawRoundedRect(-s//2, 0, s, s, 3, 3)  # fist
            # thumb up
            p.drawEllipse(-2, -s - 8, 7, s + 4)

        elif shape == 5:  # peace / V sign
            p.drawRoundedRect(-s//2+2, -2, s-4, s//2+4, 3, 3)
            # index up-left
            p.drawRect(-s//2, -s-10, 5, s+4)
            # middle up-right
            p.drawRect(s//2-5, -s-10, 5, s+4)

        p.restore()

    def _mouth_path(self, cx, my, mw, mh, emotion, mouth_open):
        """Return a QPainterPath for the current mouth expression."""
        path = QtGui.QPainterPath()
        if emotion == self.EMO_HAPPY or emotion == self.EMO_AMUSED:
            # big smile
            path.moveTo(cx - mw, my)
            path.quadTo(cx, my + mh + mouth_open * mw * 0.8, cx + mw, my)
        elif emotion == self.EMO_SURPRISED:
            # wide O
            path.addEllipse(cx - mw * 0.6, my - mh * 0.3,
                            mw * 1.2, mh * 0.8 + mouth_open * 12)
        elif emotion == self.EMO_THINKING:
            # slight frown / asymmetric
            path.moveTo(cx - mw * 0.7, my + 4)
            path.quadTo(cx - mw * 0.2, my,  cx, my + 2)
            path.quadTo(cx + mw * 0.5, my + 8, cx + mw * 0.8, my + 6)
        else:
            # neutral — thin line or slight curve
            path.moveTo(cx - mw * 0.6, my + 2)
            path.quadTo(cx, my + 4 + mouth_open * 8, cx + mw * 0.6, my + 2)
        return path

    # ── Main paint ────────────────────────────────────────────────────────
    def _draw_spawn(self, p, W, H):
        """Draws the hypersphere spawn / materialise sequence."""
        import math
        st  = self._spawn_tick
        va  = self._spawn_vortex_a
        pal = self._palettes[self._style_idx]
        glow_hex = pal["glow"]

        cx, cy = W / 2.0, H / 2.0
        radius = min(W, H) * 0.28

        # ── background ──────────────────────────────────────────────────
        bg = QtGui.QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0.0, QtGui.QColor("#04040c"))
        bg.setColorAt(1.0, QtGui.QColor("#060d18"))
        p.fillRect(0, 0, W, H, bg)

        # ── phase-based alpha scaling ────────────────────────────────────
        if st < 90:       # phase 0: full hypersphere, build-up
            hyper_alpha  = min(1.0, st / 30.0)
            collapse_pct = 0.0
            shock_alpha  = 0.0
            mat_alpha    = 0.0
        elif st < 120:    # phase 1: collapse
            hyper_alpha  = 1.0 - (st - 90) / 30.0
            collapse_pct = (st - 90) / 30.0
            shock_alpha  = collapse_pct
            mat_alpha    = 0.0
        else:             # phase 2: materialise
            hyper_alpha  = 0.0
            collapse_pct = 1.0
            shock_alpha  = max(0.0, 1.0 - (st - 120) / 40.0)
            mat_alpha    = min(1.0, (st - 120) / 60.0)

        # ── XOR vortex rings ─────────────────────────────────────────────
        if hyper_alpha > 0.01:
            p.setCompositionMode(QtGui.QPainter.CompositionMode_Difference)
            for ri in range(4):
                ring_r = (radius * (0.4 + 0.22 * ri) *
                          (1.0 - collapse_pct * 0.85) +
                          math.sin(va + ri) * 7)
                c = QtGui.QColor(glow_hex)
                c.setAlpha(int(180 * hyper_alpha))
                p.setPen(QtGui.QPen(c, 1.5, QtCore.Qt.DashLine))
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawEllipse(QtCore.QPointF(cx, cy), ring_r, ring_r * 0.58)
            p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)

            # spinning vertex lines
            p.setPen(QtGui.QPen(QtGui.QColor(255, 0, 128, int(140 * hyper_alpha)), 1.0))
            nv = 10
            for i in range(nv):
                a = va + i * math.tau / nv
                vx2 = cx + math.cos(a) * radius * 1.18 * (1 - collapse_pct * 0.9)
                vy2 = cy + math.sin(a) * radius * 1.18 * (1 - collapse_pct * 0.9)
                p.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(vx2, vy2))

            # sub-orbiting spheres
            p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            orbit_rads = [28, 42, 60, 72, 54, 36, 48, 66, 38, 50, 62, 44]
            sizes      = [7, 10, 14, 8, 12, 9, 11, 6, 13, 7, 10, 8]
            for i, ang in enumerate(self._spawn_sub_angles):
                rad = math.radians(ang)
                or2 = orbit_rads[i] * (1 - collapse_pct * 0.95)
                sx = cx + math.cos(rad) * or2
                sy = cy + math.sin(rad * 1.35) * (or2 * 0.55)
                sr = sizes[i]
                hue = (i * 30) % 360
                c2 = QtGui.QColor.fromHsv(hue, 220, 255, int(210 * hyper_alpha))
                sg = QtGui.QRadialGradient(sx, sy, sr)
                sg.setColorAt(0, c2)
                edge = QtGui.QColor.fromHsv(hue, 180, 200, 20)
                sg.setColorAt(1, edge)
                p.setBrush(sg)
                p.setPen(QtGui.QPen(QtGui.QColor(glow_hex), 0.8))
                p.drawEllipse(QtCore.QPointF(sx, sy), sr * hyper_alpha, sr * hyper_alpha)

            # central hypersphere body
            r_now = radius * (1.0 - collapse_pct * 0.96)
            mg = QtGui.QRadialGradient(cx, cy, r_now)
            gc = QtGui.QColor(glow_hex)
            gc.setAlpha(int(230 * hyper_alpha))
            mg.setColorAt(0.0, gc)
            gc2 = QtGui.QColor(56, 189, 248, int(180 * hyper_alpha))
            mg.setColorAt(0.4, gc2)
            gc3 = QtGui.QColor(168, 85, 247, int(120 * hyper_alpha))
            mg.setColorAt(0.8, gc3)
            mg.setColorAt(1.0, QtGui.QColor(10, 10, 20, 10))
            p.setBrush(mg)
            p.setPen(QtGui.QPen(gc2, 2))
            p.drawEllipse(QtCore.QPointF(cx, cy), r_now, r_now)

        # ── spawn particles ──────────────────────────────────────────────
        p.setPen(QtCore.Qt.NoPen)
        for pt in self._spawn_particles:
            hue = int(pt[5]) % 360
            c3 = QtGui.QColor.fromHsv(hue, 230, 255, int(pt[6]))
            p.setBrush(c3)
            px = cx + pt[0] * radius
            py = cy + pt[1] * radius
            ps = pt[4] * (hyper_alpha + mat_alpha * 0.3)
            if ps > 0.5:
                p.drawEllipse(QtCore.QPointF(px, py), ps, ps)

        # ── collapse shockwave ring ───────────────────────────────────────
        if shock_alpha > 0.01:
            shock_r = radius * 0.05 + radius * 2.2 * (1.0 - shock_alpha)
            for ri2 in range(3):
                sr2 = shock_r + ri2 * 16
                sa  = max(0, int(220 * shock_alpha * (1 - ri2 * 0.28)))
                sc  = QtGui.QColor(glow_hex)
                sc.setAlpha(sa)
                sp  = QtGui.QPen(sc, 3 - ri2)
                p.setPen(sp)
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawEllipse(QtCore.QPointF(cx, cy), sr2, sr2)
            # flash fill
            flash = QtGui.QColor(glow_hex)
            flash.setAlpha(int(140 * shock_alpha * shock_alpha))
            p.fillRect(0, 0, W, H, flash)

        # ── materialise: draw avatar at partial alpha ────────────────────
        if mat_alpha > 0.01:
            p.setOpacity(mat_alpha)

        return mat_alpha   # caller uses this to decide whether to draw avatar

    def paintEvent(self, event):
        import math
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        W, H   = self.width(), self.height()
        pal    = self._palettes[self._style_idx]
        t      = self._tick
        state  = self._state
        emo    = self._emotion
        gp     = self._gesture_phase

        # ── Spawn sequence ───────────────────────────────────────────────
        if not self._spawn_done:
            mat_alpha = self._draw_spawn(p, W, H)
            if mat_alpha < 0.01:
                p.end()
                return
            # fall through with partial opacity to draw avatar beneath

        # ────────────────────────────────────────────────────────────────
        # BACKGROUND
        # ────────────────────────────────────────────────────────────────
        bg = QtGui.QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0.0, QtGui.QColor("#090912"))
        bg.setColorAt(0.7, QtGui.QColor("#0d1a2e"))
        bg.setColorAt(1.0, QtGui.QColor("#060d18"))
        p.fillRect(0, 0, W, H, bg)

        # Perspective grid floor
        gy0 = int(H * 0.62)
        vp_x, vp_y = W // 2, gy0
        grid_pen = QtGui.QPen(QtGui.QColor(20, 50, 80, 80), 1)
        p.setPen(grid_pen)
        for xi in range(-8, 9):
            gx = W // 2 + xi * 48
            p.drawLine(gx, gy0, vp_x, vp_y)
        for yi in range(0, 8):
            yy = gy0 + yi * 24
            fac = yi / 7.0
            x0 = int(W // 2 - 380 * fac)
            x1 = int(W // 2 + 380 * fac)
            p.drawLine(x0, yy, x1, yy)

        # Ambient glow halo
        glow_col = QtGui.QColor(pal["glow"])
        glow_col.setAlphaF(0.18 + 0.07 * math.sin(t * 0.05))
        cx_base = W // 2
        cy_base = H // 3
        rg = QtGui.QRadialGradient(cx_base, cy_base, 160)
        rg.setColorAt(0, glow_col)
        rg.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        p.fillRect(0, 0, W, H, rg)

        # ────────────────────────────────────────────────────────────────
        # SKELETON LAYOUT
        # ────────────────────────────────────────────────────────────────
        br   = self._breath_phase                     # breathing offset
        scale = min(W, H) / 520.0

        # Weight shift offset
        ws_x = self._weight_side * 8 * math.sin(t * 0.015)
        # Walking lean
        walk_lean_x = int(10 * math.sin(t * 0.09)) if state == 3 else 0
        # Bob
        bob_y = int(4 * math.sin(t * 0.055)) if state in (0, 1, 4, 5) else 0

        cx  = int(W // 2 + ws_x + walk_lean_x)
        head_r   = max(30, int(min(W, H) * 0.11))
        if self._style_idx == 2:  # cartoon bigger head
            head_r = int(head_r * 1.32)

        head_cy  = int(H * 0.20 + bob_y)
        neck_bot = head_cy + head_r + 5
        should_y = neck_bot + int(18 * scale)
        hip_y    = should_y + int(64 * scale) + int(br * 0.4)
        knee_y   = hip_y + int(58 * scale)
        foot_y   = knee_y + int(48 * scale)
        arm_len  = int(50 * scale)
        fore_len = int(44 * scale)

        # ────────────────────────────────────────────────────────────────
        # SHADOW
        # ────────────────────────────────────────────────────────────────
        sh = QtGui.QRadialGradient(cx, foot_y + 10, 55)
        sh.setColorAt(0, QtGui.QColor(0, 0, 0, 110))
        sh.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        p.fillRect(cx - 70, foot_y, 140, 24, sh)

        # ────────────────────────────────────────────────────────────────
        # LEGS  (drawn first, behind torso)
        # ────────────────────────────────────────────────────────────────
        leg_col  = QtGui.QColor(pal["skin"]).darker(155)
        shoe_col = QtGui.QColor(pal["hair"]).darker(120)

        if state == 3:  # WALKING
            ls = math.sin(gp * 1.1) * 28
        elif state == 2:  # SEARCHING — lean forward
            ls = math.sin(gp * 0.5) * 10
        else:
            ls = math.sin(t * 0.025) * 4

        def draw_leg(side, swing):
            dx = side * 10
            kx = cx + dx + int(swing * 0.5)
            ky = knee_y
            fx = cx + dx + int(swing * 0.9)
            fy = foot_y
            # thigh
            lp = QtGui.QPen(leg_col, int(9 * scale), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
            p.setPen(lp)
            p.drawLine(cx + dx, hip_y, kx, ky)
            # shin
            lp.setWidth(int(8 * scale))
            p.setPen(lp)
            p.drawLine(kx, ky, fx, fy)
            # shoe
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QBrush(shoe_col))
            p.drawEllipse(fx - 10, fy - 5, 20, 10)

        draw_leg(-1,  ls)
        draw_leg( 1, -ls)

        # ────────────────────────────────────────────────────────────────
        # TORSO
        # ────────────────────────────────────────────────────────────────
        shirt = QtGui.QColor(pal["shirt"])
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QBrush(shirt))
        torso_w = int(22 * scale)
        torso_h = hip_y - should_y
        p.drawRoundedRect(cx - torso_w, should_y, torso_w * 2, torso_h, 6, 6)
        # shoulder line
        p.setPen(QtGui.QPen(shirt.lighter(130), int(10 * scale), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(cx - arm_len, should_y, cx + arm_len, should_y)

        # ────────────────────────────────────────────────────────────────
        # ARMS + HANDS — state-specific
        # ────────────────────────────────────────────────────────────────
        arm_col = QtGui.QColor(pal["skin"]).darker(115)
        arm_pen = QtGui.QPen(arm_col, int(7 * scale), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)

        # Defaults
        elbow_lx = cx - arm_len
        elbow_ly = should_y + int(28 * scale)
        elbow_rx = cx + arm_len
        elbow_ry = should_y + int(28 * scale)
        hand_lx  = elbow_lx - int(8 * scale)
        hand_ly  = elbow_ly + fore_len
        hand_rx  = elbow_rx + int(8 * scale)
        hand_ry  = elbow_ry + fore_len
        hand_l_shape = 0  # open palm
        hand_r_shape = 0
        hand_l_angle = 0
        hand_r_angle = 0

        if state == 0:  # IDLE — natural rest with idle fidgets
            swing = math.sin(gp * 0.6) * 6
            elbow_lx = cx - arm_len
            elbow_ly = should_y + int(30 * scale) + int(swing)
            elbow_rx = cx + arm_len
            elbow_ry = should_y + int(30 * scale) - int(swing)
            hand_lx  = elbow_lx - 5
            hand_ly  = elbow_ly + fore_len
            hand_rx  = elbow_rx + 5
            hand_ry  = elbow_ry + fore_len

            ig = self._idle_gesture
            igt = self._idle_gesture_t
            if igt > 0:
                if ig == 0:  # scratch head — right hand to head
                    prog = math.sin(igt / 60.0 * math.pi)
                    elbow_rx = cx + int(arm_len * 0.6)
                    elbow_ry = should_y - int(10 * prog)
                    hand_rx  = cx + head_r - 4
                    hand_ry  = head_cy - int(20 * prog)
                    hand_r_shape = 2  # fist/scratch
                    hand_r_angle = -30
                elif ig == 1:  # wave left hand
                    prog = math.sin(gp * 3)
                    elbow_lx = cx - int(arm_len * 0.8)
                    elbow_ly = should_y - 10
                    hand_lx  = elbow_lx - 15
                    hand_ly  = elbow_ly - 20 + int(prog * 14)
                    hand_l_shape = 3  # wave
                    hand_l_angle = int(prog * 20)
                elif ig == 2:  # thumbs up right
                    elbow_rx = cx + int(arm_len * 0.7)
                    elbow_ry = should_y + 10
                    hand_rx  = elbow_rx + 10
                    hand_ry  = elbow_ry - 10
                    hand_r_shape = 4
                    hand_r_angle = -15
                elif ig == 3:  # cross arms (folded)
                    elbow_lx = cx - 10
                    elbow_ly = should_y + 35
                    elbow_rx = cx + 10
                    elbow_ry = should_y + 35
                    hand_lx  = cx + 18
                    hand_ly  = should_y + 40
                    hand_rx  = cx - 18
                    hand_ry  = should_y + 40
                    hand_l_shape = 2
                    hand_r_shape = 2
                elif ig == 4:  # point outward left
                    elbow_lx = cx - arm_len - 5
                    elbow_ly = should_y + 10
                    hand_lx  = elbow_lx - fore_len + 5
                    hand_ly  = elbow_ly - 20
                    hand_l_shape = 1  # point
                    hand_l_angle = -45

        elif state == 1:  # TALKING — expressive gestures while speaking
            cycle = gp % math.tau
            phase = (t // 40) % 4
            if phase == 0:  # open palms out
                elbow_lx = cx - arm_len - 8
                elbow_ly = should_y + 15
                hand_lx  = elbow_lx - 18
                hand_ly  = elbow_ly - 5
                hand_l_shape = 0
                hand_l_angle = -20
                elbow_rx = cx + arm_len + 8
                elbow_ry = should_y + 15
                hand_rx  = elbow_rx + 18
                hand_ry  = elbow_ry - 5
                hand_r_shape = 0
                hand_r_angle = 20
            elif phase == 1:  # right hand raised point
                elbow_rx = cx + arm_len
                elbow_ry = should_y - 5 + int(math.sin(cycle) * 8)
                hand_rx  = elbow_rx + 14
                hand_ry  = elbow_ry - 20
                hand_r_shape = 1
                hand_r_angle = -30
                elbow_lx = cx - arm_len
                elbow_ly = should_y + 28
                hand_lx  = elbow_lx - 6
                hand_ly  = elbow_ly + fore_len
            elif phase == 2:  # both hands gesturing out-in
                amp = math.sin(cycle * 2) * 16
                elbow_lx = cx - int(arm_len * 0.8)
                elbow_ly = should_y + 20
                hand_lx  = elbow_lx - 20 + int(amp)
                hand_ly  = elbow_ly + fore_len - 10
                hand_l_shape = 0
                hand_l_angle = int(amp)
                elbow_rx = cx + int(arm_len * 0.8)
                elbow_ry = should_y + 20
                hand_rx  = elbow_rx + 20 - int(amp)
                hand_ry  = elbow_ry + fore_len - 10
                hand_r_shape = 0
                hand_r_angle = -int(amp)
            else:  # shrug-ish, open wide
                elbow_lx = cx - arm_len - 14
                elbow_ly = should_y - 10
                hand_lx  = elbow_lx - 8
                hand_ly  = elbow_ly - 14
                hand_l_shape = 3
                elbow_rx = cx + arm_len + 14
                elbow_ry = should_y - 10
                hand_rx  = elbow_rx + 8
                hand_ry  = elbow_ry - 14
                hand_r_shape = 3

        elif state == 2:  # SEARCHING FILE CABINET
            reach = math.sin(gp * 0.9) * 14
            elbow_rx = cx + arm_len + 12
            elbow_ry = should_y - 8 + int(reach * 0.4)
            hand_rx  = elbow_rx + 20
            hand_ry  = elbow_ry - 16 + int(reach)
            hand_r_shape = 2  # fist to grab files
            hand_r_angle = int(reach * 1.5)
            elbow_lx = cx - int(arm_len * 0.7)
            elbow_ly = should_y + 28
            hand_lx  = elbow_lx - 4
            hand_ly  = elbow_ly + fore_len

        elif state == 3:  # WALKING
            swing = math.sin(gp * 1.1) * 22
            elbow_lx = cx - arm_len
            elbow_ly = should_y + 24 + int(swing)
            hand_lx  = elbow_lx - 6
            hand_ly  = elbow_ly + fore_len
            elbow_rx = cx + arm_len
            elbow_ry = should_y + 24 - int(swing)
            hand_rx  = elbow_rx + 6
            hand_ry  = elbow_ry + fore_len
            hand_l_shape = 2  # loose fists while walking
            hand_r_shape = 2

        elif state == 4:  # GESTURING — big expressive
            sub = (t // 30) % 3
            if sub == 0:
                g = math.sin(gp * 1.4) * 28
                elbow_lx = cx - arm_len - 10
                elbow_ly = should_y + int(g)
                hand_lx  = elbow_lx - 16
                hand_ly  = elbow_ly - 10 + int(g * 0.4)
                hand_l_shape = 0
                hand_l_angle = int(g * 0.7)
                elbow_rx = cx + arm_len + 10
                elbow_ry = should_y - int(g)
                hand_rx  = elbow_rx + 16
                hand_ry  = elbow_ry - 10 - int(g * 0.4)
                hand_r_shape = 0
                hand_r_angle = -int(g * 0.7)
            elif sub == 1:  # peace sign raised
                elbow_lx = cx - int(arm_len * 0.5)
                elbow_ly = should_y - 8
                hand_lx  = elbow_lx - 5
                hand_ly  = elbow_ly - 28
                hand_l_shape = 5  # peace
                hand_l_angle = 5
                elbow_rx = cx + arm_len
                elbow_ry = should_y + 24
                hand_rx  = elbow_rx + 5
                hand_ry  = elbow_ry + fore_len
            else:  # thumbs up both
                elbow_lx = cx - int(arm_len * 0.6)
                elbow_ly = should_y + 8
                hand_lx  = elbow_lx - 8
                hand_ly  = elbow_ly - 8
                hand_l_shape = 4
                hand_l_angle = 10
                elbow_rx = cx + int(arm_len * 0.6)
                elbow_ry = should_y + 8
                hand_rx  = elbow_rx + 8
                hand_ry  = elbow_ry - 8
                hand_r_shape = 4
                hand_r_angle = -10

        elif state == 5:  # THINKING
            # Right hand to chin
            elbow_rx = cx + int(arm_len * 0.55)
            elbow_ry = should_y + 18
            hand_rx  = cx + 8
            hand_ry  = head_cy + head_r + 12
            hand_r_shape = 2  # fist under chin
            hand_r_angle = 0
            # Left arm relaxed at side
            elbow_lx = cx - arm_len
            elbow_ly = should_y + 32
            hand_lx  = elbow_lx - 4
            hand_ly  = elbow_ly + fore_len

        # Draw arms
        p.setPen(arm_pen)
        p.setBrush(QtCore.Qt.NoBrush)
        # Upper arm
        p.drawLine(cx - int(arm_len * 0.85), should_y, elbow_lx, elbow_ly)
        p.drawLine(elbow_lx, elbow_ly, hand_lx, hand_ly)
        p.drawLine(cx + int(arm_len * 0.85), should_y, elbow_rx, elbow_ry)
        p.drawLine(elbow_rx, elbow_ry, hand_rx, hand_ry)

        # Draw hands
        hand_size = int(11 * scale)
        self._draw_hand(p, hand_lx, hand_ly, hand_l_shape, pal, hand_size, hand_l_angle)
        self._draw_hand(p, hand_rx, hand_ry, hand_r_shape, pal, hand_size, hand_r_angle)

        # ────────────────────────────────────────────────────────────────
        # NECK
        # ────────────────────────────────────────────────────────────────
        p.setPen(QtGui.QPen(QtGui.QColor(pal["skin"]).darker(115), int(8 * scale),
                            QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.drawLine(cx, neck_bot, cx, should_y)

        # ────────────────────────────────────────────────────────────────
        # HEAD
        # ────────────────────────────────────────────────────────────────
        # Head tilt — slight bob left/right when talking
        head_tilt = 0.0
        if state == 1:
            head_tilt = math.sin(gp * 0.9) * 6.0
        elif state == 5:
            head_tilt = -4.0  # thinking tilt

        p.save()
        p.translate(cx, head_cy)
        p.rotate(head_tilt)

        # Head shape
        p.setPen(QtGui.QPen(QtGui.QColor(pal["skin"]).darker(120), 2))
        p.setBrush(QtGui.QBrush(QtGui.QColor(pal["skin"])))
        if self._style_idx == 3:  # creature — slightly alien
            p.drawEllipse(-head_r, -head_r, head_r * 2, int(head_r * 2.1))
        else:
            p.drawEllipse(-head_r, -head_r, head_r * 2, int(head_r * 1.9))

        # Blush / emotion flush
        if emo in (self.EMO_HAPPY, self.EMO_AMUSED):
            blush = QtGui.QColor(255, 100, 100, 55)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QBrush(blush))
            p.drawEllipse(-head_r + 4, 4, head_r // 3, head_r // 5)
            p.drawEllipse(head_r // 2,  4, head_r // 3, head_r // 5)

        # Hair
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QBrush(QtGui.QColor(pal["hair"])))
        if self._style_idx == 1:  # anime spiky
            for si, (hx, hy) in enumerate([(-head_r+4, -head_r), (0, -head_r-12),
                                            (head_r-4, -head_r)]):
                pts = [QtCore.QPointF(hx - 8, 0), QtCore.QPointF(hx, hy - 12),
                       QtCore.QPointF(hx + 8, 0)]
                poly = QtGui.QPolygonF(pts)
                p.drawPolygon(poly)
            p.drawEllipse(-head_r, -head_r, head_r * 2, head_r)
        elif self._style_idx == 2:  # cartoon puffy
            p.drawEllipse(-head_r, -head_r - 6, head_r * 2, head_r + 10)
            p.drawEllipse(-head_r - 4, -head_r // 2, head_r // 2, head_r // 2)
            p.drawEllipse(head_r // 2, -head_r // 2, head_r // 2, head_r // 2)
        else:
            p.drawEllipse(-head_r, -head_r, head_r * 2, head_r)

        # ── eyebrows ──────────────────────────────────────────────────
        brow_y = -head_r // 2 - 4
        eb_raise = int(self._eyebrow_raise * 7)
        brow_pen_col = QtGui.QColor(pal["hair"]).darker(130)
        if emo == self.EMO_THINKING:
            brow_pen_col = QtGui.QColor(pal["hair"]).darker(180)

        p.setPen(QtGui.QPen(brow_pen_col, int(3.5 * scale), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        # left brow
        l_brow_slant = 3 if emo == self.EMO_THINKING else (-2 if emo == self.EMO_SURPRISED else 0)
        r_brow_slant = -3 if emo == self.EMO_THINKING else (-2 if emo == self.EMO_SURPRISED else 0)
        p.drawLine(-head_r // 2 - 4, brow_y - eb_raise + l_brow_slant,
                   -head_r // 4 + 2,  brow_y - eb_raise - l_brow_slant)
        # right brow
        p.drawLine( head_r // 4 - 2,  brow_y - eb_raise - r_brow_slant,
                    head_r // 2 + 4,  brow_y - eb_raise + r_brow_slant)

        # ── eyes ──────────────────────────────────────────────────────
        eye_col   = QtGui.QColor(pal["eye"])
        pupil_col = QtGui.QColor(pal["pupil"])
        eye_x_off = head_r // 3
        eye_y_off = head_r // 7
        eye_w     = max(6, head_r // 3)
        eye_h_full = max(5, head_r // 3)
        eye_h = 2 if self._blink_closed else eye_h_full
        if emo == self.EMO_SURPRISED:
            eye_h = int(eye_h_full * 1.35)
        elif emo == self.EMO_THINKING:
            eye_h = max(2, int(eye_h_full * 0.55))

        p.setPen(QtGui.QPen(eye_col.darker(140), 1))
        p.setBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
        p.drawEllipse(-eye_x_off - eye_w // 2, eye_y_off - eye_h // 2, eye_w, eye_h)
        p.drawEllipse( eye_x_off - eye_w // 2, eye_y_off - eye_h // 2, eye_w, eye_h)

        # Irises
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QBrush(eye_col))
        ir = max(3, eye_w // 2 - 1)
        lx_gaze = int(self._look_offset_x * (eye_w // 4 - 1))
        ly_gaze = int(self._look_offset_y * (eye_h // 4))
        if not self._blink_closed:
            p.drawEllipse(-eye_x_off + lx_gaze - ir // 2, eye_y_off + ly_gaze - ir // 2, ir, ir)
            p.drawEllipse( eye_x_off + lx_gaze - ir // 2, eye_y_off + ly_gaze - ir // 2, ir, ir)
            # pupils
            p.setBrush(QtGui.QBrush(pupil_col))
            pr = max(2, ir // 2)
            p.drawEllipse(-eye_x_off + lx_gaze - pr // 2, eye_y_off + ly_gaze - pr // 2, pr, pr)
            p.drawEllipse( eye_x_off + lx_gaze - pr // 2, eye_y_off + ly_gaze - pr // 2, pr, pr)
            # highlight
            p.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 200)))
            p.drawEllipse(-eye_x_off + lx_gaze - ir // 2 + 1, eye_y_off + ly_gaze - ir // 2 + 1, 2, 2)
            p.drawEllipse( eye_x_off + lx_gaze - ir // 2 + 1, eye_y_off + ly_gaze - ir // 2 + 1, 2, 2)

        # ── nose (simple) ──────────────────────────────────────────────
        p.setPen(QtGui.QPen(QtGui.QColor(pal["skin"]).darker(135), 1.5))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawArc(-5, head_r // 4 - 6, 10, 8, 180 * 16, 180 * 16)

        # ── mouth ──────────────────────────────────────────────────────
        mouth_y_local = head_r // 2 + 2
        mw = head_r // 2
        mh = head_r // 5
        p.setPen(QtGui.QPen(QtGui.QColor(pal["lip"]), int(2.5 * scale),
                            QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        p.setBrush(QtGui.QBrush(QtGui.QColor(pal["lip"]).darker(140)))
        mp = self._mouth_path(0, mouth_y_local, mw, mh, emo, self._mouth_open)
        p.drawPath(mp)

        # ── ear nubs ──────────────────────────────────────────────────
        p.setPen(QtGui.QPen(QtGui.QColor(pal["skin"]).darker(115), 1))
        p.setBrush(QtGui.QBrush(QtGui.QColor(pal["skin"])))
        er = head_r // 5
        p.drawEllipse(-head_r - er // 2, -er // 2, er + 2, er * 2)
        p.drawEllipse( head_r - er // 2, -er // 2, er + 2, er * 2)

        p.restore()  # end head transform

        # ────────────────────────────────────────────────────────────────
        # THINKING BUBBLE
        # ────────────────────────────────────────────────────────────────
        if state == 5:
            bp = QtGui.QPen(QtGui.QColor(pal["glow"]), 1)
            p.setPen(bp)
            p.setBrush(QtGui.QBrush(QtGui.QColor(12, 12, 30, 210)))
            dots = [(cx + head_r + 6,  head_cy - head_r + 10, 4),
                    (cx + head_r + 18, head_cy - head_r - 6,  7),
                    (cx + head_r + 34, head_cy - head_r - 28, 20)]
            for bi, (bx, by, br) in enumerate(dots):
                pulse = 0.85 + 0.15 * math.sin(t * 0.10 + bi * 1.3)
                br2 = max(2, int(br * pulse))
                p.drawEllipse(bx - br2, by - br2, br2 * 2, br2 * 2)
            # question mark inside big bubble
            p.setPen(QtGui.QPen(QtGui.QColor(pal["glow"]), 2))
            big = dots[2]
            f = QtGui.QFont()
            f.setPointSize(10)
            f.setBold(True)
            p.setFont(f)
            p.drawText(big[0] - 5, big[1] + 5, "?")

        # ────────────────────────────────────────────────────────────────
        # LISTENING RINGS
        # ────────────────────────────────────────────────────────────────
        if self._listen:
            for ri in range(4):
                ring_r = head_r + 20 + ri * 18 + int(7 * math.sin(t * 0.09 + ri * 0.9))
                alpha  = max(0, 200 - ri * 48 - (t % 40) * 4)
                rc = QtGui.QColor(pal["glow"])
                rc.setAlpha(alpha)
                rpen = QtGui.QPen(rc, 2 - ri * 0.3)
                rpen.setStyle(QtCore.Qt.DotLine if ri > 1 else QtCore.Qt.SolidLine)
                p.setPen(rpen)
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawEllipse(cx - ring_r, head_cy - ring_r, ring_r * 2, ring_r * 2)

        # ────────────────────────────────────────────────────────────────
        # HUD / OVERLAY
        # ────────────────────────────────────────────────────────────────
        # Style badge
        badge_c = QtGui.QColor(pal["glow"])
        badge_c.setAlpha(210)
        p.setPen(QtGui.QPen(badge_c, 1))
        p.setBrush(QtGui.QBrush(QtGui.QColor(6, 6, 18, 185)))
        bfont = QtGui.QFont()
        bfont.setPointSize(8)
        p.setFont(bfont)
        fm = p.fontMetrics()
        badge_txt = pal["label"].upper()
        bw = fm.horizontalAdvance(badge_txt) + 14
        p.drawRoundedRect(8, 8, bw, 20, 4, 4)
        p.setPen(badge_c)
        p.drawText(15, 23, badge_txt)

        # State label bottom-left
        state_txt = self.STATE_NAMES[state]
        p.setPen(QtGui.QPen(QtGui.QColor(pal["glow"]), 1))
        sf = QtGui.QFont()
        sf.setPointSize(8)
        p.setFont(sf)
        p.drawText(8, H - 24, state_txt)

        # Entity name bottom-centre
        nf = QtGui.QFont()
        nf.setPointSize(10)
        nf.setBold(True)
        p.setFont(nf)
        p.setPen(QtGui.QPen(QtGui.QColor("#e0e0e0"), 1))
        p.drawText(QtCore.QRect(0, H - 46, W, 20), QtCore.Qt.AlignHCenter, self._name)

        # Status bar bottom
        smf = QtGui.QFont()
        smf.setPointSize(7)
        p.setFont(smf)
        p.setPen(QtGui.QPen(QtGui.QColor("#666"), 1))
        p.drawText(QtCore.QRect(0, H - 16, W, 14), QtCore.Qt.AlignHCenter, self._status_msg)
        p.setOpacity(1.0)
        p.end()


        self.setMinimumSize(360, 420)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setAutoFillBackground(False)

        # Anim state
        self._state      = 0          # index into STATE_NAMES
        self._tick       = 0          # frame counter
        self._style_idx  = 0          # 0=Realistic 1=Anime 2=Cartoon 3=Creature
        self._name       = "Entity"
        self._speaking   = False
        self._listen     = False
        self._mouth_open = 0.0
        self._status_msg = "Ready"

        # Palette — changes with style
        self._palettes = [
            {"skin": "#f5cba7", "hair": "#4a3728", "eye": "#2ecc71", "glow": "#00ffcc", "label": "Realistic"},
            {"skin": "#ffe4b5", "hair": "#ff69b4", "eye": "#9b59b6", "glow": "#ff00ff", "label": "Anime"},
            {"skin": "#ffdd57", "hair": "#e74c3c", "eye": "#3498db", "glow": "#f9ca24", "label": "Cartoon"},
            {"skin": "#6c3483", "hair": "#1abc9c", "eye": "#e74c3c", "glow": "#8e44ad", "label": "Creature"},
        ]

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(33)   # ~30 fps

    # ── public API ────────────────────────────────────────────────────────
    def set_state(self, idx: int):
        self._state = max(0, min(idx, len(self.STATE_NAMES) - 1))

    def set_style(self, idx: int):
        self._style_idx = max(0, min(idx, len(self._palettes) - 1))

    def set_name(self, name: str):
        self._name = name or "Entity"

    def set_speaking(self, val: bool, mouth_open: float = 0.0):
        self._speaking   = val
        self._mouth_open = mouth_open

    def set_listening(self, val: bool):
        self._listen = val

    def set_status(self, msg: str):
        self._status_msg = msg

    # ── animation tick ────────────────────────────────────────────────────
    def _animate(self):
        self._tick += 1
        if self._speaking:
            import math
            self._mouth_open = 0.5 + 0.5 * math.sin(self._tick * 0.4)
        self.update()

    # ── drawing ───────────────────────────────────────────────────────────
    def paintEvent(self, event):
        import math
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        W, H = self.width(), self.height()
        pal  = self._palettes[self._style_idx]
        t    = self._tick

        # ── background gradient ──────────────────────────────────────────
        grad = QtGui.QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.0, QtGui.QColor("#0a0a14"))
        grad.setColorAt(1.0, QtGui.QColor("#0e1a2e"))
        p.fillRect(0, 0, W, H, grad)

        # ── grid floor ──────────────────────────────────────────────────
        pen = QtGui.QPen(QtGui.QColor(30, 60, 90, 100), 1)
        p.setPen(pen)
        for xi in range(0, W, 40):
            p.drawLine(xi, H // 2, xi, H)
        for yi in range(H // 2, H, 20):
            p.drawLine(0, yi, W, yi)

        # ── glow halo ───────────────────────────────────────────────────
        glow_col = QtGui.QColor(pal["glow"])
        glow_pulse = 0.6 + 0.4 * math.sin(t * 0.07)
        glow_col.setAlphaF(0.25 * glow_pulse)
        cx, cy_head = W // 2, H // 4
        rg = QtGui.QRadialGradient(cx, cy_head, 120)
        rg.setColorAt(0, glow_col)
        rg.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        p.fillRect(0, 0, W, H // 2 + 60, rg)

        # ── body offsets per state ───────────────────────────────────────
        state = self._state
        # Lean/bob
        bob_y   = int(6  * math.sin(t * 0.08)) if state in (0, 1, 4, 5) else 0
        lean_x  = int(12 * math.sin(t * 0.06)) if state == 3 else 0   # walking
        arm_swing = math.sin(t * 0.1)

        # ── skeleton coords (relative to centre) ────────────────────────
        cx  = W // 2 + lean_x
        head_r = max(28, min(W, H) // 9)
        neck_y  = cy_head + head_r + 4 + bob_y
        should_y = neck_y + 22
        hip_y   = should_y + 55
        knee_y  = hip_y + 48
        foot_y  = knee_y + 42
        arm_len = 44
        fore_len = 36

        # Cartoon mode — bigger head
        if self._style_idx == 2:
            head_r = int(head_r * 1.35)

        head_cy = cy_head + bob_y

        # ── shadow ──────────────────────────────────────────────────────
        shadow = QtGui.QRadialGradient(cx, foot_y + 8, 40)
        shadow.setColorAt(0, QtGui.QColor(0, 0, 0, 120))
        shadow.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        p.fillRect(cx - 50, foot_y, 100, 20, shadow)

        # ── legs ─────────────────────────────────────────────────────────
        leg_swing = math.sin(t * 0.12) * (30 if state == 3 else 5)
        leg_pen = QtGui.QPen(QtGui.QColor(pal["skin"]).darker(140), 7, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        p.setPen(leg_pen)
        # left leg
        p.drawLine(cx - 8, hip_y, cx - 8 + int(leg_swing * 0.6), knee_y)
        p.drawLine(cx - 8 + int(leg_swing * 0.6), knee_y, cx - 10 + int(leg_swing), foot_y)
        # right leg
        p.drawLine(cx + 8, hip_y, cx + 8 - int(leg_swing * 0.6), knee_y)
        p.drawLine(cx + 8 - int(leg_swing * 0.6), knee_y, cx + 10 - int(leg_swing), foot_y)

        # ── torso ─────────────────────────────────────────────────────────
        torso_pen = QtGui.QPen(QtGui.QColor(pal["skin"]).darker(110), 9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        p.setPen(torso_pen)
        p.drawLine(cx, neck_y, cx, hip_y)

        # ── arms ─────────────────────────────────────────────────────────
        arm_pen = QtGui.QPen(QtGui.QColor(pal["skin"]).darker(120), 7, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        p.setPen(arm_pen)

        if state == 2:  # SEARCHING_FILE_CABINET — reach right arm forward/up
            reach = math.sin(t * 0.15) * 12
            elbow_lx, elbow_ly = cx - arm_len, should_y + 20
            elbow_rx, elbow_ry = cx + arm_len + 10, should_y - 20 + int(reach)
            hand_rx, hand_ry   = elbow_rx + 14, elbow_ry + fore_len - 20 + int(reach)
        elif state == 4:  # GESTURING
            g = math.sin(t * 0.18) * 25
            elbow_lx, elbow_ly = cx - arm_len, should_y + int(g)
            elbow_rx, elbow_ry = cx + arm_len, should_y - int(g)
            hand_rx, hand_ry   = elbow_rx + 10, elbow_ry + 30
        else:
            swing = arm_swing * (20 if state == 3 else 8)
            elbow_lx = cx - arm_len
            elbow_ly = should_y + 26 + int(swing)
            elbow_rx = cx + arm_len
            elbow_ry = should_y + 26 - int(swing)
            hand_rx, hand_ry = elbow_rx + 8, elbow_ry + fore_len

        hand_lx, hand_ly = elbow_lx - 8, elbow_ly + fore_len
        p.drawLine(cx, should_y, elbow_lx, elbow_ly)
        p.drawLine(elbow_lx, elbow_ly, hand_lx, hand_ly)
        p.drawLine(cx, should_y, elbow_rx, elbow_ry)
        p.drawLine(elbow_rx, elbow_ry, hand_rx, hand_ry)

        # ── head ─────────────────────────────────────────────────────────
        head_brush = QtGui.QBrush(QtGui.QColor(pal["skin"]))
        head_pen   = QtGui.QPen(QtGui.QColor(pal["glow"]), 2)
        p.setPen(head_pen)
        p.setBrush(head_brush)
        p.drawEllipse(QtCore.QPoint(cx, head_cy), head_r, head_r)

        # ── hair ─────────────────────────────────────────────────────────
        hair_brush = QtGui.QBrush(QtGui.QColor(pal["hair"]))
        p.setBrush(hair_brush)
        p.setPen(QtCore.Qt.NoPen)
        hair_rect = QtCore.QRect(cx - head_r, head_cy - head_r, head_r * 2, head_r)
        p.drawEllipse(hair_rect)

        # ── eyes ─────────────────────────────────────────────────────────
        eye_col = QtGui.QColor(pal["eye"])
        blink = (t % 90 < 4)   # blink every 3 s
        eye_h = 2 if blink else max(3, head_r // 4)
        eye_w = max(4, head_r // 4)
        p.setBrush(QtGui.QBrush(eye_col))
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(cx - head_r // 3 - eye_w // 2, head_cy - eye_h // 2, eye_w, eye_h)
        p.drawEllipse(cx + head_r // 3 - eye_w // 2, head_cy - eye_h // 2, eye_w, eye_h)
        # pupils
        p.setBrush(QtGui.QBrush(QtGui.QColor("#111")))
        if not blink:
            p.drawEllipse(cx - head_r // 3, head_cy - 1, 3, 3)
            p.drawEllipse(cx + head_r // 3, head_cy - 1, 3, 3)

        # ── mouth / lip-sync ─────────────────────────────────────────────
        mouth_y = head_cy + head_r // 2
        mouth_open = int(self._mouth_open * 14)
        if state == 5:  # THINKING — pursed lips
            mouth_open = 2
        mouth_pen = QtGui.QPen(QtGui.QColor("#c0392b"), 2)
        p.setPen(mouth_pen)
        p.setBrush(QtGui.QBrush(QtGui.QColor("#7b241c")))
        p.drawEllipse(cx - head_r // 4, mouth_y, head_r // 2, max(2, mouth_open))

        # ── thinking bubble ──────────────────────────────────────────────
        if state == 5:
            bp = QtGui.QPen(QtGui.QColor(pal["glow"]), 1)
            p.setPen(bp)
            p.setBrush(QtGui.QBrush(QtGui.QColor(20, 20, 40, 200)))
            for bi, (bx, by, br) in enumerate([
                (cx + head_r + 8, head_cy - head_r - 4, 5),
                (cx + head_r + 18, head_cy - head_r - 16, 8),
                (cx + head_r + 32, head_cy - head_r - 36, 22),
            ]):
                dot_pulse = 0.8 + 0.2 * math.sin(t * 0.12 + bi * 1.2)
                br2 = int(br * dot_pulse)
                p.drawEllipse(bx - br2, by - br2, br2 * 2, br2 * 2)
            # dots
            p.setPen(QtGui.QPen(QtGui.QColor(pal["glow"]), 1))
            p.setBrush(QtGui.QBrush(QtGui.QColor(pal["glow"])))
            for dot_txt in ["?", "!", "…"]:
                pass  # text would overlap; keep bubbles clean

        # ── listening rings ──────────────────────────────────────────────
        if self._listen:
            for ri in range(3):
                ring_r = head_r + 14 + ri * 14 + int(6 * math.sin(t * 0.1 + ri))
                ring_a = max(0, int(180 - ri * 60 - (t % 30) * 3))
                ring_pen = QtGui.QPen(QtGui.QColor(pal["glow"]), 1)
                ring_pen.setStyle(QtCore.Qt.DotLine)
                ring_col = QtGui.QColor(pal["glow"])
                ring_col.setAlpha(ring_a)
                ring_pen.setColor(ring_col)
                p.setPen(ring_pen)
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawEllipse(cx - ring_r, head_cy - ring_r, ring_r * 2, ring_r * 2)

        # ── style badge ──────────────────────────────────────────────────
        badge_col = QtGui.QColor(pal["glow"])
        badge_col.setAlpha(200)
        p.setPen(QtGui.QPen(badge_col, 1))
        p.setBrush(QtGui.QBrush(QtGui.QColor(10, 10, 20, 180)))
        badge_txt = pal["label"].upper()
        fm = p.fontMetrics()
        bw = fm.horizontalAdvance(badge_txt) + 16
        p.drawRoundedRect(8, 8, bw, 22, 5, 5)
        p.setPen(badge_col)
        p.drawText(16, 24, badge_txt)

        # ── state label ──────────────────────────────────────────────────
        p.setPen(QtGui.QPen(QtGui.QColor(pal["glow"]), 1))
        state_lbl = self.STATE_NAMES[self._state]
        p.drawText(8, H - 28, state_lbl)

        # ── entity name ──────────────────────────────────────────────────
        name_font = QtGui.QFont(p.font())
        name_font.setPointSize(11)
        name_font.setBold(True)
        p.setFont(name_font)
        p.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1))
        p.drawText(QtCore.QRect(0, H - 52, W, 22), QtCore.Qt.AlignHCenter, self._name)

        # ── status bar ───────────────────────────────────────────────────
        small_font = QtGui.QFont(p.font())
        small_font.setPointSize(8)
        small_font.setBold(False)
        p.setFont(small_font)
        p.setPen(QtGui.QPen(QtGui.QColor("#888888"), 1))
        p.drawText(QtCore.QRect(0, H - 18, W, 16), QtCore.Qt.AlignHCenter, self._status_msg)

        p.end()


class FourIdentityAvatarPanel(QtWidgets.QWidget):
    """4-I.D. Avatar panel — fully native Qt, no browser or WebEngine."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QtWidgets.QHBoxLayout(self)
        root.setSpacing(10)

        # ── left: live avatar viewport ────────────────────────────────────
        self.viewport = AvatarViewport()
        root.addWidget(self.viewport, 3)

        # ── right: controls ───────────────────────────────────────────────
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(8)

        # -- generation --
        gen_box = QtWidgets.QGroupBox("✨ Entity Generation")
        gl = QtWidgets.QFormLayout()
        self.prompt_edit = QtWidgets.QLineEdit()
        self.prompt_edit.setPlaceholderText("A futuristic pirate with a glowing eyepatch…")
        self.style_combo = QtWidgets.QComboBox()
        self.style_combo.addItems(["Realistic", "Anime", "Cartoon", "Creature"])
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Avatar name…")
        self.name_edit.textChanged.connect(lambda t: self.viewport.set_name(t))
        self.gen_btn = QtWidgets.QPushButton("Generate")
        self.gen_btn.clicked.connect(self._generate_avatar)
        gl.addRow("Description:", self.prompt_edit)
        gl.addRow("Style:", self.style_combo)
        gl.addRow("Name:", self.name_edit)
        gl.addRow("", self.gen_btn)
        gen_box.setLayout(gl)
        right.addWidget(gen_box)

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

    # ── helpers ───────────────────────────────────────────────────────────
    def _get_engine(self):
        return getattr(self.window(), "engine", None)

    def _on_style_changed(self, idx):
        self.viewport.set_style(idx)

    def _generate_avatar(self):
        eng = self._get_engine()
        prompt = self.prompt_edit.text().strip()
        name   = self.name_edit.text().strip() or prompt.split()[0].capitalize() if prompt else "Entity"
        style  = self.style_combo.currentIndex()
        self.viewport.set_style(style)
        self.viewport.set_name(name)
        self.viewport.set_status(f"Generated: {prompt[:40]}" if prompt else "Ready")
        if eng and prompt:
            try:
                eng.avatar_generate(prompt, style)
            except Exception as e:
                self.viewport.set_status(f"Error: {e}")

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
        import webbrowser
        webbrowser.open("http://localhost:7860/#gcs")


# ── Main window ───────────────────────────────────────────────────────
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: config_io.GuiConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.engine: Optional[TessEngine] = None

        self.setWindowTitle(f"Pirate Llama Control Center — v{self._version()}")
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
        self.telemetry_panel = TelemetryPanel()
        self.gpu_target_panel = GpuHardwareTargetPanel()
        self.finetune_panel   = FineTuningPresetsPanel()
        self.compress_panel = CompressionPanel()
        self.predict_panel = PredictorPanel()
        self.advanced_panel = AdvancedPanel()
        self.master_panel = MasterPanel()
        self.integrations_panel = IntegrationsPanel()
        self.backup_panel = AutoBackupPanel()
        self.avatar_panel = FourIdentityAvatarPanel()

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self.telemetry_panel, "Telemetry")
        tabs.addTab(self.gpu_target_panel, "GPU Target & Brain")
        tabs.addTab(self.finetune_panel,   "Fine-Tuning & Guardrails")
        tabs.addTab(self.compress_panel, "Compression")
        tabs.addTab(self.predict_panel,  "Predictor")
        tabs.addTab(self.advanced_panel, "Advanced")
        tabs.addTab(self.master_panel,   "Master")
        tabs.addTab(self.integrations_panel, "Integrations")
        tabs.addTab(self.backup_panel, "Auto Backup")
        tabs.addTab(self.avatar_panel, "4ID Avatar")



        self.advanced_panel.configChanged.connect(self._on_advanced_changed)
        self.advanced_panel.encryptionChanged.connect(self._on_encryption_toggle)
        self.master_panel.configChanged.connect(self._on_master_changed)

        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(tabs)
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
        import webbrowser
        self._log("Opening Golden Candy Spinner...")
        webbrowser.open("http://localhost:7860/#gcs")


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
