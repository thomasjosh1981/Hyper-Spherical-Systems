#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# HypeS (Hyper-Spherical Systems) Universal Suite Launcher for macOS
# ════════════════════════════════════════════════════════════════════════════

echo "============================================================"
echo "  HypeS (Hyper-Spherical Systems) — macOS Release Suite    "
echo "============================================================"
echo "[*] Checking Python3 runtime..."

if ! command -v python3 &> /dev/null; then
    echo "[!] Error: python3 is required to launch HypeS Web Server & GUI."
    exit 1
fi

echo "[*] Booting Hyper-Spherical Flask Backend & PySide6 Desktop GUI..."
python3 -c "import sys; sys.path.insert(0, 'gui'); import server; server.start_server_in_thread(); import pirate_gui.__main__ as gui; gui.main()"
