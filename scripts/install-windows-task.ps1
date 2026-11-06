param(
    [string]$TaskName = 'Reel Skill Factory'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) {
    $venvPython
} else {
    (Get-Command python -ErrorAction Stop).Source
}

Push-Location $repoRoot
try {
    & $python -m reel_skill_factory doctor
    if ($LASTEXITCODE -ne 0) {
        throw 'El diagnóstico debe pasar antes de instalar el inicio automático.'
    }
} finally {
    Pop-Location
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    $action = $existing.Actions | Select-Object -First 1
    if ($action.WorkingDirectory -ne $repoRoot) {
        throw "Ya existe una tarea llamada '$TaskName' con otra ubicación. Usa -TaskName para elegir otro nombre."
    }
}

$action = New-ScheduledTaskAction -Execute $python -Argument '-m reel_skill_factory once' -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$trigger.Repetition = $repeat.Repetition
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'Procesa videos y enlaces sincronizados con Google Drive.' -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Tarea '$TaskName' instalada para $identity. Procesará la carpeta cada 5 minutos mientras la sesión esté abierta."
