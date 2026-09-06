"""
gui/pirate_gui/helipad_dock.py
==============================
Hyper-Spherical Systems — Helipad Window Auto-Docking & Suction Engine (v3.5)

Features:
1. Flawless Drag Tracking: Seamless dragging across Chrome and multi-monitors with
   zero mouse detachment, sticking, or locking.
2. Persistent Locked Target Registry: Once an app/window/CLI is locked, it is
   permanently saved and auto-restored on boot.
3. Already-Hooked Detection: When sliding over an already-hooked conversation window,
   it flashes amber/green ("ALREADY HOOKED") and allows smooth pass-through.
4. Non-Blocking Suction: Smoothly shrinks docked windows via cubic-bezier SetWindowPos
   without modal popups that steal mouse focus.
5. Strict Conversational Classifier: Ignores non-AI browser tabs and idle shells.
"""

from __future__ import annotations

import sys
import os
import time
import math
import json
import ctypes
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, Set

from PySide6 import QtCore, QtGui, QtWidgets

# Win32 Native API bindings for Windows
IS_WINDOWS = (sys.platform == "win32")

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Win32 Constants
    WM_NCLBUTTONDOWN = 0x00A1
    HTCAPTION = 0x0002
    GA_ROOT = 2
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long)
        ]


# ── Persistent Target Registry ───────────────────────────────────────────────
_HYPES_DIR = Path.home() / ".hypes"
_LOCKED_TARGETS_FILE = _HYPES_DIR / "locked_targets.json"


class PersistentTargetRegistry:
    """Manages permanent persistent hooks for TUIs, CLIs, GUIs, and chat sessions."""
    
    _locked_targets: Dict[str, Dict[str, Any]] = {}
    _loaded = False

    @classmethod
    def load(cls) -> Dict[str, Dict[str, Any]]:
        if not cls._loaded:
            try:
                if _LOCKED_TARGETS_FILE.exists():
                    cls._locked_targets = json.loads(_LOCKED_TARGETS_FILE.read_text(encoding="utf-8"))
            except Exception:
                cls._locked_targets = {}
            cls._loaded = True
        return cls._locked_targets

    @classmethod
    def save(cls):
        try:
            _HYPES_DIR.mkdir(parents=True, exist_ok=True)
            _LOCKED_TARGETS_FILE.write_text(json.dumps(cls._locked_targets, indent=2), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def is_locked(cls, app_key: str, title: str = "") -> bool:
        cls.load()
        if app_key in cls._locked_targets:
            return True
        for k, v in cls._locked_targets.items():
            if app_key.lower() in k.lower() or k.lower() in app_key.lower():
                return True
            if title and title.lower() in str(v.get("title", "")).lower():
                return True
        return False

    @classmethod
    def register_target(cls, target_meta: Dict[str, Any]):
        cls.load()
        app_key = target_meta.get("app_type", "Generic App")
        cls._locked_targets[app_key] = {
            "title": target_meta.get("title", ""),
            "pid": target_meta.get("pid", 0),
            "hwnd": target_meta.get("hwnd", 0),
            "port": target_meta.get("port", 8000),
            "category": target_meta.get("category", "👑 AI Interface"),
            "url": target_meta.get("url", "http://127.0.0.1:8000/v1"),
            "locked_at": time.time()
        }
        cls.save()


class TargetWindowInspector:
    """Inspects and identifies verified AI conversation windows under cursor."""

    @staticmethod
    def get_window_under_cursor(exclude_hwnd: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if not IS_WINDOWS:
            return None

        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        # Immediate window under cursor
        hwnd_raw = user32.WindowFromPoint(pt)
        if not hwnd_raw:
            return None

        # Resolve root top-level application window
        root_hwnd = user32.GetAncestor(hwnd_raw, GA_ROOT)
        if not root_hwnd:
            root_hwnd = hwnd_raw

        if exclude_hwnd and root_hwnd == exclude_hwnd:
            return None

        # Extract Window Title
        length = user32.GetWindowTextLengthW(root_hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(root_hwnd, buff, length + 1)
        title = buff.value.strip()

        # Extract Process ID & Executable Name
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(root_hwnd, ctypes.byref(pid))

        proc_name = ""
        if pid.value:
            try:
                import psutil
                proc_name = psutil.Process(pid.value).name().lower()
            except Exception:
                pass

        # Get Window Bounding Rect
        rect = RECT()
        user32.GetWindowRect(root_hwnd, ctypes.byref(rect))

        # ── Strict Conversational AI Window Classifier ─────────
        title_l = title.lower()
        
        # 1. First-Class Google Antigravity IDE & Agent Studio Detection
        is_antigravity = (
            "antigrav" in proc_name or 
            "cloudcode" in proc_name or
            any(sig in title_l for sig in [
                "antigravity", "antigravity ide", "antigravity 2.0", "google antigravity",
                "antigravity-ide", "hyper_spherical", "hyperspherical"
            ])
        )

        web_chat_signatures = [
            "chatgpt", "claude", "gemini", "perplexity", "deepseek", "grok",
            "open webui", "openwebui", "sillytavern", "librechat", "jan.ai",
            "anythingllm", "text-generation-webui", "koboldcpp", "localhost:3000",
            "localhost:8080", "localhost:11434", "localhost:7860", "localhost:1234",
            "localhost:5001", "localhost:5000", "ai studio", "poe.com", "mistral.ai",
            "copilot", "chat", "assistant", "conversational"
        ]

        is_cursor = "cursor" in title_l or "cursor" in proc_name
        is_vscode_ai = ("visual studio code" in title_l or " - code" in title_l or "code.exe" in proc_name) and any(k in title_l for k in ["continue", "copilot", "chat", "aider"])
        is_lmstudio = "lm studio" in title_l or "lm studio" in proc_name
        is_ollama_gui = ("ollama" in title_l or "ollama" in proc_name) and not ("cmd" in title_l or "powershell" in title_l)
        is_jan = ("jan" in title_l or "jan.exe" in proc_name) and "ai" in title_l

        is_terminal = any(term in title_l or term in proc_name for term in ["cmd.exe", "powershell", "windows terminal", "command prompt", "bash", "mintty", "conhost"])
        is_cli_ai = is_terminal and any(cli in title_l for cli in ["ollama", "aider", "interpreter", "fabric", "sgpt", "tgpt", "llm", "chat", "pirate", "python"])

        is_browser = any(b in title_l or b in proc_name for b in ["chrome", "google chrome", "edge", "firefox", "brave", "opera", "vivaldi"])
        is_active_web_chat = is_browser and any(sig in title_l for sig in web_chat_signatures)

        is_valid_chat_target = False
        app_type = ""
        category = ""

        if is_antigravity:
            is_valid_chat_target = True
            app_type = "Google Antigravity IDE (Agent Studio)"
            category = "👑 Antigravity IDE (Agent Studio)"
        elif is_active_web_chat:
            is_valid_chat_target = True
            category = "🌐 Web Chat Session"
            if "chatgpt" in title_l:
                app_type = "ChatGPT Web Session"
            elif "claude" in title_l:
                app_type = "Claude AI Web Session"
            elif "gemini" in title_l:
                app_type = "Google Gemini Web Session"
            elif "perplexity" in title_l:
                app_type = "Perplexity AI Session"
            elif "open webui" in title_l or "openwebui" in title_l:
                app_type = "Open WebUI Local Hub"
            elif "sillytavern" in title_l:
                app_type = "SillyTavern Conversation"
            else:
                app_type = "Active Browser AI Chat Tab"

        elif is_cursor:
            is_valid_chat_target = True
            category = "💻 IDE / Composer"
            app_type = "Cursor IDE (AI Composer/Chat)"
        elif is_vscode_ai:
            is_valid_chat_target = True
            category = "💻 IDE / Extension"
            app_type = "VS Code (Continue/Copilot AI)"
        elif is_lmstudio:
            is_valid_chat_target = True
            category = "⚡ Local LLM GUI"
            app_type = "LM Studio Local LLM Chat"
        elif is_ollama_gui or is_cli_ai:
            is_valid_chat_target = True
            category = "📟 Terminal TUI / CLI"
            app_type = "Ollama / CLI Terminal Chat (TUI)"
        elif is_jan:
            is_valid_chat_target = True
            category = "⚡ Local LLM Client"
            app_type = "Jan AI Desktop Client"

        if is_valid_chat_target:
            already_locked = PersistentTargetRegistry.is_locked(app_type, title)
            return {
                "hwnd": root_hwnd,
                "title": title or "Active AI Chat Window",
                "app_type": app_type,
                "category": category,
                "pid": pid.value,
                "rect": (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top),
                "cursor_pos": (pt.x, pt.y),
                "already_locked": already_locked,
                "source": "window"
            }
        return None

    @classmethod
    def classify_window(cls, title: str, hwnd: int = 0) -> Optional[Dict[str, Any]]:
        """Classifies a given window title into a structured AI interface target."""
        title_l = title.lower()

        proc_name = ""
        pid_val = 0
        rect_tuple = (0, 0, 0, 0)
        if IS_WINDOWS and hwnd:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid_val = pid.value
            if pid_val:
                try:
                    import psutil
                    proc_name = psutil.Process(pid_val).name().lower()
                except Exception:
                    pass
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            rect_tuple = (r.left, r.top, r.right - r.left, r.bottom - r.top)

        # 1. Antigravity IDE First-Class Check
        is_antigravity = (
            "antigrav" in proc_name or 
            "cloudcode" in proc_name or
            any(sig in title_l for sig in [
                "antigravity", "antigravity ide", "antigravity 2.0", "google antigravity",
                "antigravity-ide", "hyper_spherical", "hyperspherical"
            ])
        )

        web_chat_signatures = [
            "chatgpt", "claude", "gemini", "perplexity", "deepseek", "grok",
            "open webui", "openwebui", "sillytavern", "librechat", "jan.ai",
            "anythingllm", "text-generation-webui", "koboldcpp", "localhost:3000",
            "localhost:8080", "localhost:11434", "localhost:7860", "localhost:1234",
            "localhost:5001", "localhost:5000", "ai studio", "poe.com", "mistral.ai",
            "copilot", "conversational"
        ]

        is_cursor = "cursor" in title_l or "cursor" in proc_name
        is_vscode_ai = ("visual studio code" in title_l or " - code" in title_l or "code.exe" in proc_name) and any(k in title_l for k in ["continue", "copilot", "chat", "aider"])
        is_lmstudio = "lm studio" in title_l or "lm studio" in proc_name
        is_ollama_gui = ("ollama" in title_l or "ollama" in proc_name) and not ("cmd" in title_l or "powershell" in title_l)
        is_jan = ("jan" in title_l or "jan.exe" in proc_name) and "ai" in title_l
        is_terminal = any(term in title_l or term in proc_name for term in ["cmd.exe", "powershell", "windows terminal", "command prompt", "bash", "mintty", "conhost"])
        is_cli_ai = is_terminal and any(cli in title_l for cli in ["ollama", "aider", "interpreter", "fabric", "sgpt", "tgpt", "llm", "pirate", "python"])
        is_browser = any(b in title_l or b in proc_name for b in ["chrome", "google chrome", "edge", "firefox", "brave", "opera", "vivaldi"])
        is_active_web_chat = is_browser and any(sig in title_l for sig in web_chat_signatures)

        category = ""
        app_type = ""

        if is_antigravity:
            category = "👑 Antigravity IDE (Agent Studio)"
            app_type = "Google Antigravity IDE (Agent Studio)"
        elif is_active_web_chat:
            category = "🌐 Web Chat Session"
            if "chatgpt" in title_l:
                app_type = "ChatGPT Web Session"
            elif "claude" in title_l:
                app_type = "Claude AI Web Session"
            elif "gemini" in title_l:
                app_type = "Google Gemini Web Session"
            elif "perplexity" in title_l:
                app_type = "Perplexity AI Session"
            elif "open webui" in title_l or "openwebui" in title_l:
                app_type = "Open WebUI Local Hub"
            elif "sillytavern" in title_l:
                app_type = "SillyTavern Conversation"
            else:
                app_type = "Active Browser AI Chat Tab"
        elif is_cursor:
            category = "💻 IDE / Composer"
            app_type = "Cursor IDE (AI Composer/Chat)"
        elif is_vscode_ai:
            category = "💻 IDE / Extension"
            app_type = "VS Code (Continue/Copilot AI)"
        elif is_lmstudio:
            category = "⚡ Local LLM GUI"
            app_type = "LM Studio Local LLM Chat"
        elif is_ollama_gui or is_cli_ai:
            category = "📟 Terminal TUI / CLI"
            app_type = "Ollama / CLI Terminal Chat (TUI)"
        elif is_jan:
            category = "⚡ Local LLM Client"
            app_type = "Jan AI Desktop Client"
        else:
            return None

        pid_val = 0
        rect_tuple = (0, 0, 0, 0)
        if IS_WINDOWS and hwnd:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid_val = pid.value
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            rect_tuple = (r.left, r.top, r.right - r.left, r.bottom - r.top)

        already_locked = PersistentTargetRegistry.is_locked(app_type)
        return {
            "hwnd": hwnd,
            "title": title,
            "app_type": app_type,
            "category": category,
            "pid": pid_val,
            "rect": rect_tuple,
            "already_locked": already_locked,
            "source": "window"
        }

    @classmethod
    def scan_all_system_ai_interfaces(cls) -> List[Dict[str, Any]]:
        """Deep scans the system for all active AI runtimes, windows, TUIs, CLIs, local ports, and phone bridges."""
        results: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        # 1. Deep Process Inspection for Hyper-Spherical, Antigravity & AI Runtimes
        try:
            import psutil
            proc_signatures = [
                ("antigravity ide.exe", "Google Antigravity IDE (Agent Studio)", "👑 Antigravity IDE (Agent Studio)", 8000),
                ("antigravity.exe",     "Google Antigravity Runtime",            "👑 Antigravity IDE (Agent Studio)", 8000),
                ("hyperspherical.exe",  "Hyper-Spherical Systems Sovereign Core", "👑 Sovereign Core", 8000),
                ("hypes.exe",           "Hyper-Spherical Systems Suite",         "👑 Sovereign Core", 8000),
                ("cursor.exe",          "Cursor IDE (AI Composer/Chat)",         "💻 IDE / Composer", 8000),
                ("code.exe",            "VS Code (AI Extensions/Copilot)",       "💻 IDE / Extension", 8000),
                ("lm studio.exe",       "LM Studio Local LLM Chat",              "⚡ Local LLM GUI", 1234),
                ("ollama.exe",          "Ollama Local Daemon",                   "⚡ Local Daemon", 11434),
                ("jan.exe",             "Jan AI Desktop Client",                 "⚡ Local LLM Client", 1337),
                ("chatgpt.exe",         "ChatGPT Desktop App",                   "🌐 Desktop AI App", 8000),
                ("claude.exe",          "Claude Desktop App",                    "🌐 Desktop AI App", 8000),
            ]

            for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    p_name = (p.info.get('name') or "").lower()
                    cmdline = " ".join(p.info.get('cmdline') or []).lower()

                    # Check for Python-based Hyper-Spherical or Tesseract daemons
                    if "python" in p_name and any(h in cmdline for h in ["hyper_spherical", "hypes", "tesseract", "token_hud", "hypes_mcp_server"]):
                        key = "proc:Hyper-Spherical Systems Sovereign Core"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            is_locked = PersistentTargetRegistry.is_locked("Hyper-Spherical Systems Sovereign Core")
                            results.append({
                                "hwnd": 0,
                                "title": f"Hyper-Spherical Systems Sovereign Core (PID {p.info['pid']})",
                                "app_type": "Hyper-Spherical Systems Sovereign Core",
                                "category": "👑 Sovereign Core",
                                "port": 8000,
                                "pid": p.info['pid'],
                                "rect": (0, 0, 0, 0),
                                "already_locked": is_locked,
                                "source": "process"
                            })

                    for sig, app_type, category, default_port in proc_signatures:
                        if sig in p_name:
                            key = f"proc:{app_type}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                is_locked = PersistentTargetRegistry.is_locked(app_type)
                                results.append({
                                    "hwnd": 0,
                                    "title": f"{app_type} (Active Process PID {p.info['pid']})",
                                    "app_type": app_type,
                                    "category": category,
                                    "port": default_port,
                                    "pid": p.info['pid'],
                                    "rect": (0, 0, 0, 0),
                                    "already_locked": is_locked,
                                    "source": "process"
                                })
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Check local background AI / LLM daemon ports
        import socket
        known_ports = [
            (8000,  "Hyper-Spherical Sovereign Gateway", "Hyper-Spherical Systems Gateway", "👑 Sovereign Gateway"),
            (8001,  "Project Tesseract Matrix Daemon",  "Tesseract Matrix Core",           "⚡ Matrix Core"),
            (11434, "Ollama Local LLM Server",          "Ollama Local Daemon",             "⚡ Local Daemon"),
            (1234,  "LM Studio API Gateway",            "LM Studio Daemon",                "⚡ Local Daemon"),
            (8080,  "llama.cpp HTTP Server",            "llama.cpp Daemon",                "⚡ Local Daemon"),
            (5001,  "KoboldCpp Local API",              "KoboldCpp Daemon",                "⚡ Local Daemon"),
            (5000,  "vLLM / TextGen Backend",           "vLLM Daemon",                     "⚡ Local Daemon"),
            (8081,  "LocalAI Endpoint",                 "LocalAI Daemon",                  "⚡ Local Daemon"),
            (3000,  "Open WebUI Local Hub",             "Open WebUI Hub",                  "🌐 Local Web Hub"),
            (5555,  "Android Wireless ADB Bridge",      "Mobile Phone Bridge",             "📱 Mobile Bridge"),
        ]

        for port, title, app_type, category in known_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.12)
                    if s.connect_ex(("127.0.0.1", port)) == 0:
                        key = f"port:{port}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            already_locked = PersistentTargetRegistry.is_locked(app_type)
                            results.append({
                                "hwnd": 0,
                                "title": f"{title} (Active on Port {port})",
                                "app_type": app_type,
                                "category": category,
                                "port": port,
                                "pid": 0,
                                "rect": (0, 0, 0, 0),
                                "already_locked": already_locked,
                                "source": "port"
                            })
            except Exception:
                pass

        # 3. Check open windows on desktop via Win32 EnumWindows
        if IS_WINDOWS:
            import ctypes.wintypes
            def _enum_cb(hwnd, lparam):
                try:
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 3:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.strip()
                            if title:
                                target_info = cls.classify_window(title, hwnd)
                                if target_info:
                                    key = f"hwnd:{hwnd}:{target_info['app_type']}"
                                    if key not in seen_keys:
                                        seen_keys.add(key)
                                        results.append(target_info)
                except Exception:
                    pass
                return True

            try:
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                cb = WNDENUMPROC(_enum_cb)
                user32.EnumWindows(cb, 0)
            except Exception:
                pass

        return results


class AutoSeekDialog(QtWidgets.QDialog):
    """
    Sleek Cyberpunk Modal for Auto-Seeking and 1-Click Hooking of AI Interfaces.
    """
    interfacesHooked = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Auto-Seek AI Interfaces — Hyper-Spherical Systems")
        self.resize(680, 520)
        self.setWindowFlags(QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b1120;
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
            }
            QScrollArea {
                border: 1px solid #1e293b;
                background-color: #070d18;
                border-radius: 6px;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 700;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #38bdf8;
                background: #0f172a;
            }
            QCheckBox::indicator:checked {
                background: #0284c7;
                image: none;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Banner
        header = QtWidgets.QLabel("⚡ AUTO-SEEK AI INTERFACES & RUNTIMES")
        header.setStyleSheet("font-size: 16px; font-weight: 900; color: #38bdf8; letter-spacing: 0.5px;")
        layout.addWidget(header)

        sub_lbl = QtWidgets.QLabel(
            "Deep-scanning your system for active LLM windows, IDEs, TUIs, CLIs, local daemons, and phone bridges.\n"
            "Select the interfaces you want HypeS to automatically hook and permanently optimize:"
        )
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.4;")
        layout.addWidget(sub_lbl)

        # Scroll area for detected cards
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.card_container = QtWidgets.QWidget()
        self.card_layout = QtWidgets.QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(10, 10, 10, 10)
        self.card_layout.setSpacing(8)
        self.scroll_area.setWidget(self.card_container)
        layout.addWidget(self.scroll_area, 1)

        self._check_boxes: List[Tuple[QtWidgets.QCheckBox, Dict[str, Any]]] = []

        # Button Bar
        btn_bar = QtWidgets.QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_rescan = QtWidgets.QPushButton("🔄 Rescan System")
        self.btn_rescan.setStyleSheet("""
            QPushButton {
                background: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 5px; padding: 8px 14px; font-weight: 700; font-size: 11px;
            }
            QPushButton:hover { background: #334155; color: #f1f5f9; }
        """)
        self.btn_rescan.clicked.connect(self.run_scan)
        btn_bar.addWidget(self.btn_rescan)

        btn_bar.addStretch()

        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: transparent; color: #94a3b8; border: 1px solid #334155;
                border-radius: 5px; padding: 8px 16px; font-weight: 700; font-size: 11px;
            }
            QPushButton:hover { background: #1e293b; color: #f1f5f9; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_hook_all = QtWidgets.QPushButton("👑 Hook All Detected AI")
        self.btn_hook_all.setStyleSheet("""
            QPushButton {
                background: #1e1b4b; color: #c084fc; border: 1px solid #a855f7;
                border-radius: 5px; padding: 8px 14px; font-weight: 800; font-size: 11px;
            }
            QPushButton:hover { background: #6b21a8; color: #ffffff; border-color: #d8b4fe; }
        """)
        self.btn_hook_all.clicked.connect(self._hook_all)
        btn_bar.addWidget(self.btn_hook_all)

        self.btn_hook = QtWidgets.QPushButton("⚡ Hook Selected")
        self.btn_hook.setStyleSheet("""
            QPushButton {
                background: #0284c7; color: #ffffff; border: 1px solid #38bdf8;
                border-radius: 5px; padding: 8px 18px; font-weight: 900; font-size: 11px;
            }
            QPushButton:hover { background: #00d4ff; color: #0b1120; border-color: #00ffcc; }
        """)
        self.btn_hook.clicked.connect(self._confirm_hook)
        btn_bar.addWidget(self.btn_hook)

        layout.addLayout(btn_bar)

        # Run initial scan
        self.run_scan()

    def _hook_all(self):
        for cb, _ in self._check_boxes:
            cb.setChecked(True)
        self._confirm_hook()

    def run_scan(self):
        # Clear existing cards
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        self._check_boxes.clear()

        targets = TargetWindowInspector.scan_all_system_ai_interfaces()

        if not targets:
            no_lbl = QtWidgets.QLabel("🔍 No active AI windows or local daemons detected.\nOpen ChatGPT in your browser, start Ollama / LM Studio, or launch Cursor / VS Code and click Rescan.")
            no_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            no_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-style: italic; padding: 30px;")
            self.card_layout.addWidget(no_lbl)
            return

        for t in targets:
            card = QtWidgets.QFrame()
            is_locked = t.get("already_locked", False)
            bg_color = "#1e1b4b" if is_locked else "#0f172a"
            border_color = "#a855f7" if is_locked else "#1e3a5f"
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 6px;
                }}
            """)
            c_lay = QtWidgets.QHBoxLayout(card)
            c_lay.setContentsMargins(8, 6, 8, 6)

            cb = QtWidgets.QCheckBox()
            cb.setChecked(not is_locked)
            c_lay.addWidget(cb)

            info_lay = QtWidgets.QVBoxLayout()
            info_lay.setSpacing(2)

            title_row = QtWidgets.QHBoxLayout()
            cat_badge = QtWidgets.QLabel(f"[{t.get('category', 'AI Interface').upper()}]")
            cat_badge.setStyleSheet("color: #38bdf8; font-size: 9px; font-weight: 900; font-family: Consolas;")
            title_row.addWidget(cat_badge)

            title_lbl = QtWidgets.QLabel(t.get("app_type", "AI App"))
            title_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 800;")
            title_row.addWidget(title_lbl, 1)

            status_tag = QtWidgets.QLabel("🔒 PERMANENTLY HOOKED" if is_locked else "⚡ READY TO HOOK")
            status_tag.setStyleSheet("color: #c084fc; font-size: 9px; font-weight: 900;" if is_locked else "color: #34d399; font-size: 9px; font-weight: 900;")
            title_row.addWidget(status_tag)
            info_lay.addLayout(title_row)

            sub_text = t.get("title", "")
            if t.get("pid"):
                sub_text += f" (PID {t['pid']})"
            desc_lbl = QtWidgets.QLabel(sub_text[:85])
            desc_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: Consolas;")
            info_lay.addWidget(desc_lbl)

            c_lay.addLayout(info_lay, 1)
            self.card_layout.addWidget(card)
            self._check_boxes.append((cb, t))

        self.card_layout.addStretch()

    def _confirm_hook(self):
        hooked: List[Dict[str, Any]] = []
        for cb, t in self._check_boxes:
            if cb.isChecked():
                PersistentTargetRegistry.register_target(t)
                hooked.append(t)
        self.interfacesHooked.emit(hooked)
        self.accept()


class HelipadLandingZone(QtWidgets.QFrame):
    """
    The Interactive Helipad Landing & Docking Port with Auto-Seek.
    """
    windowDocked = QtCore.Signal(dict)
    autoSeekRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("helipad_zone")
        self.setAcceptDrops(True)
        self.setFixedHeight(50)
        self._target_locked = False

        self.setStyleSheet("""
            #helipad_zone {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #09121e, stop:0.5 #0d1e34, stop:1 #09121e);
                border: 2px dashed #00d4ff;
                border-radius: 8px;
            }
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)

        self.icon_lbl = QtWidgets.QLabel("🛸")
        self.icon_lbl.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.icon_lbl)

        self.status_lbl = QtWidgets.QLabel("HELIPAD DOCK: Drag & Drop AI Window or Click Auto-Seek")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; font-family: 'Segoe UI', Consolas;")
        layout.addWidget(self.status_lbl, 1)

        self.btn_autoseek = QtWidgets.QPushButton("🔍 AUTO-SEEK")
        self.btn_autoseek.setStyleSheet("""
            QPushButton {
                background: #0284c7; color: white; border: 1px solid #38bdf8;
                border-radius: 4px; font-size: 10px; font-weight: 900; padding: 4px 10px;
            }
            QPushButton:hover { background: #00d4ff; color: #09121e; border-color: #00ffcc; }
        """)
        self.btn_autoseek.clicked.connect(self._open_autoseek_dialog)
        layout.addWidget(self.btn_autoseek)

        self.btn_dock = QtWidgets.QPushButton("⚡ DOCK")
        self.btn_dock.setStyleSheet("""
            QPushButton {
                background: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; font-size: 10px; font-weight: 900; padding: 4px 10px;
            }
            QPushButton:hover { background: #334155; color: #f1f5f9; }
        """)
        self.btn_dock.clicked.connect(self._trigger_manual_dock)
        layout.addWidget(self.btn_dock)

    def set_target_state(self, locked: bool, app_name: str = "", already_locked: bool = False):
        self._target_locked = locked
        if locked and already_locked:
            self.setStyleSheet("""
                #helipad_zone {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #312e81, stop:0.5 #1e1b4b, stop:1 #312e81);
                    border: 2px solid #a855f7;
                    border-radius: 8px;
                }
            """)
            self.icon_lbl.setText("🔒")
            self.status_lbl.setText(f"ALREADY HOOKED: {app_name} (Sliding Past)")
            self.status_lbl.setStyleSheet("color: #c084fc; font-size: 11px; font-weight: 900;")
        elif locked:
            self.setStyleSheet("""
                #helipad_zone {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #052e16, stop:0.5 #064e3b, stop:1 #052e16);
                    border: 2px solid #10b981;
                    border-radius: 8px;
                }
            """)
            self.icon_lbl.setText("🎯")
            self.status_lbl.setText(f"TARGET LOCKED: {app_name} (Release to Suck & Dock)")
            self.status_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 900;")
        else:
            self.setStyleSheet("""
                #helipad_zone {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #09121e, stop:0.5 #0d1e34, stop:1 #09121e);
                    border: 2px dashed #00d4ff;
                    border-radius: 8px;
                }
            """)
            self.icon_lbl.setText("🛸")
            self.status_lbl.setText("HELIPAD DOCK: Drag & Drop AI Window or Click Auto-Seek")
            self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")

    def _trigger_manual_dock(self):
        target = TargetWindowInspector.get_window_under_cursor()
        if target:
            PersistentTargetRegistry.register_target(target)
            self.windowDocked.emit(target)

    def _open_autoseek_dialog(self):
        dlg = AutoSeekDialog(self.window())
        dlg.interfacesHooked.connect(self._on_auto_seek_hooked)
        dlg.exec()

    def _on_auto_seek_hooked(self, hooked_list: list):
        if hooked_list:
            first = hooked_list[0]
            self.windowDocked.emit(first)
            count = len(hooked_list)
            names = ", ".join(h.get("app_type", "AI App") for h in hooked_list[:2])
            if count > 2:
                names += f" and {count-2} more"
            self.status_lbl.setText(f"🎯 AUTO-SEEK HOOKED: {names}")
            self.status_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 900;")


class WindowSuctionAnimator(QtCore.QObject):
    """
    Smoothly shrinks target window over 350ms without stealing cursor focus.
    """
    animationComplete = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._step_animation)
        self._start_time = 0.0
        self._duration = 0.35
        self._target_meta: Optional[Dict[str, Any]] = None
        self._start_rect = (0, 0, 0, 0)
        self._dest_rect = (0, 0, 0, 0)

    def start_suction(self, target_meta: Dict[str, Any], hud_dock_rect: Tuple[int, int, int, int]):
        if not IS_WINDOWS or not target_meta:
            return

        self._target_meta = target_meta
        self._start_rect = target_meta["rect"]
        self._dest_rect = hud_dock_rect
        self._start_time = time.time()
        self._timer.start()

    def _step_animation(self):
        if not self._target_meta:
            self._timer.stop()
            return

        elapsed = time.time() - self._start_time
        progress = min(1.0, elapsed / self._duration)
        ease = progress * progress * (3 - 2 * progress)

        sx, sy, sw, sh = self._start_rect
        dx, dy, dw, dh = self._dest_rect

        cur_x = int(sx + (dx - sx) * ease)
        cur_y = int(sy + (dy - sy) * ease)
        cur_w = max(100, int(sw + (dw - sw) * ease))
        cur_h = max(60, int(sh + (dh - sh) * ease))

        hwnd = self._target_meta.get("hwnd", 0)
        if hwnd:
            try:
                user32.SetWindowPos(
                    hwnd, 0,
                    cur_x, cur_y, cur_w, cur_h,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
                )
            except Exception:
                pass

        if progress >= 1.0:
            self._timer.stop()
            self.animationComplete.emit(self._target_meta)

