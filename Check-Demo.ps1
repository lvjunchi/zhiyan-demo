param([switch]$SkipE2E)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $checkArgs = @('scripts/check_demo.py')
    if ($SkipE2E) { $checkArgs += '--skip-e2e' }
    & python @checkArgs
    $checkExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $checkExitCode
