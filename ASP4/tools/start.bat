@echo off
setlocal

echo [1] Batch file started.
echo [2] Launching Access_To_SQLite.py...

python Access_To_SQLite.py "%~dp0"

echo [3] Python command finished executing.
pause
endlocal