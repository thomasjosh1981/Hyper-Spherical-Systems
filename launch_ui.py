# launch_ui.py — Hyper-Spherical Systems
#
# Launcher for the Pirate Llama web dashboard.
# Tries to start a local Flask/http.server backend on port 7860.
# Falls back to opening the HTML file directly if no server is available.
#
# Usage:
#   python launch_ui.py           # Auto-detect (server preferred)
#   python launch_ui.py --no-server   # Force file:// open
#   python launch_ui.py --port 8080   # Custom port
#
# License: MIT

import os
import sys
import time
import socket
import subprocess
import webbrowser
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
GUI_DIR = ROOT / "gui" / "pirate_gui"
SERVER_PY = ROOT / "gui" / "server.py"
INDEX_HTML = GUI_DIR / "index.html"
DEFAULT_PORT = 7860


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def check_flask() -> bool:
    try:
        import importlib
        return importlib.util.find_spec("flask") is not None
    except Exception:
        return False


def start_server(port: int) -> subprocess.Popen | None:
    if not SERVER_PY.exists():
        return None
    env = os.environ.copy()
    env["PIRATE_PORT"] = str(port)
    env["PIRATE_ROOT"] = str(ROOT)
    try:
        proc = subprocess.Popen(
            [sys.executable, str(SERVER_PY), "--port", str(port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait up to 3 seconds for server to start
        for _ in range(15):
            time.sleep(0.2)
            if port_is_free(port) is False:  # port is now occupied → server started
                return proc
            if proc.poll() is not None:  # process died
                return None
        return proc
    except Exception as e:
        print(f"[launch_ui] Server start failed: {e}")
        return None


def open_file_fallback():
    if not INDEX_HTML.exists():
        print(f"[launch_ui] ERROR: GUI not found at {INDEX_HTML}")
        print("  Run the build step or ensure gui/pirate_gui/index.html exists.")
        return False
    url = INDEX_HTML.as_uri()
    print(f"[launch_ui] Opening file directly: {url}")
    webbrowser.open(url)
    return True


def main():
    parser = argparse.ArgumentParser(description="Pirate Llama Web UI Launcher")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Server port")
    parser.add_argument("--no-server", action="store_true",
                        help="Skip server, open HTML directly")
    args = parser.parse_args()

    print("=" * 60)
    print("  🏴‍☠️  PIRATE LLAMA — WEB UI LAUNCHER")
    print("  Hyper-Spherical Systems  |  v2.0")
    print("=" * 60)

    if args.no_server:
        open_file_fallback()
        return

    port = args.port
    if not port_is_free(port):
        print(f"[launch_ui] Port {port} already in use — opening existing server.")
        url = f"http://localhost:{port}"
        webbrowser.open(url)
        print(f"[launch_ui] Dashboard at: {url}")
        return

    # Try to start the server
    print(f"[launch_ui] Starting backend server on port {port}...")
    proc = start_server(port)

    if proc is not None:
        url = f"http://localhost:{port}"
        print(f"[launch_ui] ✅ Server running at: {url}")
        print(f"[launch_ui] Opening dashboard...")
        time.sleep(0.3)
        webbrowser.open(url)

        print("\n[launch_ui] Press Ctrl+C to stop the server.")
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            print("\n[launch_ui] Server stopped. Goodbye, Captain.")
    else:
        print("[launch_ui] Server unavailable — falling back to file mode.")
        open_file_fallback()


if __name__ == "__main__":
    main()
