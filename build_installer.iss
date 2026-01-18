; ============================================================
; MACRO AUTO - Inno Setup Script
; Tạo installer chuyên nghiệp từ Nuitka onefile build
; ============================================================

#define MyAppName "MacroAuto"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Szuyu"
#define MyAppURL "https://szuyu.dev"
#define MyAppExeName "AutoTool.exe"

[Setup]
; Thông tin app
AppId={{SZUYU-MACRO-AUTO-12345678-1234-1234-1234-123456789012}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Đường dẫn cài đặt
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir=installer_output
OutputBaseFilename=MacroAuto_Setup_v{#MyAppVersion}
SetupIconFile=icon.ico


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo shortcut trên Desktop"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; Copy ONLY the onefile exe (không có folder nào khác)
Source: "dist\AutoTool.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Desktop
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; Tùy chọn chạy app sau khi cài đặt
Filename: "{app}\{#MyAppExeName}"; Description: "Chạy {#MyAppName} ngay"; Flags: nowait postinstall skipifsilent

[Code]
// Kiểm tra .NET Framework hoặc dependencies khác (nếu cần)
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Thêm logic kiểm tra ở đây nếu cần
end;
