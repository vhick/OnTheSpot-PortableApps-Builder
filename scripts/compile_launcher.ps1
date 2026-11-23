param([Parameter(Mandatory=$true)][string]$IconPath,
      [Parameter(Mandatory=$true)][string]$OutExe)
$ErrorActionPreference='Stop'
$vswhere="${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (!(Test-Path -LiteralPath $vswhere)) { throw 'MSVC_NOT_FOUND: vswhere.exe missing on Windows runner' }
$vs=(& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if (!$vs) { throw 'MSVC_NOT_FOUND: required C++ toolset is missing' }
$vsdev=Join-Path $vs 'Common7\Tools\VsDevCmd.bat'
if (!(Test-Path $vsdev)) { throw 'MSVC_SETUP_MISSING' }
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\launcher-work'
New-Item -ItemType Directory -Force -Path $work,(Split-Path -Parent $OutExe) | Out-Null
Copy-Item -LiteralPath $IconPath -Destination (Join-Path $work 'appicon.ico') -Force
Set-Content -LiteralPath (Join-Path $work 'icon.rc') -Encoding Ascii -Value 'APPICON ICON "appicon.ico"'
$source=Join-Path $root 'launcher\OnTheSpotPortable.cpp'
$rc=Join-Path $work 'icon.rc'
$res=Join-Path $work 'icon.res'
# All paths quoted; VS developer environment is provided by the installed runner.
$cmd='call "'+$vsdev+'" -arch=amd64 -host_arch=amd64 >nul && rc.exe /nologo /fo "'+$res+'" "'+$rc+'" && cl.exe /nologo /EHsc /std:c++17 /O2 /W4 /DUNICODE /D_UNICODE "'+$source+'" "'+$res+'" user32.lib shell32.lib /link /SUBSYSTEM:WINDOWS /MACHINE:X64 /OUT:"'+$OutExe+'"'
Push-Location $work
try {
    & cmd.exe /d /s /c $cmd
    if ($LASTEXITCODE -ne 0) { throw "LAUNCHER_COMPILE_FAILED: MSVC exit code $LASTEXITCODE" }
} finally { Pop-Location }
if (!(Test-Path -LiteralPath $OutExe)) { throw 'LAUNCHER_EXE_MISSING_AFTER_BUILD' }
Write-Host "Compiled Windows x64 launcher: $OutExe"
