param(
  [ValidateSet("portable", "installer", "all")][string]$Format = "all",
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$version = "3.2.0"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dist = Join-Path $root "dist"
$work = Join-Path $root "build"

if (-not $SkipTests) { & "$root\.venv\Scripts\python.exe" -m unittest discover -s "$root\tests" -q }
& "$root\.venv\Scripts\python.exe" -m pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) { throw "PyInstaller is required. Install it with: .venv\\Scripts\\python.exe -m pip install pyinstaller" }

New-Item -ItemType Directory -Force -Path $dist, $work | Out-Null
& "$root\.venv\Scripts\python.exe" "$root\release\make_icon.py" "$root\assets\echodesk.svg" "$root\assets\echodesk.ico"
& "$root\.venv\Scripts\pyinstaller.exe" --noconfirm --clean "$root\release\EchoDesk.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

if ($Format -in "installer", "all") {
  $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if (-not $iscc) { throw "Inno Setup 6 is required to build the installer (ISCC.exe was not found)." }
  & $iscc.Source "$root\release\EchoDesk.iss" "/DMyAppVersion=$version"
  if ($LASTEXITCODE -ne 0) { throw "Installer build failed." }
}

if ($Format -eq "portable") { Compress-Archive -Path "$dist\EchoDesk\*" -DestinationPath "$dist\EchoDesk-$version-windows-portable.zip" -Force }
Write-Host "Build artifacts are in $dist"
