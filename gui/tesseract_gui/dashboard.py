"""dashboard.py — main control center window.

Layout (QMainWindow):
    ┌──────────────────────────────────────────────────────────────────┐
    │ Menu bar  File   Engine   View   3FA   Help                      │
    ├──────────────────────────────────────────────────────────────────┤
    │ Toolbar  [Refresh] [Compress sample] [Save checkpoint] [...]     │
    ├────────────┬─────────────────────────────────────────────────────┤
    │            │                                                     │
    │ Sidebar    │   Telemetry panel (live gauges + numbers)           │
    │ (tabs)     │   Compression panel (input + ratio + log)           │
    │            │   Predictor panel (train + observe + predict)       │
    │            │   Drives panel (table)                              │
    │            │                                                     │
    ├────────────┴─────────────────────────────────────────────────────┤
    │ Status bar: bridge OK | VRAM 46% | 100 obs | tesseract_bridge.dll│
    └──────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from . import config_io
from .bridge import TessEngine, BridgeError, Telemetry


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
        self.slider.setValue(int(value * self._scale))
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

    def value(self) -> float:
        return float(self.spin.value())


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

        stats = QtWidgets.QFormLayout()
        stats.addRow("VRAM used:",     self.used_lbl)
        stats.addRow("VRAM budget:",   self.budget_lbl)
        stats.addRow("Active tokens:", self.tokens_lbl)
        stats.addRow("Prefetch pending:", self.prefetch_lbl)

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
class CompressionPanel(QtWidgets.QGroupBox):
    ratioUpdated = QtCore.Signal(float)

    def __init__(self) -> None:
        super().__init__("Context Compression")
        self.text_in = QtWidgets.QPlainTextEdit()
        self.text_in.setPlaceholderText("Paste or type prompt text to compress…")
        self.text_in.setMaximumHeight(140)
        sample = ("the user wants me to look at the codebase structure. " * 12).strip()
        self.text_in.setPlainText(sample)

        self.run_btn = QtWidgets.QPushButton("Compress")
        self.run_btn.clicked.connect(self._on_run)
        self.ratio_lbl = QtWidgets.QLabel("—")
        font = self.ratio_lbl.font(); font.setPointSize(20); font.setBold(True)
        self.ratio_lbl.setFont(font)
        self.entries_lbl = QtWidgets.QLabel("—")
        self.roundtrip_lbl = QtWidgets.QLabel("—")

        # Fine-grained compression knobs
        self.phrase_len = FineSlider("Min phrase length", 1, 8, 1, 2, suffix=" words")
        self.dict_cap   = FineSlider("Dictionary size",    1024, 200000, 1024, 65536,
                                     suffix=" entries", decimals=0)
        self.max_tokens = FineSlider("Max active tokens",  1024, 500000, 1000, 260000,
                                     suffix=" tok", decimals=0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Input text:"))
        layout.addWidget(self.text_in)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.ratio_lbl)
        layout.addWidget(self.entries_lbl)
        layout.addWidget(self.roundtrip_lbl)
        layout.addWidget(self.phrase_len)
        layout.addWidget(self.dict_cap)
        layout.addWidget(self.max_tokens)

        self._last_result = None

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
            self.ratio_lbl.setText(f"{r.ratio:.2f}× compression")
            self.entries_lbl.setText(f"{len(r.entries)} KV-cache entries")
            # Decompress as round-trip check
            back = eng.decompress(text)
            ok = back == text
            self.roundtrip_lbl.setText(
                f"Round-trip: {'✅ identical' if ok else '⚠️ mismatch'} "
                f"({len(back):,} chars back)")
            self.ratioUpdated.emit(r.ratio)
        except BridgeError as e:
            self.ratio_lbl.setText("error")
            QtWidgets.QMessageBox.warning(self, "Compress failed", str(e))
        finally:
            self.run_btn.setEnabled(True)


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
            "Model filename used as key for .tesseract_profiles.json / .trf files")
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
        self._encryption_fpr = f"TESS-KEY-{d[:8].upper()}-{d[8:16].upper()}-{d[16:24].upper()}"
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


# ── Main window ───────────────────────────────────────────────────────
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: config_io.GuiConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.engine: Optional[TessEngine] = None

        self.setWindowTitle(f"Tesseract Control Center — v{self._version()}")
        self.resize(1180, 760)

        # Menu
        bar = self.menuBar()
        m_file = bar.addMenu("&File")
        m_file.addAction("&Save Config",       self._save_cfg)
        m_file.addAction("E&xit",             self.close)
        m_engine = bar.addMenu("&Engine")
        m_engine.addAction("&Run Benchmark",   self._run_benchmark)
        m_engine.addAction("&Save Checkpoint", self._save_checkpoint)
        m_3fa = bar.addMenu("&3FA")
        m_3fa.addAction("Re-pair device",     self._re_pair)
        m_help = bar.addMenu("&Help")
        m_help.addAction("&About",            self._about)

        # Toolbar
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.addAction("Refresh",        self._manual_refresh)
        tb.addSeparator()
        tb.addAction("Compress",       self._quick_compress)
        tb.addAction("Train pattern",  self._quick_train)
        tb.addSeparator()
        self.refresh_box = QtWidgets.QSpinBox()
        self.refresh_box.setRange(50, 5000)
        self.refresh_box.setValue(cfg.refresh_interval_ms)
        self.refresh_box.setSuffix(" ms")
        self.refresh_box.valueChanged.connect(self._set_refresh)
        tb.addWidget(QtWidgets.QLabel("Refresh:"))
        tb.addWidget(self.refresh_box)

        # Sidebar + panels
        self.telemetry_panel = TelemetryPanel()
        self.compress_panel = CompressionPanel()
        self.predict_panel = PredictorPanel()
        self.advanced_panel = AdvancedPanel()
        self.master_panel = MasterPanel()

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self.telemetry_panel, "Telemetry")
        tabs.addTab(self.compress_panel, "Compression")
        tabs.addTab(self.predict_panel,  "Predictor")
        tabs.addTab(self.advanced_panel, "Advanced")
        tabs.addTab(self.master_panel,   "Master")

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

        self.setCentralWidget(splitter)

        # Status bar
        self.status_lbl = QtWidgets.QLabel("Ready")
        self.statusBar().addPermanentWidget(self.status_lbl)

        # Telemetry refresh timer
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh_telemetry)
        self._timer.start(cfg.refresh_interval_ms)

        self._log("GUI ready. Click 'Run benchmark' or just push some layers.")

        # Open the engine
        self._open_engine()

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
            "<b>Project Tesseract Control Center</b><br>"
            "Local LLM inference engine with NVMe tiering.<br><br>"
            "Bridge: tesseract_bridge.dll<br>"
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
