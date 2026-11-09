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

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $python
$startInfo.Arguments = '-m reel_skill_factory once'
$startInfo.WorkingDirectory = $repoRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
$startInfo.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'

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
