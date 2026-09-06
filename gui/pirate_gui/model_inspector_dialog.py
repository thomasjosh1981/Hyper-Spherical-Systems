"""
gui/pirate_gui/model_inspector_dialog.py
========================================
Interactive Pre-Execution Model Inspector & Brain Director Orchestrator.

Opens when double-clicking or selecting any model before execution, providing:
1. Core Sampling Controls: Temperature, Top-P, Repetition Penalty, Context Limit.
2. Speculative Decoding & Draft Token Auto-Optimizer:
   - Dynamic Draft Token Usage: Auto-backs off draft passes if system latency spikes.
   - Anti-Looping & Anti-Repetition 4D Angular Torque Governor.
3. Brain Director Binding:
   - Attaches supervisory 5GB–7GB Brain Model (Qwen-2.5-Coder, Llama-3.1, Gemma-2).
   - Cross-Model Skill Borrowing over SFS+ InteropBus.
   - Recursive Self-Learning & Capability Solidification.
   - Multilingual Intent Bridge & Extended Tool/Vision Gateway.
4. Spark & 5D OCEAN Personality Vector Injection.
"""

from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6 import QtCore, QtGui, QtWidgets


class ModelInspectorDialog(QtWidgets.QDialog):
    """Pre-Run Model Configuration & Brain Director Orchestrator."""

    launchRequested = QtCore.Signal(dict)
    openSpinnerRequested = QtCore.Signal(str)

    def __init__(self, model_info: Optional[Dict[str, Any]] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.model_info = model_info or {
            "name": "Local-Model-Current.gguf",
            "path": "",
            "size": "Unknown",
            "params": "Unknown"
        }
        self.setWindowTitle(f"🧠 Model Inspector — {self.model_info.get('name', 'Model Config')}")
        self.resize(780, 680)
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background: #040810;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QGroupBox {
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #ffd700);
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
            QCheckBox {
                color: #f1f5f9;
                font-size: 12px;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #38bdf8;
                border-radius: 3px;
                background: #0f172a;
            }
            QCheckBox::indicator:checked {
                background: #0284c7;
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background: #0f172a;
                border: 1px solid #334155;
                color: #f8fafc;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Banner
        header = QtWidgets.QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a0f00, stop:0.5 #2a1b02, stop:1 #081a2e);
                border: 1px solid #ffd700;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        h_lay = QtWidgets.QHBoxLayout(header)
        icon_lbl = QtWidgets.QLabel("🧠⚡")
        icon_lbl.setStyleSheet("font-size: 26px;")
        h_lay.addWidget(icon_lbl)

        info_lay = QtWidgets.QVBoxLayout()
        title_lbl = QtWidgets.QLabel(f"Target Model: {self.model_info.get('name', 'Unspecified')}")
        title_lbl.setStyleSheet("color: #ffd700; font-weight: 900; font-size: 15px;")
        sub_lbl = QtWidgets.QLabel(f"Size: {self.model_info.get('size', 'N/A')}  |  Params: {self.model_info.get('params', 'N/A')}  |  Architecture: SFS+ / GGUF Hybrid")
        sub_lbl.setStyleSheet("color: #38bdf8; font-size: 11px;")
        info_lay.addWidget(title_lbl)
        info_lay.addWidget(sub_lbl)
        h_lay.addLayout(info_lay, 1)
        layout.addWidget(header)

        # Architectural & Runtime Notices Banner
        runtime_banner = QtWidgets.QFrame()
        runtime_banner.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        rb_lay = QtWidgets.QVBoxLayout(runtime_banner)
        rb_lay.setSpacing(3)
        rb_lay.setContentsMargins(4, 4, 4, 4)

        lbl_sfs_notice = QtWidgets.QLabel("⚓ <b>SFS / SFS+ Requirement:</b> Pirate Llama must be installed & functional to execute SFS containers. Supports universal routing to <b>LM Studio</b> via <code>http://localhost:8000/v1</code>.")
        lbl_sfs_notice.setStyleSheet("color: #38bdf8; font-size: 11px;")

        lbl_gguf_notice = QtWidgets.QLabel("🦙 <b>Native GGUF Execution:</b> Ported from <b>llama.cpp</b> — runs standard .gguf models natively with full feature parity plus ISSI 10× compression.")
        lbl_gguf_notice.setStyleSheet("color: #4ade80; font-size: 11px;")

        rb_lay.addWidget(lbl_sfs_notice)
        rb_lay.addWidget(lbl_gguf_notice)
        layout.addWidget(runtime_banner)

        # ── Group 1: Speculative Decoding & Draft Token Auto-Optimizer ───────
        draft_box = QtWidgets.QGroupBox("⚡ Speculative Decoding & Draft Token Auto-Optimizer")
        d_lay = QtWidgets.QVBoxLayout(draft_box)
        d_lay.setSpacing(8)

        self.cb_enable_draft = QtWidgets.QCheckBox("Enable Speculative Decoding (Use Fast Draft Predictor)")
        self.cb_enable_draft.setChecked(True)
        d_lay.addWidget(self.cb_enable_draft)

        row_depth = QtWidgets.QHBoxLayout()
        row_depth.addWidget(QtWidgets.QLabel("Speculative Draft Passes:"))
        self.slider_draft = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_draft.setRange(1, 8)
        self.slider_draft.setValue(4)
        self.lbl_draft_val = QtWidgets.QLabel("4 passes")
        self.lbl_draft_val.setStyleSheet("color: #ffd700; font-weight: bold; width: 60px;")
        self.slider_draft.valueChanged.connect(lambda v: self.lbl_draft_val.setText(f"{v} passes"))
        row_depth.addWidget(self.slider_draft, 1)
        row_depth.addWidget(self.lbl_draft_val)
        d_lay.addLayout(row_depth)

        self.cb_auto_opt_draft = QtWidgets.QCheckBox("🚀 Dynamic Auto-Optimize Draft Usage (Auto-reduces passes if latency spikes)")
        self.cb_auto_opt_draft.setChecked(True)
        self.cb_auto_opt_draft.setToolTip("If the system detects draft token latency bogging down execution, passes are automatically scaled down in real-time.")
        d_lay.addWidget(self.cb_auto_opt_draft)

        self.cb_anti_loop = QtWidgets.QCheckBox("🔄 4D Angular Loop Breaker (Prevents repetitive loops & token fixation)")
        self.cb_anti_loop.setChecked(True)
        d_lay.addWidget(self.cb_anti_loop)

        layout.addWidget(draft_box)

        # ── Group 2: Brain Director & Supervisory Architecture ───────────────
        brain_box = QtWidgets.QGroupBox("🧠 Brain Director & Supervisory Model Attachment")
        b_lay = QtWidgets.QVBoxLayout(brain_box)
        b_lay.setSpacing(8)

        row_brain_sel = QtWidgets.QHBoxLayout()
        row_brain_sel.addWidget(QtWidgets.QLabel("Supervisory Brain Model:"))
        self.combo_brain = QtWidgets.QComboBox()
        self.combo_brain.addItems([
            "Qwen-2.5-Coder-7B-Instruct (4.68 GB — Coding & Architecture Specialist)",
            "Llama-3.1-8B-Instruct (4.92 GB — Multilingual & Reasoning Orchestrator)",
            "Gemma-2-9B-IT (5.86 GB — Math & Deep Logic Specialist)",
            "DeepSeek-Coder-V2-Lite-16B (9.12 GB — Polyglot Coding vMoE)",
            "Mistral-7B-Instruct-v0.3 (4.37 GB — Compact Real-Time Director)"
        ])
        row_brain_sel.addWidget(self.combo_brain, 1)
        b_lay.addLayout(row_brain_sel)

        feat_grid = QtWidgets.QGridLayout()
        self.cb_interop_borrow = QtWidgets.QCheckBox("SFS+ Skill Borrowing (Activate capabilities from other models)")
        self.cb_interop_borrow.setChecked(True)
        feat_grid.addWidget(self.cb_interop_borrow, 0, 0)

        self.cb_recursive_learn = QtWidgets.QCheckBox("Recursive Self-Learning (Absorb verified skills permanently)")
        self.cb_recursive_learn.setChecked(True)
        feat_grid.addWidget(self.cb_recursive_learn, 0, 1)

        self.cb_multilingual = QtWidgets.QCheckBox("Multilingual & Polyglot Intent Normalizer")
        self.cb_multilingual.setChecked(True)
        feat_grid.addWidget(self.cb_multilingual, 1, 0)

        self.cb_tool_vision = QtWidgets.QCheckBox("Extended Vision & Tool Calling Gateway (Bypass model limits)")
        self.cb_tool_vision.setChecked(True)
        feat_grid.addWidget(self.cb_tool_vision, 1, 1)

        b_lay.addLayout(feat_grid)
        layout.addWidget(brain_box)

        # ── Group 3: Spark & 5D Personality Vector (OCEAN) ───────────────────
        spark_box = QtWidgets.QGroupBox("✨ Personality Spark & Trait Modulation (5D OCEAN)")
        s_lay = QtWidgets.QVBoxLayout(spark_box)
        s_lay.setSpacing(6)

        self.cb_personality = QtWidgets.QCheckBox("Inject Custom Personality Spark Profile")
        self.cb_personality.setChecked(True)
        s_lay.addWidget(self.cb_personality)

        ocean_grid = QtWidgets.QGridLayout()
        self.sliders_ocean: Dict[str, QtWidgets.QSlider] = {}
        traits = [
            ("Openness (Creativity & Range)", 90, 0),
            ("Conscientiousness (Rigorous Accuracy)", 95, 1),
            ("Extraversion (Expressive Tone)", 45, 2),
            ("Agreeableness (Constructive Empathy)", 65, 3),
            ("Emotional Stability (Composure)", 95, 4)
        ]
        for name, default_val, row in traits:
            lbl = QtWidgets.QLabel(name)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default_val)
            val_lbl = QtWidgets.QLabel(f"{default_val/100:.2f}")
            val_lbl.setStyleSheet("color: #10b981; font-weight: bold; width: 40px;")
            slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(f"{v/100:.2f}"))
            ocean_grid.addWidget(lbl, row, 0)
            ocean_grid.addWidget(slider, row, 1)
            ocean_grid.addWidget(val_lbl, row, 2)
            self.sliders_ocean[name] = slider

        s_lay.addLayout(ocean_grid)
        layout.addWidget(spark_box)

        # ── Group 4: Standard Sampling Overrides ──────────────────────────────
        samp_box = QtWidgets.QGroupBox("🎛️ Core Sampling Overrides")
        samp_lay = QtWidgets.QHBoxLayout(samp_box)

        samp_lay.addWidget(QtWidgets.QLabel("Temperature:"))
        self.spin_temp = QtWidgets.QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 2.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.70)
        samp_lay.addWidget(self.spin_temp)

        samp_lay.addWidget(QtWidgets.QLabel("Top-P:"))
        self.spin_topp = QtWidgets.QDoubleSpinBox()
        self.spin_topp.setRange(0.1, 1.0)
        self.spin_topp.setSingleStep(0.05)
        self.spin_topp.setValue(0.90)
        samp_lay.addWidget(self.spin_topp)

        samp_lay.addWidget(QtWidgets.QLabel("Repeat Penalty:"))
        self.spin_rep = QtWidgets.QDoubleSpinBox()
        self.spin_rep.setRange(1.0, 2.0)
        self.spin_rep.setSingleStep(0.05)
        self.spin_rep.setValue(1.15)
        samp_lay.addWidget(self.spin_rep)

        layout.addWidget(samp_box)

        # ── Bottom Action Buttons ─────────────────────────────────────────────
        btn_bar = QtWidgets.QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_spinner = QtWidgets.QPushButton("🍬 OPEN IN GOLDEN CANDY SPINNER")
        self.btn_spinner.setStyleSheet("background: #854d0e; color: #fef08a; border: 1px solid #eab308; font-weight: bold; padding: 10px 16px; border-radius: 6px;")
        self.btn_spinner.clicked.connect(self._open_spinner)
        btn_bar.addWidget(self.btn_spinner)

        btn_bar.addStretch(1)

        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.setStyleSheet("background: #1e293b; color: #94a3b8; font-weight: bold; padding: 10px 16px; border-radius: 6px;")
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        self.btn_launch = QtWidgets.QPushButton("🚀 LAUNCH WITH BRAIN GOVERNOR")
        self.btn_launch.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #10b981); color: white; font-weight: 900; padding: 10px 22px; border-radius: 6px;")
        self.btn_launch.clicked.connect(self._on_launch)
        btn_bar.addWidget(self.btn_launch)

        layout.addLayout(btn_bar)

    def _open_spinner(self):
        model_path = self.model_info.get("path", "")
        self.openSpinnerRequested.emit(model_path)
        self.accept()

    def _on_launch(self):
        config = {
            "model_path": self.model_info.get("path", ""),
            "model_name": self.model_info.get("name", ""),
            "temperature": self.spin_temp.value(),
            "top_p": self.spin_topp.value(),
            "repeat_penalty": self.spin_rep.value(),
            "speculative_decoding": self.cb_enable_draft.isChecked(),
            "draft_passes": self.slider_draft.value(),
            "auto_optimize_draft": self.cb_auto_opt_draft.isChecked(),
            "anti_looping_governor": self.cb_anti_loop.isChecked(),
            "brain_model": self.combo_brain.currentText(),
            "skill_borrowing": self.cb_interop_borrow.isChecked(),
            "recursive_learning": self.cb_recursive_learn.isChecked(),
            "multilingual_bridge": self.cb_multilingual.isChecked(),
            "tool_vision_gateway": self.cb_tool_vision.isChecked(),
            "personality_spark_enabled": self.cb_personality.isChecked(),
            "ocean_traits": {k: v.value() / 100.0 for k, v in self.sliders_ocean.items()}
        }
        self.launchRequested.emit(config)
        self.accept()
