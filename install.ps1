<#
    Terraria Journey Tracker — one-line setup for Windows.

    Run this in PowerShell:

        irm https://raw.githubusercontent.com/enzomaruffa/terraria-journey-tracker-server/main/install.ps1 | iex

    It installs uv (a single self-contained binary) if it is missing, then runs the tracker
    straight from GitHub. No Python, no Node, no Git, no cloning, nothing to uninstall
    afterwards beyond uv itself.

    Implementation note: this script is normally executed through `iex`, which runs it in the
    caller's own session. That means `exit` would close the user's window and
    `$ErrorActionPreference` would outlive the script, so neither is used here. The uv
    installer is likewise run in a child process, because it calls `exit` internally.
#>

function Invoke-TerrariaTrackerSetup {
    [CmdletBinding()]
    param([string[]] $TrackerArgs = @())

    $repo    = 'enzomaruffa/terraria-journey-tracker-server'
    $archive = "https://github.com/$repo/archive/refs/heads/main.zip"
    $logPath = Join-Path $env:TEMP 'terraria-tracker-setup.log'

    function Write-Log([string] $message) {
        # Always leave evidence behind, even if the console disappears.
        try { Add-Content -Path $logPath -Value "$(Get-Date -Format o)  $message" -ErrorAction SilentlyContinue } catch {}
    }

    function Write-Step([string] $message) {
        Write-Host "`n==> $message" -ForegroundColor Cyan
        Write-Log $message
    }

    function Find-Uv {
        $command = Get-Command uv -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }

        # A fresh install lands here but is not on PATH until the shell restarts.
        foreach ($candidate in @(
            (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\uv\uv.exe')
        )) {
            if ($candidate -and (Test-Path $candidate)) { return $candidate }
        }
        return $null
    }

    Write-Host 'Terraria Journey Tracker' -ForegroundColor Green
    Write-Host 'Research progress, live from your character file.'
    Write-Log "--- setup started (PowerShell $($PSVersionTable.PSVersion)) ---"

    $uv = Find-Uv

    if (-not $uv) {
        Write-Step 'Installing uv (about 40 MB)'

        # Run the installer in a child process: it calls `exit`, which would otherwise close
        # this window before any of the output below could be read.
        # No null-coalescing here: Windows still ships PowerShell 5.1 by default, which
        # cannot even parse `??`.
        $shell = Get-Command powershell.exe -ErrorAction SilentlyContinue
        if (-not $shell) { $shell = Get-Command pwsh -ErrorAction SilentlyContinue }
        if (-not $shell) {
            Write-Host 'Could not find a PowerShell executable to run the uv installer.' -ForegroundColor Red
            $script:TerrariaTrackerExitCode = 1
            return
        }

        $installer = 'irm https://astral.sh/uv/install.ps1 | iex'
        $installerOutput = & $shell.Source -NoProfile -ExecutionPolicy Bypass -Command $installer 2>&1
        $installerOutput | ForEach-Object { Write-Host "    $_" }
        Write-Log ($installerOutput -join "`n")

        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
        $uv = Find-Uv

        if (-not $uv) {
            Write-Host ''
            Write-Host 'Could not install uv automatically.' -ForegroundColor Red
            Write-Host 'Install it manually from https://docs.astral.sh/uv/getting-started/installation/'
            Write-Host "then run this command again. Details: $logPath"
            $script:TerrariaTrackerExitCode = 1
            return
        }
    }

    Write-Step "Using uv at $uv"

    Write-Step 'Starting the tracker'
    Write-Host 'The first run downloads the tracker and its dependencies, which takes a'
    Write-Host 'minute or two. Later runs start immediately.'
    Write-Host ''
    Write-Host 'When it is ready, a browser opens at http://127.0.0.1:4777' -ForegroundColor Green
    Write-Host 'If it does not open, type that address in yourself.'
    Write-Host 'Press Ctrl+C here to stop the tracker.'
    Write-Host ''

    # The archive URL is not versioned, so without --refresh-package a re-run would keep
    # serving whatever was cached the first time.
    $uvArgs = @(
        'tool', 'run',
        '--refresh-package', 'terraria-journey-tracker',
        '--from', $archive,
        'terraria-journey-tracker'
    ) + $TrackerArgs

    Write-Log "running: $uv $($uvArgs -join ' ')"

    # Not captured or piped anywhere: the tracker's own output has to reach the console.
    & $uv @uvArgs
    $code = $LASTEXITCODE
    Write-Log "tracker exited with $code"

    if ($code -ne 0) {
        Write-Host ''
        Write-Host 'The tracker stopped with an error.' -ForegroundColor Red
        Write-Host 'If it could not find your character, point it at the file yourself:' -ForegroundColor Yellow
        Write-Host ''
        Write-Host "    & '$uv' tool run --from '$archive' terraria-journey-tracker 'C:\path\to\Character.plr'"
        Write-Host ''
        Write-Host "To see everything it checked:" -ForegroundColor Yellow
        Write-Host "    & '$uv' tool run --from '$archive' terraria-journey-tracker --doctor"
        Write-Host ''
        Write-Host "A copy of this output is in $logPath"
    }

    $script:TerrariaTrackerExitCode = $code
}

# Never `exit` at script scope: under `irm | iex` that would close the caller's window.
# The call is deliberately not piped or assigned, so the tracker's own output is not
# swallowed on its way to the console.
Invoke-TerrariaTrackerSetup -TrackerArgs $args
