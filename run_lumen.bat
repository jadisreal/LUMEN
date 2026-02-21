@echo off
echo ============================
echo   LUMEN Desktop Assistant
echo ============================
echo.
echo Activating virtual environment...
call "D:\LUMEN\venv\Scripts\activate.bat"
echo Activated. Starting LUMEN...
cd /d "D:\LUMEN\V1"
"D:\LUMEN\venv\Scripts\python.exe" main.py
pause
