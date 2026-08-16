@echo off
rem WRC 9 Telemetry Dashboard launcher (double-click, no console window)
cd /d "%~dp0"
set "PYW=C:\Users\Administrator\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "WRC9Telemetry" "%PYW%" dashboard\main.py %*
