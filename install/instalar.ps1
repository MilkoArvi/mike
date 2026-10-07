# Ejecuta en PowerShell (como usuario normal): .\install\instalar.ps1
# Instala dependencias y registra Mike para que arranque con Windows (sin abrir código ni terminal).
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $raiz

Write-Host "1/4 Python..." ; python -m venv .venv ; .\.venv\Scripts\pip install -r requirements.txt
Write-Host "2/4 Electron..." ; Set-Location ui ; npm install ; Set-Location ..
Write-Host "3/4 Lanzador..."
@"
@echo off
cd /d "$raiz"
start "" /min "$raiz\.venv\Scripts\pythonw.exe" core\main.py
timeout /t 3 >nul
set "EL=$raiz\ui\node_modules\electron\dist\electron.exe"
if exist "%EL%" (
  start "" "%EL%" "$raiz\ui"
) else (
  echo Falta Electron. Abre PowerShell y corre:  cd "$raiz\ui"  ^&^&  npm install
  timeout /t 10 >nul
)
"@ | Set-Content "$raiz\install\mike.bat" -Encoding ASCII

Write-Host "4/4 Arranque con Windows..."
$accion = New-ScheduledTaskAction -Execute "$raiz\install\mike.bat"
$disparo = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "Mike" -Action $accion -Trigger $disparo -Settings $ajustes -Force | Out-Null

Write-Host ""
Write-Host "Listo. Mike arrancará cada vez que inicies sesión. Para probarlo ahora: .\install\mike.bat"
Write-Host "Para quitarlo: Unregister-ScheduledTask -TaskName Mike"
