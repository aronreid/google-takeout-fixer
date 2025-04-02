#!/bin/bash
# Simple installation script for Google Takeout Fixer

echo "Installing Google Takeout Fixer..."

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python version: $PYTHON_VERSION"

# Check if pip is installed
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    echo "Using pip3 for installation..."
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    echo "Using pip for installation..."
else
    echo "Error: Neither pip nor pip3 is installed. Please install pip for Python 3 first."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
if ! $PIP_CMD install -r requirements.txt; then
    echo ""
    echo "Error: Failed to install dependencies."
    echo ""
    echo "If you're seeing 'externally managed environment' errors on Debian/Ubuntu:"
    echo ""
    echo "Option 1: Install dependencies with apt (recommended):"
    echo "    sudo apt install python3-piexif python3-tqdm python3-colorama"
    echo ""
    echo "Option 2: Force pip installation (use with caution):"
    echo "    $PIP_CMD install --break-system-packages -r requirements.txt"
    echo ""
    exit 1
fi

# Install the package
echo "Installing the package..."
if ! $PIP_CMD install -e .; then
    echo ""
    echo "Error: Failed to install the package."
    echo ""
    echo "If you're seeing 'externally managed environment' errors on Debian/Ubuntu:"
    echo ""
    echo "Option 1: Install the package with apt if available"
    echo ""
    echo "Option 2: Force pip installation (use with caution):"
    echo "    $PIP_CMD install --break-system-packages -e ."
    echo ""
    exit 1
fi

echo ""
echo "Installation complete!"
echo "You can now use the tool by running:"
echo "  google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>"
echo "Or directly with:"
echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
echo ""
echo "For help, run:"
echo "  google-takeout-fixer -h"
echo "  python3 main.py -h"
