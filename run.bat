@echo off
REM Google Takeout Fixer Tool Runner Script
REM This script helps you run the Google Takeout Fixer tool with the required arguments

echo Google Takeout Fixer Tool
echo =====================================================
echo This tool processes Google Takeout data to restore proper EXIF metadata and file timestamps.
echo.

REM Check if the tool is installed
where google-takeout-fixer >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo The tool is not installed yet. Running installation script...
    call install.bat
    if %ERRORLEVEL% neq 0 (
        echo Installation failed. Please check the error messages above.
        pause
        exit /b %ERRORLEVEL%
    )
    echo Installation completed successfully!
    echo.
)

REM Get input directory
set /p INPUT_DIR="Enter the path to your Google Takeout directory: "
if "%INPUT_DIR%"=="" (
    echo Input directory cannot be empty.
    pause
    exit /b 1
)

REM Get output directory
set /p OUTPUT_DIR="Enter the path where processed files should be saved: "
if "%OUTPUT_DIR%"=="" (
    echo Output directory cannot be empty.
    pause
    exit /b 1
)

REM Get error directory
set /p ERROR_DIR="Enter the path where files with errors should be saved: "
if "%ERROR_DIR%"=="" (
    echo Error directory cannot be empty.
    pause
    exit /b 1
)

echo.
echo Running Google Takeout Fixer tool with the following parameters:
echo Input directory:  %INPUT_DIR%
echo Output directory: %OUTPUT_DIR%
echo Error directory:  %ERROR_DIR%
echo.
echo Processing will start in 3 seconds...
timeout /t 3 >nul

REM Run the tool
google-takeout-fixer -i "%INPUT_DIR%" -o "%OUTPUT_DIR%" -e "%ERROR_DIR%"

echo.
if %ERRORLEVEL% equ 0 (
    echo Processing completed successfully!
) else (
    echo Processing completed with errors. Please check the messages above.
)

pause
