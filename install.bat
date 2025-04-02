@echo off
REM Installation script for Google Photos EXIF

echo Installing Google Photos EXIF tool...
echo.

REM Install required dependencies
echo Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b %ERRORLEVEL%
)

REM Install the package in development mode
echo Installing Google Photos EXIF package...
pip install -e .
if %ERRORLEVEL% neq 0 (
    echo Installation failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Installation completed successfully!
echo You can now run the tool using: google-photos-exif -i INPUT_DIR -o OUTPUT_DIR -e ERROR_DIR
echo.

pause
