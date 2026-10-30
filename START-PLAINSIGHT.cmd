@echo off
setlocal
cd /d "%~dp0"
title PlainSight launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-plainsight.ps1" %*
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo The launcher stopped with an error ^(code %EXITCODE%^).
  pause
)
exit /b %EXITCODE%
