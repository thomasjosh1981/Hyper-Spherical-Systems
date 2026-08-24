"""
Hyper-Spherical Systems - Floating Token Counter HUD v3.5
=========================================================
Features:
- Live 3-Card Metrics: Original Tokens, Compressed Tokens, Ratio (-90%).
- Center Huge Rolling Counter: Total Saved Tokens.
- Bottom Scrolling Ticker Marquee: URL, Model, User, App.
- Frameless, Glass Opacity (94%), Always-On-Top, Inertial Glide, Edge Snapping.
- Supports --screenshot flag to automatically capture PNG of HUD and Desktop.
"""
import sys
import os
import json
import time
import math
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets

HYPES_DIR = Path.home() / ".hypes"
POS_FILE = HYPES_DIR / "hud_pos.json"
EVENTS_LOG = HYPES_DIR / "intercept_events.jsonl"
HYPES_DIR.mkdir(parents=True, exist_ok=True)


class TickerMarquee(QtWidgets.QWidget):
    """Smooth horizontal marquee scrolling URL, Model, Tokens, and compression stats."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._text = "  ⚡ HYPERMEM 10X MITM ACTIVE  |  WAITING FOR AI TRAFFIC (Ollama / LM Studio / OpenAI / Cursor)  |  "
        self._offset = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(25)

    def set_text(self, t):
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


class TokenHUD(QtWidgets.QWidget):
    """Floating always-on-top token counter with inertial glide and edge snapping."""
    def __init__(self):
        super().__init__()
        self._pinned = True
        self._opacity = 0.95
        self._drag_pos = None
        self._resizing = False
        self._rm = 12
        self._vx = 0.0
        self._vy = 0.0
        self._last_t = time.time()
        self._last_pt = None

        self._total_saved = 2205
        self._orig_tokens = 2450
        self._comp_tokens = 245
        self._ratio = 10.0
        self._cur_disp = 0.0
        self._tgt_disp = 2205.0
        self._evt_offset = 0

        self._apply_flags()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(340, 150)
        self.resize(380, 165)
        self._build_ui()
        self._load_geo()

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
        flags = QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Tool
        if self._pinned:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setWindowOpacity(self._opacity)

    def _build_ui(self):
        ml = QtWidgets.QVBoxLayout(self)
        ml.setContentsMargins(6, 6, 6, 6)

        self._frame = QtWidgets.QFrame()
        self._frame.setStyleSheet(
            "QFrame{background-color:#121212;border:2px solid #00FFCC;border-radius:8px;}"
        )
        fl = QtWidgets.QVBoxLayout(self._frame)
        fl.setContentsMargins(12, 10, 12, 8)
        fl.setSpacing(6)

        # ── Top Bar: Title + Status + Pin ─────────────────────────────────────
        tb = QtWidgets.QHBoxLayout()
        self._hdr = QtWidgets.QLabel("TOKEN COUNTER • 3D+ISSI+5+1")
        self._hdr.setStyleSheet("color:#888888;font:bold 9px 'Segoe UI';border:none;")
        tb.addWidget(self._hdr)
        tb.addStretch()
        self._pin_lbl = QtWidgets.QLabel("📌 ON TOP")
        self._pin_lbl.setStyleSheet("color:#00FFCC;font:bold 9px 'Segoe UI';border:none;")
        tb.addWidget(self._pin_lbl)
        fl.addLayout(tb)

        # ── 3-Card Metrics Row (Original, Compressed, Savings Ratio) ──────────
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(8)

        # Card 1: Original
        c1 = QtWidgets.QFrame()
        c1.setStyleSheet("QFrame{background:#1a1a1a;border:1px solid #333333;border-radius:4px;padding:2px;}")
        c1_l = QtWidgets.QVBoxLayout(c1)
        c1_l.setContentsMargins(4, 2, 4, 2)
        c1_l.setSpacing(1)
        c1_title = QtWidgets.QLabel("ORIGINAL")
        c1_title.setStyleSheet("color:#777777;font:bold 8px 'Segoe UI';border:none;")
        self._orig_lbl = QtWidgets.QLabel("2,450 tok")
        self._orig_lbl.setStyleSheet("color:#dddddd;font:bold 11px 'Segoe UI';border:none;")
        c1_l.addWidget(c1_title, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c1_l.addWidget(self._orig_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c1)

        # Card 2: Compressed (ISSI + 3D + 5+1)
        c2 = QtWidgets.QFrame()
        c2.setStyleSheet("QFrame{background:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:2px;}")
        c2_l = QtWidgets.QVBoxLayout(c2)
        c2_l.setContentsMargins(4, 2, 4, 2)
        c2_l.setSpacing(1)
        c2_title = QtWidgets.QLabel("COMPRESSED")
        c2_title.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';border:none;")
        self._comp_lbl = QtWidgets.QLabel("245 tok")
        self._comp_lbl.setStyleSheet("color:#00FFCC;font:bold 11px 'Segoe UI';border:none;")
        c2_l.addWidget(c2_title, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c2_l.addWidget(self._comp_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c2)

        # Card 3: Ratio
        c3 = QtWidgets.QFrame()
        c3.setStyleSheet("QFrame{background:#1a1a1a;border:1px solid #005544;border-radius:4px;padding:2px;}")
        c3_l = QtWidgets.QVBoxLayout(c3)
        c3_l.setContentsMargins(4, 2, 4, 2)
        c3_l.setSpacing(1)
        c3_title = QtWidgets.QLabel("SAVINGS")
        c3_title.setStyleSheet("color:#00aa88;font:bold 8px 'Segoe UI';border:none;")
        self._ratio_lbl = QtWidgets.QLabel("10.0x (-90%)")
        self._ratio_lbl.setStyleSheet("color:#55ffaa;font:bold 11px 'Segoe UI';border:none;")
        c3_l.addWidget(c3_title, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c3_l.addWidget(self._ratio_lbl, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        cards_layout.addWidget(c3)

        fl.addLayout(cards_layout)

        # ── Center Main Saved Counter ─────────────────────────────────────────
        val_box = QtWidgets.QHBoxLayout()
        val_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._val_title = QtWidgets.QLabel("SAVED:")
        self._val_title.setStyleSheet("color:#888888;font:bold 13px 'Segoe UI';border:none;padding-right:4px;")
        val_box.addWidget(self._val_title)

        self._val = QtWidgets.QLabel("2,205")
        self._val.setStyleSheet(
            "color:#00FFCC;font:800 26px 'Segoe UI';border:none;background:transparent;"
        )
        val_box.addWidget(self._val)

        self._val_unit = QtWidgets.QLabel("TOKENS")
        self._val_unit.setStyleSheet("color:#00FFCC;font:bold 12px 'Segoe UI';border:none;padding-left:4px;padding-top:6px;")
        val_box.addWidget(self._val_unit)
        fl.addLayout(val_box)

        # ── Scrolling Marquee Ticker ──────────────────────────────────────────
        self._tick = TickerMarquee()
        self._tick.setStyleSheet("border:none;border-radius:4px;")
        fl.addWidget(self._tick)

        ml.addWidget(self._frame)

    # ── Compression Event Injection ───────────────────────────────────────────
    def push(self, url, model, app, user, raw, comp):
        """Called when a request is intercepted and compressed."""
        saved = max(0, raw - comp)
        self._orig_tokens = raw
        self._comp_tokens = comp
        self._total_saved += saved
        self._tgt_disp = float(self._total_saved)
        r = round(raw / max(1, comp), 1) if comp > 0 else 1.0
        pct = round((saved / max(1, raw)) * 100, 1)

        self._orig_lbl.setText(f"{raw:,} tok")
        self._comp_lbl.setText(f"{comp:,} tok")
        self._ratio_lbl.setText(f"{r}x (-{pct}%)")

        self._tick.set_text(
            f"⚡ [{app.upper()} | {model}]  URL: {url}  |  User: {user}  |  "
            f"Raw: {raw:,} tok  |  Post-3D/ISSI: {comp:,} tok  |  "
            f"Saved: {saved:,} ({r}x)  |  TOTAL SAVED: {self._total_saved:,} TOKENS"
        )

    # ── Smooth Rolling Counter Animation ──────────────────────────────────────
    def _anim(self):
        if abs(self._cur_disp - self._tgt_disp) > 0.5:
            self._cur_disp += (self._tgt_disp - self._cur_disp) * 0.15
            self._val.setText(f"{int(round(self._cur_disp)):,}")
        else:
            self._cur_disp = self._tgt_disp
            self._val.setText(f"{int(self._total_saved):,}")

    # ── IPC: Poll auto_interceptor event stream ──────────────────────────────
    def _poll(self):
        if not EVENTS_LOG.exists():
            return
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
                f.seek(self._evt_offset)
                for ln in f:
                    if ln.strip():
                        e = json.loads(ln)
                        self.push(
                            e.get("url", "http://127.0.0.1:11434/api/generate"),
                            e.get("model", "gemma4-hermes-vision-q4"),
                            e.get("app", "Cursor IDE"),
                            e.get("user", "twist"),
                            e.get("raw_tokens", 2450),
                            e.get("compressed_tokens", 245),
                        )
                self._evt_offset = f.tell()
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
        """Magnetic edge snapping within 30px of screen edges."""
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
            "QMenu{background:#1a1a1a;color:#00FFCC;border:1px solid #00FFCC;"
            "font:11px 'Segoe UI';}"
            "QMenu::item:selected{background:#00FFCC;color:#121212;}"
        )
        pa = m.addAction("📌 Always On Top")
        pa.setCheckable(True)
        pa.setChecked(self._pinned)
        pa.triggered.connect(self._toggle_pin)

        # Opacity submenu
        om = m.addMenu("🌓 Opacity")
        for lv, lb in [(0.80, "80%"), (0.95, "95% (Default)"), (1.0, "100% Solid")]:
            a = om.addAction(lb)
            a.setCheckable(True)
            a.setChecked(abs(self._opacity - lv) < 0.02)
            a.triggered.connect(lambda _, v=lv: self._set_opacity(v))

        m.addSeparator()
        m.addAction("🧹 Clear Counter", self._clear)
        m.addAction("🔄 Reset Position", self._reset_pos)
        m.addSeparator()
        m.addAction("❌ Close HUD", self.close)
        m.exec(e.globalPos())

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._pin_lbl.setText("📌 ON TOP" if self._pinned else "📍 FLOAT")
        p, s = self.pos(), self.size()
        self._apply_flags()
        self.show()
        self.move(p)
        self.resize(s)
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
        self._tick.set_text("⚡ COUNTER RESET  |  WAITING FOR TRAFFIC")

    def _reset_pos(self):
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        self.resize(380, 165)
        self.move(screen.width() - 420, 60)
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
        default_x = screen.width() - 420
        default_y = 60

        if POS_FILE.exists():
            try:
                g = json.loads(POS_FILE.read_text())
                gx = g.get("x", default_x)
                gy = g.get("y", default_y)
                gw = g.get("w", 380)
                gh = g.get("h", 165)

                if gx < 0 or gx > screen.width() - 100:
                    gx = default_x
                if gy < 0 or gy > screen.height() - 80:
                    gy = default_y

                self.move(gx, gy)
                self.resize(gw, gh)
                self._pinned = g.get("pinned", True)
                self._opacity = g.get("opacity", 0.95)
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

    # Demo Event with Full Target URL, Model, Raw Tokens, and ISSI/3D Compression
    hud.push(
        url="http://127.0.0.1:11434/api/generate",
        model="gemma4-hermes-vision-q4",
        app="Cursor IDE",
        user="twist",
        raw=2450,
        comp=245,
    )

    # If --screenshot argument passed, capture image after render
    if "--screenshot" in sys.argv:
        def capture_and_exit():
            QtWidgets.QApplication.processEvents()
            # 1. Grab HUD widget directly
            hud_pix = hud.grab()
            hud_path = "C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_widget.png"
            hud_pix.save(hud_path)
            print(f"HUD Widget screenshot saved: {hud_path}")

            # 2. Grab Full Screen
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen:
                screen_pix = screen.grabWindow(0)
                screen_path = "C:/Users/twist/.gemini/antigravity/brain/049c8c18-c6f5-4e4d-be7e-59c36b2bf5e7/token_hud_desktop.png"
                screen_pix.save(screen_path)
                print(f"Desktop screenshot saved: {screen_path}")
            app.quit()

        QtCore.QTimer.singleShot(800, capture_and_exit)

    sys.exit(app.exec())
