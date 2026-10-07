@echo off
cd /d "C:\Users\popos\Desktop\mike"
start "" /min "C:\Users\popos\Desktop\mike\.venv\Scripts\pythonw.exe" core\main.py
timeout /t 3 >nul
set "EL=C:\Users\popos\Desktop\mike\ui\node_modules\electron\dist\electron.exe"
if exist "%EL%" (
  start "" "%EL%" "C:\Users\popos\Desktop\mike\ui"
) else (
  echo Falta Electron. Abre PowerShell y corre:  cd "C:\Users\popos\Desktop\mike\ui"  ^&^&  npm install
  timeout /t 10 >nul
)
