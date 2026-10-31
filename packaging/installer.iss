; «موظف واتساب» — Inno Setup 6 script (Arabic-first, per-user, no admin).
; Build: ISCC packaging\installer.iss   (after PyInstaller → dist\WhatsAppEmployee)
#define AppName "موظف واتساب"
#define AppVer "2.3.0"
#define AppExe "WhatsAppEmployee.exe"
#define Publisher "Mohammed alzhrani"
#define AppUrl "https://github.com/moha700m/whatsapp-employee-pro"

[Setup]
AppId={{6E7D3F0A-5B1C-4C2E-9D4F-5A3E2B1C0D20}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher={#Publisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
AppCopyright=© 2026 {#Publisher}
VersionInfoVersion={#AppVer}.0
VersionInfoCompany={#Publisher}
VersionInfoDescription={#AppName} — مثبت البرنامج
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVer}
VersionInfoCopyright=© 2026 {#Publisher}
DefaultDirName={localappdata}\Programs\WhatsAppEmployee
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
CloseApplicationsFilter={#AppExe},node.exe
RestartApplications=no
OutputDir=..\dist
OutputBaseFilename=WhatsAppEmployee-Setup-{#AppVer}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
WizardImageFile=art\side_164.bmp,art\side_192.bmp,art\side_246.bmp,art\side_273.bmp,art\side_328.bmp,art\side_410.bmp
WizardSmallImageFile=art\small_55.bmp,art\small_64.bmp,art\small_83.bmp,art\small_92.bmp,art\small_110.bmp,art\small_119.bmp,art\small_138.bmp
WizardImageStretch=no
SetupIconFile=..\app\web\static\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
ShowLanguageDialog=no
LanguageDetectionMethod=none
SetupLogging=yes

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
arabic.WelcomeLabel1=هلا والله! خلنا نثبت «{#AppName}»
arabic.WelcomeLabel2=بنثبت «{#AppName}» {#AppVer} على جهازك.%n%nالبرنامج يرتب محادثات واتساب وطلبات محلك، ويجهز لك الردود، وما يرسل شي بدون موافقتك.%n%nيفضّل تقفل البرامج الثانية قبل ما نكمل.%n%nتطوير: Mohammed alzhrani
arabic.FinishedHeadingLabel=تمام، خلصنا التثبيت
arabic.FinishedLabel=«{#AppName}» صار جاهز على جهازك. تلقاه في قائمة ابدأ وعلى سطح المكتب.
arabic.FinishedLabelNoIcons=«{#AppName}» صار جاهز على جهازك.
arabic.ClickFinish=اضغط «إنهاء» عشان تقفل المثبت.

[CustomMessages]
arabic.LaunchApp=شغّل «موظف واتساب» الحين
english.LaunchApp=Launch WhatsApp Employee now
arabic.DesktopIcon=حط اختصار على سطح المكتب
english.DesktopIcon=Create a desktop shortcut
arabic.Shortcuts=الاختصارات:
english.Shortcuts=Shortcuts:
arabic.KeepData=تبي تحذف بياناتك كمان؟%n%n(العملاء، الطلبات، الإعدادات، وربط واتساب)%n%nاضغط «لا» عشان تحتفظ فيها لو رجعت تثبت البرنامج.
english.KeepData=Also delete your data (customers, orders, settings, WhatsApp session)?%n%nChoose No to keep it for a future reinstall.
arabic.UpgradeNote=لقيت نسخة سابقة من البرنامج، وبحدّثها مكانها. بياناتك بتبقى زي ما هي.
english.UpgradeNote=A previous version was found and will be upgraded in place. Your data is kept.
arabic.Uninstall=إلغاء تثبيت «موظف واتساب»
english.Uninstall=Uninstall WhatsApp Employee

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:Shortcuts}"

[Files]
Source: "..\dist\WhatsAppEmployee\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "data\*,*.gguf"
; the local AI model is already compressed (Q4) — store it as-is so building and installing stay fast
Source: "..\dist\WhatsAppEmployee\llm\*.gguf"; DestDir: "{app}\llm"; Flags: ignoreversion nocompression

[Dirs]
Name: "{app}\data"; Flags: uninsneveruninstall

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Comment: "{#AppName}"
Name: "{autoprograms}\{cm:Uninstall}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
procedure KillApp();
var R: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, R);
end;

function PrevInstalled(): Boolean;
begin
  Result := RegKeyExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E7D3F0A-5B1C-4C2E-9D4F-5A3E2B1C0D20}_is1')
         or RegKeyExists(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E7D3F0A-5B1C-4C2E-9D4F-5A3E2B1C0D20}_is1');
end;

procedure InitializeWizard();
begin
  if PrevInstalled() then
    WizardForm.WelcomeLabel2.Caption := WizardForm.WelcomeLabel2.Caption + #13#10#13#10 + CustomMessage('UpgradeNote');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillApp();   { the app holds files open; close it before copying }
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  KillApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if (not UninstallSilent) and (MsgBox(CustomMessage('KeepData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    begin
      DelTree(ExpandConstant('{app}'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\WhatsAppEmployee'), True, True, True);
    end;
  end;
end;
