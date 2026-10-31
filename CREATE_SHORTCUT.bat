@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "TARGET=%~dp0START.bat"
set "ICON=%~dp0app\web\static\icon.ico"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'WhatsApp Employee.lnk'));" ^
  "$s.TargetPath=$env:TARGET; $s.WorkingDirectory=(Split-Path $env:TARGET); $s.WindowStyle=7; $s.Description='AI WhatsApp Employee';" ^
  "if (Test-Path $env:ICON) { $s.IconLocation=$env:ICON }; $s.Save()"
if errorlevel 1 (
  echo  [!] ما قدرت أسوي اختصار على سطح المكتب.
) else (
  if not exist "data" mkdir "data"
  echo ok> "data\shortcut_ok"
  if /i not "%~1"=="/quiet" echo  [OK] تم إنشاء اختصار "WhatsApp Employee" على سطح المكتب.
)
if /i not "%~1"=="/quiet" pause
