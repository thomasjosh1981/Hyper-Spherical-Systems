@echo off
REM Pirate Llama Control Center — launcher
REM Double-click this file to start the GUI.
REM First run will walk you through the setup wizard.

setlocal
set ROOT=%~dp0
set GUI=%ROOT%gui
set PYTHON=C:\Users\twist\AppData\Local\Programs\Python\Python313\python.exe

if not exist "%PYTHON%" (
  echo ERROR: Python 3.13 not found at %PYTHON%.
  echo Install Python 3.13 and PySide6 + pyyaml, then retry.
  pause
  exit /b 1
)

REM Make sure PySide6 and yaml are available
"%PYTHON%" -c "import PySide6, yaml" 2>nul
if errorlevel 1 (
  echo Installing required Python packages...
  "%PYTHON%" -m pip install --quiet PySide6 pyyaml qrcode[pil]
)

cd /d "%GUI%"
"%PYTHON%" -m pirate_gui %*
endlocal
