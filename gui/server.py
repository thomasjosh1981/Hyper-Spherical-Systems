# gui/server.py — Pirate Llama Web Dashboard Backend
#
# Routes:
#   GET  /                      → index.html
#   GET  /api/status            → system status JSON
#   GET  /api/drives            → drive topology JSON
#   GET  /api/models/local      → discovered SFS/GGUF/HSCC files JSON
#   GET  /api/assets            → full asset registry JSON
#   POST /api/benchmark         → run nvme_benchmark
#   POST /api/gcs/spin          → launch GCS (SSE stream)
#   GET  /api/hf/search         → HuggingFace search proxy
#   GET  /api/hf/recs           → brain model recommendations
#   GET  /api/onboarding        → onboarding status
#   POST /api/onboarding        → save onboarding config
#   POST /api/session/open      → open a M2M+SISSI+5+1 cloud session
#   POST /api/session/chat      → send compressed message, get decoded response
#   GET  /api/session/stats     → live token savings stats
#   POST /api/session/close     → teardown session (zeroes key material)
#   POST /api/session/preview   → stateless compression preview
#
# License: MIT

import os
import sys
import json
import time
import shutil
import subprocess
import argparse
import threading
from pathlib import Path
from typing import Generator

ROOT    = Path(os.environ.get("PIRATE_ROOT", Path(__file__).parent.parent))
GUI_DIR = Path(__file__).parent / "pirate_gui"
BIN_DIR = ROOT / "build"
KEYSTORE= ROOT / "pirate_keystore.enc"
PORT    = int(os.environ.get("PIRATE_PORT", 7860))

# Import session engine (Python thin wrapper — core logic is C++ DLL)
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from session_engine import CloudSession, SessionCipher
    _SESSION_ENGINE_OK = True
except ImportError as e:
    _SESSION_ENGINE_OK = False
    print(f"[server] session_engine not available: {e}")

# Active sessions store  { session_id: CloudSession }
_sessions: dict = {}
_sessions_lock  = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_exe(name: str) -> str | None:
    """Find a built executable in common build dirs."""
    candidates = [
        BIN_DIR / "Release" / f"{name}.exe",
        BIN_DIR / "Debug"   / f"{name}.exe",
        BIN_DIR / name,
        ROOT / "build_enterprise" / "Release" / f"{name}.exe",
        ROOT / "release" / f"{name}.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return shutil.which(name)


def scan_models(root: str, max_depth: int = 3) -> list[dict]:
    """Scan for AI model files."""
    exts = {".gguf", ".sfs", ".sfsp", ".hscc"}
    results = []
    base = Path(root)
    if not base.exists():
        return results

    def _scan(p: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for entry in p.iterdir():
                if entry.is_dir():
                    _scan(entry, depth + 1)
                elif entry.is_file() and entry.suffix.lower() in exts:
                    results.append({
                        "path":     str(entry),
                        "filename": entry.name,
                        "format":   entry.suffix.lstrip(".").lower(),
                        "size_mb":  round(entry.stat().st_size / 1e6, 1),
                    })
        except PermissionError:
            pass
    _scan(base, 0)
    return results


def get_drives() -> list[dict]:
    """Enumerate fixed drives (Windows) or return / on Linux/Mac."""
    drives = []
    if sys.platform == "win32":
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if not (mask & (1 << i)):
                continue
            letter = chr(ord("A") + i)
            path = f"{letter}:\\"
            dtype = ctypes.windll.kernel32.GetDriveTypeW(path)
            if dtype != 3:  # DRIVE_FIXED
                continue
            try:
                import shutil as _shutil
                total, used, free = _shutil.disk_usage(path)
                drives.append({
                    "letter": letter,
                    "path":   path,
                    "total_gb": round(total / 1e9, 1),
                    "free_gb":  round(free  / 1e9, 1),
                    "type":  "HDD" if total > 4e12 else "NVMe/SSD",
                    "recommended_storage": total > 4e12,
                })
            except Exception:
                pass
    else:
        import shutil as _shutil
        total, used, free = _shutil.disk_usage("/")
        drives.append({
            "letter": "/", "path": "/",
            "total_gb": round(total / 1e9, 1),
            "free_gb":  round(free  / 1e9, 1),
            "type": "Unknown", "recommended_storage": total > 4e12,
        })
    return drives


BRAIN_RECS = [
    {"repo_id": "Qwen/Qwen2.5-0.5B-Instruct",          "name": "Qwen2.5-0.5B",   "size": "0.5B", "fast": True,  "reason": "Fastest brain model — minimal RAM, best for auto-adjustment loops"},
    {"repo_id": "Qwen/Qwen2.5-1.5B-Instruct",          "name": "Qwen2.5-1.5B",   "size": "1.5B", "fast": True,  "reason": "Great balance of speed and reasoning for recursive self-adjustment"},
    {"repo_id": "microsoft/phi-3.5-mini-instruct",      "name": "Phi-3.5-Mini",   "size": "3.8B", "fast": True,  "reason": "Excellent code + reasoning, low VRAM, great supervisor brain"},
    {"repo_id": "google/gemma-2-2b-it",                 "name": "Gemma-2-2B",     "size": "2B",   "fast": True,  "reason": "High accuracy for size — good for homophonic logic"},
    {"repo_id": "meta-llama/Llama-3.2-3B-Instruct",    "name": "Llama-3.2-3B",   "size": "3B",   "fast": True,  "reason": "Excellent instruction following — recommended all-rounder"},
    {"repo_id": "meta-llama/Llama-3.1-8B-Instruct",    "name": "Llama-3.1-8B",   "size": "8B",   "fast": False, "reason": "More capable brain — requires ~6GB VRAM, best for complex models"},
]

# ── Flask routes ──────────────────────────────────────────────────────────────

def create_flask_app():
    from flask import Flask, jsonify, request, send_file, Response, stream_with_context
    app = Flask(__name__, static_folder=str(GUI_DIR), static_url_path="")

    @app.route("/")
    def index():
        return send_file(str(GUI_DIR / "index.html"))

    @app.route("/api/status")
    def api_status():
        return jsonify({
            "ok": True,
            "version": "2.0",
            "onboarding_done": KEYSTORE.exists(),
            "gcs_available": find_exe("golden_candy_spinner") is not None,
            "timestamp": time.time(),
        })

    @app.route("/api/drives")
    def api_drives():
        return jsonify(get_drives())

    @app.route("/api/models/local")
    def api_models_local():
        root = request.args.get("root", str(ROOT))
        depth = int(request.args.get("depth", 3))
        return jsonify(scan_models(root, depth))

    @app.route("/api/assets")
    def api_assets():
        # Scan common model dirs
        results = []
        for search_root in [str(ROOT), str(Path.home() / "models"),
                             str(Path.home() / "Downloads")]:
            results.extend(scan_models(search_root, 3))
        seen = set()
        unique = []
        for r in results:
            if r["path"] not in seen:
                seen.add(r["path"])
                unique.append(r)
        return jsonify(unique)

    @app.route("/api/benchmark", methods=["POST"])
    def api_benchmark():
        exe = find_exe("nvme_benchmark")
        if not exe:
            return jsonify({"error": "nvme_benchmark not found", "ok": False}), 404
        try:
            result = subprocess.run([exe], capture_output=True, text=True, timeout=60)
            return jsonify({"ok": True, "output": result.stdout, "stderr": result.stderr})
        except subprocess.TimeoutExpired:
            return jsonify({"ok": False, "error": "Benchmark timed out"}), 504

    @app.route("/api/gcs/spin", methods=["POST"])
    def api_gcs_spin():
        """Launch GCS and stream stdout as Server-Sent Events."""
        data = request.get_json(force=True)
        exe = find_exe("golden_candy_spinner")
        if not exe:
            return jsonify({"error": "golden_candy_spinner not found"}), 404

        args = [exe]
        if data.get("hf_download"):
            args += ["--hf-download", data["hf_download"]]
        elif data.get("inputs"):
            args += ["--inputs"] + data["inputs"]

        if data.get("output"):      args += ["--output", data["output"]]
        if data.get("mode"):        args += ["--mode",   data["mode"]]
        if data.get("brain"):       args += ["--brain",  data["brain"]]
        if data.get("brain_hf"):    args += ["--brain-hf", data["brain_hf"]]
        if data.get("hf_token"):    args += ["--hf-token",  data["hf_token"]]
        if data.get("hf_validate"): args += ["--hf-validate", data["hf_validate"]]
        if data.get("mtp"):         args += ["--mtp"]
        if data.get("multimodal"):  args += ["--multimodal"]
        if data.get("tool_calling"):args += ["--tool-calling"]
        if data.get("persist"):     args += ["--persist"]
        if data.get("advanced"):    args += ["--advanced"]
        if data.get("compression_order"):
            args += ["--compression-order", data["compression_order"]]
        if data.get("benchmark_compare"):
            args += ["--benchmark-compare"]
        if data.get("hdd_drive"):   args += ["--hdd-drive", data["hdd_drive"]]

        def generate() -> Generator[str, None, None]:
            try:
                proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
                rc = proc.wait()
                yield f"data: {json.dumps({'done': True, 'rc': rc})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(stream_with_context(generate()),
                        content_type="text/event-stream",
                        headers={"Cache-Control": "no-cache",
                                 "X-Accel-Buffering": "no"})

    @app.route("/api/hf/search")
    def api_hf_search():
        q = request.args.get("q", "")
        # Simple HF API proxy
        try:
            import urllib.request
            url = f"https://huggingface.co/api/models?search={q}&limit=10&sort=downloads"
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read())
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e), "fallback": BRAIN_RECS})

    @app.route("/api/hf/recs")
    def api_hf_recs():
        return jsonify(BRAIN_RECS)

    @app.route("/api/onboarding", methods=["GET"])
    def api_onboarding_get():
        return jsonify({"completed": KEYSTORE.exists()})

    @app.route("/api/onboarding", methods=["POST"])
    def api_onboarding_post():
        cfg = request.get_json(force=True)
        # Write a minimal keystore so is_completed() returns True
        try:
            import base64
            raw = "\n".join(f"{k}={v}" for k, v in cfg.items()) + "\ncompleted=1\n"
            # XOR-obfuscate (must match C++ implementation)
            encoded = bytes(b ^ 0xA7 for b in raw.encode())
            KEYSTORE.write_bytes(encoded)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/github/check_update")
    def api_github_check_update():
        """Checks GitHub releases to determine if a major update has been cut."""
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/repos/thomasjosh1981/Hyper-Spherical-Systems/releases/latest",
                headers={"User-Agent": "PirateLlama-VersionChecker/2.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "v2.0-beta")
            return jsonify({
                "latest_version": tag,
                "current_version": "v2.0-beta",
                "is_beta": True,
                "mandatory_update": False, # set to True when major version > current
                "html_url": data.get("html_url", "https://github.com/thomasjosh1981/Hyper-Spherical-Systems"),
            })
        except Exception as e:
            return jsonify({
                "latest_version": "v2.0-beta",
                "current_version": "v2.0-beta",
                "is_beta": True,
                "mandatory_update": False,
                "error": str(e),
            })

    # ── M2M Session Endpoints ──────────────────────────────────────────────────
    @app.route("/api/session/open", methods=["POST"])
    def api_session_open():
        if not _SESSION_ENGINE_OK:
            return jsonify({"ok": False, "error": "session_engine not loaded"}), 500
        data = request.get_json(force=True) or {}
        provider = data.get("provider", "openai")
        model    = data.get("model", "gpt-4o")
        api_key  = data.get("api_key", "")
        base_url = data.get("base_url", "")

        sess = CloudSession(provider=provider, model=model, api_key=api_key, base_url=base_url)
        stats = sess.open()
        with _sessions_lock:
            _sessions[sess.stats.session_token] = sess

        return jsonify({
            "ok": True,
            "session_token": sess.stats.session_token,
            "status": stats.handshake_status,
            "handshake_cost": stats.handshake_tokens_cost,
            "ack_message": stats.ack_message,
        })

    @app.route("/api/session/chat", methods=["POST"])
    def api_session_chat():
        if not _SESSION_ENGINE_OK:
            return jsonify({"ok": False, "error": "session_engine not loaded"}), 500
        data = request.get_json(force=True) or {}
        token = data.get("session_token", "")
        text  = data.get("message", "")

        with _sessions_lock:
            sess = _sessions.get(token)

        if not sess:
            # Fallback: create an ephemeral preview session if no token provided
            sess = CloudSession(provider=data.get("provider", "openai"), model=data.get("model", "gpt-4o"))
            sess.open()

        res = sess.chat(text)
        return jsonify(res)

    @app.route("/api/session/stats")
    def api_session_stats():
        token = request.args.get("session_token", "")
        with _sessions_lock:
            sess = _sessions.get(token)
            if not sess and _sessions:
                sess = list(_sessions.values())[-1]  # get latest session

        if not sess:
            return jsonify({"is_open": False, "total_tokens_saved": 0, "overall_ratio": 1.0})

        return jsonify(sess.get_stats())

    @app.route("/api/session/close", methods=["POST"])
    def api_session_close():
        data = request.get_json(force=True) or {}
        token = data.get("session_token", "")
        with _sessions_lock:
            sess = _sessions.pop(token, None)

        if sess:
            stats = sess.close()
            return jsonify({"ok": True, "total_saved": stats.total_tokens_saved, "ratio": round(stats.overall_ratio, 2)})
        return jsonify({"ok": False, "error": "Session not found"})

    @app.route("/api/session/preview", methods=["POST"])
    def api_session_preview():
        if not _SESSION_ENGINE_OK:
            return jsonify({"ok": False, "error": "session_engine not loaded"}), 500
        data = request.get_json(force=True) or {}
        text = data.get("text", "")
        res = CloudSession.preview_compression(text)
        return jsonify(res)

    return app


# ── Stdlib fallback server ─────────────────────────────────────────────────────

def run_stdlib_server(port: int):
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import urllib.parse

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(GUI_DIR), **kw)

        def do_GET(self):
            if self.path.startswith("/api/"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = {"error": "Install Flask for full API support", "ok": False}
                if self.path == "/api/status":
                    payload = {"ok": True, "version": "2.0-lite",
                               "onboarding_done": KEYSTORE.exists()}
                elif self.path == "/api/drives":
                    payload = get_drives()
                elif self.path == "/api/hf/recs":
                    payload = BRAIN_RECS
                self.wfile.write(json.dumps(payload).encode())
            else:
                super().do_GET()

        def log_message(self, fmt, *args):
            pass  # Suppress request log spam

    server = HTTPServer(("", port), Handler)
    print(f"[server] Stdlib HTTP server on http://localhost:{port}")
    server.serve_forever()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    try:
        import flask
        app = create_flask_app()
        print(f"[server] Flask server on http://localhost:{args.port}")
        app.run(host="0.0.0.0", port=args.port, threaded=True, debug=False)
    except ImportError:
        print("[server] Flask not installed — using stdlib server (limited API).")
        print("[server] Install Flask for full SSE streaming: pip install flask")
        run_stdlib_server(args.port)
