$ErrorActionPreference = "Stop"

Write-Host "Re-building Release Target to ensure UPX packing..."
Set-Location "$PSScriptRoot\build"
cmake --build . --config Release

$StubPath = "..\installer_stub.bat"
$OutputPath = "..\PirateLlama_Installer.bat"

if (-not (Test-Path $StubPath)) {
    Write-Error "installer_stub.bat not found!"
}

$StubContent = Get-Content $StubPath -Raw

$Binaries = @(
    "Release\pirate_llama.exe",
    "Release\python_bridge.dll"
)

$PayloadScript = ""

foreach ($Bin in $Binaries) {
    if (-not (Test-Path $Bin)) {
        Write-Error "Missing binary: $Bin"
    }
    
    $FileName = Split-Path $Bin -Leaf
    Write-Host "Encoding $FileName..."
    
    $Bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $Bin).Path)
    $Base64 = [Convert]::ToBase64String($Bytes)
    
    $PayloadScript += "`nWrite-Base64ToFile -B64 '$Base64' -Path `"`$InstallDir\$FileName`""
}

$FinalContent = $StubContent -replace "# --- PAYLOADS INJECTED HERE BY BUILD SCRIPT ---`r?`n# --- END PAYLOADS ---", $PayloadScript

Set-Content -Path $OutputPath -Value $FinalContent -Encoding Ascii
Write-Host "Success! Created Single-Click Installer at $OutputPath"
