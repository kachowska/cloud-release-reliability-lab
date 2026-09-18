[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$RequireDocker,
    [switch]$RequireTerraform,
    [switch]$SkipDocker,
    [switch]$SkipTerraform
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Collector = Join-Path $PSScriptRoot "collect_evidence.py"

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python executable not found: $Python"
}

$Arguments = @($Collector)
if ($RequireDocker) { $Arguments += "--require-docker" }
if ($RequireTerraform) { $Arguments += "--require-terraform" }
if ($SkipDocker) { $Arguments += "--skip-docker" }
if ($SkipTerraform) { $Arguments += "--skip-terraform" }

Push-Location $RepoRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Validation failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

