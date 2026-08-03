<#
    Terraria Journey Tracker — one-line setup for Windows.

    Run this in PowerShell:

        irm https://raw.githubusercontent.com/enzomaruffa/terraria-journey-tracker-server/main/install.ps1 | iex

    It installs uv (a single self-contained binary) if it is missing, then runs the tracker
    straight from GitHub. No Python, no Node, no Git, no cloning, nothing to uninstall
    afterwards beyond uv itself.
#>

$ErrorActionPreference = 'Stop'

$Repo    = 'enzomaruffa/terraria-journey-tracker-server'
$Archive = "https://github.com/$Repo/archive/refs/heads/main.zip"

function Write-Step($message) {
    Write-Host "`n==> $message" -ForegroundColor Cyan
}

function Find-Uv {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    # A fresh install lands here but is not on PATH until the shell restarts.
    $local = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $local) { return $local }

    return $null
}

Write-Host 'Terraria Journey Tracker' -ForegroundColor Green
Write-Host 'Research progress, live from your character file.'

$uv = Find-Uv
if (-not $uv) {
    Write-Step 'Installing uv'
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression

    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    $uv = Find-Uv

    if (-not $uv) {
        Write-Host "`nuv installed but could not be found. Close this window, open a new" -ForegroundColor Red
        Write-Host 'PowerShell, and run this command again.' -ForegroundColor Red
        exit 1
    }
} else {
    Write-Step "Using uv at $uv"
}

Write-Step 'Starting the tracker'
Write-Host 'First run downloads the tracker and its dependencies; later runs are instant.'
Write-Host 'Your browser opens automatically. Press Ctrl+C here to stop.'
Write-Host ''

# The archive URL is not versioned, so without this a re-run would keep serving whatever was
# cached the first time. Scoped to this package to avoid re-resolving every dependency.
& $uv tool run --refresh-package terraria-journey-tracker --from $Archive terraria-journey-tracker @args

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nThe tracker exited with an error." -ForegroundColor Red
    Write-Host 'If it could not find your character, pass the path directly:' -ForegroundColor Yellow
    Write-Host '  & $env:USERPROFILE\.local\bin\uv.exe tool run --from ' -NoNewline -ForegroundColor Yellow
    Write-Host "$Archive terraria-journey-tracker `"C:\path\to\Character.plr`"" -ForegroundColor Yellow
}
