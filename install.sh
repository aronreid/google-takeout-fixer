#!/bin/bash

echo "Google Takeout Fix - Installation Script"
echo "======================================"
echo

# Function to detect the package manager
detect_package_manager() {
    if command -v apt-get &> /dev/null; then
        echo "debian"
    elif command -v dnf &> /dev/null; then
        echo "redhat_dnf"
    elif command -v yum &> /dev/null; then
        echo "redhat_yum"
    elif command -v brew &> /dev/null; then
        echo "mac"
    else
        echo "unknown"
    fi
}

# Function to install Python if not present
install_python() {
    local pkg_manager=$1
    echo "Python is not installed. Attempting to install Python 3..."
    
    case $pkg_manager in
        debian)
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip
            ;;
        redhat_dnf)
            sudo dnf install -y python3 python3-pip
            ;;
        redhat_yum)
            sudo yum install -y python3 python3-pip
            ;;
        mac)
            brew install python3
            ;;
        *)
            echo "Error: Unsupported package manager. Please install Python 3 manually."
            exit 1
            ;;
    esac
    
    # Check if installation was successful
    if ! command -v python3 &> /dev/null; then
        echo "Error: Failed to install Python 3. Please install it manually."
        exit 1
    fi
}

# Function to install pip if not present
install_pip() {
    local pkg_manager=$1
    echo "pip is not installed. Attempting to install pip..."
    
    case $pkg_manager in
        debian)
            sudo apt-get update
            sudo apt-get install -y python3-pip
            ;;
        redhat_dnf)
            sudo dnf install -y python3-pip
            ;;
        redhat_yum)
            sudo yum install -y python3-pip
            ;;
        mac)
            # On macOS, pip should come with Python, but we can try to install it separately
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            python3 get-pip.py
            rm get-pip.py
            ;;
        *)
            echo "Error: Unsupported package manager. Please install pip manually."
            exit 1
            ;;
    esac
    
    # Check if installation was successful
    if ! python3 -m pip --version &> /dev/null; then
        echo "Error: Failed to install pip. Please install it manually."
        exit 1
    fi
}

# Detect the package manager
PKG_MANAGER=$(detect_package_manager)
echo "Detected system type: $PKG_MANAGER"

# Check if Python is installed
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    # Check if 'python' is Python 3
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}' | cut -d. -f1)
    if [ "$PYTHON_VERSION" -ge 3 ]; then
        PYTHON_CMD="python"
    else
        echo "Error: Python 3 is required but Python 2 is installed."
        install_python "$PKG_MANAGER"
        PYTHON_CMD="python3"
    fi
else
    install_python "$PKG_MANAGER"
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo "Detected Python version: $PYTHON_VERSION"

# Check if pip is installed
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    install_pip "$PKG_MANAGER"
fi

echo
echo "Installation complete!"
echo
echo "You can now use the tool by running:"
echo "  $PYTHON_CMD google-fix.py -i \"input_folder\" -o \"output_folder\" -e \"error_folder\" [-p threads]"
echo
echo "Examples:"
echo "  $PYTHON_CMD google-fix.py -i \"~/Takeout 10gb Feb 12\" -o \"~/complete/take 14\" -e \"~/error\""
echo "  $PYTHON_CMD google-fix.py -i \"~/Takeout 10gb Feb 12\" -o \"~/complete/take 14\" -e \"~/error\" -p 4"
echo
echo "Note: By default, the tool will use 1 thread for processing. If you have an SSD or NVMe drive,"
echo "      you can increase the thread count (-p flag) for faster processing. For example:"
echo "      -p 4 for a quad-core system with an SSD"
echo "      -p 8 for an octa-core system with an NVMe drive"
echo

# Make the script executable
chmod +x google-fix.py
