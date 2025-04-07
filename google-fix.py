#!/usr/bin/env python3
"""
Google Takeout Fix - A simple tool to fix file dates in Google Takeout exports

This script processes Google Photos Takeout folders and fixes the file creation
and modification dates based on the metadata in the JSON files.

Usage:
    python google-fix.py -i "input_folder" -o "output_folder" -e "error_folder" [-p num_workers]

PowerShell Usage (for paths with spaces):
    python google-fix.py -i="C:/Path With Spaces" -o="D:/Output Path" -e="E:/Error Path"
    
    # Note: In PowerShell, use equals sign with no space between flag and path,
    # and enclose paths with spaces in quotes

Requirements:
    - Python 3.6+
    - pywin32 (for Windows file date handling)
"""

import os
import sys
import json
import shutil
import argparse
import tempfile
import subprocess
import concurrent.futures
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Counter
from collections import Counter

# Check if running on Windows
import platform
IS_WINDOWS = platform.system() == "Windows"

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Check for required dependencies
if IS_WINDOWS:
    try:
        import win32file
    except ImportError:
        print("Error: pywin32 is required for Windows file date handling.")
        print("Please install it with: pip install pywin32")
        sys.exit(1)


def fix_powershell_args():
    """
    Fix PowerShell command line arguments with spaces.
    
    PowerShell has issues with spaces in arguments even when quoted.
    This function detects if we're running in PowerShell and fixes the arguments.
    """
    if IS_WINDOWS and 'powershell' in os.environ.get('PSModulePath', '').lower():
        # We're in PowerShell
        fixed_args = []
        i = 0
        while i < len(sys.argv):
            arg = sys.argv[i]
            # Check for arguments in the form -flag=value or --flag=value
            if arg.startswith('-') and '=' in arg:
                flag, value = arg.split('=', 1)
                fixed_args.append(flag)
                fixed_args.append(value)
            else:
                fixed_args.append(arg)
            i += 1
        sys.argv = fixed_args


def parse_arguments():
    """Parse command line arguments."""
    # Fix PowerShell arguments if needed
    fix_powershell_args()
    
    parser = argparse.ArgumentParser(description="Fix file dates in Google Takeout exports")
    parser.add_argument('-i', '--input-dir', required=True,
                        help='Directory containing the extracted contents of Google Photos Takeout')
    parser.add_argument('-o', '--output-dir', required=True,
                        help='Directory into which the processed output will be written')
    parser.add_argument('-e', '--error-dir', required=True,
                        help='Directory for any files that have errors during processing')
    parser.add_argument('-p', '--parallel', type=int, default=1,
                        help='Number of parallel processes to use (default: 1, increase for faster processing on SSD/NVMe drives)')
    
    args = parser.parse_args()
    
    # Strip any extra quotes that might be present in Windows paths
    input_dir = args.input_dir.strip("'\"")
    output_dir = args.output_dir.strip("'\"")
    error_dir = args.error_dir.strip("'\"")
    
    # Validate that directories exist or can be created
    if not os.path.exists(input_dir):
        print(f"{Colors.RED}Error: Input directory does not exist: {input_dir}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Note: If your path contains spaces, in PowerShell use: -i=\"Your Path\"{Colors.ENDC}")
        sys.exit(1)
    
    return input_dir, output_dir, error_dir


def validate_directories(input_dir: str, output_dir: str, error_dir: str) -> None:
    """Validate and create directories as needed."""
    # Check input directory
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    if os.path.exists(output_dir):
        if os.listdir(output_dir):
            print(f"Error: Output directory '{output_dir}' is not empty.")
            sys.exit(1)
    else:
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Create error directory if it doesn't exist
    if os.path.exists(error_dir):
        if os.listdir(error_dir):
            print(f"Error: Error directory '{error_dir}' is not empty.")
            sys.exit(1)
    else:
        os.makedirs(error_dir)
        print(f"Created error directory: {error_dir}")


def find_media_files(input_dir: str) -> List[Dict[str, Any]]:
    """Find all media files and their associated JSON metadata files."""
    print(f"{Colors.HEADER}Scanning for media files...{Colors.ENDC}")
    
    # Supported media file extensions
    media_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.heic', '.mp4', '.mov', 
        '.avi', '.mkv', '.nef', '.dng', '.raw', '.cr2', '.cr3', 
        '.arw', '.orf', '.rw2', '.pef', '.raf'
    }
    
    media_files = []
    format_counter = Counter()
    
    # Walk through the input directory
    for root, _, files in os.walk(input_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            # Skip JSON files
            if file_ext == '.json':
                continue
            
            # Check if this is a supported media file
            if file_ext in media_extensions:
                # Count file formats
                format_counter[file_ext] += 1
                # Look for corresponding JSON files with different naming patterns
                # Pattern 1: file.jpg.json
                json_path1 = file_path + '.json'
                # Pattern 2: file.jpg.suppl.json
                json_path2 = file_path + '.suppl.json'
                # Pattern 3: file.mp4.supplemental-metadata.json
                json_path3 = file_path + '.supplemental-metadata.json'
                # Pattern 4: file.json (where file is without extension)
                base_name = os.path.splitext(file_path)[0]
                json_path4 = base_name + '.json'
                
                # Check each pattern
                if os.path.exists(json_path1):
                    media_files.append({
                        'media_path': file_path,
                        'json_path': json_path1,
                        'filename': file,
                        'extension': file_ext
                    })
                elif os.path.exists(json_path2):
                    media_files.append({
                        'media_path': file_path,
                        'json_path': json_path2,
                        'filename': file,
                        'extension': file_ext
                    })
                elif os.path.exists(json_path3):
                    media_files.append({
                        'media_path': file_path,
                        'json_path': json_path3,
                        'filename': file,
                        'extension': file_ext
                    })
                elif os.path.exists(json_path4):
                    media_files.append({
                        'media_path': file_path,
                        'json_path': json_path4,
                        'filename': file,
                        'extension': file_ext
                    })
                else:
                    # No JSON found, but still process the file
                    media_files.append({
                        'media_path': file_path,
                        'json_path': None,
                        'filename': file,
                        'extension': file_ext
                    })
    
    # Print summary of file formats
    print(f"{Colors.BOLD}Found {len(media_files)} media files.{Colors.ENDC}")
    print(f"\n{Colors.CYAN}=== File Format Summary ==={Colors.ENDC}")
    for ext, count in sorted(format_counter.items(), key=lambda x: x[1], reverse=True):
        print(f"{Colors.BLUE}{ext:<6}{Colors.ENDC}: {Colors.GREEN}{count}{Colors.ENDC}")
    print(f"{Colors.CYAN}========================={Colors.ENDC}\n")
    
    return media_files


def read_photo_taken_time(json_path: Optional[str]) -> Optional[str]:
    """Read the photo taken time from the Google JSON metadata file."""
    if not json_path:
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Try to find the photo taken time in the metadata
        if 'photoTakenTime' in metadata:
            timestamp = metadata['photoTakenTime'].get('timestamp')
            if timestamp:
                # Convert Unix timestamp to ISO format
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.isoformat()
        
        # Alternative fields to check
        if 'creationTime' in metadata:
            timestamp = metadata['creationTime'].get('timestamp')
            if timestamp:
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.isoformat()
        
        return None
    except Exception as e:
        print(f"Error reading JSON metadata: {e}")
        return None


def update_file_dates(file_path: str, time_taken: str) -> bool:
    """Update the file creation and modification dates."""
    try:
        # Convert ISO format to datetime
        dt = datetime.fromisoformat(time_taken)
        
        if IS_WINDOWS:
            # Use the approach from basic_test.bat
            return update_windows_file_dates(file_path, dt)
        else:
            # For non-Windows platforms, just set the modification time
            timestamp = dt.timestamp()
            os.utime(file_path, (timestamp, timestamp))
            return True
    except Exception as e:
        print(f"Error updating file dates: {e}")
        return False


def update_windows_file_dates(file_path: str, dt: datetime) -> bool:
    """Update file dates on Windows using PowerShell."""
    try:
        # Create a temporary PowerShell script file
        ps_file = os.path.join(tempfile.gettempdir(), f"set_dates_{os.getpid()}.ps1")
        
        # Format date for PowerShell
        ps_date = dt.strftime("%m/%d/%Y %H:%M:%S")
        
        # PowerShell script content
        ps_script = f"""
# Get the file path
$filePath = "{file_path.replace('"', '`"')}"

# Use .NET Framework method (most reliable)
[System.IO.File]::SetCreationTime($filePath, "{ps_date}")
[System.IO.File]::SetLastWriteTime($filePath, "{ps_date}")
[System.IO.File]::SetLastAccessTime($filePath, "{ps_date}")

# Verify the change
$file = Get-Item -LiteralPath $filePath -Force
if ($file.CreationTime.ToString("MM/dd/yyyy HH:mm:ss") -ne "{ps_date}") {{
    # If verification fails, try again with direct property assignment
    $file.CreationTime = "{ps_date}"
    $file.LastWriteTime = "{ps_date}"
    $file.LastAccessTime = "{ps_date}"
}}
"""
        
        # Write PowerShell commands to the script file
        with open(ps_file, 'w') as f:
            f.write(ps_script)
        
        # Execute the PowerShell script
        result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file], 
                      check=False, timeout=10, capture_output=True, text=True)
        
        # Clean up the temporary script file
        try:
            os.remove(ps_file)
        except:
            pass
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error in PowerShell execution: {e}")
        return False


def print_progress_bar(current, total):
    """Print a progress bar to show processing status."""
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    length = 50
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r{Colors.BOLD}Progress:{Colors.ENDC} |{Colors.CYAN}{bar}{Colors.ENDC}| {percent}% {Colors.BOLD}{current}/{total}{Colors.ENDC}', end='', flush=True)
    if current == total:
        print()

def process_media_file(media_file: Dict[str, Any], output_dir: str, error_dir: str, input_dir: str) -> Dict[str, Any]:
    """Process a single media file."""
    result = {
        'success': False,
        'dates_updated': False,
        'error': None,
        'has_metadata': False
    }
    
    try:
        # Determine the output path
        rel_path = os.path.relpath(media_file['media_path'], input_dir)
        output_path = os.path.join(output_dir, rel_path)
        
        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Copy the file to the output directory
        shutil.copy2(media_file['media_path'], output_path)
        result['success'] = True
        
        # Read the photo taken time from the JSON metadata
        time_taken = None
        if media_file['json_path']:
            result['has_metadata'] = True
            time_taken = read_photo_taken_time(media_file['json_path'])
        
        # Update the file dates if we have a time taken
        if time_taken:
            if update_file_dates(output_path, time_taken):
                result['dates_updated'] = True
    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
        
        # Move the file to the error directory if there was an error
        try:
            if os.path.exists(output_path):
                error_path = os.path.join(error_dir, rel_path)
                os.makedirs(os.path.dirname(error_path), exist_ok=True)
                shutil.move(output_path, error_path)
        except:
            pass
    
    return result


def process_file_wrapper(media_file, output_dir, error_dir, input_dir):
    """Wrapper function for parallel processing."""
    try:
        result = process_media_file(media_file, output_dir, error_dir, input_dir)
        # Add filename to result for error reporting
        result['filename'] = media_file['filename']
        return result
    except Exception as e:
        # Handle any exceptions in the worker process
        return {
            'success': False,
            'dates_updated': False,
            'error': str(e),
            'filename': media_file['filename']
        }

def main():
    """Main function."""
    # Parse command line arguments
    input_dir, output_dir, error_dir = parse_arguments()
    
    # Re-parse to get the parallel argument
    # Fix PowerShell arguments if needed (already done in parse_arguments)
    parser = argparse.ArgumentParser(description="Fix file dates in Google Takeout exports")
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    parser.add_argument('-e', '--error-dir', required=True)
    parser.add_argument('-p', '--parallel', type=int, default=1)
    args = parser.parse_args()
    workers = args.parallel
    
    # Validate directories
    validate_directories(input_dir, output_dir, error_dir)
    
    # Find media files
    media_files = find_media_files(input_dir)
    
    # Process media files
    print(f"{Colors.HEADER}Processing {len(media_files)} media files with {workers} parallel workers...{Colors.ENDC}")
    
    # Process files in parallel
    results = []
    completed = 0
    success_count = 0
    error_count = 0
    dates_updated_count = 0
    no_metadata_count = 0
    
    # Initial progress bar
    print_progress_bar(0, len(media_files))
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                process_file_wrapper, 
                media_file, 
                output_dir, 
                error_dir, 
                input_dir
            ): media_file['filename']
            for media_file in media_files
        }
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                
                # Update counters
                completed += 1
                if result['success']:
                    success_count += 1
                    if result.get('dates_updated', False):
                        dates_updated_count += 1
                    if not result.get('has_metadata', False):
                        no_metadata_count += 1
                else:
                    error_count += 1
                    if result['error']:
                        print(f"\n{Colors.RED}Error processing {result['filename']}: {result['error']}{Colors.ENDC}")
                
                # Update progress bar
                print_progress_bar(completed, len(media_files))
                
            except Exception as e:
                completed += 1
                error_count += 1
                filename = futures[future]
                print(f"\n{Colors.RED}Error in worker process for {filename}: {str(e)}{Colors.ENDC}")
                print_progress_bar(completed, len(media_files))
    
    # Make sure we end with a newline after the progress bar
    if completed == len(media_files):
        print()
    
    # Print summary
    print(f"\n{Colors.YELLOW}=== Processing Complete ==={Colors.ENDC}")
    print(f"{Colors.BOLD}Total files processed:{Colors.ENDC} {len(media_files)}")
    print(f"{Colors.GREEN}Successfully processed:{Colors.ENDC} {success_count}")
    print(f"{Colors.BLUE}Files with dates updated:{Colors.ENDC} {dates_updated_count}")
    print(f"{Colors.YELLOW}Files without metadata:{Colors.ENDC} {no_metadata_count}")
    print(f"{Colors.RED}Errors:{Colors.ENDC} {error_count}")
    print(f"\n{Colors.BOLD}Output directory:{Colors.ENDC} {output_dir}")
    print(f"{Colors.BOLD}Error directory:{Colors.ENDC} {error_dir}")
    
    if error_count > 0:
        print(f"\n{Colors.RED}Some files had errors during processing. Check the error directory for details.{Colors.ENDC}")
    
    # Print a summary of file dates for a sample file
    if dates_updated_count > 0:
        print(f"\n{Colors.CYAN}=== Sample File Date Summary ==={Colors.ENDC}")
        # Find a file that had its dates updated
        sample_file = None
        sample_json = None
        sample_time = None
        
        for media_file in media_files:
            if media_file['json_path'] and os.path.exists(media_file['json_path']):
                rel_path = os.path.relpath(media_file['media_path'], input_dir)
                output_path = os.path.join(output_dir, rel_path)
                
                if os.path.exists(output_path):
                    sample_file = output_path
                    sample_json = media_file['json_path']
                    sample_time = read_photo_taken_time(media_file['json_path'])
                    break
        
        if sample_file and sample_time:
            # Convert ISO format to datetime
            expected_date = datetime.fromisoformat(sample_time)
            
            # Get the file's creation and modification times
            file_stat = os.stat(sample_file)
            modified_time = datetime.fromtimestamp(file_stat.st_mtime)
            
            print(f"{Colors.BOLD}File:{Colors.ENDC} {os.path.basename(sample_file)}")
            print(f"{Colors.BOLD}JSON Metadata:{Colors.ENDC} {sample_json}")
            print(f"{Colors.BOLD}Expected date from JSON:{Colors.ENDC} {expected_date}")
            
            # On Windows, we can also check creation time
            if hasattr(file_stat, 'st_ctime'):
                creation_time = datetime.fromtimestamp(file_stat.st_ctime)
                print(f"{Colors.BOLD}File creation date:{Colors.ENDC} {creation_time}")
            
            print(f"{Colors.BOLD}File modification date:{Colors.ENDC} {modified_time}")
            print(f"{Colors.CYAN}=============================={Colors.ENDC}")
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}Done!{Colors.ENDC}")


if __name__ == "__main__":
    main()
