# Google Takeout Fixer

A high-performance Python tool to fix metadata in Google Takeout exports, including restoring proper EXIF data and file timestamps.

## Simple Usage
1. Download takeout files from google and uncompress them into a single Takeout folder
2. Install the script (windows / macos / linux)
3. Run main.py with the appropirate flags

## Description

This tool processes Google Photos Takeout data to restore proper EXIF metadata and file timestamps. It extracts all photo/video files from your Google Photos Takeout and places them into an output directory while:

1. Setting the file's last modified date to match the timestamp in Google's JSON metadata
2. Adding the "DateTimeOriginal" (date taken), "DateTimeDigitized" (date created), and "DateTime" (last modified) EXIF fields for supported file types
3. Preserving the original folder structure from the Google Photos Takeout
4. Providing detailed progress tracking and summary statistics

The tool uses parallel processing to maximize performance on multi-core systems, making it significantly faster for large photo collections.

## Architecture

```mermaid
graph TD
    A[Input: Google Photos Takeout] --> B[Count Files]
    B --> C[Find Supported Media Files]
    C --> D[Process Files in Parallel]
    
    subgraph "Parallel Processing"
        D --> |Worker 1| E1[Process File]
        D --> |Worker 2| E2[Process File]
        D --> |Worker 3| E3[Process File]
        D --> |Worker N| E4[Process File]
        
        E1 --> F1[Copy File with Buffer]
        E1 --> G1[Read JSON Metadata]
        G1 --> H1{Has EXIF Date?}
        H1 -->|No| I1[Update EXIF]
        H1 -->|Yes| J1[Skip EXIF Update]
        I1 --> K1[Update File Timestamp]
        J1 --> K1
        
        E2 --> F2[Copy File with Buffer]
        E2 --> G2[Read JSON Metadata]
        G2 --> H2{Has EXIF Date?}
        H2 -->|No| I2[Update EXIF]
        H2 -->|Yes| J2[Skip EXIF Update]
        I2 --> K2[Update File Timestamp]
        J2 --> K2
        
        E3 --> F3[Copy File with Buffer]
        E3 --> G3[Read JSON Metadata]
        G3 --> H3{Has EXIF Date?}
        H3 -->|No| I3[Update EXIF]
        H3 -->|Yes| J3[Skip EXIF Update]
        I3 --> K3[Update File Timestamp]
        J3 --> K3
        
        E4 --> F4[Copy File with Buffer]
        E4 --> G4[Read JSON Metadata]
        G4 --> H4{Has EXIF Date?}
        H4 -->|No| I4[Update EXIF]
        H4 -->|Yes| J4[Skip EXIF Update]
        I4 --> K4[Update File Timestamp]
        J4 --> K4
    end
    
    F1 --> L[Progress Tracking]
    F2 --> L
    F3 --> L
    F4 --> L
    
    K1 --> M[Output: Processed Files]
    K2 --> M
    K3 --> M
    K4 --> M
    
    L --> N[Generate Summary]
```

## Features

- **Parallel Processing**: Utilizes multiple CPU cores for significantly faster processing
- **Buffered File I/O**: Efficiently handles large files with optimized memory usage
- **Progress Tracking**: Real-time progress bar with file counts and percentage complete
- **Detailed Statistics**: Comprehensive summary of processed files by type
- **Error Handling**: Robust error handling with detailed reporting
- **Original Structure**: Preserves the folder structure from the Google Photos Takeout
- **Colorful Terminal Output**: Color-coded console output for better readability
- **Centralized Format Configuration**: Easy to add support for new file formats
- **RAW Format Support**: Handles various RAW image formats from different camera manufacturers

## Installation

### Option 1: Using Installation Scripts (Recommended)

1. Clone this repository or download the source code.
2. Run the appropriate installation script:

**On Linux/macOS:**
```bash
./install.sh
```

**On Windows:**
```bash
install.bat
```

These scripts will automatically:
- Install all required dependencies
- Install the package in development mode
- Make the tool available as a command-line utility

You can also view help information for the installation scripts:

**On Linux/macOS:**
```bash
./install.sh -h
```

**On Windows:**
```bash
install.bat -h
```

### Option 2: Manual Installation

1. Clone this repository or download the source code.
2. Install the required dependencies:

```bash
# For Python 3 (recommended)
pip3 install -r requirements.txt

# Or if pip3 is not available
pip install -r requirements.txt
```

3. Run the tool directly:

```bash
# For Python 3 (recommended)
python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>

# Or if python3 command is not available
python main.py -i <input_dir> -o <output_dir> -e <error_dir>
```

### Option 3: Install as a Package

You can install the tool as a Python package, which makes it available as a command-line utility:

```bash
# Install dependencies first (for Python 3)
pip3 install -r requirements.txt

# Or if pip3 is not available
pip install -r requirements.txt

# Install directly from the repository (for Python 3)
pip3 install .

# Or if pip3 is not available
pip install .

# Or install in development mode (for Python 3)
pip3 install -e .

# Or if pip3 is not available
pip install -e .
```

## Troubleshooting

### Missing Dependencies

If you see an error about missing dependencies when running the tool, make sure you've installed all required packages:

```bash
# For Python 3 (recommended)
pip3 install -r requirements.txt

# Or if pip3 is not available
pip install -r requirements.txt
```

The tool will automatically check for required dependencies and provide helpful error messages if any are missing.

### Import Errors

If you see errors like `No module named 'config'` or `name 'Any' is not defined`, it's likely due to Python's module import system. The tool has been updated to use relative imports and proper type annotations, which should resolve these issues. If you still encounter import errors:

1. Make sure you're running the tool from the root directory of the project
2. Try installing the package in development mode:
   ```bash
   pip3 install -e .
   ```
3. Or use the installation scripts which handle this automatically:
   ```bash
   ./install.sh  # On Linux/macOS
   install.bat   # On Windows
   ```

Common errors and their solutions:
- `No module named 'config'`: Fixed by using relative imports (e.g., `from .config import CONFIG`)
- `name 'Any' is not defined`: Fixed by adding `Any` to the imports from typing (e.g., `from typing import Dict, List, Any`)

### Python Version

This tool is designed for Python 3. If you have both Python 2 and Python 3 installed on your system:

- Use `python3` instead of `python` to run the script
- Use `pip3` instead of `pip` to install dependencies

The installation scripts will automatically detect and use the appropriate commands for your system.

### Externally Managed Environment

If you encounter an error message like "This environment is externally managed" when running the installation script on Debian/Ubuntu systems, you have two simple options:

1. **Install dependencies with the system package manager (recommended):**
   ```bash
   sudo apt install python3-piexif python3-tqdm python3-colorama
   ```
   Then run the script directly:
   ```bash
   python3 main.py -i <input_dir> -o <output_dir> -e <error_dir>
   ```

2. **Force pip installation (use with caution):**
   ```bash
   pip3 install --break-system-packages -r requirements.txt
   pip3 install --break-system-packages -e .
   ```
   This bypasses the system protection, which may cause conflicts with system packages.

The installation script will provide these suggestions if it encounters the "externally managed environment" error.

## Usage

### Option 1: Run the script directly

```bash
# Run from the root directory
python main.py -i <input_dir> -o <output_dir> -e <error_dir>
```

This method uses the main.py file in the root directory, which is a simple wrapper that calls the main function in the src/main.py module.

### Option 2: Use the installed command (if installed as a package)

```bash
google-takeout-fixer -i <input_dir> -o <output_dir> -e <error_dir>
```

### Arguments

- `-i, --input-dir`: Directory containing the extracted contents of Google Photos Takeout zip file
- `-o, --output-dir`: Directory into which the processed output will be written
- `-e, --error-dir`: Directory for any files that have bad EXIF data - including the matching metadata files
- `-v, --version`: Show the version number and exit
- `-h, --help`: Show the help message and exit

To view the help information directly:

```bash
# Using the script directly
python main.py -h

# Using the installed command
google-takeout-fixer -h
```

### Examples

```bash
# Using the script directly
python main.py -i ~/Downloads/Takeout/Google\ Photos -o ~/Pictures/Processed -e ~/Pictures/Errors

# Using the installed command
google-takeout-fixer -i ~/Downloads/Takeout/Google\ Photos -o ~/Pictures/Processed -e ~/Pictures/Errors
```

## Performance Optimizations

This tool includes several performance optimizations:

1. **Parallel Processing**: Automatically uses 75% of available CPU cores to process multiple files simultaneously
2. **Buffered File I/O**: Uses a 1MB buffer for file operations instead of loading entire files into memory
3. **Optimized Directory Traversal**: Minimizes filesystem operations by scanning directories efficiently
4. **Progress Tracking**: Real-time updates showing processed and copied file counts

## Supported File Types

The following file types are supported:

### Standard Image Formats
- JPEG (.jpg, .jpeg)
- HEIC (.heic)
- GIF (.gif)
- PNG (.png)

### Video Formats
- MP4 (.mp4)
- AVI (.avi)
- MOV (.mov)
- MKV (.mkv)

### RAW Image Formats
- Nikon (.nef)
- Digital Negative (.dng)
- General RAW (.raw)
- Canon (.cr2, .cr3)
- Sony (.arw)
- Olympus (.orf)
- Panasonic (.rw2)
- Pentax (.pef)
- Fujifilm (.raf)

You can easily add support for additional file formats by modifying the `formats.py` file.

## Notes

- The input directory must exist and contain Google Photos Takeout data.
- The output and error directories must either not exist (they will be created) or be empty.
- The tool will preserve the folder structure from the input directory in both the output and error directories.
- Files that already have EXIF date fields will not have those fields modified.
- The tool displays a progress bar and counters to track processing in real-time.
- A summary is displayed at the end showing the total number of files processed and copied.
- The `google_takeout_fixer.egg-info` directory is generated during installation and can be safely removed using the cleanup scripts if needed. It will be recreated when the package is installed again.

## Directory Maintenance

The project includes cleanup scripts to help maintain a clean directory structure:

- `cleanup.bat` (Windows) or `cleanup.py` (cross-platform) can be used to remove:
  - Generated directories (`google_takeout_fixer.egg-info`, `__pycache__`)
  - Temporary files (`.DS_Store`)
  - Duplicate directories
  - Other unnecessary files

To clean up the directory structure:

**On Windows:**
```bash
cleanup.bat
```

**On any platform with Python:**
```bash
python cleanup.py
```

These scripts help keep the project directory clean and organized, making it easier to navigate and maintain.

## Dependencies

- piexif: For reading and writing EXIF metadata
- tqdm: For displaying progress bars
- colorama: For colored terminal output
- Python's built-in multiprocessing: For parallel processing

## License

[MIT License](LICENSE)
