@echo off
echo ============================
echo   LUMEN Desktop Assistant
echo ============================
echo.
echo Activating virtual environment...
call "D:\Jarvis-Mark-X\venv\Scripts\activate.bat"
echo Activated. Starting LUMEN...
cd /d "D:\Jarvis-Mark-X\MarkX"
"D:\Jarvis-Mark-X\venv\Scripts\python.exe" main.py
pause
