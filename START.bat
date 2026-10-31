@echo off
setlocal EnableExtensions
chcp 65001 >nul
title AI WhatsApp Employee
cd /d "%~dp0"
set "APPDIR=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist "data\logs" mkdir "data\logs"
set "LOG=%APPDIR%data\logs\startup.log"
echo ==== START %DATE% %TIME% ==== >> "%LOG%"

rem ---------- 1) find Python ----------
set "PY="
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3 -c "import sys;assert sys.version_info>=(3,10)" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys;assert sys.version_info>=(3,10)" >nul 2>&1 && set "PY=python"
if not defined PY (
  echo.
  echo  [X] ما لقيت Python 3.10 او احدث على الجهاز.
  echo  [X] Python 3.10+ was not found.
  echo      نزله من: https://www.python.org/downloads/windows/
  echo      وقت التثبيت فعّل خيار "Add python.exe to PATH" ثم شغّل START.bat من جديد.
  echo python not found >> "%LOG%"
  start "" "https://www.python.org/downloads/windows/"
  goto :fail
)
echo [1/5] Python: %PY%
echo python=%PY% >> "%LOG%"

rem ---------- 2) venv ----------
if not exist ".venv\Scripts\python.exe" (
  echo [2/5] انشاء البيئة الافتراضية / Creating virtual environment...
  %PY% -m venv ".venv" >> "%LOG%" 2>&1
  if errorlevel 1 ( echo  [X] فشل انشاء البيئة venv - شوف %LOG% & goto :fail )
) else ( echo [2/5] البيئة موجودة / venv OK )
set "VPY=%APPDIR%.venv\Scripts\python.exe"

rem ---------- 3) requirements (only when changed) ----------
set "STAMP=.venv\req.stamp"
fc /b requirements.txt "%STAMP%" >nul 2>&1
if errorlevel 1 (
  echo [3/5] تثبيت المتطلبات / Installing requirements - اول مرة تاخذ دقايق...
  "%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip >> "%LOG%" 2>&1
  "%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt >> "%LOG%" 2>&1
  if errorlevel 1 ( echo  [X] فشل تثبيت المتطلبات. تأكد من الانترنت. التفاصيل: %LOG% & goto :fail )
  "%VPY%" -c "import playwright, webview" >> "%LOG%" 2>&1
  if errorlevel 1 ( echo  [X] المكتبات ما انثبتت صح - شوف %LOG% & goto :fail )
  copy /y requirements.txt "%STAMP%" >nul
) else ( echo [3/5] المتطلبات مثبتة / requirements OK )

rem ---------- 4) browser for WhatsApp Web ----------
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=1"
if defined CHROME ( echo [4/5] Google Chrome OK ) else (
  if not exist ".venv\chromium.ok" (
    echo [4/5] ما لقيت Chrome - تنزيل Chromium / Downloading Chromium...
    "%VPY%" -m playwright install chromium >> "%LOG%" 2>&1
    if errorlevel 1 ( echo  [X] فشل تنزيل المتصفح - ثبّت Google Chrome من https://www.google.com/chrome & goto :fail )
    echo ok> ".venv\chromium.ok"
  ) else ( echo [4/5] Chromium OK )
)

rem ---------- shortcut on desktop (first run) ----------
if not exist "data\shortcut_ok" call "%APPDIR%CREATE_SHORTCUT.bat" /quiet

rem ---------- 5) run (always with the venv python) ----------
set "WAE_NO_REEXEC=1"
if not exist "data\first_run_ok" (
  echo [5/5] تشغيل البرنامج - اول مرة النافذة السوداء تبقى مفتوحة عشان نشوف أي خطأ...
  "%VPY%" main.py
  if errorlevel 1 ( echo  [X] البرنامج توقف بخطأ. التفاصيل في: %LOG% & goto :fail )
  goto :eof
)
echo [5/5] تشغيل البرنامج...
start "" "%APPDIR%.venv\Scripts\pythonw.exe" "%APPDIR%main.py"
exit /b 0

:fail
echo.
echo  ------------------------------------------------------------
echo  صار خطأ. صوّر هالشاشة او ارسل الملف: %LOG%
echo  For help run DIAGNOSE.bat
echo  ------------------------------------------------------------
echo FAILED >> "%LOG%"
pause
exit /b 1
