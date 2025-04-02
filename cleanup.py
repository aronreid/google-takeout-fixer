#!/usr/bin/env python3
import os
import shutil
import sys

def cleanup_directory():
    """Clean up the directory structure."""
    print("Cleaning up directory structure...")
    
    # Remove duplicate and generated directories
    directories_to_remove = [
        "google-photos-exif-python",
        "google_takeout_fixer.egg-info",
        "src/__pycache__",
        "src/helpers/__pycache__"
    ]
    
    for directory in directories_to_remove:
        if os.path.exists(directory):
            print(f"Removing directory: {directory}")
            shutil.rmtree(directory)
    
    # Remove unnecessary files
    unnecessary_files = [
        "get-pip.py",
        "google_photos_exif_robust.py",
        "install_deps.py",
        "install_script.py",
        "test.bat",
        ".DS_Store"
    ]
    
    print("Removing unnecessary files...")
    for file in unnecessary_files:
        if os.path.exists(file):
            print(f"Removing {file}")
            os.remove(file)
    
    print("Directory cleanup completed!")

if __name__ == "__main__":
    cleanup_directory()
