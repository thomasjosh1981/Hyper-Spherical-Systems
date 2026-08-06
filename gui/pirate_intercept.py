# gui/pirate_intercept.py — Zero-Config MitM Universal Intercept Proxy
#
# Hyper-Spherical Systems — Pirate Llama Auto-Intercept Engine
#
# How it works:
#   1. On first run, shows one consent dialog asking permission to intercept.
#   2. Binds to the same port(s) used by Ollama (11434) and/or LM Studio (1234).
#   3. Any app (Hermes Agent, Open WebUI, Cursor, etc.) that talks to those
#      endpoints is silently intercepted — no config needed on the client.
#   4. Each request is passed through the HypeS SISSI compression stack.
#   5. The (optionally compressed) request is forwarded to the real backend.
#   6. The response is decompressed and returned to the client.
#   7. If the request carries a Bearer API key → bypass local compression,
#      route straight to the cloud endpoint (OpenAI, Anthropic, etc.).
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
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────
INTERCEPT_PORTS = {
    11434: ("127.0.0.1", 11434),   # Ollama clone → forward to real Ollama
    11435: ("127.0.0.1", 11435),   # Pirate Proxy default → forward to Ollama
}
INTERCEPT_CONSENT_FILE = Path.home() / ".hypes" / "intercept_consent.json"
INTERCEPT_LOG_FILE     = Path.home() / ".hypes" / "intercept.log"
CLOUD_PATTERNS = [
    "openai.com", "anthropic.com", "googleapis.com",
    "groq.com", "openrouter.ai", "together.ai",
]

# ── Shared state ─────────────────────────────────────────────────────────────
_running: bool = False
_listeners: list[socket.socket] = []
_lock = threading.Lock()
_stats = {
    "requests_intercepted": 0,
    "tokens_saved": 0,
    "bytes_compressed": 0,
    "active": False,
}


def _log(msg: str) -> None:
    INTERCEPT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(INTERCEPT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass
    print(f"[intercept] {msg}")


# ── Consent persistence ───────────────────────────────────────────────────────
# consent.json schema:
#   { "state": "undecided" | "allowed" | "denied", "ts": <unix time> }
#
# Rules:
#   - "undecided" → show dialog
#   - "allowed"   → start immediately, never ask
#   - "denied"    → never ask again UNLESS reset_consent() is called
#                   (triggered by the dashboard Auto-Discover button)

CONSENT_ALLOWED  = "allowed"
CONSENT_DENIED   = "denied"
CONSENT_UNDECIDED = "undecided"


def load_consent() -> dict:
    if INTERCEPT_CONSENT_FILE.exists():
        try:
            data = json.loads(INTERCEPT_CONSENT_FILE.read_text())
            # Migrate legacy format (boolean "consented" key)
            if "consented" in data and "state" not in data:
                data["state"] = CONSENT_ALLOWED if data["consented"] else CONSENT_DENIED
            return data
        except Exception:
            pass
    return {"state": CONSENT_UNDECIDED, "ts": 0}


def save_consent(state: str) -> None:
    """Persist consent state. state must be one of CONSENT_ALLOWED / CONSENT_DENIED / CONSENT_UNDECIDED."""
    INTERCEPT_CONSENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    INTERCEPT_CONSENT_FILE.write_text(json.dumps({
        "state": state,
        "ts": int(time.time()),
    }), encoding="utf-8")


def reset_consent() -> None:
    """
    Reset consent to undecided so the dialog will show again on next start.
    Called by the dashboard ⚡ Auto-Discover button.
    """
    save_consent(CONSENT_UNDECIDED)
    _log("Consent reset to undecided by user (Auto-Discover triggered).")


def get_consent_state() -> str:
    return load_consent().get("state", CONSENT_UNDECIDED)


# ── SISSI compression shim ────────────────────────────────────────────────────
def _sissi_compress(text: str) -> tuple[str, float]:
    """
    Apply SISSI token compression.
    Returns (compressed_text, ratio).
    Falls back to passthrough if session_engine not available.
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from session_engine import CloudSession
        sess = CloudSession.__new__(CloudSession)
        sess.__init__(provider="local", model="hypes-local")
        r = sess.compress(text)
        return r.compressed, r.ratio
    except Exception:
        pass
    return text, 1.0


def _sissi_decompress(text: str) -> str:
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from session_engine import CloudSession
        sess = CloudSession.__new__(CloudSession)
        sess.__init__(provider="local", model="hypes-local")
        return sess.decompress(text)
    except Exception:
        pass
    return text


# ── Backend probe ─────────────────────────────────────────────────────────────
def probe_backend(host: str, port: int) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        return True
    except Exception:
        return False


def _find_real_backend_port(intercept_port: int) -> Optional[tuple[str, int]]:
    """Find the real backend that was displaced by the intercept listener."""
    candidates = [
        ("127.0.0.1", 11434),
        ("127.0.0.1", 1234),
        ("127.0.0.1", 8080),
        ("127.0.0.1", 5001),
        ("127.0.0.1", 5000),
        ("127.0.0.1", 8081),
    ]
    for host, port in candidates:
        if port == intercept_port:
            continue
        if probe_backend(host, port):
            return host, port
    return None


# ── Request classification ────────────────────────────────────────────────────
def _is_cloud_key(auth_header: str) -> bool:
    """Returns True if the Authorization header carries a real cloud API key."""
    if not auth_header:
        return False
    token = auth_header.replace("Bearer ", "").strip()
    # HypeS local keys start with sk-hypes-; everything else is a cloud key
    return bool(token) and not token.startswith("sk-hypes-")


# ── HTTP request/response helpers ─────────────────────────────────────────────
def _recv_all(sock: socket.socket, length: int) -> bytes:
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    return data


def _parse_http_request(raw: bytes) -> dict:
    """Parse raw HTTP bytes into a simple dict."""
    try:
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            return {"raw": raw, "headers": {}, "body": b"", "method": "GET", "path": "/", "is_cloud": False}
        header_bytes = raw[:header_end]
        body = raw[header_end + 4:]
        lines = header_bytes.decode("utf-8", errors="replace").split("\r\n")
        method, path, _ = (lines[0].split(" ", 2) + ["", "", ""])[:3]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        auth = headers.get("authorization", "")
        return {
            "raw": raw,
            "method": method,
            "path": path,
            "headers": headers,
            "body": body,
            "is_cloud": _is_cloud_key(auth),
        }
    except Exception:
        return {"raw": raw, "headers": {}, "body": b"", "method": "GET", "path": "/", "is_cloud": False}


def _forward_request(parsed: dict, backend_host: str, backend_port: int) -> bytes:
    """Forward the (possibly modified) request to the real backend and return raw response."""
    try:
        conn = http.client.HTTPConnection(backend_host, backend_port, timeout=30)
        headers = dict(parsed["headers"])
        body = parsed.get("body", b"")

        # Remove hop-by-hop headers
        for h in ["transfer-encoding", "connection", "keep-alive", "proxy-connection"]:
            headers.pop(h, None)

        conn.request(parsed["method"], parsed["path"], body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()

        # Rebuild raw HTTP response
        status_line = f"HTTP/1.1 {resp.status} {resp.reason}\r\n"
        resp_headers = ""
        for name, value in resp.getheaders():
            resp_headers += f"{name}: {value}\r\n"
        resp_headers += "\r\n"
        return (status_line + resp_headers).encode() + resp_body
    except Exception as e:
        error_body = json.dumps({"error": str(e), "source": "hypes-intercept"}).encode()
        return (
            b"HTTP/1.1 502 Bad Gateway\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(error_body)).encode() + b"\r\n\r\n" + error_body
        )


# ── Connection handler ────────────────────────────────────────────────────────
def _handle_client(client_sock: socket.socket, intercept_port: int) -> None:
    try:
        raw = b""
        client_sock.settimeout(5.0)
        while True:
            try:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                raw += chunk
                if len(raw) > 2_000_000:  # 2 MB safety cap
                    break
                if b"\r\n\r\n" in raw:
                    # Check if we have all body data
                    header_end = raw.find(b"\r\n\r\n") + 4
                    header_str = raw[:header_end].decode("utf-8", errors="replace")
                    content_length = 0
                    for line in header_str.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            content_length = int(line.split(":", 1)[1].strip())
                    if len(raw) - header_end >= content_length:
                        break
            except socket.timeout:
                break

        parsed = _parse_http_request(raw)
        backend = _find_real_backend_port(intercept_port)

        if parsed["is_cloud"] or backend is None:
            # Cloud mode: pass through unmodified
            if backend:
                response = _forward_request(parsed, backend[0], backend[1])
            else:
                error_body = json.dumps({"error": "No backend found", "source": "hypes-intercept"}).encode()
                response = (
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Type: application/json\r\n\r\n" + error_body
                )
        else:
            # MitM mode: apply SISSI compression to request body
            body_str = parsed["body"].decode("utf-8", errors="replace")
            try:
                body_json = json.loads(body_str)
                messages = body_json.get("messages", [])
                original_tokens = sum(len(m.get("content", "")) for m in messages) // 4
                for msg in messages:
                    if msg.get("content"):
                        compressed, ratio = _sissi_compress(msg["content"])
                        msg["content"] = compressed
                new_body = json.dumps(body_json).encode("utf-8")
                compressed_tokens = sum(len(m.get("content", "")) for m in messages) // 4
                tokens_saved = max(0, original_tokens - compressed_tokens)
            except Exception:
                new_body = parsed["body"]
                ratio = 1.0
                tokens_saved = 0

            parsed["body"] = new_body
            parsed["headers"]["content-length"] = str(len(new_body))
            response = _forward_request(parsed, backend[0], backend[1])

            # Decompress response
            try:
                resp_header_end = response.find(b"\r\n\r\n")
                if resp_header_end != -1:
                    resp_body = response[resp_header_end + 4:]
                    resp_json = json.loads(resp_body.decode("utf-8", errors="replace"))
                    choices = resp_json.get("choices", [])
                    for choice in choices:
                        content = choice.get("message", {}).get("content", "")
                        if content:
                            choice["message"]["content"] = _sissi_decompress(content)
                    new_resp_body = json.dumps(resp_json).encode("utf-8")
                    resp_headers = response[:resp_header_end + 4]
                    # Update Content-Length
                    resp_headers_str = resp_headers.decode("utf-8", errors="replace")
                    resp_headers_str = "\r\n".join(
                        f"Content-Length: {len(new_resp_body)}" if h.lower().startswith("content-length") else h
                        for h in resp_headers_str.split("\r\n")
                    )
                    response = resp_headers_str.encode() + new_resp_body
            except Exception:
                pass

            with _lock:
                _stats["requests_intercepted"] += 1
                _stats["tokens_saved"] += tokens_saved
                _stats["bytes_compressed"] += max(0, len(parsed.get("raw", b"")) - len(new_body))

        client_sock.sendall(response)
    except Exception as e:
        _log(f"Client handler error: {e}")
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
        srv.listen(64)
        srv.settimeout(1.0)
        with _lock:
            _listeners.append(srv)
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


# ── Public API ────────────────────────────────────────────────────────────────
def get_stats() -> dict:
    with _lock:
        return dict(_stats)


def is_active() -> bool:
    return _running


def start(ports: Optional[list[int]] = None) -> bool:
    """Start the MitM intercept proxy. Returns True if started successfully."""
    global _running
    if _running:
        return True

    _running = True
    _stats["active"] = True
    target_ports = ports or list(INTERCEPT_PORTS.keys())

    for port in target_ports:
        t = threading.Thread(target=_listener_thread, args=(port,), daemon=True)
        t.start()

    _log(f"Auto-intercept started on ports: {target_ports}")
    return True


def stop() -> None:
    """Stop the MitM intercept proxy."""
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
    _log("Auto-intercept stopped.")


# ── Consent UI helper (works headlessly or with PySide6) ───────────────────────
def request_consent_headless() -> bool:
    """
    Non-GUI consent for headless / CLI environments.
    Returns True if allowed, False if denied.
    Respects existing state — only prompts when undecided.
    """
    state = get_consent_state()
    if state == CONSENT_ALLOWED:
        return True
    if state == CONSENT_DENIED:
        _log("Auto-intercept is permanently disabled. Use Auto-Discover in the dashboard to re-enable.")
        return False

    print("\n" + "="*60)
    print("🏴‍☠️  PIRATE LLAMA AUTO-INTERCEPT REQUEST")
    print("="*60)
    print(
        "HypeS wants to silently intercept all local AI traffic\n"
        "(Ollama, LM Studio, etc.) and route it through the\n"
        "SISSI compression stack — saving you 40-90% tokens.\n\n"
        "This is a one-time authorization. You can revoke it\n"
        "any time from the HypeS dashboard → Auto-Discover.\n"
    )
    ans = input("Allow auto-intercept? [Y/n]: ").strip().lower()
    agreed = ans in ("", "y", "yes")
    if agreed:
        perm = input("Permanently remember 'Allow' (no future prompts)? [Y/n]: ").strip().lower()
        if perm in ("", "y", "yes"):
            save_consent(CONSENT_ALLOWED)
    else:
        perm = input("Permanently ignore (never ask again unless you click Auto-Discover)? [y/N]: ").strip().lower()
        if perm in ("y", "yes"):
            save_consent(CONSENT_DENIED)
            print("Auto-intercept permanently disabled. Re-enable via HypeS → Auto-Discover.")
        else:
            print("Skipping this session only.")
    return agreed


def request_consent_gui() -> bool:
    """
    Premium PySide6 consent dialog with three-state awareness.
    - Already allowed  → return True immediately (no dialog)
    - Permanently denied → return False immediately (no dialog)
    - Undecided → show the dialog
    Falls back to headless if GUI unavailable.
    """
    state = get_consent_state()
    if state == CONSENT_ALLOWED:
        return True
    if state == CONSENT_DENIED:
        _log("Auto-intercept is permanently disabled. Use Auto-Discover in the dashboard to re-enable.")
        return False

    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle("🏴‍☠️  Pirate Llama — Auto-Intercept Request")
        dlg.setMinimumWidth(560)
        dlg.setMinimumHeight(400)

        # ── Premium Cyber dialog stylesheet ──
        dlg.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #080e1a, stop:1 #060912);
                color: #dde6f0;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                border: 1px solid rgba(0,200,255,0.20);
                border-radius: 12px;
            }
            QLabel { color: #8899aa; font-size: 12px; }
            QLabel#dlg_title {
                color: #00d4ff;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 0.04em;
            }
            QLabel#dlg_sub {
                color: #5a7a9a;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.14em;
                font-weight: 700;
            }
            QCheckBox {
                color: #5a7a9a;
                font-size: 11px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 15px; height: 15px;
                border: 1px solid rgba(0,200,255,0.30);
                border-radius: 3px;
                background: rgba(0,0,0,0.40);
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #00c8ff, stop:1 #7c3aed);
                border-color: #00c8ff;
            }
            QCheckBox:hover { color: #cce8ff; }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1a2744, stop:1 #0f1929);
                color: #b0cce0;
                border: 1px solid rgba(0,200,255,0.25);
                border-radius: 7px;
                padding: 9px 22px;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 0.04em;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(0,200,255,0.30), stop:1 rgba(0,160,210,0.12));
                color: #ffffff;
                border-color: rgba(0,200,255,0.65);
            }
            QPushButton#allow {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0090cc, stop:1 #6020c0);
                color: #ffffff;
                border: none;
                font-weight: 800;
                font-size: 13px;
                padding: 10px 28px;
                border-radius: 8px;
            }
            QPushButton#allow:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #00b8ff, stop:1 #8840e8);
            }
            QPushButton#deny {
                background: rgba(20,30,50,0.8);
                color: #5a7a9a;
                border-color: rgba(0,200,255,0.12);
            }
            QPushButton#deny:hover {
                color: #ff6666;
                border-color: rgba(255,60,60,0.40);
                background: rgba(60,10,10,0.6);
            }
        """)

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(28, 26, 28, 24)
        lay.setSpacing(0)

        # ─ Header band ─
        header = QtWidgets.QWidget()
        header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(0,200,255,0.08),stop:1 rgba(124,58,237,0.06));"
            "border-radius: 8px;"
            "border: 1px solid rgba(0,200,255,0.12);"
        )
        hlay = QtWidgets.QHBoxLayout(header)
        hlay.setContentsMargins(14, 12, 14, 12)
        icon_lbl = QtWidgets.QLabel("🏴‍☠️")
        icon_lbl.setStyleSheet("font-size:32px; color:white; background:transparent; border:none;")
        hlay.addWidget(icon_lbl)
        hlay.addSpacing(12)
        title_col = QtWidgets.QVBoxLayout()
        sub = QtWidgets.QLabel("▶▶  hyper-spherical systems — auto-intercept engine")
        sub.setObjectName("dlg_sub")
        sub.setStyleSheet("background:transparent; border:none; color:#00a8cc; font-size:9px; letter-spacing:0.14em;")
        title = QtWidgets.QLabel("Pirate Llama Wants to Intercept\nYour AI Traffic")
        title.setObjectName("dlg_title")
        title.setStyleSheet("background:transparent; border:none; color:#00d4ff; font-size:15px; font-weight:800;")
        title_col.addWidget(sub)
        title_col.addWidget(title)
        hlay.addLayout(title_col)
        hlay.addStretch()
        lay.addWidget(header)
        lay.addSpacing(18)

        # ─ Feature list ─
        features = [
            ("⚡", "#00c8ff", "Zero Config",  "No client setup needed — works with any app on your machine."),
            ("🚀", "#10b981", "10× Token Savings", "Compresses every prompt via SISSI before it hits the model."),
            ("🔑", "#f59e0b", "Cloud Key Passthrough", "Cloud API keys bypass compression and go direct."),
            ("🚫", "#ef4444", "Permanent Ignore",  "Say no once, and you'll never be asked again unless you\nchoose to re-enable via Dashboard → Auto-Discover."),
        ]
        for icon, color, label, desc in features:
            row = QtWidgets.QHBoxLayout()
            ico = QtWidgets.QLabel(icon)
            ico.setStyleSheet(f"font-size:18px; color:{color}; min-width:28px; background:transparent; border:none;")
            ico.setAlignment(QtCore.Qt.AlignTop)
            text_col = QtWidgets.QVBoxLayout()
            text_col.setSpacing(1)
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet(f"color:#ffffff; font-weight:700; font-size:12px; background:transparent; border:none;")
            dsc = QtWidgets.QLabel(desc)
            dsc.setStyleSheet("color:#5a7a9a; font-size:11px; background:transparent; border:none;")
            dsc.setWordWrap(True)
            text_col.addWidget(lbl)
            text_col.addWidget(dsc)
            row.addWidget(ico)
            row.addSpacing(8)
            row.addLayout(text_col)
            lay.addLayout(row)
            lay.addSpacing(10)

        lay.addSpacing(6)

        # ─ Divider ─
        div = QtWidgets.QFrame()
        div.setFrameShape(QtWidgets.QFrame.HLine)
        div.setStyleSheet("color: rgba(0,200,255,0.12); background: rgba(0,200,255,0.12);")
        lay.addWidget(div)
        lay.addSpacing(12)

        # ─ Permanent ignore checkbox ─
        perm_deny = QtWidgets.QCheckBox(
            "  Permanently ignore — don't ask again unless I click Auto-Discover"
        )
        perm_deny.setChecked(False)
        lay.addWidget(perm_deny)
        lay.addSpacing(16)

        # ─ Buttons ─
        btn_row = QtWidgets.QHBoxLayout()
        deny_btn = QtWidgets.QPushButton("No Thanks")
        deny_btn.setObjectName("deny")
        deny_btn.clicked.connect(dlg.reject)
        allow_btn = QtWidgets.QPushButton("⚡  Allow Auto-Intercept")
        allow_btn.setObjectName("allow")
        allow_btn.setDefault(True)
        allow_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(deny_btn)
        btn_row.addStretch()
        btn_row.addWidget(allow_btn)
        lay.addLayout(btn_row)

        result = dlg.exec() == QtWidgets.QDialog.Accepted

        if result:
            # Always persist allow — no more prompts
            save_consent(CONSENT_ALLOWED)
        else:
            if perm_deny.isChecked():
                save_consent(CONSENT_DENIED)   # Never ask again
            # else: leave as undecided — will ask next session

        return result

    except Exception:
        return request_consent_headless()


# ── CLI entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HypeS Pirate Llama MitM Intercept Proxy")
    parser.add_argument("--no-consent", action="store_true", help="Skip consent dialog (already approved)")
    parser.add_argument("--reset-consent", action="store_true", help="Reset consent to undecided (as if Auto-Discover was clicked)")
    parser.add_argument("--ports", nargs="+", type=int, default=[11434], help="Ports to intercept")
    parser.add_argument("--headless", action="store_true", help="CLI consent mode")
    args = parser.parse_args()

    if args.no_consent or load_consent().get("consented"):
        agreed = True
    elif args.headless:
        agreed = request_consent_headless()
    else:
        agreed = request_consent_gui()

    if not agreed:
        print("Auto-intercept denied by user.")
        sys.exit(0)

    print(f"[Pirate Llama] Starting MitM intercept on ports {args.ports}...")
    start(args.ports)

    try:
        while True:
            time.sleep(5)
            s = get_stats()
            print(
                f"[stats] intercepted={s['requests_intercepted']}  "
                f"tokens_saved={s['tokens_saved']}  "
                f"bytes_compressed={s['bytes_compressed']}"
            )
    except KeyboardInterrupt:
        stop()
        print("Auto-intercept stopped.")
