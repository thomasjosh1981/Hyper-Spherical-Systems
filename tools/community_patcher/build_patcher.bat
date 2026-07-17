@echo off
setlocal

set "SRC=%~dp0PirateLlama_patch.cpp"
set "OUT=%~dp0PirateLlama_patch.exe"

rem Find vcvars64.bat
set "VCVARS="
for /f "delims=" %%F in ('where /r "C:\Program Files\Microsoft Visual Studio" vcvars64.bat 2^>nul') do (
    if not defined VCVARS set "VCVARS=%%F"
)
if not defined VCVARS (
    for /f "delims=" %%F in ('where /r "C:\Program Files (x86)\Microsoft Visual Studio" vcvars64.bat 2^>nul') do (
        if not defined VCVARS set "VCVARS=%%F"
    )
)
if not defined VCVARS (
    echo [ERROR] Cannot find vcvars64.bat. Open a VS Developer Command Prompt manually.
    pause
    exit /b 1
)

echo [*] Using: %VCVARS%
call "%VCVARS%" >nul 2>&1

echo [*] Compiling patcher...
cl /nologo /O2 /EHsc "%SRC%" advapi32.lib /Fe:"%OUT%" /link /SUBSYSTEM:CONSOLE

if %ERRORLEVEL% EQU 0 (
    echo [+] Built: %OUT%
    where upx >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [*] Packing with UPX...
        upx --best --lzma "%OUT%"
    ) else (
        echo [~] UPX not on PATH - skipping
    )
    echo.
    echo [+] DONE. Distribute: PirateLlama_patch.exe
) else (
    echo [!] Build failed.
)

endlocal
pause
