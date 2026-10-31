; Inno Setup script — ISCC packaging\installer.iss (after the PyInstaller build)
#define AppName "موظف واتساب"
#define AppVer "2.0.0"
[Setup]
AppId={{6E7D3F0A-5B1C-4C2E-9D4F-5A3E2B1C0D20}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=WhatsApp Employee
DefaultDirName={localappdata}\WhatsAppEmployee
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=WhatsAppEmployee-Setup-{#AppVer}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\app\web\static\icon.ico
UninstallDisplayIcon={app}\WhatsAppEmployee.exe
UninstallDisplayName={#AppName}
[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "اختصار على سطح المكتب"
[Files]
Source: "..\dist\WhatsAppEmployee\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Dirs]
Name: "{app}\data"; Flags: uninsneveruninstall
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\WhatsAppEmployee.exe"
Name: "{group}\إلغاء التثبيت"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\WhatsAppEmployee.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\WhatsAppEmployee.exe"; Description: "شغّل موظف واتساب"; Flags: nowait postinstall skipifsilent
