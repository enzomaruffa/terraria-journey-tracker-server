@echo off
REM Double-click launcher for Windows. Installs uv on first run, then starts the tracker
REM and opens the browser. No Python, Node or PATH setup needed beforehand.

setlocal

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv ...
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

echo Starting the Terraria Journey Tracker ...
uv run terraria-journey-tracker %*

if errorlevel 1 (
    echo.
    echo The tracker exited with an error. Press any key to close.
    pause >nul
)

endlocal
