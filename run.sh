#!/bin/bash
# Google Takeout Fixer Tool Runner Script
# This script helps you run the Google Takeout Fixer tool with the required arguments

echo "Google Takeout Fixer Tool"
echo "====================================================="
echo "This tool processes Google Takeout data to restore proper EXIF metadata and file timestamps."
echo

# Make the script executable
chmod +x ./install.sh

# Check if the tool is installed
if ! command -v google-takeout-fixer &> /dev/null; then
    echo "The tool is not installed yet. Running installation script..."
    ./install.sh
    if [ $? -ne 0 ]; then
        echo "Installation failed. Please check the error messages above."
        read -p "Press Enter to continue..."
        exit 1
    fi
    echo "Installation completed successfully!"
    echo
fi

# Get input directory
read -p "Enter the path to your Google Takeout directory: " INPUT_DIR
if [ -z "$INPUT_DIR" ]; then
    echo "Input directory cannot be empty."
    read -p "Press Enter to continue..."
    exit 1
fi

# Get output directory
read -p "Enter the path where processed files should be saved: " OUTPUT_DIR
if [ -z "$OUTPUT_DIR" ]; then
    echo "Output directory cannot be empty."
    read -p "Press Enter to continue..."
    exit 1
fi

# Get error directory
read -p "Enter the path where files with errors should be saved: " ERROR_DIR
if [ -z "$ERROR_DIR" ]; then
    echo "Error directory cannot be empty."
    read -p "Press Enter to continue..."
    exit 1
fi

echo
echo "Running Google Takeout Fixer tool with the following parameters:"
echo "Input directory:  $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo "Error directory:  $ERROR_DIR"
echo
echo "Processing will start in 3 seconds..."
sleep 3

# Run the tool
google-takeout-fixer -i "$INPUT_DIR" -o "$OUTPUT_DIR" -e "$ERROR_DIR"

echo
if [ $? -eq 0 ]; then
    echo "Processing completed successfully!"
else
    echo "Processing completed with errors. Please check the messages above."
fi

read -p "Press Enter to continue..."
