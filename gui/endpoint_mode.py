# gui/endpoint_mode.py — HypeS Universal Endpoint Mode Selector
#
# Hyper-Spherical Systems — Universal Endpoint First-Run Configurator
#
# Asks the user ONCE which API endpoint style they want:
#
#   ┌──────────────────────────────────────────────────────────────────┐
#   │  NATIVE HYPES  (Recommended)                                    │
#   │  http://localhost:7860  — fully self-configuring, all features  │
#   ├──────────────────────────────────────────────────────────────────┤
#   │  OPENAI COMPATIBLE                                               │
#   │  http://localhost:7860/v1  — drop-in for any OpenAI client      │
#   ├──────────────────────────────────────────────────────────────────┤
#   │  ANTHROPIC COMPATIBLE                                            │
#   │  http://localhost:7860  — drop-in for Anthropic SDK             │
#   └──────────────────────────────────────────────────────────────────┘
#
# After selection it:
#   1. Saves mode to ~/.hypes/endpoint_mode.json
#   2. Writes a .env file with correct env vars
#   3. Sets process env vars immediately
#   4. Returns a config dict used by server.py routing
#
# Developer: twiztedsocal
# License: Proprietary — All Rights Reserved

from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional

# ── Storage ───────────────────────────────────────────────────────────────────
HYPES_DIR         = Path.home() / ".hypes"
MODE_FILE         = HYPES_DIR / "endpoint_mode.json"
ENV_FILE          = HYPES_DIR / "hypes.env"
HYPES_PORT        = int(os.environ.get("PIRATE_PORT", 7860))

# ── Mode definitions ──────────────────────────────────────────────────────────
MODES = {
    "native": {
        "id":          "native",
        "name":        "Native HypeS",
        "tagline":     "Recommended — Best Performance & Full Features",
        "description": (
            "The full Hyper-Spherical experience. Auto-detects every connected AI backend, "
            "applies ISSI + CCTM compression, manages cloud routing, and gives you "
            "the Control Center dashboard. Zero config — it just works."
        ),
        "base_url":    f"http://localhost:{HYPES_PORT}",
        "api_key":     "sk-hypes-native",
        "env_vars": {
            "HYPES_MODE":        "native",
            "HYPES_BASE_URL":    f"http://localhost:{HYPES_PORT}",
            "HYPES_API_KEY":     "sk-hypes-native",
            "OPENAI_API_BASE":   f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_BASE_URL":   f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_API_KEY":    "sk-hypes-native",
        },
        "color":   "#f59e0b",   # Gold
        "icon":    "⚡",
        "badge":   "RECOMMENDED",
    },
    "openai": {
        "id":          "openai",
        "name":        "OpenAI Compatible",
        "tagline":     "Drop-in replacement for api.openai.com/v1",
        "description": (
            "Point any OpenAI client, LangChain, LlamaIndex, AutoGen, or "
            "Open WebUI here and it works with zero changes. "
            "Set OPENAI_API_BASE to the URL shown and you're done."
        ),
        "base_url":    f"http://localhost:{HYPES_PORT}/v1",
        "api_key":     "sk-hypes-openai",
        "env_vars": {
            "HYPES_MODE":        "openai",
            "HYPES_BASE_URL":    f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_API_BASE":   f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_BASE_URL":   f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_API_KEY":    "sk-hypes-openai",
        },
        "color":   "#10b981",   # Green
        "icon":    "🤖",
        "badge":   "OPENAI DROP-IN",
    },
    "anthropic": {
        "id":          "anthropic",
        "name":        "Anthropic Compatible",
        "tagline":     "Drop-in replacement for api.anthropic.com",
        "description": (
            "Works with Anthropic SDK, Claude clients, and any tool that uses the "
            "Messages API format. Point ANTHROPIC_BASE_URL here and it routes "
            "through HypeS with full CCTM optimization."
        ),
        "base_url":    f"http://localhost:{HYPES_PORT}",
        "api_key":     "sk-hypes-anthropic",
        "env_vars": {
            "HYPES_MODE":          "anthropic",
            "HYPES_BASE_URL":      f"http://localhost:{HYPES_PORT}",
            "ANTHROPIC_BASE_URL":  f"http://localhost:{HYPES_PORT}",
            "ANTHROPIC_API_KEY":   "sk-hypes-anthropic",
            "OPENAI_API_BASE":     f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_BASE_URL":     f"http://localhost:{HYPES_PORT}/v1",
            "OPENAI_API_KEY":      "sk-hypes-anthropic",
        },
        "color":   "#a855f7",   # Purple
        "icon":    "🔮",
        "badge":   "ANTHROPIC DROP-IN",
    },
}

DEFAULT_MODE = "native"


# ── Persistence ───────────────────────────────────────────────────────────────
def load_mode() -> Optional[dict]:
    """Load saved endpoint mode. Returns None if not yet configured."""
    if MODE_FILE.exists():
        try:
            data = json.loads(MODE_FILE.read_text())
            mode_id = data.get("mode", DEFAULT_MODE)
            if mode_id in MODES:
                return {**MODES[mode_id], **data}
        except Exception:
            pass
    return None


def save_mode(mode_id: str) -> dict:
    """Persist the selected endpoint mode and write env file."""
    HYPES_DIR.mkdir(parents=True, exist_ok=True)
    mode = MODES.get(mode_id, MODES[DEFAULT_MODE])

    # Save mode file
    MODE_FILE.write_text(json.dumps({
        "mode":     mode_id,
        "base_url": mode["base_url"],
        "api_key":  mode["api_key"],
        "ts":       int(time.time()),
    }), encoding="utf-8")

    # Write .env file
    env_lines = [
        "# HypeS Universal Endpoint — Auto-Generated Environment Config",
        f"# Mode: {mode['name']}  ({mode['tagline']})",
        f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for k, v in mode["env_vars"].items():
        env_lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    # Apply to current process env immediately
    for k, v in mode["env_vars"].items():
        os.environ[k] = v

    return mode


def reset_mode() -> None:
    """Reset mode selection so the dialog shows again on next start."""
    MODE_FILE.unlink(missing_ok=True)


def get_active_mode() -> dict:
    """Get active mode, defaulting to native if not configured."""
    saved = load_mode()
    if saved:
        return saved
    return MODES[DEFAULT_MODE]


def apply_env_vars(mode_id: Optional[str] = None) -> None:
    """Apply env vars for the current (or specified) mode to the process."""
    mode = MODES.get(mode_id or get_active_mode()["id"], MODES[DEFAULT_MODE])
    for k, v in mode["env_vars"].items():
        os.environ.setdefault(k, v)


# ── Headless selector ─────────────────────────────────────────────────────────
def select_mode_headless() -> dict:
    """CLI mode selector. Returns the selected mode dict."""
    saved = load_mode()
    if saved:
        return saved

    print("\n" + "═" * 64)
    print("  ⚡  HYPES UNIVERSAL ENDPOINT — MODE SELECTION")
    print("═" * 64)
    print(
        "Choose how other apps connect to your HypeS endpoint.\n"
        "You can change this any time from the Control Center.\n"
    )

    options = list(MODES.values())
    for i, m in enumerate(options, 1):
        badge = f"  [{m['badge']}]" if m.get("badge") else ""
        print(f"  {i}. {m['icon']}  {m['name']}{badge}")
        print(f"       {m['tagline']}")
        print(f"       URL: {m['base_url']}")
        print()

    print("  Press ENTER for Native HypeS (recommended)")
    choice = input("  Select [1-3]: ").strip()

    try:
        idx = int(choice) - 1
        mode_id = options[idx]["id"] if 0 <= idx < len(options) else DEFAULT_MODE
    except (ValueError, IndexError):
        mode_id = DEFAULT_MODE

    mode = save_mode(mode_id)
    print(f"\n  ✅  Mode set: {mode['name']}")
    print(f"  📡  Your endpoint: {mode['base_url']}")
        
    if ENV_FILE.exists():
        print(f"  📄  Env file written: {ENV_FILE}")
    print("═" * 64 + "\n")
    return mode


# ── GUI selector ──────────────────────────────────────────────────────────────
def select_mode_gui() -> dict:
    """
    Premium PySide6 endpoint mode selector.
    Shows once on first run, never again unless reset.
    Falls back to headless if GUI unavailable.
    """
    saved = load_mode()
    if saved:
        apply_env_vars(saved["id"])
        return saved

    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle("⚡ HypeS — Choose Your Endpoint Mode")
        dlg.setMinimumWidth(640)
        dlg.setMinimumHeight(560)
        dlg.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0a0f1e, stop:1 #060912);
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel { background: transparent; border: none; color: #8899aa; font-size: 12px; }
            QLabel#title { color: #ffffff; font-size: 18px; font-weight: 800; letter-spacing: 0.02em; }
            QLabel#subtitle { color: #4a6a8a; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; }
            QAbstractButton { font-family: 'Segoe UI', 'Inter', sans-serif; }
        """)

        outer = QtWidgets.QVBoxLayout(dlg)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # ── Header ──
        hdr = QtWidgets.QWidget()
        hdr.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(245,158,11,0.12),stop:1 rgba(168,85,247,0.06));"
            "border-radius:10px; border:1px solid rgba(245,158,11,0.20);"
        )
        hlay = QtWidgets.QVBoxLayout(hdr)
        hlay.setContentsMargins(20, 16, 20, 16)
        sub_lbl = QtWidgets.QLabel("▶▶  universal endpoint configuration  —  one-time setup")
        sub_lbl.setObjectName("subtitle")
        title_lbl = QtWidgets.QLabel("How should other apps connect to HypeS?")
        title_lbl.setObjectName("title")
        desc_lbl = QtWidgets.QLabel(
            "Select your preferred API style. HypeS auto-configures everything — "
            "no manual setup required. You can change this any time from the Control Center."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "color: #5a7a9a; font-size: 11px; background: transparent; border: none;"
        )
        hlay.addWidget(sub_lbl)
        hlay.addSpacing(4)
        hlay.addWidget(title_lbl)
        hlay.addSpacing(6)
        hlay.addWidget(desc_lbl)
        outer.addWidget(hdr)
        outer.addSpacing(20)

        # ── Mode cards ──
        selected_mode = [DEFAULT_MODE]
        card_buttons = {}

        def _make_card(mode: dict) -> QtWidgets.QAbstractButton:
            btn = QtWidgets.QPushButton()
            btn.setCheckable(True)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            btn.setMinimumHeight(110)

            color   = mode["color"]
            icon    = mode["icon"]
            name    = mode["name"]
            tagline = mode["tagline"]
            desc    = mode["description"]
            url     = mode["base_url"]
            badge   = mode.get("badge", "")
            is_rec  = mode["id"] == DEFAULT_MODE

            # Build card layout
            card_lay = QtWidgets.QVBoxLayout(btn)
            card_lay.setContentsMargins(18, 14, 18, 14)
            card_lay.setSpacing(4)

            # Top row: icon + name + badge
            top_row = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size:24px; color:{color}; background:transparent; border:none;")
            name_col = QtWidgets.QVBoxLayout()
            name_col.setSpacing(1)
            name_lbl = QtWidgets.QLabel(name)
            name_lbl.setStyleSheet(
                f"color:#ffffff; font-size:14px; font-weight:800;"
                f" background:transparent; border:none;"
            )
            tag_lbl = QtWidgets.QLabel(tagline)
            tag_lbl.setStyleSheet(
                f"color:{color}; font-size:10px; font-weight:700;"
                f" letter-spacing:0.06em; background:transparent; border:none;"
            )
            name_col.addWidget(name_lbl)
            name_col.addWidget(tag_lbl)
            top_row.addWidget(icon_lbl)
            top_row.addSpacing(10)
            top_row.addLayout(name_col)
            top_row.addStretch()
            if badge:
                badge_lbl = QtWidgets.QLabel(f"  {badge}  ")
                badge_lbl.setStyleSheet(
                    f"color:{color}; font-size:9px; font-weight:800;"
                    f" border:1px solid {color}; border-radius:4px;"
                    f" padding:2px 4px; letter-spacing:0.10em;"
                    f" background:rgba(0,0,0,0.30);"
                )
                top_row.addWidget(badge_lbl)
            card_lay.addLayout(top_row)

            # Description
            desc_lbl2 = QtWidgets.QLabel(desc)
            desc_lbl2.setWordWrap(True)
            desc_lbl2.setStyleSheet(
                "color:#5a7a9a; font-size:10px; background:transparent; border:none;"
            )
            card_lay.addWidget(desc_lbl2)

            # URL
            url_lbl = QtWidgets.QLabel(f"📡  {url}")
            url_lbl.setStyleSheet(
                f"color:{color}; font-size:11px; font-weight:700;"
                f" background:transparent; border:none;"
            )
            card_lay.addWidget(url_lbl)

            # Style (normal + checked)
            base_style = f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(255,255,255,0.03),
                        stop:1 rgba(255,255,255,0.01));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 10px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba({_hex_to_rgb(color)},0.10),
                        stop:1 rgba({_hex_to_rgb(color)},0.04));
                    border-color: rgba({_hex_to_rgb(color)},0.40);
                }}
                QPushButton:checked {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba({_hex_to_rgb(color)},0.18),
                        stop:1 rgba({_hex_to_rgb(color)},0.08));
                    border: 2px solid {color};
                    border-radius: 10px;
                }}
            """
            btn.setStyleSheet(base_style)

            def _on_toggle(checked, mid=mode["id"]):
                if checked:
                    selected_mode[0] = mid
                    for other_id, other_btn in card_buttons.items():
                        if other_id != mid:
                            other_btn.setChecked(False)
            btn.toggled.connect(_on_toggle)

            return btn

        mode_list = list(MODES.values())
        # Put native first
        mode_list.sort(key=lambda m: 0 if m["id"] == DEFAULT_MODE else 1)

        for mode in mode_list:
            card = _make_card(mode)
            card_buttons[mode["id"]] = card
            outer.addWidget(card)
            outer.addSpacing(10)

        # Pre-select native
        card_buttons[DEFAULT_MODE].setChecked(True)

        outer.addSpacing(8)

        # ── Env file note ──
        note = QtWidgets.QLabel(
            f"⚡  HypeS will write a .env file to {ENV_FILE} and set environment "
            f"variables automatically. Compatible with Python dotenv, Node.js dotenv, "
            f"and any shell that sources it."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#3a5a7a; font-size:10px; background:transparent; border:none;"
        )
        outer.addWidget(note)
        outer.addSpacing(16)

        # ── Confirm button ──
        confirm_btn = QtWidgets.QPushButton("⚡  Confirm & Auto-Configure")
        confirm_btn.setMinimumHeight(44)
        confirm_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #b45309, stop:1 #7c3aed);
                color: #ffffff; border: none; border-radius: 9px;
                font-size: 14px; font-weight: 800; letter-spacing: 0.04em;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #d97706, stop:1 #9333ea);
            }
        """)
        confirm_btn.clicked.connect(dlg.accept)
        outer.addWidget(confirm_btn)

        dlg.exec()

        mode_id = selected_mode[0]
        mode = save_mode(mode_id)
        return mode

    except Exception:
        return select_mode_headless()


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #rrggbb to 'r,g,b' string for use in rgba()."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    return "255,255,255"


# ── Auto-config entry point (called by server.py on startup) ──────────────────
def auto_configure(headless: bool = False) -> dict:
    """
    Main entry point called by server.py on startup.
    Shows mode dialog on first run, returns active mode config.
    """
    if headless:
        mode = select_mode_headless()
    else:
        mode = select_mode_gui()

    apply_env_vars(mode["id"])
    return mode


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HypeS Endpoint Mode Selector")
    parser.add_argument("--reset", action="store_true", help="Reset mode (show selector again)")
    parser.add_argument("--headless", action="store_true", help="CLI mode selector")
    parser.add_argument("--status", action="store_true", help="Show current mode")
    parser.add_argument("--set", choices=list(MODES.keys()), help="Set mode directly")
    args = parser.parse_args()

    if args.reset:
        reset_mode()
        print("Mode reset. Selector will show on next start.")
    elif args.status:
        m = get_active_mode()
        print(f"Mode:    {m['name']}")
        print(f"URL:     {m['base_url']}")
        print(f"API Key: {m['api_key']}")
        if ENV_FILE.exists():
            print(f"Env:     {ENV_FILE}")
    elif args.set:
        m = save_mode(args.set)
        print(f"Mode set to: {m['name']} → {m['base_url']}")
    else:
        mode = auto_configure(headless=args.headless)
        print(json.dumps({
            "mode": mode["id"],
            "name": mode["name"],
            "base_url": mode["base_url"],
            "api_key": mode["api_key"],
        }, indent=2))
