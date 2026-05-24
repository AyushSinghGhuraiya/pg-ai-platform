@echo off
REM Start FastAPI dev server with auto-reload
REM Run from the project root: scripts\start_dev.bat

cd /d "%~dp0..\backend"

REM Activate venv if present
if exist "..\venv\Scripts\activate.bat" (
    call ..\venv\Scripts\activate.bat
)

echo.
echo  Starting PG AI Backend (dev mode)...
echo  Docs: http://localhost:8000/docs
echo  Health: http://localhost:8000/health
echo.

uvicorn main:app --reload --host 0.0.0.0 --port 8000
