@echo off
REM Double-click launcher for Windows.
REM
REM Installs uv on first run if it is missing, then starts the tracker from this folder and
REM opens your browser. Nothing else needs to be installed first.
REM
REM If you have not downloaded this repository at all, you do not need it — run this in
REM PowerShell instead:
REM   irm https://raw.githubusercontent.com/enzomaruffa/terraria-journey-tracker-server/main/install.ps1 | iex

setlocal
cd /d "%~dp0"

set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
    ) else (
        echo Installing uv ...
        powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
        set "UV=%USERPROFILE%\.local\bin\uv.exe"
    )
)

echo.
echo Starting the Terraria Journey Tracker ...
echo Your browser will open automatically. Close this window to stop.
echo.

"%UV%" run terraria-journey-tracker %*

if errorlevel 1 (
    echo.
    echo The tracker exited with an error.
    echo If it could not find your character, drag the .plr file onto this .bat file.
    echo.
    pause
)

endlocal
