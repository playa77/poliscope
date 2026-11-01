# Private key stays in the Windows certificate store. Never accept/export a PFX.
param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
if (-not $env:POLISCOPE_SIGN_THUMBPRINT -or -not $env:POLISCOPE_TIMESTAMP_URL) { throw 'Signing certificate thumbprint and timestamp URL are required.' }
if ($env:POLISCOPE_TIMESTAMP_URL -notmatch '^https://') { throw 'Use an HTTPS timestamp service.' }
$tool = (Get-Command signtool.exe -ErrorAction Stop).Source
Get-ChildItem -LiteralPath $AppDirectory -Recurse -File | Where-Object { $_.Extension -in '.exe','.dll','.pyd' } | ForEach-Object {
    & $tool sign /sha1 $env:POLISCOPE_SIGN_THUMBPRINT /fd SHA256 /tr $env:POLISCOPE_TIMESTAMP_URL /td SHA256 $_.FullName
    if ($LASTEXITCODE -ne 0) { throw 'Native signing failed.' }
    & $tool verify /pa /all $_.FullName
    if ($LASTEXITCODE -ne 0) { throw 'Native signature verification failed.' }
}
