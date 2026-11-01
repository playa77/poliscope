# Per-user, versioned installation. No elevation, Python, Node or data migration.
param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'Programs/Poliscope/@VERSION@'))
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    if ($file.path -match '(^/|^[A-Za-z]:|(^|/)\.\.(/|$)|\\)') { throw 'Invalid manifest path.' }
    $actual = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot $file.path)
    if ($actual.Hash.ToLowerInvariant() -ne $file.sha256) { throw 'Distribution integrity check failed.' }
}
if (-not [System.IO.Path]::IsPathRooted($Destination)) { throw 'Choose an absolute installation path.' }
if ($Destination -match '[\r\n]') { throw 'Installation path contains a line break.' }
if (Test-Path -LiteralPath $Destination) { throw 'Installation path already exists; close the app and choose a new directory.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot 'app/*') -Destination $Destination -Recurse
& (Join-Path $Destination 'resources/poliscope-engine/poliscope-engine.exe') --self-test
if ($LASTEXITCODE -ne 0) { throw 'Bundled engine self-test failed; shortcut was not changed.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'Poliscope.lnk'))
$shortcut.TargetPath = Join-Path $Destination 'poliscope.exe'
$shortcut.WorkingDirectory = $Destination
$shortcut.Save()
Write-Output "Installed $Destination. Previous versions and user data are retained."
