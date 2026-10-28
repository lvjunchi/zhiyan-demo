@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Demo.ps1" %*
set "demo_exit=%ERRORLEVEL%"
if not "%demo_exit%"=="0" pause
exit /b %demo_exit%
