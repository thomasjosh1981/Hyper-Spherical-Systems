Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  PROJECT TESSERACT & HYPERMEM MASTER ECOSYSTEM SETUP" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan

$root = $PSScriptRoot
Set-Location $root

$packages = @("hypermem", "synthuron_context", "tesseract_engine", "issi_compression", "layer_streamer")

foreach ($pkg in $packages) {
    Write-Host "[*] Installing $pkg package in editable mode..." -ForegroundColor Yellow
    pip install -e $pkg
}

Write-Host "`n[SUCCESS] All 5 packages installed successfully!" -ForegroundColor Green
Write-Host "  • Start HyperMem Service: python hypermem/hypermem/cli.py --serve --port 8765"
Write-Host "  • 3D Tesseract WebGL:    Open tesseract_engine/index.html in browser"
