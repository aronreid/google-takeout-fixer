#!/usr/bin/env python3
"""
Google Takeout Fixer Tool - Main Entry Point

This file serves as a convenience entry point for running the tool directly.
It imports and calls the main_cli function from the src/main.py module.
"""

import sys
import subprocess
import importlib.util

def check_dependency(package_name):
    """Check if a package is installed."""
    return importlib.util.find_spec(package_name) is not None

def main():
    # List of required dependencies
    required_dependencies = ['tqdm', 'piexif', 'colorama']
    missing_dependencies = [pkg for pkg in required_dependencies if not check_dependency(pkg)]
    
    if missing_dependencies:
        print("\nERROR: Missing required dependencies:", ", ".join(missing_dependencies))
        print("\nPlease install the required dependencies before running the tool:")
        print("\nOption 1: Install using pip:")
        print("    pip install -r requirements.txt")
        print("\nOption 2: Install using the installation script:")
        print("    ./install.sh  # On Linux/macOS")
        print("    install.bat   # On Windows")
        print("\nOption 3: If you're on Debian/Ubuntu and seeing 'externally managed environment' errors:")
        print("    # Install system packages first:")
        print("    sudo apt install python3-piexif python3-tqdm python3-colorama")
        print("\n    # Or use a virtual environment (recommended):")
        print("    sudo apt install python3-venv python3-full")
        print("    ./install.sh --venv")
        print("    source venv/bin/activate")
        print("\nSee the README.md file for more detailed installation instructions.")
        sys.exit(1)
    
    # If all dependencies are installed, import and run the main function
    try:
        from src.main import main_cli
        main_cli()
    except ImportError as e:
        print(f"\nERROR: Failed to import required modules: {e}")
        print("\nThis might be due to running the script from the wrong directory.")
        print("Make sure you're running the script from the root directory of the project.")
        print("Or try installing the package in development mode:")
        print("    pip install -e .")
        sys.exit(1)

if __name__ == "__main__":
    main()
