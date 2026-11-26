@echo off
setlocal
cd /d "%~dp0"
python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo Python and NumPy are required. Run: python -m pip install numpy
    pause
    exit /b 1
)
python server.py --open
if errorlevel 1 pause
