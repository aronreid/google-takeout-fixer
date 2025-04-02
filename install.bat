@echo off
REM Simple installation script for Google Takeout Fixer

echo Installing Google Takeout Fixer...
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

REM Install dependencies
echo Installing dependencies...
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error: Failed to install dependencies.
    echo.
    echo If you're having permission issues, try running the command prompt as administrator.
    pause
    exit /b 1
)

REM Install the package
echo Installing the package...
python -m pip install -e .
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error: Failed to install the package.
    echo.
    echo If you're having permission issues, try running the command prompt as administrator.
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo You can now use the tool by running:
echo   google-takeout-fixer -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
echo Or directly with:
echo   python main.py -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
echo.
echo For help, run:
echo   google-takeout-fixer -h
echo   python main.py -h

pause
