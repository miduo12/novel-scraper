$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    python -m venv (Join-Path $Root ".venv")
}

Set-Location $Root

& $Python -m pip install -e ".[gui,build]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python (Join-Path $Root "scripts\generate_icon.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m PyInstaller --noconfirm --clean (Join-Path $Root "packaging\NovelScraper.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Exe = Join-Path $Root "dist\NovelScraper.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "Build failed: $Exe was not created."
}

Write-Host ""
Write-Host "Build complete: $Exe" -ForegroundColor Green
Write-Host "Copy this EXE to another Windows computer to run the app."
