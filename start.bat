@echo off
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
echo.
echo  YouTube MP3 Converter
echo  http://localhost:5000
echo.
.venv\Scripts\python app.py
pause
