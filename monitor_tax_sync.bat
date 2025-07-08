@echo off
REM Form 2290 Tax Calculation Monitor
REM This script checks for tax calculation mismatches and sends notifications

echo.
echo ================================================
echo Form 2290 Tax Calculation Sync Monitor
echo ================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Run the notification script
python notify_on_mismatch.py

REM Check exit code
if %errorlevel% equ 0 (
    echo.
    echo [%date% %time%] Tax calculations are synchronized >> tax_monitor.log
    echo SUCCESS: Tax calculations are synchronized
) else (
    echo.
    echo [%date% %time%] Tax calculation mismatches detected >> tax_monitor.log
    echo WARNING: Tax calculation mismatches detected - check notifications
)

echo.
pause
