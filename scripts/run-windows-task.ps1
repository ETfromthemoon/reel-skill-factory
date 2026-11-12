param([switch]$RetryFailed)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$stateDir = Join-Path $repoRoot '.local-state'
$logPath = Join-Path $stateDir 'task.log'
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $python)) {
    [System.IO.File]::AppendAllText($logPath, "$(Get-Date -Format o) Falta .venv\Scripts\python.exe`r`n")
    exit 1
}

# Codex Desktop keeps its CLI in a versioned directory that is not part of
# the persistent user PATH. A scheduled task does not inherit the app's PATH.
$codexCommand = Get-Command codex.exe -ErrorAction SilentlyContinue
$codexPath = if ($codexCommand) { $codexCommand.Source } else { $null }
if (-not $codexPath) {
    $codexRoot = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
    if (Test-Path -LiteralPath $codexRoot) {
        $codexPath = Get-ChildItem -LiteralPath $codexRoot -Directory |
            ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName 'codex.exe') -ErrorAction SilentlyContinue } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1 -ExpandProperty FullName
    }
}
if (-not $codexPath) {
    [System.IO.File]::AppendAllText($logPath, "$(Get-Date -Format o) No se encontró codex.exe para la tarea programada`r`n")
    exit 1
}
$env:PATH = (Split-Path -Parent $codexPath) + [IO.Path]::PathSeparator + $env:PATH

$vaultPidPath = Join-Path $stateDir 'vault-server.pid'
$vaultProcess = $null
if (Test-Path -LiteralPath $vaultPidPath) {
    $oldPid = [System.IO.File]::ReadAllText($vaultPidPath).Trim()
    if ($oldPid -match '^\d+$') {
        $vaultProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $oldPid" -ErrorAction SilentlyContinue
        if ($vaultProcess -and $vaultProcess.CommandLine -notlike '*reel_skill_factory vault --serve*') {
            $vaultProcess = $null
        }
        if ($vaultProcess) {
            $childPids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $oldPid" -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty ProcessId)
            $listener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue |
                Where-Object { $_.OwningProcess -eq $vaultProcess.ProcessId -or $childPids -contains $_.OwningProcess }
            if (-not $listener) { $vaultProcess = $null }
        }
    }
}
if (-not $vaultProcess) {
    try {
        $vault = Start-Process -FilePath $python -ArgumentList '-m reel_skill_factory vault --serve' `
            -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $stateDir 'vault-server.out.log') `
            -RedirectStandardError (Join-Path $stateDir 'vault-server.err.log')
        [System.IO.File]::WriteAllText($vaultPidPath, [string]$vault.Id)
        [System.IO.File]::AppendAllText($logPath, "$(Get-Date -Format o) Bóveda PID=$($vault.Id)`r`n")
    } catch {
        [System.IO.File]::AppendAllText($logPath, "$(Get-Date -Format o) No se pudo iniciar bóveda: $($_.Exception.Message)`r`n")
    }
}

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $python
$startInfo.Arguments = if ($RetryFailed) { '-m reel_skill_factory once --retry-failed' } else { '-m reel_skill_factory once' }
$startInfo.WorkingDirectory = $repoRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
$startInfo.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
$startInfo.EnvironmentVariables['PATH'] = (Split-Path -Parent $codexPath) + [IO.Path]::PathSeparator + $startInfo.EnvironmentVariables['PATH']

$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
try {
    if (-not $process.Start()) { throw 'No se pudo iniciar el trabajador' }
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $message = "$(Get-Date -Format o) PID=$($process.Id) exit=$($process.ExitCode)`r`n" +
        $stdout.GetAwaiter().GetResult() + $stderr.GetAwaiter().GetResult() + "`r`n"
    [System.IO.File]::AppendAllText($logPath, $message)
    exit $process.ExitCode
} catch {
    [System.IO.File]::AppendAllText($logPath, "$(Get-Date -Format o) ERROR: $($_.Exception.Message)`r`n")
    exit 1
} finally {
    $process.Dispose()
}
