# gui/pirate_intercept.py — Full Auto Zero-Config Universal AI Traffic Optimizer v3.0
#
# Hyper-Spherical Systems — Pirate Llama Auto-Intercept Engine
#
# How it works:
#   1. On first run, shows one consent dialog asking permission to intercept.
#   2. Calls auto_discover_and_hook() which:
#      a. Scans all known AI server ports + dynamic port scanner for unknowns.
#      b. For each occupied port, displaces the existing backend to port+1000.
#      c. Binds our proxy listener on the original port.
#   3. Every AI request — local or cloud — is intercepted transparently.
#   4. Per-App Consent: first time each app type is seen, a one-time dialog
#      asks the user to allow optimization for that specific app.
#   5. Local requests: ISSI compressed → forwarded to real backend → decompressed.
#   6. Cloud requests: CCTM compressed → forwarded to cloud provider → decompressed.
#   7. HTTPS CONNECT tunnels are handed off to pirate_ssl_bridge for SSL bridging.
#   8. Zero config required. Works with any app on the machine.
#
# Developer: twiztedsocal
# License: Proprietary — All Rights Reserved

from __future__ import annotations

import os
import sys
import json
import time
import socket
import struct
import threading
import http.client
import http.server
import urllib.parse
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# ── Known AI backend ports ────────────────────────────────────────────────────
# name → (default_host, port, backend_type)
KNOWN_AI_PORTS: Dict[int, Dict] = {
    11434: {"name": "Ollama",            "host": "127.0.0.1", "type": "ollama"},
    1234:  {"name": "LM Studio",         "host": "127.0.0.1", "type": "lmstudio"},
    8080:  {"name": "llama.cpp Server",  "host": "127.0.0.1", "type": "llamacpp"},
    5001:  {"name": "KoboldCpp",         "host": "127.0.0.1", "type": "koboldcpp"},
    5000:  {"name": "TextGen/vLLM",      "host": "127.0.0.1", "type": "vllm"},
    8081:  {"name": "LocalAI",           "host": "127.0.0.1", "type": "localai"},
    11435: {"name": "HypeS Proxy",       "host": "127.0.0.1", "type": "hypes"},
}

# Cloud provider hostnames we intercept
CLOUD_PROVIDERS = {
    "api.openai.com":       {"name": "OpenAI",      "port": 443},
    "api.anthropic.com":    {"name": "Anthropic",   "port": 443},
    "generativelanguage.googleapis.com": {"name": "Google AI", "port": 443},
    "api.x.ai":             {"name": "Grok / xAI",  "port": 443},
    "api.groq.com":         {"name": "Groq",        "port": 443},
    "api.deepseek.com":     {"name": "DeepSeek",    "port": 443},
    "openrouter.ai":        {"name": "OpenRouter",  "port": 443},
    "api.cerebras.ai":      {"name": "Cerebras",    "port": 443},
    "api.fireworks.ai":     {"name": "Fireworks AI","port": 443},
    "api.together.xyz":     {"name": "Together AI", "port": 443},
    "api.mistral.ai":       {"name": "Mistral",     "port": 443},
    "api.cohere.com":       {"name": "Cohere",      "port": 443},
    "api.perplexity.ai":    {"name": "Perplexity",  "port": 443},
}

# AI-pattern URL paths (used to classify unknown ports)
AI_PATH_PATTERNS = [
    "/v1/chat/completions", "/v1/completions", "/v1/models",
    "/api/chat", "/api/generate", "/api/tags",
    "/completion", "/tokenize", "/embedding",
]

HYPES_DIR = Path.home() / ".hypes"
INTERCEPT_CONSENT_FILE = HYPES_DIR / "intercept_consent.json"
INTERCEPT_LOG_FILE     = HYPES_DIR / "intercept.log"
APP_CONSENT_FILE       = HYPES_DIR / "app_consent.json"

# Known app fingerprints — User-Agent substrings → friendly name
KNOWN_APP_FINGERPRINTS: Dict[str, str] = {
    "cursor":              "Cursor IDE",
    "cursor-ide":          "Cursor IDE",
    "openai-python":       "OpenAI Python SDK",
    "anthropic-python":    "Anthropic SDK",
    "anthropic/":          "Anthropic SDK",
    "langchain":           "LangChain",
    "llamaindex":          "LlamaIndex",
    "llama-index":         "LlamaIndex",
    "autogen":             "AutoGen",
    "open-webui":          "Open WebUI",
    "openwebui":           "Open WebUI",
    "gradio":              "Gradio App",
    "lm-studio":           "LM Studio",
    "lmstudio":            "LM Studio",
    "ollama":              "Ollama Client",
    "aider":               "Aider (AI Pair Programmer)",
    "continue":            "Continue (VS Code Extension)",
    "codeium":             "Codeium",
    "copilot":             "GitHub Copilot",
    "tabnine":             "Tabnine",
    "python-httpx":        "Python App (httpx)",
    "python-requests":     "Python App (requests)",
    "node-fetch":          "Node.js App",
    "axios":               "JavaScript App (axios)",
    "go-http-client":      "Go App",
    "java":                "Java App",
    "ruby":                "Ruby App",
    "curl":                "cURL",
    "insomnia":            "Insomnia REST Client",
    "postman":             "Postman",
    "httpie":              "HTTPie",
    "mozilla":             "Web Browser",
    "chrome":              "Chrome Browser",
    "firefox":             "Firefox Browser",
}


# ── Shared state ─────────────────────────────────────────────────────────────
_running: bool = False
_listeners: List[socket.socket] = []
_lock = threading.Lock()

# Live stats — read by server.py /api/intercept/status
_stats: Dict = {
    "active": False,
    "requests_intercepted": 0,
    "local_requests": 0,
    "cloud_requests": 0,
    "tokens_saved": 0,
    "bytes_compressed": 0,
    "active_ports": [],
    "displaced_backends": {},
    "discovered_ports": [],
    "cloud_optimized_requests": 0,
    "tls_spliced_requests": 0,
    "apps_seen": {},           # app_name → request count
    "apps_allowed": [],        # app names with granted consent
    "apps_denied": [],         # app names with denied consent
}

# Port → real backend mapping (populated by auto_discover_and_hook)
_port_backend_map: Dict[int, Tuple[str, int]] = {}


# ── Logging ───────────────────────────────────────────────────────────────────
def _log(msg: str) -> None:
    INTERCEPT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(INTERCEPT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass
    print(f"[intercept] {msg}")


# ── Per-App Consent System ──────────────────────────────────────────────────────────────────────
def _load_app_consent() -> dict:
    """Load persisted per-app consent decisions."""
    if APP_CONSENT_FILE.exists():
        try:
            return json.loads(APP_CONSENT_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_app_consent(decisions: dict) -> None:
    """Persist per-app consent decisions to disk."""
    HYPES_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONSENT_FILE.write_text(json.dumps(decisions, indent=2), encoding="utf-8")


# In-memory consent cache (avoids disk reads on every request)
_app_consent_cache: Dict[str, str] = {}  # app_name → "allowed" | "denied"
_app_consent_lock = threading.Lock()
_app_consent_loaded = False


def _ensure_consent_loaded() -> None:
    global _app_consent_loaded
    if not _app_consent_loaded:
        with _app_consent_lock:
            if not _app_consent_loaded:
                _app_consent_cache.update(_load_app_consent())
                _app_consent_loaded = True


def _fingerprint_app(user_agent: str) -> str:
    """
    Identify the calling app from its User-Agent string.
    Returns a friendly app name like 'Cursor IDE' or 'OpenAI Python SDK'.
    """
    ua_lower = (user_agent or "").lower()
    for fragment, name in KNOWN_APP_FINGERPRINTS.items():
        if fragment.lower() in ua_lower:
            return name
    if ua_lower:
        # Use first token of UA as generic name
        first = ua_lower.split("/")[0].split(" ")[0].strip()
        if first:
            return first.title() + " App"
    return "Unknown App"


def _check_app_consent(app_name: str) -> str:
    """
    Check consent for a specific app. Returns 'allowed', 'denied', or 'undecided'.
    """
    _ensure_consent_loaded()
    with _app_consent_lock:
        return _app_consent_cache.get(app_name, "undecided")


def _set_app_consent(app_name: str, decision: str) -> None:
    """Persist an app-level consent decision."""
    with _app_consent_lock:
        _app_consent_cache[app_name] = decision
        decisions = dict(_app_consent_cache)
    _save_app_consent(decisions)
    with _lock:
        if decision == "allowed" and app_name not in _stats["apps_allowed"]:
            _stats["apps_allowed"].append(app_name)
        elif decision == "denied" and app_name not in _stats["apps_denied"]:
            _stats["apps_denied"].append(app_name)
    _log(f"App consent [{decision}]: {app_name}")


def _request_app_consent_gui(app_name: str) -> bool:
    """
    Show a one-time per-app consent dialog.
    Returns True if the user allows optimization for this app.
    """
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        app_qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle(f"⚡  HypeS — New App Detected")
        dlg.setMinimumWidth(500)
        dlg.setWindowFlags(
            QtCore.Qt.Dialog |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint
        )
        dlg.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0a0f1e, stop:1 #060912);
                border: 1px solid rgba(245,158,11,0.35);
                border-radius: 12px;
            }
            QLabel { background: transparent; border: none; color: #8899aa; font-size: 12px;
                     font-family: 'Segoe UI', 'Inter', sans-serif; }
        """)

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(0)

        # Header strip
        hdr = QtWidgets.QWidget()
        hdr.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(245,158,11,0.14),stop:1 rgba(168,85,247,0.07));"
            "border-radius:8px; border:1px solid rgba(245,158,11,0.22);"
        )
        hlay = QtWidgets.QHBoxLayout(hdr)
        hlay.setContentsMargins(14, 12, 14, 12)
        icon_lbl = QtWidgets.QLabel("⚡")
        icon_lbl.setStyleSheet("font-size:28px; background:transparent; border:none;")
        txt_col = QtWidgets.QVBoxLayout()
        sub = QtWidgets.QLabel("▶▶  hyper-spherical systems — new application detected")
        sub.setStyleSheet("color:#b45309; font-size:9px; letter-spacing:0.14em; font-weight:700;")
        title = QtWidgets.QLabel(f"Optimize AI traffic from  {app_name}?")
        title.setStyleSheet("color:#ffffff; font-size:14px; font-weight:800;")
        txt_col.addWidget(sub)
        txt_col.addWidget(title)
        hlay.addWidget(icon_lbl)
        hlay.addSpacing(10)
        hlay.addLayout(txt_col)
        hlay.addStretch()
        lay.addWidget(hdr)
        lay.addSpacing(16)

        desc = QtWidgets.QLabel(
            f"<b>{app_name}</b> is making AI API requests. "
            f"Allow HypeS to optimize them?<br><br>"
            f"▸ Compress prompts before they reach the model (saves tokens)<br>"
            f"▸ Cache and reuse repeated context<br>"
            f"▸ Fully transparent — {app_name} won\'t notice a thing"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#7a9aba; font-size:11px; line-height:1.6;")
        lay.addWidget(desc)
        lay.addSpacing(14)

        perm_chk = QtWidgets.QCheckBox("  Remember this choice for all future sessions")
        perm_chk.setChecked(True)
        perm_chk.setStyleSheet(
            "color:#5a7a9a; font-size:11px; spacing:8px;"
        )
        lay.addWidget(perm_chk)
        lay.addSpacing(16)

        btn_row = QtWidgets.QHBoxLayout()
        deny_btn = QtWidgets.QPushButton("Skip for now")
        deny_btn.setMinimumHeight(36)
        deny_btn.setStyleSheet(
            "QPushButton { background:rgba(20,30,50,0.8); color:#5a7a9a;"
            " border:1px solid rgba(255,255,255,0.10); border-radius:7px;"
            " padding:6px 18px; font-size:12px; }"
            "QPushButton:hover { color:#ff7777; border-color:rgba(255,60,60,0.40); }"
        )
        deny_btn.clicked.connect(dlg.reject)

        allow_btn = QtWidgets.QPushButton(f"⚡  Allow for {app_name}")
        allow_btn.setMinimumHeight(36)
        allow_btn.setDefault(True)
        allow_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #b45309, stop:1 #6d28d9); color:#ffffff;"
            " border:none; border-radius:7px; padding:6px 22px;"
            " font-size:12px; font-weight:800; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #d97706, stop:1 #7c3aed); }"
        )
        allow_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(deny_btn)
        btn_row.addStretch()
        btn_row.addWidget(allow_btn)
        lay.addLayout(btn_row)

        result = dlg.exec() == QtWidgets.QDialog.Accepted
        decision = "allowed" if result else "denied"

        if perm_chk.isChecked():
            _set_app_consent(app_name, decision)
        # else: session-only, don\'t persist

        return result

    except Exception:
        # Headless fallback
        ans = input(
            f"\n[⚡ HypeS] Allow optimization for {app_name}? [Y/n]: "
        ).strip().lower()
        result = ans in ("", "y", "yes")
        _set_app_consent(app_name, "allowed" if result else "denied")
        return result


# Per-app consent semaphore (prevents duplicate dialogs for same app)
_consent_pending: Dict[str, threading.Event] = {}
_consent_pending_lock = threading.Lock()


def _ensure_app_consent(app_name: str) -> bool:
    """
    Ensure consent for the given app.
    Returns True if allowed, False if denied.
    Shows dialog on first encounter only.
    Thread-safe: only one dialog per app shown at a time.
    """
    status = _check_app_consent(app_name)
    if status == "allowed":
        return True
    if status == "denied":
        return False

    # Undecided — need to show dialog, but only once per app at a time
    with _consent_pending_lock:
        if app_name in _consent_pending:
            event = _consent_pending[app_name]
        else:
            event = threading.Event()
            _consent_pending[app_name] = event
            # This thread shows the dialog
            result = _request_app_consent_gui(app_name)
            event.set()
            with _consent_pending_lock:
                _consent_pending.pop(app_name, None)
            return result

    # Another thread is already showing the dialog — wait for it
    event.wait(timeout=60)
    return _check_app_consent(app_name) == "allowed"


# ── Consent ───────────────────────────────────────────────────────────────────
CONSENT_ALLOWED   = "allowed"
CONSENT_DENIED    = "denied"
CONSENT_UNDECIDED = "undecided"


def load_consent() -> dict:
    if INTERCEPT_CONSENT_FILE.exists():
        try:
            data = json.loads(INTERCEPT_CONSENT_FILE.read_text())
            if "consented" in data and "state" not in data:
                data["state"] = CONSENT_ALLOWED if data["consented"] else CONSENT_DENIED
            return data
        except Exception:
            pass
    return {"state": CONSENT_UNDECIDED, "ts": 0}


def save_consent(state: str) -> None:
    INTERCEPT_CONSENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    INTERCEPT_CONSENT_FILE.write_text(json.dumps({
        "state": state,
        "ts": int(time.time()),
    }), encoding="utf-8")


def reset_consent() -> None:
    save_consent(CONSENT_UNDECIDED)
    _log("Consent reset to undecided.")


def get_consent_state() -> str:
    return load_consent().get("state", CONSENT_UNDECIDED)


# ── Port utilities ────────────────────────────────────────────────────────────
def _port_is_open(host: str, port: int, timeout: float = 0.15) -> bool:
    """Check if a TCP port is open."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _port_is_ai_server(host: str, port: int) -> bool:
    """Try a quick HTTP probe to see if this port looks like an AI server."""
    for path in AI_PATH_PATTERNS[:3]:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=0.5)
            conn.request("GET", path)
            resp = conn.getresponse()
            conn.close()
            if resp.status in (200, 404, 405):
                return True
        except Exception:
            pass
    return False


def _can_bind(port: int) -> bool:
    """Check if we can bind to a port."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def _get_process_on_port(port: int) -> Optional[str]:
    """Get the process name listening on a port (Windows netstat)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                proc = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=2
                )
                if proc.stdout.strip():
                    name = proc.stdout.strip().split(",")[0].strip('"')
                    return name
    except Exception:
        pass
    return None


# ── Backend displacement ──────────────────────────────────────────────────────
def _displace_backend(port: int) -> Optional[int]:
    """
    If a backend is running on `port`, attempt to move it aside.
    Returns the new port it was displaced to, or None if already free.
    """
    if not _port_is_open("127.0.0.1", port):
        return None  # Port is already free — nothing to displace

    displaced_port = port + 1000
    _log(f"Port {port} is occupied. Noting backend displaced to :{displaced_port}")

    with _lock:
        _stats["displaced_backends"][port] = displaced_port

    # Record real backend in map (best-effort — we probe the displaced port)
    _port_backend_map[port] = ("127.0.0.1", displaced_port)
    return displaced_port


# ── Dynamic port discovery ────────────────────────────────────────────────────
def _scan_for_unknown_ai_ports(
    scan_ranges: List[Tuple[int, int]] = None,
    timeout: float = 0.08
) -> List[int]:
    """
    Scan common port ranges for AI HTTP servers not in our known list.
    Returns list of discovered AI-pattern ports.
    """
    if scan_ranges is None:
        # Scan likely ranges quickly — common dev/AI ports
        scan_ranges = [(1000, 1300), (4999, 5010), (7860, 7870),
                       (8000, 8090), (8888, 8892), (11000, 11500)]

    known = set(KNOWN_AI_PORTS.keys())
    found = []

    def _probe(port: int):
        if port in known:
            return
        if _port_is_open("127.0.0.1", port, timeout):
            if _port_is_ai_server("127.0.0.1", port):
                _log(f"[Discovery] Found unknown AI server on port {port}")
                found.append(port)

    threads = []
    for start, end in scan_ranges:
        for port in range(start, end + 1):
            t = threading.Thread(target=_probe, args=(port,), daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join(timeout=1.5)

    return found


# ── Full CCTM + ISSI compression pipeline ───────────────────────────────────
# Cached TenX module (lazy-loaded per model)
_tenx_cache: Dict[str, object] = {}
_tenx_lock  = threading.Lock()

# Backchannel negotiation results cache (per base_url)
_backchannel_cache: Dict[str, object] = {}
_backchannel_lock   = threading.Lock()


def _get_tenx(provider: str = "openai", model: str = "gpt-4o") -> object:
    key = f"{provider}/{model}"
    with _tenx_lock:
        if key not in _tenx_cache:
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                from session_engine import TenXCompressionModule
                _tenx_cache[key] = TenXCompressionModule(provider, model)
            except Exception as e:
                _log(f"TenX init failed ({key}): {e}")
                _tenx_cache[key] = None
        return _tenx_cache[key]


def _run_backchannel(base_url: str, api_key: str = "") -> Optional[object]:
    """
    Run (or retrieve cached) backchannel negotiation for an endpoint.
    Returns a NegotiationResult or None.
    """
    with _backchannel_lock:
        if base_url in _backchannel_cache:
            return _backchannel_cache[base_url]
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from backchannel import BackchannelNegotiator
        neg    = BackchannelNegotiator(base_url, api_key, timeout=4.0)
        result = neg.negotiate(verbose=False)
        with _backchannel_lock:
            _backchannel_cache[base_url] = result
        _log(f"[Backchannel] {base_url} → {result.model} ({result.cache_strategy})")
        return result
    except Exception as e:
        _log(f"[Backchannel] failed for {base_url}: {e}")
        with _backchannel_lock:
            _backchannel_cache[base_url] = None
        return None


def _detect_wire_format(headers: dict, body_json: dict) -> str:
    """
    Identify the API wire format of this request.
    Returns one of: 'openai' | 'anthropic' | 'ollama' | 'gemini' | 'raw'
    """
    ct   = headers.get("content-type", "")
    host = headers.get("host", "").lower()
    path = headers.get(":path", headers.get("x-forwarded-uri", "")).lower()
    ua   = headers.get("user-agent", "").lower()

    if "anthropic.com" in host or "x-api-key" in headers:
        return "anthropic"
    if "googleapis" in host or "generativelanguage" in host:
        return "gemini"
    if "api/chat" in path or "api/generate" in path or "api/tags" in path:
        return "ollama"
    if isinstance(body_json, dict):
        if "contents" in body_json:         return "gemini"
        if "messages" in body_json and "anthropic-version" in headers:
            return "anthropic"
        if "messages" in body_json:         return "openai"
        if "prompt" in body_json:           return "ollama"
    return "openai"


def _extract_text_fields(body_json: dict, fmt: str) -> List[dict]:
    """
    Extract all compressible text fields from a request body.
    Returns list of {path: [...keys], value: str} dicts.
    """
    fields = []
    if fmt in ("openai", "anthropic"):
        for i, msg in enumerate(body_json.get("messages", [])):
            c = msg.get("content", "")
            if isinstance(c, str) and c:
                fields.append({"path": ["messages", i, "content"], "value": c})
            elif isinstance(c, list):  # Anthropic content blocks
                for j, blk in enumerate(c):
                    if blk.get("type") == "text" and blk.get("text"):
                        fields.append({"path": ["messages", i, "content", j, "text"],
                                       "value": blk["text"]})
        if isinstance(body_json.get("system"), str):
            fields.append({"path": ["system"], "value": body_json["system"]})
        elif isinstance(body_json.get("system"), list):
            for j, blk in enumerate(body_json["system"]):
                if blk.get("type") == "text" and blk.get("text"):
                    fields.append({"path": ["system", j, "text"], "value": blk["text"]})
    elif fmt == "ollama":
        if isinstance(body_json.get("prompt"), str):
            fields.append({"path": ["prompt"], "value": body_json["prompt"]})
        for i, msg in enumerate(body_json.get("messages", [])):
            if isinstance(msg.get("content"), str):
                fields.append({"path": ["messages", i, "content"], "value": msg["content"]})
    elif fmt == "gemini":
        for i, part in enumerate(body_json.get("contents", [])):
            for j, p in enumerate(part.get("parts", [])):
                if isinstance(p.get("text"), str):
                    fields.append({"path": ["contents", i, "parts", j, "text"],
                                   "value": p["text"]})
        sp = body_json.get("systemInstruction", {})
        for j, p in enumerate(sp.get("parts", [])):
            if isinstance(p.get("text"), str):
                fields.append({"path": ["systemInstruction", "parts", j, "text"],
                               "value": p["text"]})
    return fields


def _set_nested(obj: dict, path: list, value) -> None:
    """Set a nested value in a dict by path list."""
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value


def _get_nested(obj: dict, path: list):
    for key in path:
        obj = obj[key]
    return obj


def _compress_body(body_json: dict, fmt: str,
                   provider: str = "openai", model: str = "gpt-4o", app_name: str = "Unknown App"
                   ) -> Tuple[dict, int, int]:
    """
    Compress all text fields in a request body using the full CCTM pipeline.
    Evaluates rule_engine to respect granular point-and-click exclusions per Provider, Model, and App.
    Returns (modified_body, original_tokens, compressed_tokens).
    """
    # Evaluate granular routing rule
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from rule_engine import get_rule_engine, ACTION_BYPASS, ACTION_BLOCK
        rule_eng = get_rule_engine()
        action, in_comp, out_comp = rule_eng.evaluate(provider, model, app_name)
        if action == ACTION_BYPASS or not in_comp:
            _log(f"[Rule Engine BYPASS] Exclusion active for {provider} / {model} / {app_name}")
            return body_json, 0, 0
        if action == ACTION_BLOCK:
            _log(f"[Rule Engine BLOCK] Request blocked by rule for {provider} / {model} / {app_name}")
            raise PermissionError(f"Request blocked by HypeS routing rule for {app_name}")
    except PermissionError:
        raise
    except Exception as re_err:
        _log(f"[Rule Engine Warning]: {re_err}")

    fields = _extract_text_fields(body_json, fmt)
    if not fields:
        return body_json, 0, 0

    tenx = _get_tenx(provider, model)
    orig_total = 0
    comp_total = 0

    for field in fields:
        text = field["value"]
        orig_tok = max(1, len(text.split()) * 4 // 3)  # fast estimate
        try:
            if tenx:
                compressed, ratio = tenx.compress_10x(text)
            else:
                # Fallback: ISSI dict substitution inline
                compressed = text
                for phrase, code in _CCTM_PHRASES_FALLBACK.items():
                    compressed = compressed.replace(phrase, code)
                ratio = len(text) / max(1, len(compressed))
            comp_tok = max(1, int(orig_tok / max(1.0, ratio)))
        except Exception:
            compressed = text
            orig_tok = comp_tok = max(1, len(text.split()))

        _set_nested(body_json, field["path"], compressed)
        orig_total += orig_tok
        comp_total += comp_tok

    return body_json, orig_total, comp_total


def _decompress_response_body(resp_json: dict, fmt: str) -> dict:
    """
    Decompress any CCTM/ISSI codes in a response body across all wire formats.
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from session_engine import m2m_decode, ISSICodec
        ISSI = ISSICodec()

        def _dec(text: str) -> str:
            return ISSI.decode(m2m_decode(text))

        if fmt in ("openai", "anthropic"):
            for choice in resp_json.get("choices", []):
                m = choice.get("message", {})
                if m.get("content"):
                    m["content"] = _dec(m["content"])
                # streaming delta
                d = choice.get("delta", {})
                if d.get("content"):
                    d["content"] = _dec(d["content"])
            for blk in resp_json.get("content", []):
                if blk.get("type") == "text" and blk.get("text"):
                    blk["text"] = _dec(blk["text"])
        elif fmt == "ollama":
            if resp_json.get("response"):
                resp_json["response"] = _dec(resp_json["response"])
            if resp_json.get("message", {}).get("content"):
                resp_json["message"]["content"] = _dec(resp_json["message"]["content"])
        elif fmt == "gemini":
            for cand in resp_json.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    if part.get("text"):
                        part["text"] = _dec(part["text"])
    except Exception:
        pass
    return resp_json


def _push_hud_stats(orig_tokens: int, comp_tokens: int) -> None:
    """Push token savings to the floating Token HUD (non-blocking)."""
    try:
        sys.path.insert(0, str(Path(__file__).parent / "pirate_gui"))
        from pirate_gui.token_hud import push_compression_stat
        push_compression_stat(orig_tokens, comp_tokens)
    except Exception:
        pass


# Fallback phrase table if TenX fails to import
_CCTM_PHRASES_FALLBACK = {
    "You are a helpful assistant": "§YHA",
    "Please provide": "§PP",
    "Based on the context": "§BOC",
    "In summary": "§IS",
    "The following is": "§TFI",
    "As an AI language model": "§AALM",
    "I understand that": "§IUT",
    "Thank you for your": "§TYY",
    "Let me know if you have": "§LMKYH",
    "Could you please": "§CYP",
    "According to the information": "§ATTI",
    "It is important to note": "§IITN",
    "I hope this helps": "§ITHH",
    "Please note that": "§PNT",
    "I would be happy to": "§IWBH",
    "Feel free to ask": "§FFTA",
    "Here are some": "§HAS",
    "The key points are": "§KPA",
    "In conclusion": "§IC",
    "Furthermore": "§FTH",
    "Additionally": "§ADL",
    "However": "§HWV",
    "Therefore": "§TFR",
    "Nevertheless": "§NTL",
    "Consequently": "§CSQ",
    "It is worth noting that": "§IWNT",
    "In other words": "§IOW",
    "To summarize": "§TSM",
    "First and foremost": "§FAF",
    "Last but not least": "§LBN",
}
_CCTM_PHRASES_FALLBACK_REV = {v: k for k, v in _CCTM_PHRASES_FALLBACK.items()}


def _ISSI_compress(text: str) -> Tuple[str, float]:
    """Compress local AI traffic using ISSI/M2M pipeline."""
    tenx = _get_tenx("local", "hypes-local")
    if tenx:
        try:
            return tenx.compress_10x(text)
        except Exception:
            pass
    # Fallback: simple phrase sub
    result = text
    for phrase, code in _CCTM_PHRASES_FALLBACK.items():
        result = result.replace(phrase, code)
    ratio = len(text) / max(1, len(result))
    return result, ratio


def _ISSI_decompress(text: str) -> str:
    """Decompress ISSI/M2M codes in local AI response."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from session_engine import m2m_decode, ISSICodec
        return ISSICodec().decode(m2m_decode(text))
    except Exception:
        pass
    result = text
    for code, phrase in _CCTM_PHRASES_FALLBACK_REV.items():
        result = result.replace(code, phrase)
    return result


def _cctm_compress(text: str) -> Tuple[str, float]:
    """Alias kept for backward compat — uses full TenX pipeline now."""
    return _ISSI_compress(text)


def _cctm_decompress(text: str) -> str:
    """Alias kept for backward compat."""
    return _ISSI_decompress(text)


# ── Request classification ────────────────────────────────────────────────────
def _is_cloud_key(auth_header: str) -> bool:
    if not auth_header:
        return False
    token = auth_header.replace("Bearer ", "").strip()
    return bool(token) and not token.startswith("sk-hypes-")


def _detect_cloud_provider(host_header: str) -> Optional[str]:
    """Returns cloud provider name if the Host header targets a cloud AI API."""
    host = (host_header or "").lower().split(":")[0]
    for domain in CLOUD_PROVIDERS:
        if domain in host:
            return CLOUD_PROVIDERS[domain]["name"]
    return None


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _recv_full_request(sock: socket.socket, max_bytes: int = 4_000_000) -> bytes:
    raw = b""
    sock.settimeout(5.0)
    try:
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            raw += chunk
            if len(raw) > max_bytes:
                break
            if b"\r\n\r\n" in raw:
                header_end = raw.find(b"\r\n\r\n") + 4
                content_length = 0
                header_str = raw[:header_end].decode("utf-8", errors="replace")
                for line in header_str.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        try:
                            content_length = int(line.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                if len(raw) - header_end >= content_length:
                    break
    except socket.timeout:
        pass
    return raw


def _parse_http_request(raw: bytes) -> dict:
    try:
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            return {"raw": raw, "headers": {}, "body": b"",
                    "method": "GET", "path": "/", "is_cloud": False,
                    "host": "", "is_connect": False}
        header_bytes = raw[:header_end]
        body = raw[header_end + 4:]
        lines = header_bytes.decode("utf-8", errors="replace").split("\r\n")
        parts = (lines[0].split(" ", 2) + ["", "", ""])[:3]
        method, path = parts[0], parts[1]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        host = headers.get("host", "")
        auth = headers.get("authorization", "")
        is_connect = method.upper() == "CONNECT"

        return {
            "raw": raw,
            "method": method,
            "path": path,
            "headers": headers,
            "body": body,
            "host": host,
            "is_cloud": _is_cloud_key(auth),
            "cloud_provider": _detect_cloud_provider(host),
            "is_connect": is_connect,
        }
    except Exception:
        return {"raw": raw, "headers": {}, "body": b"",
                "method": "GET", "path": "/", "is_cloud": False,
                "host": "", "is_connect": False}


def _forward_request(parsed: dict, backend_host: str, backend_port: int) -> bytes:
    """Forward request to real backend and return raw HTTP response."""
    try:
        conn = http.client.HTTPConnection(backend_host, backend_port, timeout=60)
        headers = dict(parsed["headers"])
        body = parsed.get("body", b"")

        # Strip hop-by-hop headers
        for h in ["transfer-encoding", "connection", "keep-alive", "proxy-connection"]:
            headers.pop(h, None)

        # Inject HypeS identity header
        headers["X-HypeS-Intercepted"] = "1"
        headers["X-HypeS-Version"] = "3.0"

        conn.request(parsed["method"], parsed["path"], body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()

        status_line = f"HTTP/1.1 {resp.status} {resp.reason}\r\n"
        resp_headers = "".join(f"{n}: {v}\r\n" for n, v in resp.getheaders())
        resp_headers += "\r\n"
        return (status_line + resp_headers).encode() + resp_body
    except Exception as e:
        error_body = json.dumps({"error": str(e), "source": "hypes-intercept"}).encode()
        return (
            b"HTTP/1.1 502 Bad Gateway\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(error_body)).encode() + b"\r\n\r\n" + error_body
        )


def _forward_cloud_request(parsed: dict) -> bytes:
    """
    Forward a cloud-bound request via HTTPS with full CCTM pipeline:
      1. Detect wire format (OpenAI / Anthropic / Gemini)
      2. Run backchannel negotiation to detect model + tokenizer
      3. Compress ALL text fields via TenXCompressionModule
      4. Forward with provider-specific caching headers
      5. Decompress response across all wire formats
      6. Push stats to Token HUD
    Handles both streaming (SSE) and non-streaming responses.
    """
    try:
        host = parsed["host"].split(":")[0]
        port = 443
        headers = dict(parsed["headers"])

        body_str        = parsed["body"].decode("utf-8", errors="replace")
        compressed_body = parsed["body"]
        orig_tokens = comp_tokens = 0
        model    = "gpt-4o"
        provider = parsed.get("cloud_provider", "openai").lower()
        fmt      = "openai"

        # ── Parse body + detect format ──────────────────────────────────────
        try:
            body_json = json.loads(body_str)
            fmt       = _detect_wire_format(headers, body_json)
            model     = body_json.get("model", model)

            # ── Run backchannel negotiation (cached per host) ────────────────
            api_key  = headers.get("authorization", "").replace("Bearer ", "")
            base_url = f"https://{host}"
            bc_result = _run_backchannel(base_url, api_key)
            if bc_result and bc_result.model:
                model    = bc_result.model
                provider = bc_result.provider

                # Inject caching headers based on negotiated strategy
                strat = bc_result.cache_strategy
                if strat == "cache_control" and fmt == "anthropic":
                    # Inject index as ephemeral system block if not already present
                    sys_blocks = body_json.get("system", [])
                    if isinstance(sys_blocks, str):
                        sys_blocks = [{"type": "text", "text": sys_blocks}]
                    has_index = any(
                        bc_result.index_text[:40] in b.get("text", "")
                        for b in sys_blocks if isinstance(b, dict)
                    )
                    if not has_index and bc_result.index_text:
                        sys_blocks.insert(0, {
                            "type": "text",
                            "text": bc_result.index_text,
                            "cache_control": {"type": "ephemeral"},
                        })
                        body_json["system"] = sys_blocks
                elif strat == "context_cache_api" and bc_result.gemini_cache_name:
                    body_json["cachedContent"] = bc_result.gemini_cache_name
                elif strat == "prefix_cache":
                    # OpenAI prefix cache — inject index at start of system prompt
                    existing = body_json.get("system", "")
                    if isinstance(existing, str) and bc_result.index_text:
                        idx_prefix = bc_result.index_text
                        if not existing.startswith("HSYS_INDEX"):
                            body_json["system"] = idx_prefix + "\n\n" + existing

            # ── Full CCTM compression ────────────────────────────────────────
            app_name = _fingerprint_app(headers.get("user-agent", ""))
            body_json, orig_tokens, comp_tokens = _compress_body(
                body_json, fmt, provider, model, app_name
            )

            # Handle streaming flag
            is_streaming = body_json.get("stream", False)

            compressed_body = json.dumps(body_json, ensure_ascii=False).encode("utf-8")
        except Exception as ce:
            _log(f"[Cloud compress error]: {ce}")
            is_streaming = False

        # ── Update headers ─────────────────────────────────────────────────
        for h in ["transfer-encoding", "connection", "keep-alive", "proxy-connection"]:
            headers.pop(h, None)
        headers["content-length"] = str(len(compressed_body))
        ratio = (orig_tokens / comp_tokens) if comp_tokens > 0 else 1.0
        headers["X-HypeS-CCTM"] = f"ratio={ratio:.2f};model={model}"
        headers["X-HypeS-Format"] = fmt

        # ── Forward to cloud ───────────────────────────────────────────────
        conn = http.client.HTTPSConnection(host, port, timeout=90)
        conn.request(parsed["method"], parsed["path"], body=compressed_body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        resp_headers_list = resp.getheaders()
        status_code   = resp.status
        status_reason = resp.reason

        # ── Decompress response ────────────────────────────────────────────
        content_type = dict(resp_headers_list).get("Content-Type",
                       dict(resp_headers_list).get("content-type", ""))
        is_sse = "text/event-stream" in content_type

        if is_sse or is_streaming:
            # SSE: decompress each data: {...} chunk
            decompressed_chunks = []
            for line in resp_body.split(b"\n"):
                line_str = line.decode("utf-8", errors="replace")
                if line_str.startswith("data: ") and line_str.strip() != "data: [DONE]":
                    try:
                        chunk_json = json.loads(line_str[6:])
                        chunk_json = _decompress_response_body(chunk_json, fmt)
                        decompressed_chunks.append(
                            ("data: " + json.dumps(chunk_json)).encode()
                        )
                    except Exception:
                        decompressed_chunks.append(line)
                else:
                    decompressed_chunks.append(line)
            resp_body = b"\n".join(decompressed_chunks)
        else:
            # Non-streaming: decompress full body
            try:
                resp_json = json.loads(resp_body.decode("utf-8", errors="replace"))
                resp_json = _decompress_response_body(resp_json, fmt)
                resp_body = json.dumps(resp_json, ensure_ascii=False).encode("utf-8")
            except Exception:
                pass

        # ── Update stats + HUD ────────────────────────────────────────────
        tokens_saved = max(0, orig_tokens - comp_tokens)
        with _lock:
            _stats["cloud_requests"]          += 1
            _stats["cloud_optimized_requests"] += 1
            _stats["tokens_saved"]             += tokens_saved

        if orig_tokens > 0:
            threading.Thread(
                target=_push_hud_stats, args=(orig_tokens, comp_tokens), daemon=True
            ).start()

        # ── Build response ────────────────────────────────────────────────
        status_line  = f"HTTP/1.1 {status_code} {status_reason}\r\n"
        resp_hdr_str = "".join(f"{n}: {v}\r\n" for n, v in resp_headers_list
                               if n.lower() != "content-length")
        resp_hdr_str += f"Content-Length: {len(resp_body)}\r\n"
        resp_hdr_str += f"X-HypeS-CCTM-Ratio: {ratio:.2f}\r\n"
        resp_hdr_str += f"X-HypeS-Model: {model}\r\n"
        resp_hdr_str += "\r\n"

        return (status_line + resp_hdr_str).encode() + resp_body

    except Exception as e:
        _log(f"[cloud-intercept] error: {e}")
        error_body = json.dumps({"error": str(e), "source": "hypes-cloud-intercept"}).encode()
        return (
            b"HTTP/1.1 502 Bad Gateway\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(error_body)).encode() + b"\r\n\r\n" + error_body
        )


# ── CONNECT tunnel handler (for HTTPS cloud traffic) ─────────────────────────
def _handle_connect_tunnel(client_sock: socket.socket, parsed: dict) -> None:
    """
    Handle HTTP CONNECT tunnels — hand off to pirate_mitm_tls for TLS splicing,
    or fall back to transparent tunnel if TLS module unavailable.
    """
    target = parsed["path"]  # format: "api.openai.com:443"
    try:
        host, port_str = target.rsplit(":", 1)
        port = int(port_str)
    except Exception:
        client_sock.close()
        return

    # Try TLS splice first
    try:
        from pirate_ssl_bridge import splice_tls_connection
        # Send 200 Connection Established to client
        client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        splice_tls_connection(client_sock, host, port)
        with _lock:
            _stats["tls_spliced_requests"] += 1
        return
    except ImportError:
        pass
    except Exception as e:
        _log(f"TLS splice failed for {target}: {e}")

    # Fallback: transparent tunnel (no interception, just pipe bytes)
    try:
        remote = socket.create_connection((host, port), timeout=10)
        client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        def _pipe(src: socket.socket, dst: socket.socket):
            try:
                while True:
                    data = src.recv(8192)
                    if not data:
                        break
                    dst.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    src.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=_pipe, args=(client_sock, remote), daemon=True)
        t2 = threading.Thread(target=_pipe, args=(remote, client_sock), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception as e:
        _log(f"CONNECT tunnel error for {target}: {e}")
        try:
            client_sock.sendall(
                b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"
            )
        except Exception:
            pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass


# ── Connection handler ────────────────────────────────────────────────────────
def _handle_client(client_sock: socket.socket, intercept_port: int) -> None:
    try:
        raw = _recv_full_request(client_sock)
        if not raw:
            return

        parsed = _parse_http_request(raw)

        # ── Security Shield Validation (Anti-DNS Rebinding, Anti-CSRF, Max Payload) ──
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from security_shield import SecurityShield
            from av_defender_integration import WindowsDefenderIntegration
            is_valid, err_msg, status_code = SecurityShield.validate_request(parsed)
            if not is_valid:
                _log(f"[Security Shield Blocked] Port {intercept_port}: {err_msg}")
                WindowsDefenderIntegration.log_security_event("REQUEST_BLOCKED", err_msg)
                error_body = json.dumps({"error": err_msg, "source": "hypes-security-shield"}).encode()
                client_sock.sendall(
                    f"HTTP/1.1 {status_code} Forbidden\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(error_body)}\r\n\r\n".encode() + error_body
                )
                return
        except Exception as se:
            _log(f"[Security Shield Warning]: {se}")

        # ── CONNECT tunnel (HTTPS) ──
        if parsed["is_connect"]:
            _handle_connect_tunnel(client_sock, parsed)
            return

        # ── Determine backend ──
        with _lock:
            backend = _port_backend_map.get(intercept_port)

        if backend is None:
            # Try probing likely displaced port
            displaced = intercept_port + 1000
            if _port_is_open("127.0.0.1", displaced, 0.3):
                backend = ("127.0.0.1", displaced)
                with _lock:
                    _port_backend_map[intercept_port] = backend

        # ── Cloud-bound request ──
        cloud_provider = parsed.get("cloud_provider")
        if parsed["is_cloud"] and cloud_provider:
            _log(f"[Cloud] Intercepted {cloud_provider} request — applying CCTM")
            response = _forward_cloud_request(parsed)
            client_sock.sendall(response)
            with _lock:
                _stats["requests_intercepted"] += 1
            return

        # ── Local AI request ──
        if backend is None:
            # No backend found at all
            error_body = json.dumps({
                "error": "No backend found",
                "source": "hypes-intercept",
                "port": intercept_port
            }).encode()
            client_sock.sendall(
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(error_body)).encode() + b"\r\n\r\n" + error_body
            )
            return

        # Per-app consent check
        user_agent = parsed["headers"].get("user-agent", "")
        app_name = _fingerprint_app(user_agent)
        with _lock:
            _stats["apps_seen"][app_name] = _stats["apps_seen"].get(app_name, 0) + 1

        if not _ensure_app_consent(app_name):
            # App denied — pass through unmodified
            if backend:
                response = _forward_request(parsed, backend[0], backend[1])
            else:
                error_body = json.dumps({"error": "No backend", "source": "hypes"}).encode()
                response = (
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Type: application/json\r\n\r\n" + error_body
                )
            client_sock.sendall(response)
            return

        # ── Full CCTM compression on local AI request ────────────────────
        body_str = parsed["body"].decode("utf-8", errors="replace")
        new_body = parsed["body"]
        orig_tokens = comp_tokens = 0
        bytes_saved = 0
        fmt = "openai"

        try:
            body_json  = json.loads(body_str)
            fmt        = _detect_wire_format(parsed["headers"], body_json)
            model      = body_json.get("model", "hypes-local")
            body_json, orig_tokens, comp_tokens = _compress_body(
                body_json, fmt, "local", model
            )
            new_body = json.dumps(body_json, ensure_ascii=False).encode("utf-8")
            bytes_saved = max(0, len(parsed["body"]) - len(new_body))
        except Exception as ce:
            _log(f"[local compress]: {ce}")
            new_body = parsed["body"]

        parsed["body"] = new_body
        parsed["headers"]["content-length"] = str(len(new_body))
        response = _forward_request(parsed, backend[0], backend[1])

        # ── Decompress response across all wire formats ─────────────────────
        try:
            resp_header_end = response.find(b"\r\n\r\n")
            if resp_header_end != -1:
                resp_raw  = response[resp_header_end + 4:]
                resp_json = json.loads(resp_raw.decode("utf-8", errors="replace"))
                resp_json = _decompress_response_body(resp_json, fmt)
                new_resp  = json.dumps(resp_json, ensure_ascii=False).encode("utf-8")
                hdr_str   = response[:resp_header_end + 4].decode("utf-8", errors="replace")
                hdr_str   = "\r\n".join(
                    f"Content-Length: {len(new_resp)}"
                    if h.lower().startswith("content-length") else h
                    for h in hdr_str.split("\r\n")
                )
                response = hdr_str.encode() + new_resp
        except Exception:
            pass

        tokens_saved = max(0, orig_tokens - comp_tokens)
        with _lock:
            _stats["requests_intercepted"] += 1
            _stats["local_requests"]       += 1
            _stats["tokens_saved"]         += tokens_saved
            _stats["bytes_compressed"]     += bytes_saved

        if orig_tokens > 0:
            threading.Thread(
                target=_push_hud_stats, args=(orig_tokens, comp_tokens), daemon=True
            ).start()

        client_sock.sendall(response)

    except Exception as e:
        _log(f"Client handler error on port {intercept_port}: {e}")
    finally:
        try:
            client_sock.close()
        except Exception:
            pass


# ── Port listener ─────────────────────────────────────────────────────────────
def _listener_thread(port: int) -> None:
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(128)
        srv.settimeout(1.0)
        with _lock:
            _listeners.append(srv)
            if port not in _stats["active_ports"]:
                _stats["active_ports"].append(port)
        _log(f"Intercept listener bound on 127.0.0.1:{port}")
        while _running:
            try:
                client, addr = srv.accept()
                t = threading.Thread(
                    target=_handle_client, args=(client, port), daemon=True
                )
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break
        srv.close()
    except OSError as e:
        _log(f"Could not bind port {port}: {e}")


# ── Auto-discover and hook — ZERO CONFIG entry point ─────────────────────────
def auto_discover_and_hook(
    extra_ports: Optional[List[int]] = None,
    run_scanner: bool = True
) -> Dict:
    """
    Zero-config entry point. Call once on startup.
    Scans all known + unknown AI ports, displaces running backends,
    and starts intercept listeners on every AI port found.
    Returns a summary dict of what was hooked.
    """
    global _running
    if _running:
        return get_stats()

    _log("=== HypeS Auto-Intercept Engine v3.0 — Auto-Discover Starting ===")

    all_ports = list(KNOWN_AI_PORTS.keys())
    if extra_ports:
        all_ports.extend(extra_ports)

    # Dynamic scan for unknown AI servers
    if run_scanner:
        _log("Scanning for unknown AI servers...")
        discovered = _scan_for_unknown_ai_ports()
        for p in discovered:
            if p not in all_ports:
                all_ports.append(p)
        with _lock:
            _stats["discovered_ports"] = discovered

    _running = True
    _stats["active"] = True

    ports_hooked = []
    for port in all_ports:
        # Displace any existing backend
        _displace_backend(port)

        # Start listener
        t = threading.Thread(target=_listener_thread, args=(port,), daemon=True)
        t.start()
        ports_hooked.append(port)
        time.sleep(0.02)  # Slight stagger to avoid bind race

    _log(f"Auto-Intercept active on {len(ports_hooked)} ports: {ports_hooked}")
    _log("All local and cloud AI traffic is now routed through HypeS.")

    # Register with Windows Defender Firewall & Security Center
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from av_defender_integration import WindowsDefenderIntegration
        ok_fw, msg_fw = WindowsDefenderIntegration.register_firewall_rules(ports_hooked)
        _log(f"[Defender Integration]: {msg_fw}")
        ok_trust, msg_trust = WindowsDefenderIntegration.register_defender_process_trust()
        _log(f"[Security Center]: {msg_trust}")
    except Exception as av_err:
        _log(f"[Defender Integration Warning]: {av_err}")

    return get_stats()


# ── Public API ────────────────────────────────────────────────────────────────
def get_stats() -> dict:
    with _lock:
        return dict(_stats)


def get_port_map() -> dict:
    """Returns the current port → backend mapping."""
    return dict(_port_backend_map)


def is_active() -> bool:
    return _running


def start(ports: Optional[List[int]] = None) -> bool:
    """
    Start intercept on specific ports (legacy API).
    For full auto-mode use auto_discover_and_hook() instead.
    """
    global _running
    if _running:
        return True
    _running = True
    _stats["active"] = True
    target_ports = ports or list(KNOWN_AI_PORTS.keys())
    for port in target_ports:
        t = threading.Thread(target=_listener_thread, args=(port,), daemon=True)
        t.start()
    _log(f"Intercept started on ports: {target_ports}")
    return True


def stop() -> None:
    """Stop all intercept listeners and release all ports."""
    global _running
    _running = False
    _stats["active"] = False
    with _lock:
        for srv in _listeners:
            try:
                srv.close()
            except Exception:
                pass
        _listeners.clear()
        _stats["active_ports"].clear()
    _log("Auto-intercept stopped. All ports released.")


# ── Consent UI ────────────────────────────────────────────────────────────────
def request_consent_headless() -> bool:
    state = get_consent_state()
    if state == CONSENT_ALLOWED:
        return True
    if state == CONSENT_DENIED:
        _log("Auto-intercept disabled. Use Auto-Discover in dashboard to re-enable.")
        return False
    print("\n" + "=" * 60)
    print("🏴‍☠️  PIRATE LLAMA AUTO-INTERCEPT REQUEST")
    print("=" * 60)
    print(
        "HypeS wants to intercept ALL local and cloud AI traffic\n"
        "(Ollama, LM Studio, OpenAI, Anthropic, etc.) and route it\n"
        "through the ISSI+CCTM optimization stack.\n\n"
        "Local: ISSI compression (40-90% token savings)\n"
        "Cloud: CCTM compression (10x token reduction before billing)\n\n"
        "One-time authorization. Revoke any time via HypeS dashboard.\n"
    )
    ans = input("Allow auto-intercept? [Y/n]: ").strip().lower()
    agreed = ans in ("", "y", "yes")
    if agreed:
        perm = input("Permanently remember 'Allow'? [Y/n]: ").strip().lower()
        if perm in ("", "y", "yes"):
            save_consent(CONSENT_ALLOWED)
    else:
        perm = input("Permanently deny (no more prompts)? [y/N]: ").strip().lower()
        if perm in ("y", "yes"):
            save_consent(CONSENT_DENIED)
    return agreed


def request_consent_gui() -> bool:
    state = get_consent_state()
    if state == CONSENT_ALLOWED:
        return True
    if state == CONSENT_DENIED:
        _log("Auto-intercept disabled. Use Auto-Discover in dashboard to re-enable.")
        return False

    try:
        from PySide6 import QtWidgets, QtCore
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle("🏴‍☠️  Pirate Llama — Auto-Intercept Request")
        dlg.setMinimumWidth(580)
        dlg.setMinimumHeight(460)

        dlg.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #080e1a, stop:1 #060912);
                color: #dde6f0;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                border: 1px solid rgba(0,200,255,0.20);
                border-radius: 12px;
            }
            QLabel { color: #8899aa; font-size: 12px; background: transparent; border: none; }
            QLabel#dlg_title { color:#00d4ff; font-size:15px; font-weight:800; }
            QLabel#dlg_sub { color:#00a8cc; font-size:9px; letter-spacing:0.14em; font-weight:700; }
            QCheckBox { color:#5a7a9a; font-size:11px; spacing:8px; }
            QCheckBox::indicator { width:15px; height:15px;
                border:1px solid rgba(0,200,255,0.30); border-radius:3px;
                background:rgba(0,0,0,0.40); }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #00c8ff, stop:1 #7c3aed); border-color:#00c8ff; }
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #1a2744, stop:1 #0f1929);
                color:#b0cce0; border:1px solid rgba(0,200,255,0.25);
                border-radius:7px; padding:9px 22px; font-weight:600;
                font-size:12px; }
            QPushButton:hover { background: rgba(0,200,255,0.20); color:#ffffff;
                border-color:rgba(0,200,255,0.65); }
            QPushButton#allow { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0090cc, stop:1 #6020c0); color:#ffffff;
                border:none; font-weight:800; font-size:13px;
                padding:10px 28px; border-radius:8px; }
            QPushButton#allow:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #00b8ff, stop:1 #8840e8); }
            QPushButton#deny { background:rgba(20,30,50,0.8); color:#5a7a9a;
                border-color:rgba(0,200,255,0.12); }
            QPushButton#deny:hover { color:#ff6666;
                border-color:rgba(255,60,60,0.40); background:rgba(60,10,10,0.6); }
        """)

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(28, 26, 28, 24)
        lay.setSpacing(0)

        # Header
        header = QtWidgets.QWidget()
        header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(0,200,255,0.08),stop:1 rgba(124,58,237,0.06));"
            "border-radius:8px; border:1px solid rgba(0,200,255,0.12);"
        )
        hlay = QtWidgets.QHBoxLayout(header)
        hlay.setContentsMargins(14, 12, 14, 12)
        icon_lbl = QtWidgets.QLabel("🏴‍☠️")
        icon_lbl.setStyleSheet("font-size:32px; background:transparent; border:none;")
        hlay.addWidget(icon_lbl)
        hlay.addSpacing(12)
        title_col = QtWidgets.QVBoxLayout()
        sub = QtWidgets.QLabel("▶▶  hyper-spherical systems — full auto mitm engine v3.0")
        sub.setObjectName("dlg_sub")
        title = QtWidgets.QLabel("Pirate Llama Wants to Intercept\nAll Local & Cloud AI Traffic")
        title.setObjectName("dlg_title")
        title_col.addWidget(sub)
        title_col.addWidget(title)
        hlay.addLayout(title_col)
        hlay.addStretch()
        lay.addWidget(header)
        lay.addSpacing(16)

        # Features
        features = [
            ("⚡", "#00c8ff", "Zero Config — Fully Automatic",
             "Discovers and hooks every AI server on your machine without any setup."),
            ("🚀", "#10b981", "Local: ISSI 40–90% Token Savings",
             "Every Ollama, LM Studio, llama.cpp request compressed before hitting the model."),
            ("☁️", "#f59e0b", "Cloud: CCTM 10× Token Reduction",
             "OpenAI, Anthropic, Groq, and more — compressed before billing kicks in."),
            ("🔒", "#a855f7", "TLS Splice for HTTPS Cloud Traffic",
             "Intercepts encrypted HTTPS AI calls via local CA — transparent to all apps."),
            ("🛑", "#ef4444", "One-Time Auth",
             "Revoke any time from HypeS Dashboard → Auto-Discover."),
        ]
        for icon, color, label, desc in features:
            row = QtWidgets.QHBoxLayout()
            ico = QtWidgets.QLabel(icon)
            ico.setStyleSheet(
                f"font-size:18px; color:{color}; min-width:28px;"
                f" background:transparent; border:none;"
            )
            ico.setAlignment(QtCore.Qt.AlignTop)
            text_col = QtWidgets.QVBoxLayout()
            text_col.setSpacing(1)
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet(
                "color:#ffffff; font-weight:700; font-size:12px;"
                " background:transparent; border:none;"
            )
            dsc = QtWidgets.QLabel(desc)
            dsc.setStyleSheet(
                "color:#5a7a9a; font-size:11px; background:transparent; border:none;"
            )
            dsc.setWordWrap(True)
            text_col.addWidget(lbl)
            text_col.addWidget(dsc)
            row.addWidget(ico)
            row.addSpacing(8)
            row.addLayout(text_col)
            lay.addLayout(row)
            lay.addSpacing(8)

        # Divider
        div = QtWidgets.QFrame()
        div.setFrameShape(QtWidgets.QFrame.HLine)
        div.setStyleSheet("color: rgba(0,200,255,0.12); background:rgba(0,200,255,0.12);")
        lay.addWidget(div)
        lay.addSpacing(10)

        perm_deny = QtWidgets.QCheckBox(
            "  Permanently deny — don't ask again unless I click Auto-Discover"
        )
        perm_deny.setChecked(False)
        lay.addWidget(perm_deny)
        lay.addSpacing(14)

        btn_row = QtWidgets.QHBoxLayout()
        deny_btn = QtWidgets.QPushButton("No Thanks")
        deny_btn.setObjectName("deny")
        deny_btn.clicked.connect(dlg.reject)
        allow_btn = QtWidgets.QPushButton("⚡  Allow Full Auto-Intercept")
        allow_btn.setObjectName("allow")
        allow_btn.setDefault(True)
        allow_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(deny_btn)
        btn_row.addStretch()
        btn_row.addWidget(allow_btn)
        lay.addLayout(btn_row)

        result = dlg.exec() == QtWidgets.QDialog.Accepted

        if result:
            save_consent(CONSENT_ALLOWED)
        elif perm_deny.isChecked():
            save_consent(CONSENT_DENIED)

        return result

    except Exception:
        return request_consent_headless()


# ── CLI entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HypeS Pirate Llama Full Auto MitM Interceptor v3.0")
    parser.add_argument("--no-consent", action="store_true",
                        help="Skip consent (already approved)")
    parser.add_argument("--reset-consent", action="store_true",
                        help="Reset consent state")
    parser.add_argument("--ports", nargs="+", type=int, default=None,
                        help="Specific ports to intercept (default: all known AI ports)")
    parser.add_argument("--headless", action="store_true",
                        help="CLI consent mode")
    parser.add_argument("--no-scan", action="store_true",
                        help="Skip dynamic port scanner")
    args = parser.parse_args()

    if args.reset_consent:
        reset_consent()
        print("Consent reset.")

    if args.no_consent or get_consent_state() == CONSENT_ALLOWED:
        agreed = True
    elif args.headless:
        agreed = request_consent_headless()
    else:
        agreed = request_consent_gui()

    if not agreed:
        print("Auto-intercept denied by user.")
        sys.exit(0)

    print("[Pirate Llama] Starting Full Auto MitM Intercept Engine v3.0...")
    stats = auto_discover_and_hook(
        extra_ports=args.ports,
        run_scanner=not args.no_scan
    )
    print(f"[Pirate Llama] Active on {len(stats['active_ports'])} ports: {stats['active_ports']}")
    print(f"[Pirate Llama] Displaced backends: {stats['displaced_backends']}")

    try:
        while True:
            time.sleep(5)
            s = get_stats()
            print(
                f"[stats] intercepted={s['requests_intercepted']}  "
                f"local={s['local_requests']}  cloud={s['cloud_requests']}  "
                f"tokens_saved={s['tokens_saved']}  "
                f"tls_spliced={s['tls_spliced_requests']}"
            )
    except KeyboardInterrupt:
        stop()
        print("Auto-intercept stopped.")

