[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [string]$ExpectedVersion = "",
    [string]$ExpectedCommitSha = "",
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$Live = $null

do {
    try {
        $Live = Invoke-RestMethod -Uri "$BaseUrl/health/live" -TimeoutSec 3
    }
    catch {
        if ((Get-Date) -ge $Deadline) {
            throw "Service did not become live within ${TimeoutSeconds}s at $BaseUrl"
        }
        Start-Sleep -Seconds 1
    }
} until ($null -ne $Live)

$Ready = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 3
$Version = Invoke-RestMethod -Uri "$BaseUrl/version" -TimeoutSec 3
$MetricsResponse = Invoke-WebRequest -Uri "$BaseUrl/metrics" -TimeoutSec 3

if ($Live.status -ne "live") { throw "Unexpected liveness payload" }
if ($Ready.status -ne "ready") { throw "Unexpected readiness payload" }
foreach ($Field in @("service", "version", "commit_sha", "environment")) {
    if (-not $Version.PSObject.Properties.Name.Contains($Field)) {
        throw "Version payload is missing field: $Field"
    }
}
if ($ExpectedVersion -and $Version.version -ne $ExpectedVersion) {
    throw "Version mismatch: expected $ExpectedVersion, got $($Version.version)"
}
if ($ExpectedCommitSha -and $Version.commit_sha -ne $ExpectedCommitSha) {
    throw "Commit mismatch: expected $ExpectedCommitSha, got $($Version.commit_sha)"
}
if ($MetricsResponse.Content -notmatch "release_service_ready 1") {
    throw "Metrics do not report a ready service"
}

Write-Output "smoke_status=passed endpoints_checked=4 base_url=$BaseUrl"

