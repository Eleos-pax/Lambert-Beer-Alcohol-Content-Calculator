# Downloads the latest CalibraUV from GitHub and copies it over the installation folder.
# Used by update_windows.bat when the app was installed from a ZIP (no git).
param([Parameter(Mandatory = $true)][string]$Root)
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/Eleos-pax/Lambert-Beer-Content-Calculator'
if (-not (Test-Path (Join-Path $Root 'calibrauv\methods.json'))) { throw "Not a CalibraUV folder: $Root" }
$tmp = Join-Path $env:TEMP ('calibrauv_' + [guid]::NewGuid())
New-Item -ItemType Directory $tmp | Out-Null
try {
    $zip = Join-Path $tmp 'calibrauv.zip'
    Invoke-WebRequest "$repo/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $tmp
    $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
    # Copy new files over the old ones (keeps .venv and user_settings.json)
    Copy-Item (Join-Path $src.FullName '*') $Root -Recurse -Force
    Write-Host 'Files updated.'
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
