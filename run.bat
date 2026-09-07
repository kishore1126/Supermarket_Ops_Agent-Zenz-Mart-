@echo off
REM ==============================================================================
REM Supermarket Ops Agent (Zenz Mart) — Windows Run Script
REM ==============================================================================

cd /d "%~dp0"

echo ==========================================================
echo   🛒 Starting Zenz Mart Supermarket Ops Agent...
echo ==========================================================

REM 1. Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo ⚠️ .env not found. Copying from .env.example...
        copy ".env.example" ".env"
    ) else (
        echo ❌ Error: Missing .env file.
        pause
        exit /b 1
    )
)

REM 2. Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM 3. Seed database
echo 🌱 Checking and initializing database...
python -m app.scripts.seed
if %ERRORLEVEL% neq 0 (
    echo ⚠️ Database initialization encountered an issue. Continuing to launch...
)

REM 4. Start Telegram Bot
echo 🚀 Launching Zenz Mart Telegram Bot...
echo 👉 Press Ctrl+C anytime to stop.
echo ----------------------------------------------------------
python -m app.main
pause
