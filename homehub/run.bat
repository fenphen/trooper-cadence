@echo off
rem Starts Home Hub in this window (for trying it out; the installer sets up auto-start).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Creating the Python environment...
  py -3 -m venv .venv || python -m venv .venv || goto nopython
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)
echo.
echo Home Hub is starting. Open http://localhost:8080 in a browser. Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe -m homehub %*
goto :eof
:nopython
echo Python 3 was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run this again.
pause
