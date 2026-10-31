@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( echo شغّل START.bat أول مرة & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install -q pyinstaller || goto :fail
".venv\Scripts\pyinstaller.exe" packaging\whatsapp_employee.spec --noconfirm --distpath dist --workpath build || goto :fail
where ISCC >nul 2>&1 && ISCC packaging\installer.iss
echo تم: dist\WhatsAppEmployee
pause & exit /b 0
:fail
echo فشل البناء & pause & exit /b 1
