# build_patcher.ps1 - Builds PirateLlama_patch.exe standalone
# Run from the hyper_spherical_systems root directory

$src = ".\tools\community_patcher\PirateLlama_patch.cpp"
$out = ".\tools\community_patcher\PirateLlama_patch.exe"

# Locate MSVC cl.exe for x64
$cl = Get-ChildItem "C:\Program Files\Microsoft Visual Studio" -Recurse -Filter "cl.exe" -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -like "*Hostx64*\x64*" } |
      Select-Object -First 1 -ExpandProperty FullName

if (-not $cl) {
    # Try alternate VS path
    $cl = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -Recurse -Filter "cl.exe" -ErrorAction SilentlyContinue |
          Where-Object { $_.FullName -like "*x64*" } |
          Select-Object -First 1 -ExpandProperty FullName
}

if (-not $cl) {
    Write-Host "[ERROR] Could not find MSVC cl.exe. Open a Visual Studio Developer Command Prompt and run:"
    Write-Host "  cl /nologo /O2 /EHsc $src /link advapi32.lib /OUT:$out /SUBSYSTEM:CONSOLE"
    exit 1
}

Write-Host "[*] Compiler: $cl"
Write-Host "[*] Building patcher..."

$proc = Start-Process -FilePath $cl -ArgumentList @(
    "/nologo", "/O2", "/EHsc", "/W3",
    $src,
    "/link", "advapi32.lib",
    "/OUT:$out",
    "/SUBSYSTEM:CONSOLE"
) -Wait -PassThru -NoNewWindow

if ($proc.ExitCode -eq 0) {
    Write-Host "[+] Success! Patcher built at: $out"

    # UPX pack if available
    $upx = Get-Command "upx" -ErrorAction SilentlyContinue
    if ($upx) {
        Write-Host "[*] Packing with UPX..."
        & upx --best --lzma $out | Out-Null
        Write-Host "[+] UPX done."
    } else {
        Write-Host "[~] UPX not found - skipping pack (optional)"
    }
} else {
    Write-Host "[!] Build failed with exit code $($proc.ExitCode)"
    exit 1
}
