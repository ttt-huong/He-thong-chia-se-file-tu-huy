@echo off
REM Setup script for Fileshare System - Windows Batch

echo.
echo ========================================
echo   SETUP FILESHARE SYSTEM - Windows
echo ========================================
echo.

REM Kiem tra venv
if not exist ".venv" (
    echo [1/4] Tao virtual environment...
    python -m venv .venv
    echo. [OK] venv tao thanh cong
) else (
    echo [1/4] venv da ton tai, bo qua
)

echo.

REM Activate venv va cai pip
echo [2/4] Kich hoat venv va nang cap pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel -q
echo [OK] Pip cap nhat

echo.

REM Cai requirements
echo [3/4] Cai dependencies tu requirements.txt...
python -m pip install -r requirements.txt
echo [OK] Dependencies cai xong

echo.
echo ========================================
echo   SETUP HOAN TAT
echo ========================================
echo.
echo Tiep theo:
echo   1. Bat Docker services:
echo      docker compose up -d postgres redis rabbitmq
echo.
echo   2. Chay Gateway:
echo      python src/gateway/app.py
echo.
echo   3. Chay Worker (terminal khac):
echo      python src/worker/worker.py
echo.
echo   4. Mo frontend:
echo      http://localhost:5000
echo.
pause
