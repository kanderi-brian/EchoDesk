param()

Write-Host "Building EchoDesk v3.0 release"
# placeholder: collect files, create zip
$target = Join-Path -Path $PSScriptRoot -ChildPath "echodesk-v3.0.zip"
if (Test-Path $target) { Remove-Item $target }
Compress-Archive -Path (Join-Path $PSScriptRoot "..\*") -DestinationPath $target -Force
Write-Host "Created $target"
