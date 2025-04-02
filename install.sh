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

# Check if this is a Debian/Ubuntu system
IS_DEBIAN=false
if command -v apt-get &> /dev/null; then
    IS_DEBIAN=true
    echo "Detected Debian/Ubuntu system."
fi

# Install dependencies
echo "Installing dependencies..."
# Capture the output of pip install
PIP_OUTPUT=$($PIP_CMD install -r requirements.txt 2>&1)
PIP_EXIT_CODE=$?

if [ $PIP_EXIT_CODE -ne 0 ]; then
    # Check if this is an "externally managed environment" error
    if $IS_DEBIAN && echo "$PIP_OUTPUT" | grep -q "externally-managed-environment"; then
        echo "Detected 'externally managed environment' on Debian/Ubuntu system."
        echo "Attempting to install dependencies with apt..."
        
        if sudo apt-get update && sudo apt-get install -y python3-piexif python3-tqdm python3-colorama; then
            echo "Successfully installed dependencies with apt."
        else
            echo ""
            echo "Error: Failed to install dependencies with apt."
            echo ""
            echo "Options:"
            echo "1. Force pip installation (use with caution):"
            echo "   $PIP_CMD install --break-system-packages -r requirements.txt"
            echo ""
            echo "2. Manually install the dependencies:"
            echo "   sudo apt install python3-piexif python3-tqdm python3-colorama"
            echo ""
            exit 1
        fi
    else
        # Print the original error
        echo "$PIP_OUTPUT"
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
fi

# Install the package
echo "Installing the package..."
# Capture the output of pip install
PIP_OUTPUT=$($PIP_CMD install -e . 2>&1)
PIP_EXIT_CODE=$?

if [ $PIP_EXIT_CODE -ne 0 ]; then
    # Check if this is an "externally managed environment" error on Debian
    if $IS_DEBIAN && echo "$PIP_OUTPUT" | grep -q "externally-managed-environment"; then
        echo "Detected 'externally managed environment' on Debian/Ubuntu system."
        echo "Note: The package will not be installed as a command-line tool."
        echo "You can still run the tool directly with: python3 main.py"
        
        # We don't try to install the package with apt because it's a local package
        # Just inform the user they can run it directly
        echo ""
        echo "Since this is a local package, you can run it directly with:"
        echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
        echo ""
        echo "Or force pip installation (use with caution):"
        echo "  $PIP_CMD install --break-system-packages -e ."
        
        # Don't exit with error since we're providing an alternative
        PACKAGE_INSTALLED=false
    else
        # Print the original error
        echo "$PIP_OUTPUT"
        echo ""
        echo "Error: Failed to install the package."
        echo ""
        echo "If you're seeing 'externally managed environment' errors on Debian/Ubuntu:"
        echo ""
        echo "Option 1: Run the tool directly:"
        echo "    python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
        echo ""
        echo "Option 2: Force pip installation (use with caution):"
        echo "    $PIP_CMD install --break-system-packages -e ."
        echo ""
        exit 1
    fi
fi

# Set default value for PACKAGE_INSTALLED if not set
if [ -z ${PACKAGE_INSTALLED+x} ]; then
    PACKAGE_INSTALLED=true
fi

echo ""
echo "Installation complete!"

if [ "$PACKAGE_INSTALLED" = true ]; then
    echo "You can now use the tool by running:"
    echo "  google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>"
    echo "Or directly with:"
    echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
    echo ""
    echo "For help, run:"
    echo "  google-takeout-fixer -h"
    echo "  python3 main.py -h"
else
    echo "You can now use the tool by running:"
    echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
    echo ""
    echo "For help, run:"
    echo "  python3 main.py -h"
fi
