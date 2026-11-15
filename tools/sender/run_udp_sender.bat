@echo off
setlocal
set "PYTHONUTF8=1"
python "%~dp0sender.py" %*
set "senderExit=%errorlevel%"
echo.
pause
exit /b %senderExit%
