#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun,
    [string]$Config,
    [Alias("h")]
    [switch]$Help
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

if ($Help) {
    @"
openclaw-deep-research Windows installer

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 [-Force] [-DryRun] [-Config PATH]

Options:
  -Force       Overwrite existing workspace AGENTS.md, skills, and agents.list entries
  -DryRun      Print config changes without writing openclaw.json
  -Config      Override OPENCLAW_CONFIG_PATH/default openclaw.json path
  -Help        Show this help message
"@ | Write-Host
    exit 0
}

$pluginDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$userHome = [Environment]::GetFolderPath("UserProfile")
$stateDir = if ($env:OPENCLAW_STATE_DIR) { $env:OPENCLAW_STATE_DIR } else { Join-Path $userHome ".openclaw" }
$workspaceRoot = $stateDir
$skillsDir = Join-Path $stateDir "skills"

Write-Host "=> Plugin dir:    $pluginDir"
Write-Host "=> OpenClaw home: $stateDir"
Write-Host ""

if (-not (Get-Command -Name "npm" -ErrorAction SilentlyContinue)) {
    Write-Error "npm was not found. Install Node.js/npm and retry."
}

Write-Host "=> Building plugin..."
Push-Location $pluginDir
try {
    & npm install
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & npm run build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
Write-Host ""

New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null

$agents = @("scout-agent", "plan-agent", "research-agent", "review-agent", "report-agent")
foreach ($agent in $agents) {
    $target = Join-Path $workspaceRoot ("workspace-" + $agent)
    $src = Join-Path (Join-Path (Join-Path $pluginDir "workspaces") $agent) "AGENTS.md"
    $dst = Join-Path $target "AGENTS.md"

    New-Item -ItemType Directory -Force -Path $target | Out-Null
    if ((Test-Path -LiteralPath $dst) -and -not $Force) {
        Write-Host "[skip] $dst already exists (-Force to overwrite)"
    } else {
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host "[ok]   wrote $dst"
    }
}

$skillNames = @(
    "deep-research",
    "_search-common",
    "search-code",
    "search-academic",
    "search-social-cn",
    "search-social-en",
    "report-format-discovery",
    "research-report",
    "generate-image"
)

$skippedSkills = @()
foreach ($skill in $skillNames) {
    $src = Join-Path (Join-Path $pluginDir "skills") $skill
    $dst = Join-Path $skillsDir $skill

    if (-not (Test-Path -LiteralPath $src -PathType Container)) {
        Write-Host "[warn] skill $skill is missing in the plugin directory, skipping"
        continue
    }

    if ((Test-Path -LiteralPath $dst -PathType Container) -and -not $Force) {
        Write-Host "[skip] $dst already exists (-Force to overwrite on upgrade)"
        $skippedSkills += $skill
        continue
    }

    if (Test-Path -LiteralPath $dst) {
        Remove-Item -LiteralPath $dst -Recurse -Force
    }

    Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
    Get-ChildItem -LiteralPath $dst -Directory -Recurse -Force | Where-Object { $_.Name -eq "__pycache__" } | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
    Write-Host "[ok]   copied $skill -> $dst"
}

if ($skippedSkills.Count -gt 0) {
    Write-Host ""
    Write-Host "[!!] Skipped $($skippedSkills.Count) existing skills: $($skippedSkills -join ' ')"
    Write-Host "     Re-run .\scripts\install.ps1 -Force to refresh plugin files during upgrade"
}

$pythonLaunchers = @(
    @{ Command = "py"; Args = @("-3") },
    @{ Command = "python"; Args = @() },
    @{ Command = "python3"; Args = @() }
)

$pythonLauncher = $null
foreach ($candidate in $pythonLaunchers) {
    if (Get-Command -Name $candidate.Command -ErrorAction SilentlyContinue) {
        $pythonLauncher = $candidate
        break
    }
}

if (-not $pythonLauncher) {
    Write-Error "Python 3 was not found. Install Python and retry, or run scripts\merge_config.py manually."
}

$mergeArgs = @()
if ($Force) {
    $mergeArgs += "--force"
}
if ($DryRun) {
    $mergeArgs += "--dry-run"
}
if ($Config) {
    $mergeArgs += @("--config", $Config)
}

$mergeScript = Join-Path $pluginDir "scripts/merge_config.py"
$pythonArgs = @()
$pythonArgs += $pythonLauncher.Args
$pythonArgs += $mergeScript
$pythonArgs += $mergeArgs

Write-Host ""
Write-Host "=> Running merge_config.py..."
& $pythonLauncher.Command @pythonArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=> Done. Restart OpenClaw: openclaw gateway restart"
Write-Host "=> Verify: openclaw agents list ; openclaw skills list | findstr deep-research"
