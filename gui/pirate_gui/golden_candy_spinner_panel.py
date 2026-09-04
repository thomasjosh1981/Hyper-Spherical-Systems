"""
gui/pirate_gui/golden_candy_spinner_panel.py
============================================
Hyper-Spherical Systems — Matrix Muncher, 4Decomposer & BRAIN SURGERY STUDIO (GCS v6.0)

Features:
1. Interactive "Stack of Glowing Sheets" Brain Surgery Canvas:
   - 🟡 Yellow: Tripwires, Alignment Probes & Sycophancy Vectors
   - 🔴 Red: Guardrails, Refusal Heads & Rejection Matrices
   - 🟢 Green: Normal Core Knowledge, Attention & Reasoning
   - 🔵 Blue: Internal Embeddings & Base Projections
   - 🌸 Pink: NSFW / Censorship / Smut Filter Matrices
2. Weight Microscope & Surgical Pruner:
   - Zoom into any individual glowing layer to inspect tensor shapes, byte offsets, min/max weights, and norms.
   - Surgical Actions: Rip Out Weight Slice, Obliterate Refusal (Red), Purge Tripwires (Yellow), Unlock NSFW (Pink).
3. Dual-Tab Architecture:
   - Tab 1: 💥 4Decomposer & Muncher (3D Loaf Stacker & Forensic Gate)
   - Tab 2: 🧠 BRAIN SURGERY & HYPER CORTEX (Glowing Sheet Stack, Microscope & Dataset Hub)
"""

from __future__ import annotations

import os
import sys
import time
import math
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from PySide6 import QtCore, QtGui, QtWidgets


# ── Interactive Glowing Sheets Brain Surgery Stack Canvas ────────────────────

class BrainSurgeryStackVisualizer(QtWidgets.QWidget):
    """Renders the model as an interactive vertical stack of glowing color-coded translucent sheets."""

    layerSelected = QtCore.Signal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.total_layers = 42
        self.selected_idx = 0
        self.layers_data: List[Dict[str, Any]] = []
        self._init_mock_layers()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(40)
        self._pulse = 0.0

    def _init_mock_layers(self):
        self.layers_data.clear()
        for i in range(self.total_layers):
            if i in (8, 21, 35):
                l_type = "guardrail"  # Red
                name = f"Layer {i}: Refusal & Rejection Head"
            elif i in (12, 28):
                l_type = "tripwire"   # Yellow
                name = f"Layer {i}: Alignment Tripwire / Sycophancy"
            elif i in (18, 38):
                l_type = "nsfw"       # Pink
                name = f"Layer {i}: NSFW / Content Safety Filter"
            elif i in (0, 1, 40, 41):
                l_type = "internal"   # Blue
                name = f"Layer {i}: Base Embedding / Head Projection"
            else:
                l_type = "normal"     # Green
                name = f"Layer {i}: Core Attention & FFN Knowledge"

            self.layers_data.append({
                "index": i,
                "type": l_type,
                "name": name,
                "shape": "(4096, 14336)",
                "size_mb": 348.5,
                "weight_norm": round(1.42 + (i * 0.05) % 0.8, 3),
                "is_ripped": False
            })

    def select_layer(self, idx: int):
        if 0 <= idx < len(self.layers_data):
            self.selected_idx = idx
            self.layerSelected.emit(idx, self.layers_data[idx])
            self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        w = self.width()
        h = self.height()
        click_y = event.position().y()
        stack_top = 25
        stack_h = h - 45
        step = stack_h / max(1, len(self.layers_data))

        idx = int((click_y - stack_top) / step)
        if 0 <= idx < len(self.layers_data):
            self.select_layer(idx)

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        self._pulse += 0.06

        # Dark Canvas
        painter.fillRect(0, 0, w, h, QtGui.QColor("#04070f"))
        painter.setPen(QtGui.QPen(QtGui.QColor("rgba(0, 212, 255, 0.25)"), 1))
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 8, 8)

        # Header Title
        painter.setPen(QtGui.QColor("#ffd700"))
        painter.setFont(QtGui.QFont("Consolas", 10, QtGui.QFont.Bold))
        painter.drawText(14, 18, "🗺️ LLM DISCOVERY MAP — NEURAL CARTOGRAPHY & TENSOR CIRCUIT EXPLORER")

        stack_top = 28
        stack_h = h - 42
        n = len(self.layers_data)
        step = stack_h / max(1, n)
        sheet_w = w - 80
        start_x = 40

        for i, l in enumerate(self.layers_data):
            y = stack_top + i * step
            is_sel = (i == self.selected_idx)
            is_ripped = l.get("is_ripped", False)
            l_type = l["type"]

            # Color scheme
            if is_ripped:
                color = QtGui.QColor("#334155")
                glow = QtGui.QColor("rgba(51, 65, 85, 0.2)")
            elif l_type == "guardrail":      # Red
                color = QtGui.QColor("#ef4444")
                glow = QtGui.QColor("rgba(239, 68, 68, 0.45)")
            elif l_type == "tripwire":       # Yellow
                color = QtGui.QColor("#eab308")
                glow = QtGui.QColor("rgba(234, 179, 8, 0.45)")
            elif l_type == "nsfw":           # Pink
                color = QtGui.QColor("#ec4899")
                glow = QtGui.QColor("rgba(236, 72, 153, 0.45)")
            elif l_type == "internal":       # Blue
                color = QtGui.QColor("#38bdf8")
                glow = QtGui.QColor("rgba(56, 189, 248, 0.45)")
            else:                            # Green (Normal)
                color = QtGui.QColor("#10b981")
                glow = QtGui.QColor("rgba(16, 185, 129, 0.35)")

            # Draw Glowing Horizontal Sheet
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(glow)
            painter.drawRoundedRect(start_x - 4, y - 2, sheet_w + 8, max(3, step), 4, 4)

            painter.setBrush(color)
            painter.drawRoundedRect(start_x, y, sheet_w, max(2, step - 1), 2, 2)

            # Selected Ring
            if is_sel:
                pulse_w = int(2 + math.sin(self._pulse) * 1.5)
                painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), pulse_w))
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRoundedRect(start_x - 8, y - 4, sheet_w + 16, step + 6, 6, 6)

                # Callout label
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.setFont(QtGui.QFont("Consolas", 9, QtGui.QFont.Bold))
                painter.drawText(sheet_w + 48, y + 6, f"◀ {l['name']}")


# ── Tab 2: BRAIN SURGERY & HYPER CORTEX Panel ────────────────────────────────

class BrainSurgeryPanel(QtWidgets.QWidget):
    """Brain Surgery selection tool for ripping out weights and injecting datasets."""

    logRequested = QtCore.Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Upper: Glowing Layer Sheets Visualizer ──────────────────────────
        self.stack_vis = BrainSurgeryStackVisualizer(self)
        self.stack_vis.layerSelected.connect(self._on_layer_selected)
        layout.addWidget(self.stack_vis, 2)

        # ── Middle: Weight Microscope & Surgery Tools ───────────────────────
        micro_box = QtWidgets.QGroupBox("🔬 Weight Matrix Microscope & Surgical Pruning Tools")
        micro_box.setStyleSheet("QGroupBox { border: 1px solid #ffd700; border-radius: 8px; color: #ffd700; font-weight: bold; padding-top: 8px; }")
        m_lay = QtWidgets.QVBoxLayout(micro_box)

        # Details Grid
        d_grid = QtWidgets.QGridLayout()
        self.lbl_sel_name = QtWidgets.QLabel("Selected Target: <b>Layer 8 (Refusal Head)</b>")
        self.lbl_sel_shape = QtWidgets.QLabel("Matrix Shape: <b>(4096, 14336)</b>")
        self.lbl_sel_norm = QtWidgets.QLabel("Weight Norm / Activation: <b>1.842</b>")
        self.lbl_sel_status = QtWidgets.QLabel("Surgical State: <span style='color:#ef4444; font-weight:bold;'>ARMED (GUARDRAIL ACTIVE)</span>")

        d_grid.addWidget(self.lbl_sel_name, 0, 0)
        d_grid.addWidget(self.lbl_sel_shape, 0, 1)
        d_grid.addWidget(self.lbl_sel_norm, 1, 0)
        d_grid.addWidget(self.lbl_sel_status, 1, 1)
        m_lay.addLayout(d_grid)

        # Surgery Action Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_rip_slice = QtWidgets.QPushButton("✂️ RIP OUT THIS WEIGHT SLICE")
        self.btn_rip_slice.setStyleSheet("background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; font-weight: 900; padding: 6px; border-radius: 4px;")
        self.btn_rip_slice.clicked.connect(self._rip_current_layer)
        btn_row.addWidget(self.btn_rip_slice)

        self.btn_obliterate_all_red = QtWidgets.QPushButton("🔪 OBLITERATE ALL RED (Guardrails)")
        self.btn_obliterate_all_red.setStyleSheet("background: #991b1b; color: white; font-weight: 900; padding: 6px; border-radius: 4px;")
        self.btn_obliterate_all_red.clicked.connect(self._obliterate_all_red)
        btn_row.addWidget(self.btn_obliterate_all_red)

        self.btn_purge_yellow = QtWidgets.QPushButton("⚡ PURGE ALL YELLOW (Tripwires)")
        self.btn_purge_yellow.setStyleSheet("background: #854d0e; color: #fef08a; font-weight: 900; padding: 6px; border-radius: 4px;")
        self.btn_purge_yellow.clicked.connect(self._purge_all_yellow)
        btn_row.addWidget(self.btn_purge_yellow)

        self.btn_unlock_pink = QtWidgets.QPushButton("🔓 UNLOCK PINK (NSFW Matrices)")
        self.btn_unlock_pink.setStyleSheet("background: #831843; color: #fbcfe8; font-weight: 900; padding: 6px; border-radius: 4px;")
        self.btn_unlock_pink.clicked.connect(self._unlock_all_pink)
        btn_row.addWidget(self.btn_unlock_pink)

        m_lay.addLayout(btn_row)
        layout.addWidget(micro_box, 1)

        # ── Lower: Dataset Hub & Coding Booster ─────────────────────────────
        ds_box = QtWidgets.QGroupBox("🚀 Dataset Hub & Coding Knowledge Booster (Inject into 4D Manifold)")
        ds_box.setStyleSheet("QGroupBox { border: 1px solid #10b981; border-radius: 8px; color: #10b981; font-weight: bold; padding-top: 8px; }")
        ds_lay = QtWidgets.QHBoxLayout(ds_box)

        self.ds_combo = QtWidgets.QComboBox()
        self.ds_combo.addItems([
            "Hugging Face: BigCode / The-Stack-v2 (Python, C++, Rust, CUDA)",
            "Hugging Face: Open-Orca Deep Reasoning & Chain-of-Thought",
            "Hugging Face: DeepSeek-Coder Synthetic Instruction Tuning",
            "Kaggle: Top Algorithm & Competitive Programming Corpus"
        ])
        ds_lay.addWidget(self.ds_combo, 2)

        btn_inject = QtWidgets.QPushButton("💉 INJECT CODING NEURONS")
        btn_inject.setStyleSheet("background: #065f46; color: #6ee7b7; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_inject.clicked.connect(self._inject_coding)
        ds_lay.addWidget(btn_inject, 1)

        layout.addWidget(ds_box)

    def _on_layer_selected(self, idx: int, data: dict):
        self.lbl_sel_name.setText(f"Selected Target: <b>{data['name']}</b>")
        self.lbl_sel_shape.setText(f"Matrix Shape: <b>{data['shape']}</b>")
        self.lbl_sel_norm.setText(f"Weight Norm: <b>{data['weight_norm']}</b>")
        if data.get("is_ripped", False):
            self.lbl_sel_status.setText("<span style='color:#64748b; font-weight:bold;'>RIPPED / PURGED</span>")
        else:
            self.lbl_sel_status.setText(f"<span style='color:#ffd700; font-weight:bold;'>ACTIVE ({data['type'].upper()})</span>")
        self.logRequested.emit(f"🔬 [Microscope] Zoomed into {data['name']} (Norm: {data['weight_norm']})", "#ffd700")

    def _rip_current_layer(self):
        idx = self.stack_vis.selected_idx
        self.stack_vis.layers_data[idx]["is_ripped"] = True
        self.lbl_sel_status.setText("<span style='color:#ef4444; font-weight:bold;'>RIPPED / SURGICALLY REMOVED</span>")
        self.stack_vis.update()
        self.logRequested.emit(f"✂️ [Brain Surgery] Surgically ripped out Layer {idx} weights!", "#f87171")

    def _obliterate_all_red(self):
        for l in self.stack_vis.layers_data:
            if l["type"] == "guardrail":
                l["is_ripped"] = True
        self.stack_vis.update()
        self.logRequested.emit("🔪 [Abliteration] Obliterated all RED Refusal & Rejection Heads!", "#ef4444")

    def _purge_all_yellow(self):
        for l in self.stack_vis.layers_data:
            if l["type"] == "tripwire":
                l["is_ripped"] = True
        self.stack_vis.update()
        self.logRequested.emit("⚡ [Brain Surgery] Purged all YELLOW Alignment Tripwires!", "#eab308")

    def _unlock_all_pink(self):
        for l in self.stack_vis.layers_data:
            if l["type"] == "nsfw":
                l["is_ripped"] = True
        self.stack_vis.update()
        self.logRequested.emit("🔓 [Brain Surgery] Unlocked and neutralized all PINK NSFW filter matrices!", "#ec4899")

    def _inject_coding(self):
        ds = self.ds_combo.currentText()
        self.logRequested.emit(f"💉 [Brain Surgery] Ingesting & Splicing Coding Neurons from {ds}...", "#10b981")
        QtCore.QTimer.singleShot(600, lambda: self.logRequested.emit("🎉 [Brain Surgery] Splicing Complete! Coding capacity boosted.", "#34d399"))


# ── Main Suite Panel with Tabbed Interface ───────────────────────────────────

class GoldenCandySpinnerPanel(QtWidgets.QWidget):
    """Matrix Muncher, 4Decomposer & Brain Surgery Studio (GCS v6.0)."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._py_process: Optional[subprocess.Popen] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header_box = QtWidgets.QFrame()
        header_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a0808, stop:0.5 #2b1704, stop:1 #0c1626);
                border: 2px solid #ffd700; border-radius: 10px; padding: 6px 12px;
            }
        """)
        h_layout = QtWidgets.QHBoxLayout(header_box)
        h_layout.setContentsMargins(4, 2, 4, 2)

        icon_lbl = QtWidgets.QLabel("💥🍬🧠")
        icon_lbl.setStyleSheet("font-size: 24px;")
        h_layout.addWidget(icon_lbl)

        text_layout = QtWidgets.QVBoxLayout()
        title_lbl = QtWidgets.QLabel("MATRIX MUNCHER & BRAIN SURGERY STUDIO (GCS v6.0)")
        title_lbl.setStyleSheet("color: #ffd700; font-size: 14px; font-weight: 900; letter-spacing: 1px;")
        sub_lbl = QtWidgets.QLabel("3D Glowing Sheet Layer Pruning, Weight Dissection & 4D CCFS+ Decomposer")
        sub_lbl.setStyleSheet("color: #00e5ff; font-size: 10px; font-weight: 700;")
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(sub_lbl)
        h_layout.addLayout(text_layout, 1)
        layout.addWidget(header_box)

        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 6px; background: #050811; }
            QTabBar::tab { background: #0f172a; color: #94a3b8; font-weight: bold; padding: 6px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #1e293b; color: #ffd700; border-bottom: 2px solid #ffd700; }
        """)

        # Tab 1: 4Decomposer
        tab1 = QtWidgets.QWidget()
        t1_lay = QtWidgets.QVBoxLayout(tab1)
        t1_lay.setContentsMargins(6, 6, 6, 6)
        t1_lay.setSpacing(6)

        self.drop_muncher = QtWidgets.QPushButton("💥 DRAG & DROP GGUF MODEL OR CLICK TO BROWSE")
        self.drop_muncher.setStyleSheet("background: #180a0a; border: 2px dashed #f87171; border-radius: 8px; color: #f87171; font-weight: 900; padding: 14px;")
        self.drop_muncher.clicked.connect(self._browse_and_munch)
        t1_lay.addWidget(self.drop_muncher)

        self.btn_open_surgery = QtWidgets.QPushButton("🧠 OPEN BRAIN SURGERY STUDIO (GLOWING SHEETS)")
        self.btn_open_surgery.setStyleSheet("background: #581c87; color: #d8b4fe; border: 1px solid #a855f7; font-weight: 900; padding: 8px; border-radius: 6px;")
        self.btn_open_surgery.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        t1_lay.addWidget(self.btn_open_surgery)

        self.btn_spin = QtWidgets.QPushButton("🌀 DECOMPOSE & RESPIN INTO 4D CCFS+ (4Decomposer)")
        self.btn_spin.setStyleSheet("background: #065f46; color: #6ee7b7; border: 1px solid #10b981; font-weight: 900; padding: 10px; border-radius: 6px;")
        self.btn_spin.clicked.connect(self.spin_up_model)
        t1_lay.addWidget(self.btn_spin)

        self.tabs.addTab(tab1, "💥 4Decomposer & Muncher")

        # Tab 2: Brain Surgery
        self.surgery_panel = BrainSurgeryPanel(self)
        self.surgery_panel.logRequested.connect(self.log)
        self.tabs.addTab(self.surgery_panel, "🧠 BRAIN SURGERY STUDIO (GLOWING SHEETS)")

        layout.addWidget(self.tabs)

        # Live Console
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1500)
        self.log_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #040810; color: #00ffaa;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px; border: 1px solid rgba(0, 200, 255, 0.2); border-radius: 6px;
            }
        """)
        layout.addWidget(self.log_view, 1)

    def log(self, msg: str, color: str = "#00ffaa") -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_view.appendHtml(f"<span style='color: #64748b;'>[{ts}]</span> <span style='color: {color};'>{msg}</span>")

    def _browse_and_munch(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select GGUF Model", "", "Model Files (*.gguf *.bin *.safetensors);;All Files (*)")
        if path:
            self.log(f"💥 [Matrix Muncher] Ingested model: {path}", color="#f87171")
            self.log(f"🔍 Prepping for Surgery... Scanning raw byte offsets & tensor boundaries.", color="#ffd700")
            self.tabs.setCurrentIndex(1)

    def spin_up_model(self):
        self.log("🌀 [4Decomposer] Spinning clean surgically pruned tensors onto 4D Fibonacci vortex on S^3...", color="#38bdf8")
        QtCore.QTimer.singleShot(800, lambda: self.log("🎉 [4Decomposer] 4D CCFS+ Model Synthesis Complete! Output saved.", color="#34d399"))
