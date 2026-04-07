[Setup]
AppName=YT2MP3
AppVersion=1.0.0
AppPublisher=tatsuabe69
DefaultDirName={autopf}\YT2MP3
DefaultGroupName=YT2MP3
OutputDir=dist
OutputBaseFilename=YT2MP3-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\YT2MP3.exe
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Flags: unchecked

[Files]
Source: "dist\YT2MP3.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\YT2MP3"; Filename: "{app}\YT2MP3.exe"
Name: "{group}\YT2MP3 をアンインストール"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YT2MP3"; Filename: "{app}\YT2MP3.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\YT2MP3.exe"; Description: "YT2MP3 を起動する"; Flags: nowait postinstall skipifsilent
