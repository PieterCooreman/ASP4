@echo off
setlocal

set "PORT=8080"

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /i ":%PORT% " ^| findstr /i "LISTENING"') do (
  echo Stopping PID %%P on port %PORT%...
  taskkill /pid %%P /f >nul 2>nul
)

python ASP4/server.py 0.0.0.0 8080 www

endlocal
