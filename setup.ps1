param(
    [switch]$SkipModelDownload,
    [switch]$SkipDriveDesktop,
    [string]$InboxDir,
    [switch]$NoAutostart
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Refresh-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machine, $userPath, $env:Path) -join ';'
}

function Install-WingetPackage {
    param([string]$PackageId)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Falta WinGet para instalar $PackageId. Instala 'App Installer' desde Microsoft Store y repite ./setup.ps1."
    }
    Write-Host "Instalando $PackageId..."
    & winget install --id $PackageId --exact --source winget --no-upgrade `
        --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar $PackageId con WinGet (código $LASTEXITCODE)."
    }
    Refresh-SessionPath
}

function Ensure-Tool {
    param([string]$Name, [string]$PackageId)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Install-WingetPackage $PackageId
        if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
            throw "$PackageId se instaló, pero $Name no aparece en PATH. Abre otra terminal y repite ./setup.ps1."
        }
    }
    & $Name --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "$Name está instalado, pero no se pudo ejecutar."
    }
}

function Find-Python {
    $candidates = @(
        @{ Name = 'py'; Prefix = @('-3.11') },
        @{ Name = 'py'; Prefix = @('-3.12') },
        @{ Name = 'python3.11'; Prefix = @() },
        @{ Name = 'python3.12'; Prefix = @() },
        @{ Name = 'python'; Prefix = @() }
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        $arguments = @($candidate.Prefix) + @('-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        $version = & $command.Source @arguments 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -in @('3.11', '3.12')) {
            return @{ Command = $command.Source; Prefix = @($candidate.Prefix) }
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Install-WingetPackage 'Python.Python.3.11'
    $python = Find-Python
    if (-not $python) {
        throw 'Python 3.11 se instaló, pero no está disponible todavía. Abre otra terminal y repite ./setup.ps1.'
    }
}

$preflight = @($python.Prefix) + @('-m', 'reel_skill_factory', 'doctor', '--preinstall')
& $python.Command @preflight
if ($LASTEXITCODE -ne 0) { throw 'Falló el diagnóstico inicial.' }
$diskCheck = @($python.Prefix) + @('-c', 'import shutil,sys; sys.exit(0 if shutil.disk_usage(".").free >= 3*1024**3 else 1)')
& $python.Command @diskCheck
if ($LASTEXITCODE -ne 0) { throw 'Se necesitan al menos 3 GB libres para instalar Whisper y su modelo.' }

Ensure-Tool 'codex' 'OpenAI.Codex'

if (-not $SkipDriveDesktop) {
    $driveLocation = Join-Path $env:ProgramFiles 'Google\Drive File Stream'
    if (-not (Test-Path -LiteralPath $driveLocation)) {
        Install-WingetPackage 'Google.GoogleDrive'
    }
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    $venvArgs = @($python.Prefix) + @('-m', 'venv', '.venv')
    & $python.Command @venvArgs
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear .venv.' }
}
& $venvPython -c 'import sys; assert sys.version_info[:2] in ((3, 11), (3, 12))'
if ($LASTEXITCODE -ne 0) { throw 'El .venv existente usa una versión incompatible de Python; revísalo antes de repetir.' }
& $venvPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python.' }
$runtimeArgs = @('scripts/prepare_runtime.py')
if ($SkipModelDownload) { $runtimeArgs += '--skip-model' }
& $venvPython @runtimeArgs
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar FFmpeg o Whisper.' }

if (-not $InboxDir) {
    $existingConfig = Join-Path $PSScriptRoot 'config.local.json'
    if (Test-Path -LiteralPath $existingConfig) {
        $InboxDir = (Get-Content -LiteralPath $existingConfig -Raw | ConvertFrom-Json).inbox_dir
    } elseif ([Console]::IsInputRedirected) {
        throw 'Indica la carpeta sincronizada con -InboxDir "RUTA" para completar la instalación.'
    } else {
        Write-Host 'Abre Google Drive para escritorio, inicia sesión y elige o crea una carpeta para recibir videos.'
        $InboxDir = Read-Host 'Pega aquí la ruta de esa carpeta EN ESTE COMPUTADOR'
    }
}
& $venvPython -m reel_skill_factory configure --inbox $InboxDir
if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar la carpeta de entrada.' }

& codex login status *> $null
if ($LASTEXITCODE -ne 0) {
    if ([Console]::IsInputRedirected) {
        throw 'Inicia sesión con codex login y repite el instalador.'
    }
    Write-Host 'Se abrirá el inicio de sesión de Codex; vuelve aquí al terminar.'
    & codex login
    if ($LASTEXITCODE -ne 0) { throw 'No se completó el inicio de sesión de Codex.' }
}
& $venvPython -m reel_skill_factory doctor
if ($LASTEXITCODE -ne 0) { throw 'El diagnóstico detectó un requisito pendiente; revisa las líneas FALTA.' }
if (-not $NoAutostart) {
    & (Join-Path $PSScriptRoot 'scripts\install-windows-task.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar el inicio automático.' }
}
Write-Host 'Instalación terminada. Sube un video a la carpeta elegida y abre la Bóveda de Skills desde el escritorio.'
