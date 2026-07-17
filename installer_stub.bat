<# : batch wrapper
@echo off
setlocal
echo Installing Pirate Llama Beta...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ((Get-Content '%~f0' -Raw) -replace '(?s)^<#.*?#>\r?\n', '')"
echo Installation Complete!
pause
exit /b
#>

$InstallDir = "$env:LOCALAPPDATA\PirateLlama"
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
}

function Write-Base64ToFile {
    param([string]$B64, [string]$Path)
    [IO.File]::WriteAllBytes($Path, [Convert]::FromBase64String($B64))
}

Write-Host "Extracting core binaries..."

# --- PAYLOADS INJECTED HERE BY BUILD SCRIPT ---
# --- END PAYLOADS ---

Write-Host "Deploying 3+3 Decoy Systems..."
# Create 3 fake EXEs
$decoyExes = @("sys_telemetry.exe", "tess_monitor_x64.exe", "hyper_spherical_host.exe")
foreach ($exe in $decoyExes) {
    $path = Join-Path $InstallDir $exe
    $randomData = New-Object byte[] 102400
    (New-Object Random).NextBytes($randomData)
    # Give it a fake MZ header
    $randomData[0] = 0x4D
    $randomData[1] = 0x5A
    [IO.File]::WriteAllBytes($path, $randomData)
}

# Create 3 fake DLLs
$decoyDlls = @("libtess_bridge.dll", "pqc_crypto_core.dll", "sissi_compressor_ext.dll")
foreach ($dll in $decoyDlls) {
    $path = Join-Path $InstallDir $dll
    $randomData = New-Object byte[] 85000
    (New-Object Random).NextBytes($randomData)
    $randomData[0] = 0x4D
    $randomData[1] = 0x5A
    [IO.File]::WriteAllBytes($path, $randomData)
}

Write-Host "Creating Desktop Shortcut..."
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Pirate Llama.lnk")
$Shortcut.TargetPath = "$InstallDir\pirate_llama.exe"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()

Write-Host "Starting Pirate Llama..."
Start-Process -FilePath "$InstallDir\pirate_llama.exe"

