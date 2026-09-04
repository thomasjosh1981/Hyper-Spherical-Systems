"""
avatar_window.py — Windowless, Transparent, Always-on-Top Floating Avatar

A frameless Qt window housing the 4ID Pirate Llama avatar.
No title bar, no border, no taskbar button — just the holographic figure
floating over your desktop.

Features:
  - Fully transparent background (Qt.WA_TranslucentBackground)
  - Always-on-top (Qt.WindowStaysOnTopHint)
  - Draggable by click-and-drag anywhere on the avatar
  - Right-click context menu: Pin/Unpin, Resize, Minimize to tray, Close
  - Resize handle (bottom-right corner)
  - Minimal control strip shown on hover: [—] [×]
  - Public API mirrors AvatarViewport so dashboard can still call set_state() etc.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

# ── Locate avatar_float.html ──────────────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
_FLOAT_HTML = _HERE / "avatar_float.html"

# Frozen (PyInstaller) path fallback
if getattr(sys, "frozen", False):
    _meipass = Path(getattr(sys, "_MEIPASS", ""))
    for _candidate in (
        _meipass / "gui" / "pirate_gui" / "avatar_float.html",
        _meipass / "avatar_float.html",
    ):
        if _candidate.exists():
            _FLOAT_HTML = _candidate
            break


# ── Floating avatar window ────────────────────────────────────────────────────

class AvatarFloatingWindow(QtWidgets.QWidget):
    """
    Windowless, transparent, always-on-top floating avatar.

    Usage:
        win = AvatarFloatingWindow.get_instance()
        win.show_avatar()
        win.set_state(1)   # TALKING
        win.set_name("TwistedSoCal")
    """

    _instance: Optional["AvatarFloatingWindow"] = None

    @classmethod
    def get_instance(cls) -> "AvatarFloatingWindow":
        """Singleton — only one floating avatar per process."""
        if cls._instance is None or not cls._instance.isValid():
            cls._instance = cls()
        return cls._instance

    def isValid(self) -> bool:
        try:
            return not self.isHidden() or True  # widget still alive
        except RuntimeError:
            return False

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(
            parent,
            QtCore.Qt.FramelessWindowHint        # no title bar
            | QtCore.Qt.WindowStaysOnTopHint     # always on top
            | QtCore.Qt.Tool                     # no taskbar button
            | QtCore.Qt.NoDropShadowWindowHint,  # let Qt handle compositing
        )
        # ── Transparency ──────────────────────────────────────────────────────
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)

        self.setMinimumSize(260, 340)
        self.resize(320, 440)

        # Position: bottom-right of primary screen
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 340, screen.height() - 480)

        self._drag_pos: Optional[QtCore.QPoint] = None
        self._resize_active = False
        self._resize_origin: Optional[QtCore.QPoint] = None
        self._resize_start_geom: Optional[QtCore.QRect] = None
        self._web = None
        self._loaded = False

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Hover control strip (hidden by default, shown on mouse-enter)
        self._ctrl_strip = QtWidgets.QWidget(self)
        self._ctrl_strip.setFixedHeight(28)
        self._ctrl_strip.setStyleSheet(
            "background: rgba(4,10,24,0.82); border-bottom: 1px solid rgba(0,212,255,0.25);"
        )
        cs_layout = QtWidgets.QHBoxLayout(self._ctrl_strip)
        cs_layout.setContentsMargins(8, 0, 8, 0)
        cs_layout.setSpacing(6)

        lbl = QtWidgets.QLabel("🤖 4ID Avatar")
        lbl.setStyleSheet("color:#00d4ff; font-size:10px; font-weight:700; letter-spacing:0.08em;")
        cs_layout.addWidget(lbl)
        cs_layout.addStretch()

        pin_btn = QtWidgets.QPushButton("📌")
        pin_btn.setFixedSize(22, 22)
        pin_btn.setToolTip("Toggle always-on-top")
        pin_btn.setCheckable(True)
        pin_btn.setChecked(True)
        pin_btn.toggled.connect(self._toggle_pin)
        pin_btn.setStyleSheet(self._btn_css())
        cs_layout.addWidget(pin_btn)

        min_btn = QtWidgets.QPushButton("—")
        min_btn.setFixedSize(22, 22)
        min_btn.setToolTip("Minimise")
        min_btn.clicked.connect(self.showMinimized)
        min_btn.setStyleSheet(self._btn_css())
        cs_layout.addWidget(min_btn)

        close_btn = QtWidgets.QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setToolTip("Hide avatar (doesn't unload engine)")
        close_btn.clicked.connect(self.hide_avatar)
        close_btn.setStyleSheet(self._btn_css("#ff4444"))
        cs_layout.addWidget(close_btn)

        self._ctrl_strip.hide()
        outer.addWidget(self._ctrl_strip)

        # WebEngine viewport
        self._viewport_placeholder = QtWidgets.QLabel("Loading avatar…")
        self._viewport_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._viewport_placeholder.setStyleSheet("color:#00ffcc; font-size:12px; background: transparent;")
        outer.addWidget(self._viewport_placeholder, 1)

        # Resize grip (bottom-right)
        self._grip = QtWidgets.QSizeGrip(self)
        self._grip.setStyleSheet("background: transparent;")
        grip_row = QtWidgets.QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip_row.addWidget(self._grip)
        outer.addLayout(grip_row)

    @staticmethod
    def _btn_css(color: str = "#5a7a9a") -> str:
        return (
            f"QPushButton {{ background: transparent; color: {color}; border: none; "
            f"font-size: 13px; font-weight: 700; }}"
            f"QPushButton:hover {{ color: #00d4ff; }}"
        )

    # ── Engine lifecycle ──────────────────────────────────────────────────────

    def _load_webengine(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            from PySide6 import QtWebEngineWidgets
            self._web = QtWebEngineWidgets.QWebEngineView(self)
            # Transparent WebEngine page background
            self._web.page().setBackgroundColor(QtGui.QColor(0, 0, 0, 0))
            self._web.setStyleSheet("background: transparent;")
            self._web.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

            if _FLOAT_HTML.exists():
                self._web.setUrl(QtCore.QUrl.fromLocalFile(str(_FLOAT_HTML)))
            else:
                self._web.setHtml(
                    "<body style='background:transparent;color:#00ffcc'>Avatar HTML missing</body>"
                )

            # Replace placeholder with live WebView
            layout = self.layout()
            layout.removeWidget(self._viewport_placeholder)
            self._viewport_placeholder.hide()
            # Insert after control strip (index 0), before grip (last)
            layout.insertWidget(1, self._web)

        except Exception as e:
            self._viewport_placeholder.setText(f"Avatar engine error:\n{e}")
            self._viewport_placeholder.show()

    def unload_engine(self) -> None:
        """Release WebEngine and reclaim RAM."""
        if self._web:
            self._web.setUrl(QtCore.QUrl("about:blank"))
            self.layout().removeWidget(self._web)
            self._web.deleteLater()
            self._web = None
        self._loaded = False
        self._viewport_placeholder.setText("Avatar unloaded. Call show_avatar() to reload.")
        self._viewport_placeholder.show()

    # ── Public show/hide ──────────────────────────────────────────────────────

    def show_avatar(self) -> None:
        """Show the floating avatar, loading WebEngine if needed."""
        self._load_webengine()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_avatar(self) -> None:
        self.hide()

    # ── Public API (mirrors AvatarViewport) ───────────────────────────────────

    def _js(self, code: str) -> None:
        if self._web:
            self._web.page().runJavaScript(code)

    def set_state(self, idx: int) -> None:
        try:
            clean_idx = max(0, min(int(idx), 5))
        except (ValueError, TypeError):
            clean_idx = 0
        state_names = ['IDLE', 'TALKING', 'SEARCHING', 'WALKING', 'GESTURING', 'THINKING']
        self._js(f"setAvatarState({clean_idx}, {json.dumps(state_names[clean_idx])})")

    def set_name(self, name: str) -> None:
        clean_name = name or "PIRATE LLAMA"
        self._js(f"setAvatarName({json.dumps(clean_name)})")

    def set_speaking(self, val: bool) -> None:
        self._js(f"setSpeakingState({'true' if val else 'false'})")

    def set_listening(self, val: bool) -> None:
        self.set_state(1 if val else 0)

    def set_agent_tool(self, tool_name: str, args_str: str = "") -> None:
        """Drive avatar gestures from agent tool calls."""
        clean_tool = tool_name or ""
        clean_args = (args_str or "")[:60]
        self._js(f"setAgentToolCall({json.dumps(clean_tool)}, {json.dumps(clean_args)})")

    # ── Drag to move ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == QtCore.Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.buttons() & QtCore.Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None

    # ── Hover → show/hide control strip ──────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._ctrl_strip.show()

    def leaveEvent(self, event) -> None:
        self._ctrl_strip.hide()

    # ── Context menu ─────────────────────────────────────────────────────────

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #080e1a; color: #dde6f0; border: 1px solid rgba(0,200,255,0.2); }"
            "QMenu::item:selected { background: rgba(0,200,255,0.15); }"
        )
        menu.addAction("📌 Toggle Always on Top", self._toggle_pin_action)
        menu.addAction("🔄 Reload Avatar",        lambda: self._reload())
        menu.addAction("🗑️ Unload Engine (Free RAM)", self.unload_engine)
        menu.addSeparator()
        menu.addAction("✕ Hide",                  self.hide_avatar)
        menu.exec(pos)

    def _toggle_pin(self, pinned: bool) -> None:
        flags = self.windowFlags()
        if pinned:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        else:
            flags &= ~QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _toggle_pin_action(self) -> None:
        flags = self.windowFlags()
        pinned = bool(flags & QtCore.Qt.WindowStaysOnTopHint)
        self._toggle_pin(not pinned)

    def _reload(self) -> None:
        self.unload_engine()
        self._load_webengine()

    # ── Paint transparent background ──────────────────────────────────────────

    def paintEvent(self, event) -> None:
        # Required for WA_TranslucentBackground to work — paint nothing (transparent)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 0))
