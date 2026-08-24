param(
    [string]$EnvFile = ".env.demo"
)

$ErrorActionPreference = "Stop"

function Import-DemoEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Demo environment file not found: $Path"
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }

        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { continue }

        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()

        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            if ($value.Length -ge 2) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Import-DemoEnv $EnvFile

Write-Host "Demo environment loaded (values hidden)." -ForegroundColor Green
Write-Host "Starting guarded full demo stack..." -ForegroundColor Cyan
& python -m scripts.run_meal_plan_demo --full
exit $LASTEXITCODE
