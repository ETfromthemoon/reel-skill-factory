$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Get-Command python -ErrorAction Stop
& $python.Source -m reel_skill_factory doctor --preinstall
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path '.venv')) { & $python.Source -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Dependencias instaladas. Configura config.local.json y ejecuta: .\.venv\Scripts\python.exe -m reel_skill_factory doctor'
