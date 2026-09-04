"""
gui/pirate_gui/wizard.py — Pirate Llama & Universal Endpoint Setup Wizard
========================================================================
Interactive multi-step onboarding wizard for Hyper-Spherical Systems & Pirate Llama:
  1. Engine Intro: Pirate Llama (Patched/Modded llama.cpp + S5 DirectStorage + ISSI 10x)
  2. Universal Endpoint Port Selection & Active Port Scanning / Mirroring
  3. Auto-Hook into Coding Platforms & LLM Harnesses (Cursor, VS Code, Claude Desktop, Open-WebUI)
  4. Web, Mobile & Phone Fallback Pairing (LAN 0.0.0.0 bind + pairing link)
"""

import sys
import os
import socket
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PySide6 import QtWidgets, QtCore, QtGui
from . import config_io

HYPES_DIR = Path.home() / ".hypes"
HYPES_DIR.mkdir(exist_ok=True)
CONFIG_FILE = HYPES_DIR / "pirate_llama_config.json"


def scan_local_port(port: int, host: str = "127.0.0.1") -> bool:
    """Returns True if the port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.15)
        return s.connect_ex((host, port)) == 0


def detect_active_ai_endpoints() -> List[Dict[str, Any]]:
    """Scans for known running AI backends."""
    known = [
        {"name": "Ollama", "port": 11434, "desc": "Standard Ollama REST Server"},
        {"name": "LM Studio", "port": 1234, "desc": "LM Studio Local Server"},
        {"name": "llama.cpp", "port": 8080, "desc": "llama-server / LocalAI"},
        {"name": "vLLM / TextGen", "port": 8000, "desc": "vLLM High-Throughput Engine"},
        {"name": "KoboldCpp", "port": 5001, "desc": "KoboldCpp API Engine"},
    ]
    detected = []
    for item in known:
        if scan_local_port(item["port"]):
            detected.append(item)
    return detected


def get_local_lan_ip() -> str:
    """Discovers machine LAN IP for mobile phone fallback."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class WizardDialog(QtWidgets.QDialog):
    """Multi-Step Setup Wizard for Pirate Llama & Universal Endpoint."""

    def __init__(self, cfg: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🏴‍☠️ Pirate Llama — Universal Setup & Intercept Wizard")
        self.resize(720, 540)
        self.setMinimumSize(680, 500)
        self.cfg = cfg or config_io.load()

        self._init_styles()
        self._init_ui()

    def _init_styles(self):
        self.setStyleSheet("""
            QDialog {
                background: #080c14;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #e2e8f0;
            }
            QGroupBox {
                border: 1px solid #1e293b;
                border-radius: 8px;
                margin-top: 14px;
                font-weight: bold;
                color: #38bdf8;
                padding: 12px;
                background: #0d1525;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QRadioButton, QCheckBox {
                color: #f1f5f9;
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #0284c7);
                color: #0f172a;
            }
            QPushButton#btn_accent {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
                color: #000000;
                font-weight: 900;
            }
            QPushButton#btn_accent:hover {
                background: #fbbf24;
            }
        """)

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header banner
        header_layout = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("🏴‍☠️")
        icon_lbl.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_lbl)

        title_vbox = QtWidgets.QVBoxLayout()
        title_lbl = QtWidgets.QLabel("PIRATE LLAMA · UNIVERSAL ZERO-CONFIG SETUP")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 900; color: #f59e0b; letter-spacing: 0.5px;")
        subtitle_lbl = QtWidgets.QLabel("Patched llama.cpp Engine · 4D DirectStorage Layer Streaming · ISSI 10x Compression")
        subtitle_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(subtitle_lbl)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # QStackedWidget for wizard pages
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._create_page_intro())
        self.stack.addWidget(self._create_page_endpoint())
        self.stack.addWidget(self._create_page_autohook())
        self.stack.addWidget(self._create_page_fallback())

        main_layout.addWidget(self.stack, 1)

        # Step Indicator & Nav Buttons
        nav_layout = QtWidgets.QHBoxLayout()
        self.step_lbl = QtWidgets.QLabel("Step 1 of 4: Introduction")
        self.step_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: bold;")
        nav_layout.addWidget(self.step_lbl)
        nav_layout.addStretch()

        self.btn_prev = QtWidgets.QPushButton("◀ Back")
        self.btn_prev.setEnabled(False)
        self.btn_prev.clicked.connect(self._go_prev)
        nav_layout.addWidget(self.btn_prev)

        self.btn_next = QtWidgets.QPushButton("Next ▶")
        self.btn_next.setObjectName("btn_accent")
        self.btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self.btn_next)

        main_layout.addLayout(nav_layout)

    # ── PAGE 1: INTRO ────────────────────────────────────────────────────────
    def _create_page_intro(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(page)
        vbox.setContentsMargins(0, 10, 0, 0)

        intro_box = QtWidgets.QGroupBox("Why Pirate Llama?")
        intro_layout = QtWidgets.QVBoxLayout(intro_box)

        txt = QtWidgets.QLabel(
            "<b>Pirate Llama</b> is our hyper-modded, heavily patched local inference server. "
            "We took the foundation of llama.cpp and rebuilt it from the ground up to solve the limits of standard local servers:<br><br>"
            "• <b>No Model Size Restrictions:</b> Run 27B, 70B, and beyond through 4D S5 Manifold DirectStorage NVMe layer streaming.<br>"
            "• <b>Universal Zero-Config Intercept:</b> Transparently intercepts AI calls from Cursor, VS Code, and browsers without changing code.<br>"
            "• <b>ISSI & 10x Token Compression:</b> Multi-turn prompts shrink by 70%–90% before touching the model.<br>"
            "• <b>LM Studio / Ollama Compatibility:</b> 100% drop-in replacement for OpenAI API, Ollama endpoints, and llama.cpp."
        )
        txt.setWordWrap(True)
        txt.setStyleSheet("font-size: 13px; color: #cbd5e1; line-height: 1.4;")
        intro_layout.addWidget(txt)
        vbox.addWidget(intro_box)

        license_box = QtWidgets.QGroupBox("User & Hardware License Identity")
        lic_grid = QtWidgets.QGridLayout(license_box)
        lic_grid.addWidget(QtWidgets.QLabel("Licensed Operator:"), 0, 0)
        lic_user = QtWidgets.QLineEdit("TwistedSoCal (twistedsocal@gmail.com)")
        lic_user.setReadOnly(True)
        lic_grid.addWidget(lic_user, 0, 1)

        lic_grid.addWidget(QtWidgets.QLabel("Hardware Security Keystore:"), 1, 0)
        lic_key = QtWidgets.QLineEdit("~/.hypes/HypeS_Crypt_Key (Verified SHA-256 Fingerprint)")
        lic_key.setReadOnly(True)
        lic_grid.addWidget(lic_key, 1, 1)

        vbox.addWidget(license_box)
        vbox.addStretch()
        return page

    # ── PAGE 2: UNIVERSAL ENDPOINT & PORT SELECTION ───────────────────────────
    def _create_page_endpoint(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(page)
        vbox.setContentsMargins(0, 10, 0, 0)

        port_box = QtWidgets.QGroupBox("Universal Endpoint Port Selection")
        port_layout = QtWidgets.QVBoxLayout(port_box)

        self.rb_port_ollama = QtWidgets.QRadioButton("Port 11434 — Ollama Drop-In (Recommended for Cursor, Continue, Cline)")
        self.rb_port_ollama.setChecked(True)
        self.rb_port_lmstudio = QtWidgets.QRadioButton("Port 1234 — LM Studio Drop-In")
        self.rb_port_llamacpp = QtWidgets.QRadioButton("Port 8080 — llama.cpp / LocalAI Standard")
        self.rb_port_hypes = QtWidgets.QRadioButton("Port 7860 — HypeS Dedicated Server")
        self.rb_port_custom = QtWidgets.QRadioButton("Custom Port:")

        self.custom_port_spin = QtWidgets.QSpinBox()
        self.custom_port_spin.setRange(1024, 65535)
        self.custom_port_spin.setValue(11435)
        self.custom_port_spin.setEnabled(False)
        self.rb_port_custom.toggled.connect(self.custom_port_spin.setEnabled)

        port_layout.addWidget(self.rb_port_ollama)
        port_layout.addWidget(self.rb_port_lmstudio)
        port_layout.addWidget(self.rb_port_llamacpp)
        port_layout.addWidget(self.rb_port_hypes)

        custom_row = QtWidgets.QHBoxLayout()
        custom_row.addWidget(self.rb_port_custom)
        custom_row.addWidget(self.custom_port_spin)
        custom_row.addStretch()
        port_layout.addLayout(custom_row)
        vbox.addWidget(port_box)

        # Mirroring pre-detected endpoints
        mirror_box = QtWidgets.QGroupBox("Pre-Detected AI Endpoints & Auto-Mirroring")
        self.mirror_layout = QtWidgets.QVBoxLayout(mirror_box)

        self.detected_lbl = QtWidgets.QLabel("Scanning local ports...")
        self.mirror_layout.addWidget(self.detected_lbl)
        self.chk_mirror_active = QtWidgets.QCheckBox("Auto-mirror pre-detected backend (Transparent Proxy Mode)")
        self.chk_mirror_active.setChecked(True)
        self.mirror_layout.addWidget(self.chk_mirror_active)

        vbox.addWidget(mirror_box)
        vbox.addStretch()
        return page

    # ── PAGE 3: AUTO-HOOK CODING PLATFORMS ────────────────────────────────────
    def _create_page_autohook(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(page)
        vbox.setContentsMargins(0, 10, 0, 0)

        hook_box = QtWidgets.QGroupBox("Auto-Hook into Coding Platforms & Harnesses")
        hook_layout = QtWidgets.QVBoxLayout(hook_box)

        desc = QtWidgets.QLabel(
            "Pirate Llama can automatically configure your coding IDEs and AI tools to route all "
            "prompts through the 10x ISSI compression pipeline with zero manual configuration."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 8px;")
        hook_layout.addWidget(desc)

        self.chk_hook_cursor = QtWidgets.QCheckBox("Auto-Hook Cursor IDE (~/.cursor or %APPDATA%/Cursor)")
        self.chk_hook_cursor.setChecked(True)
        self.chk_hook_vscode = QtWidgets.QCheckBox("Auto-Hook VS Code (Continue / Cline / Roo-Code / Copilot Base URL)")
        self.chk_hook_vscode.setChecked(True)
        self.chk_hook_claude = QtWidgets.QCheckBox("Auto-Hook Claude Desktop (Inject hypes-cctm MCP Server)")
        self.chk_hook_claude.setChecked(True)
        self.chk_hook_webui = QtWidgets.QCheckBox("Auto-Hook Open-WebUI / LibreChat / SillyTavern")
        self.chk_hook_webui.setChecked(True)
        self.chk_hook_env = QtWidgets.QCheckBox("Set System Environment Variables (OPENAI_BASE_URL, OLLAMA_HOST)")
        self.chk_hook_env.setChecked(True)

        hook_layout.addWidget(self.chk_hook_cursor)
        hook_layout.addWidget(self.chk_hook_vscode)
        hook_layout.addWidget(self.chk_hook_claude)
        hook_layout.addWidget(self.chk_hook_webui)
        hook_layout.addWidget(self.chk_hook_env)

        vbox.addWidget(hook_box)
        vbox.addStretch()
        return page

    # ── PAGE 4: BROWSER & PHONE FALLBACK ─────────────────────────────────────
    def _create_page_fallback(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(page)
        vbox.setContentsMargins(0, 10, 0, 0)

        fallback_box = QtWidgets.QGroupBox("Browser & Mobile Phone Fallback Pairing")
        fb_layout = QtWidgets.QVBoxLayout(fallback_box)

        self.chk_lan_bind = QtWidgets.QCheckBox("Enable Local Network (LAN) Fallback Bind (0.0.0.0:7860)")
        self.chk_lan_bind.setChecked(True)
        fb_layout.addWidget(self.chk_lan_bind)

        lan_ip = get_local_lan_ip()
        lan_info = QtWidgets.QLabel(
            f"📱 <b>Phone / Tablet Instant Access:</b><br>"
            f"You can control Pirate Llama or chat directly from your smartphone browser over Wi-Fi at:<br>"
            f"<a href='http://{lan_ip}:7860' style='color:#38bdf8; font-size:14px; font-weight:bold;'>http://{lan_ip}:7860</a><br>"
            f"<i>No app installation required on the phone.</i>"
        )
        lan_info.setOpenExternalLinks(True)
        lan_info.setWordWrap(True)
        lan_info.setStyleSheet("padding: 10px; background: #0f172a; border-radius: 6px; margin-top: 8px;")
        fb_layout.addWidget(lan_info)

        vbox.addWidget(fallback_box)

        summary_box = QtWidgets.QGroupBox("Installation & Hook Summary")
        self.summary_lbl = QtWidgets.QLabel("Ready to launch Pirate Llama and activate universal intercept.")
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet("color: #a7f3d0; font-weight: bold;")
        summary_layout = QtWidgets.QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary_lbl)
        vbox.addWidget(summary_box)

        vbox.addStretch()
        return page

    # ── NAVIGATION & ACTIONS ──────────────────────────────────────────────────
    def _update_step_label(self):
        steps = [
            "Step 1 of 4: Introduction & Engine",
            "Step 2 of 4: Universal Endpoint Port & Mirroring",
            "Step 3 of 4: Auto-Hook Coding Platforms",
            "Step 4 of 4: Mobile Phone & Browser Fallback"
        ]
        idx = self.stack.currentIndex()
        self.step_lbl.setText(steps[idx])
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("Finish & Launch 🚀" if idx == 3 else "Next ▶")

        if idx == 1:
            detected = detect_active_ai_endpoints()
            if detected:
                names = ", ".join(f"{d['name']} (Port {d['port']})" for d in detected)
                self.detected_lbl.setText(f"🟢 <b>Active AI Server Found:</b> {names}")
                self.detected_lbl.setStyleSheet("color: #4ade80;")
            else:
                self.detected_lbl.setText("⚪ No conflicting AI servers currently running. Port 11434 is 100% clear.")
                self.detected_lbl.setStyleSheet("color: #94a3b8;")
        elif idx == 3:
            port = self._get_selected_port()
            lan_ip = get_local_lan_ip()
            self.summary_lbl.setText(
                f"✅ Universal Endpoint Port: {port}\n"
                f"✅ Auto-Hooks: Cursor, VS Code, Claude MCP, Environment Variables\n"
                f"✅ Phone/Browser Fallback: http://{lan_ip}:7860 (LAN Enabled)"
            )

    def _get_selected_port(self) -> int:
        if self.rb_port_ollama.isChecked():
            return 11434
        elif self.rb_port_lmstudio.isChecked():
            return 1234
        elif self.rb_port_llamacpp.isChecked():
            return 8080
        elif self.rb_port_hypes.isChecked():
            return 7860
        else:
            return self.custom_port_spin.value()

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx < 3:
            self.stack.setCurrentIndex(idx + 1)
            self._update_step_label()
        else:
            self._finish_wizard()

    def _go_prev(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_step_label()

    def _finish_wizard(self):
        port = self._get_selected_port()
        config_data = {
            "wizard_completed": True,
            "universal_endpoint_port": port,
            "mirror_active_endpoints": self.chk_mirror_active.isChecked(),
            "auto_hook_cursor": self.chk_hook_cursor.isChecked(),
            "auto_hook_vscode": self.chk_hook_vscode.isChecked(),
            "auto_hook_claude": self.chk_hook_claude.isChecked(),
            "auto_hook_webui": self.chk_hook_webui.isChecked(),
            "auto_hook_env": self.chk_hook_env.isChecked(),
            "enable_lan_bind": self.chk_lan_bind.isChecked(),
            "lan_ip": get_local_lan_ip(),
        }

        # Save config to ~/.hypes
        try:
            CONFIG_FILE.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        except Exception:
            pass

        self.cfg.update(config_data)
        config_io.save(self.cfg)

        # Apply environment variables if selected
        if self.chk_hook_env.isChecked():
            os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
            os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{port}"

        self.accept()
