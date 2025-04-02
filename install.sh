#!/bin/bash
# Installation script for Google Photos EXIF

# Function to display help
show_help() {
    echo "Google Photos EXIF Installation Script"
    echo ""
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message and exit"
    echo ""
    echo "This script installs the Google Photos EXIF tool as a Python package,"
    echo "making it available as both a command-line utility and a Python module."
    echo ""
    echo "After installation, you can use the tool by running:"
    echo "  google-photos-exif -i <input_dir> -o <output_dir> -e <error_dir>"
    echo "Or directly with:"
    echo "  python main.py -i <input_dir> -o <output_dir> -e <error_dir>"
    echo ""
    echo "For more information, see the README.md file."
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            # Unknown option
            echo "Unknown option: $1"
            echo "Use -h or --help to see available options."
            exit 1
            ;;
    esac
    shift
done

echo "Installing Google Photos EXIF..."

# Check if pip3 is installed (preferred for Python 3)
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    echo "Using pip3 for installation..."
# If pip3 is not found, check for pip
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
    echo "Using pip for installation..."
else
    echo "Error: Neither pip nor pip3 is installed. Please install pip for Python 3 first."
    exit 1
fi

# Install dependencies first
echo "Installing dependencies..."
$PIP_CMD install -r requirements.txt

# Install the package
echo "Installing the package..."
$PIP_CMD install -e .

echo "Installation complete!"
echo "You can now use the tool by running:"
echo "  google-photos-exif -i <input_dir> -o <output_dir> -e <error_dir>"
echo "Or directly with:"
echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
echo "  or"
echo "  python main.py -i <input_dir> -o <output_dir> -e <error_dir>"
echo ""
echo "For help, run:"
echo "  google-photos-exif -h"
echo "  python main.py -h"
