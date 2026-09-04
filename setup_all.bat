@echo off
echo ============================================================================
echo   PROJECT TESSERACT & HYPERMEM MASTER ECOSYSTEM SETUP
echo ============================================================================
cd /d "%~dp0"

echo [*] Installing HyperMem Package...
pip install -e hypermem

echo [*] Installing Synthuron Context Package...
pip install -e synthuron_context

echo [*] Installing Tesseract Engine Package...
pip install -e tesseract_engine

echo [*] Installing ISSI Compression Package...
pip install -e issi_compression

echo [*] Installing Layer Streamer Package...
pip install -e layer_streamer

echo.
echo ============================================================================
echo [SUCCESS] All 5 Project Tesseract & HyperMem packages installed successfully!
echo   To launch HyperMem Proxy on Port 8765:
echo     python hypermem\hypermem\cli.py --serve --port 8765
echo.
echo   To open the Tesseract 3D Visualizer:
echo     Open tesseract_engine\index.html in your browser
echo ============================================================================
echo.
pause
