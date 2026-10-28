param(
    [switch]$CheckOnly,
    [switch]$NoBrowser,
    [int]$BackendPort = 8027,
    [int]$FrontendPort = 5181
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (!$pythonCommand) {
    Write-Host 'Python was not found. Install the runtime described in README.md.' -ForegroundColor Red
    exit 1
}
$launchArguments = @((Join-Path $PSScriptRoot 'scripts\start_demo.py'), '--backend-port', $BackendPort, '--frontend-port', $FrontendPort)
if ($CheckOnly) { $launchArguments += '--check' }
if ($NoBrowser) { $launchArguments += '--no-browser' }
& $pythonCommand.Source @launchArguments
exit $LASTEXITCODE
