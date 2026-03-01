@echo off
setlocal

set "PORT=8080"

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /i ":%PORT% " ^| findstr /i "LISTENING"') do (
  echo Stopping PID %%P on port %PORT%...
  taskkill /pid %%P /f >nul 2>nul
)

echo Starting ASP4 server...
echo Launching http://localhost:%PORT% in your default browser...
echo.

:: This command automatically opens the URL
start "" "http://localhost:%PORT%"

::set ASP_PY_LOG=1 
::set ASP_PY_TRACE_REQUEST=1 
python3 ASP4/server.py 0.0.0.0 8080 www	

endlocal

