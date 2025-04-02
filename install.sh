#!/bin/bash
# Installation script for Google Takeout Fixer

# Function to display help
show_help() {
    echo "Google Takeout Fixer Installation Script"
    echo ""
    echo "Usage: ./install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help message and exit"
    echo "  -v, --venv       Install in a virtual environment (recommended)"
    echo "  -u, --user       Install in user space (using pip --user flag)"
    echo "  -s, --system     Attempt system-wide installation (may require sudo)"
    echo ""
    echo "This script installs the Google Takeout Fixer tool as a Python package,"
    echo "making it available as both a command-line utility and a Python module."
    echo ""
    echo "After installation, you can use the tool by running:"
    echo "  google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>"
    echo "Or directly with:"
    echo "  python main.py -i <input_dir> -o <output_dir> -e <error_dir>"
    echo ""
    echo "For more information, see the README.md file."
}

# Default installation mode
INSTALL_MODE="venv"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--venv)
            INSTALL_MODE="venv"
            shift
            ;;
        -u|--user)
            INSTALL_MODE="user"
            shift
            ;;
        -s|--system)
            INSTALL_MODE="system"
            shift
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

# Function to install dependencies with apt
install_with_apt() {
    echo "Attempting to install dependencies with apt..."
    sudo apt-get update
    sudo apt-get install -y python3-piexif python3-tqdm python3-colorama
    echo "Dependencies installed with apt."
}

# Function to install the package
install_package() {
    local pip_args=$1
    
    # Install dependencies first
    echo "Installing dependencies..."
    $PIP_CMD install $pip_args -r requirements.txt
    
    # Check if installation was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies."
        echo "If you're seeing 'externally managed environment' errors, try one of these options:"
        echo "1. Run with -v/--venv to use a virtual environment (recommended)"
        echo "2. Run with -u/--user to install in user space"
        echo "3. Install dependencies with your system package manager:"
        echo "   sudo apt install python3-piexif python3-tqdm python3-colorama"
        exit 1
    fi
    
    # Install the package
    echo "Installing the package..."
    $PIP_CMD install $pip_args -e .
    
    # Check if installation was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install the package."
        exit 1
    fi
}

case $INSTALL_MODE in
    venv)
        echo "Installing in a virtual environment..."
        
        # Check if venv module is available
        if ! python3 -c "import venv" &> /dev/null; then
            echo "Python venv module not found. Trying to install it..."
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y python3-venv
            else
                echo "Error: Python venv module is not available and couldn't be installed automatically."
                echo "Please install it manually or try a different installation mode."
                exit 1
            fi
        fi
        
        # Create and activate virtual environment
        echo "Creating virtual environment..."
        python3 -m venv venv
        
        # Activate virtual environment
        echo "Activating virtual environment..."
        source venv/bin/activate
        
        # Update pip in the virtual environment
        echo "Updating pip in virtual environment..."
        pip install --upgrade pip
        
        # Install the package in the virtual environment
        install_package ""
        
        echo "Installation complete in virtual environment!"
        echo "To use the tool, you need to activate the virtual environment first:"
        echo "  source venv/bin/activate"
        echo "Then you can run:"
        echo "  google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>"
        echo "Or directly with:"
        echo "  python main.py -i <input_dir> -o <output_dir> -e <error_dir>"
        ;;
        
    user)
        echo "Installing in user space..."
        install_package "--user"
        
        echo "Installation complete in user space!"
        echo "Make sure your user bin directory is in your PATH."
        echo "You can now use the tool by running:"
        echo "  google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>"
        echo "Or directly with:"
        echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
        ;;
        
    system)
        echo "Attempting system-wide installation..."
        
        # Try to install with pip first
        if $PIP_CMD install -r requirements.txt; then
            $PIP_CMD install -e .
            echo "System-wide installation complete!"
        else
            echo "Pip installation failed. This might be due to an externally managed environment."
            
            # Check if apt is available
            if command -v apt-get &> /dev/null; then
                echo "Detected apt package manager."
                read -p "Would you like to install dependencies with apt instead? (y/n) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    install_with_apt
                    $PIP_CMD install -e .
                else
                    echo "Installation aborted."
                    exit 1
                fi
            else
                echo "Error: System-wide installation failed and apt package manager not found."
                echo "Please try installing with -v/--venv or -u/--user instead."
                exit 1
            fi
        fi
        
        echo "You can now use the tool by running:"
        echo "  google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>"
        echo "Or directly with:"
        echo "  python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>"
        ;;
esac

echo ""
echo "For help, run:"
echo "  google-takeout-fixer -h"
echo "  python3 main.py -h"
