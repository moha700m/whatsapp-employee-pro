@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "OUT=%~dp0diagnose.txt"
echo ===== AI WhatsApp Employee - Diagnose %DATE% %TIME% ===== > "%OUT%"
echo Folder: %CD% >> "%OUT%"
ver >> "%OUT%"
echo --- python launchers --- >> "%OUT%"
where py >> "%OUT%" 2>&1
where python >> "%OUT%" 2>&1
py -0p >> "%OUT%" 2>&1
python --version >> "%OUT%" 2>&1
echo --- chrome --- >> "%OUT%"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" echo Chrome: ProgramFiles >> "%OUT%"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" echo Chrome: ProgramFiles(x86) >> "%OUT%"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" echo Chrome: LocalAppData >> "%OUT%"
echo --- webview2 --- >> "%OUT%"
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >> "%OUT%" 2>&1
echo --- venv --- >> "%OUT%"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version >> "%OUT%" 2>&1
  ".venv\Scripts\python.exe" -m pip list >> "%OUT%" 2>&1
  ".venv\Scripts\python.exe" -c "import sqlite3, sys; print('sqlite', sqlite3.sqlite_version)" >> "%OUT%" 2>&1
  ".venv\Scripts\python.exe" -c "import webview; print('pywebview', webview.__version__ if hasattr(webview,'__version__') else 'ok')" >> "%OUT%" 2>&1
  ".venv\Scripts\python.exe" -c "import playwright; print('playwright ok')" >> "%OUT%" 2>&1
  echo --- smoke test --- >> "%OUT%"
  ".venv\Scripts\python.exe" main.py --smoke >> "%OUT%" 2>&1
  echo --- unit tests --- >> "%OUT%"
  ".venv\Scripts\python.exe" -m pytest -q >> "%OUT%" 2>&1
) else ( echo venv missing - run START.bat first >> "%OUT%" )
echo --- startup.log (last lines) --- >> "%OUT%"
if exist "data\logs\startup.log" powershell -NoProfile -Command "Get-Content -Encoding UTF8 -Tail 60 'data\logs\startup.log'" >> "%OUT%" 2>&1
type "%OUT%"
echo.
echo تم حفظ التقرير في: %OUT%  (أرسله لنا إذا فيه مشكلة)
pause
