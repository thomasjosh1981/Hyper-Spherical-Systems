@echo off
set "PY313=C:\Users\twist\AppData\Local\Programs\Python\Python313\pythonw.exe"
if exist "%PY313%" (
    start "" "%PY313%" "%~dp0LAUNCH_TOKEN_HUD.pyw"
) else (
    start "" pythonw "%~dp0LAUNCH_TOKEN_HUD.pyw"
)
exit
