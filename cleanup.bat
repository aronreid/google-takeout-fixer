@echo off
echo Cleaning up directory structure...

REM Remove duplicate and generated directories
echo Removing directories...
if exist google-photos-exif-python (
    echo Removing duplicate directory: google-photos-exif-python
    rmdir /s /q google-photos-exif-python
)
if exist google_takeout_fixer.egg-info (
    echo Removing generated directory: google_takeout_fixer.egg-info
    rmdir /s /q google_takeout_fixer.egg-info
)
if exist src\__pycache__ (
    echo Removing Python cache directory: src\__pycache__
    rmdir /s /q src\__pycache__
)
if exist src\helpers\__pycache__ (
    echo Removing Python cache directory: src\helpers\__pycache__
    rmdir /s /q src\helpers\__pycache__
)

REM Remove unnecessary files
echo Removing unnecessary files...
if exist get-pip.py del get-pip.py
if exist google_photos_exif_robust.py del google_photos_exif_robust.py
if exist install_deps.py del install_deps.py
if exist install_script.py del install_script.py
if exist test.bat del test.bat
if exist .DS_Store del .DS_Store

echo Directory cleanup completed!
