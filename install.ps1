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

    <#
        Pin the download to the exact commit rather than to "main".

        A branch URL never changes, so every caching layer between here and GitHub is free to
        hand back a stale copy — which is why an update could appear not to have happened. A
        commit URL is unique per version: unchanged means a genuine cache hit and an instant
        start, changed means a guaranteed fresh download. Correct by construction rather than
        by remembering a --refresh flag.
    #>
    $sha = $null
    try {
        $sha = (Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/commits/main" `
                                  -Headers @{ 'User-Agent' = 'terraria-journey-tracker' } `
                                  -TimeoutSec 15).sha
    } catch {
        Write-Log "could not resolve the latest commit: $_"
    }

    if ($sha) {
        $archive = "https://github.com/$repo/archive/$sha.zip"
        $pinned  = $true
        Write-Host "Version $($sha.Substring(0,7))" -ForegroundColor DarkGray
    } else {
        # No network to the API, or rate limited. Fall back to the branch and force a refetch.
        $archive = "https://github.com/$repo/archive/refs/heads/main.zip"
        $pinned  = $false
        Write-Host 'Could not check the latest version; downloading the branch instead.' -ForegroundColor DarkGray
    }
    Write-Log "archive: $archive"

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

    # The machine running this is the one running the game, so the useful second screen is a
    # phone. LAN mode is therefore the default here, and prints a QR to scan. Anyone who does
    # not want it can pass --host or --no-lan.
    $wantsLan = -not ($TrackerArgs | Where-Object { $_ -in @('--lan', '--no-lan', '--host') })
    $extra = if ($wantsLan) { @('--lan') } else { @() }
    # Wrapped in @() because filtering down to nothing yields $null, and $null survives array
    # concatenation as an empty argument that uv would reject.
    $TrackerArgs = @($TrackerArgs | Where-Object { $_ -ne '--no-lan' })

    Write-Step 'Starting the tracker'
    Write-Host 'The first run downloads the tracker and its dependencies, which takes a'
    Write-Host 'minute or two. Later runs start immediately.'
    Write-Host ''
    Write-Host 'When it is ready, a browser opens at http://127.0.0.1:4777' -ForegroundColor Green
    if ($wantsLan) {
        Write-Host 'A QR code will also appear — scan it to open the tracker on your phone.' -ForegroundColor Green
        Write-Host 'Windows may ask to allow network access; that prompt is what makes the'
        Write-Host 'phone link work. Decline it and only this PC can connect.'
    }
    Write-Host 'Press Ctrl+C here to stop the tracker.'
    Write-Host ''

    # A commit-pinned URL is already unique per version, so the cache can be trusted. Only the
    # branch fallback needs forcing, since that URL is the same for every version.
    $refresh = if ($pinned) { @() } else { @('--refresh-package', 'terraria-journey-tracker') }

    $uvArgs = @('tool', 'run') + $refresh + @(
        '--from', $archive,
        'terraria-journey-tracker'
    ) + $extra + $TrackerArgs

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
