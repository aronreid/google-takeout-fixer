@echo off
echo Google Takeout Fix - Installation Script
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3 and make sure it's in your PATH.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
    set PYTHON_VERSION=%%V
)
echo Detected Python version: %PYTHON_VERSION%

REM Check if pip is installed
python -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: pip is not installed or not working.
    echo Please install pip for Python 3.
    pause
    exit /b 1
)

REM Install pywin32 (required for Windows file date handling)
echo Installing pywin32...
python -m pip install pywin32>=223
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error: Failed to install pywin32.
    echo.
    echo If you're having permission issues, try running the command prompt as administrator.
    pause
    exit /b 1
)

REM Install Pillow (required for GPS data handling)
echo Installing Pillow...
python -m pip install Pillow
if %ERRORLEVEL% neq 0 (
    echo.
    echo Warning: Failed to install Pillow.
    echo GPS data handling will be disabled.
    echo.
    echo If you want GPS data handling, try running the command prompt as administrator
    echo and manually install Pillow with: python -m pip install Pillow
    echo.
    pause
)

echo.
echo Installation complete!
echo.
echo You can now use the tool by running:
echo   python google-fix.py -i "input_folder" -o "output_folder" -e "error_folder"
echo.
echo Example:
echo   python google-fix.py -i "E:\Takeout 10gb Feb 12" -o "E:\complete\take 14" -e "E:\error"
echo.

pause
