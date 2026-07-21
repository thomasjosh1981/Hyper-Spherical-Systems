#Requires -RunAsAdministrator

$InstallDir = "$env:ProgramFiles\PirateLlama"
$SourceDir = "$PSScriptRoot\build\Debug"

Write-Host "Installing Pirate Llama to $InstallDir..."

# Create installation directory
if (-not (Test-Path -Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# Copy compiled binaries and required files
Copy-Item -Path "$SourceDir\pirate_llama.exe" -Destination $InstallDir -Force
Copy-Item -Path "$SourceDir\python_bridge.dll" -Destination $InstallDir -Force -ErrorAction SilentlyContinue
Copy-Item -Path "$PSScriptRoot\*.bin" -Destination $InstallDir -Force -ErrorAction SilentlyContinue

# Register Scheduled Task to run on boot with Highest Privileges (silent background proxy)
$TaskName = "PirateLlamaAutorun"
$Action = New-ScheduledTaskAction -Execute "$InstallDir\pirate_llama.exe" -Argument "--no-gui" -WorkingDirectory $InstallDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

Write-Host "Registering Scheduled Task '$TaskName'..."
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null

# Create Start Menu shortcut
$StartMenuPath = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Pirate Llama.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($StartMenuPath)
$Shortcut.TargetPath = "$InstallDir\pirate_llama.exe"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Pirate Llama Control Panel"
$Shortcut.Save()

Write-Host "Installation Complete! Settings will be persisted in %APPDATA%\PirateLlama\config.ini"
Write-Host "You can launch Pirate Llama from the Start Menu, or it will automatically start in the background on next logon."
