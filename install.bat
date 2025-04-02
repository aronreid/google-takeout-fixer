@echo off
REM Installation script for Google Takeout Fixer

setlocal enabledelayedexpansion

REM Default installation mode
set INSTALL_MODE=venv

REM Parse command line arguments
:parse_args
if "%~1"=="" goto :end_parse_args
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-v" set INSTALL_MODE=venv& goto :next_arg
if /i "%~1"=="--venv" set INSTALL_MODE=venv& goto :next_arg
if /i "%~1"=="-u" set INSTALL_MODE=user& goto :next_arg
if /i "%~1"=="--user" set INSTALL_MODE=user& goto :next_arg
if /i "%~1"=="-s" set INSTALL_MODE=system& goto :next_arg
if /i "%~1"=="--system" set INSTALL_MODE=system& goto :next_arg

echo Unknown option: %~1
echo Use -h or --help to see available options.
exit /b 1

:next_arg
shift
goto :parse_args

:end_parse_args

goto :start_installation

:show_help
echo Google Takeout Fixer Installation Script
echo.
echo Usage: install.bat [OPTIONS]
echo.
echo Options:
echo   -h, --help       Show this help message and exit
echo   -v, --venv       Install in a virtual environment (recommended)
echo   -u, --user       Install in user space (using pip --user flag)
echo   -s, --system     Attempt system-wide installation
echo.
echo This script installs the Google Takeout Fixer tool as a Python package,
echo making it available as both a command-line utility and a Python module.
echo.
echo After installation, you can use the tool by running:
echo   google-takeout-fixer -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
echo Or directly with:
echo   python main.py -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
echo.
echo For more information, see the README.md file.
exit /b 0

:start_installation

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

REM Handle different installation modes
if "%INSTALL_MODE%"=="venv" (
    echo Installing in a virtual environment...
    
    REM Check if venv module is available
    python -c "import venv" >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo Error: Python venv module is not available.
        echo Please install it or try a different installation mode.
        pause
        exit /b 1
    )
    
    REM Create virtual environment
    echo Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
    
    REM Activate virtual environment and install
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    
    REM Update pip in the virtual environment
    echo Updating pip in virtual environment...
    python -m pip install --upgrade pip
    
    REM Install the package in the virtual environment
    call :install_package ""
    
    echo Installation complete in virtual environment!
    echo To use the tool, you need to activate the virtual environment first:
    echo   venv\Scripts\activate.bat
    echo Then you can run:
    echo   google-takeout-fixer -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
    echo Or directly with:
    echo   python main.py -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
) else if "%INSTALL_MODE%"=="user" (
    echo Installing in user space...
    call :install_package "--user"
    
    echo Installation complete in user space!
    echo Make sure your user Scripts directory is in your PATH.
    echo You can now use the tool by running:
    echo   google-takeout-fixer -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
    echo Or directly with:
    echo   python main.py -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
) else if "%INSTALL_MODE%"=="system" (
    echo Attempting system-wide installation...
    call :install_package ""
    
    echo System-wide installation complete!
    echo You can now use the tool by running:
    echo   google-takeout-fixer -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
    echo Or directly with:
    echo   python main.py -i ^<input_dir^> -o ^<output_dir^> -e ^<error_dir^>
)

echo.
echo For help, run:
echo   google-takeout-fixer -h
echo   python main.py -h

goto :eof

:install_package
set PIP_ARGS=%~1

REM Install dependencies first
echo Installing dependencies...
python -m pip install %PIP_ARGS% -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to install dependencies.
    echo If you're having permission issues, try one of these options:
    echo 1. Run with -v/--venv to use a virtual environment (recommended)
    echo 2. Run with -u/--user to install in user space
    echo 3. Run the command prompt as administrator for system-wide installation
    pause
    exit /b 1
)

REM Install the package
echo Installing the package...
python -m pip install %PIP_ARGS% -e .
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to install the package.
    pause
    exit /b 1
)

exit /b 0

pause
