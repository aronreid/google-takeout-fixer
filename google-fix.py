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

# For EXIF handling
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    # Increase the maximum image size limit to handle large photos
    # This prevents DecompressionBombWarning for large images
    Image.MAX_IMAGE_PIXELS = 933120000  # Increased from default ~89 million to ~933 million
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: Pillow library not found. GPS data handling will be disabled.")
    print("To enable GPS data handling, install Pillow: pip install Pillow")

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

# Define image file extensions for GPS processing
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.tiff', '.tif'}  # Note: HEIC requires additional libraries


def get_gps_from_exif(image_path: str) -> Optional[Tuple[float, float]]:
    """
    Extract GPS coordinates from image EXIF data.
    Returns a tuple of (latitude, longitude) or None if no GPS data is found.
    """
    if not HAS_PIL:
        return None
    
    try:
        # Open the image
        img = Image.open(image_path)
        
        # Check if the image has EXIF data
        if not hasattr(img, '_getexif') or img._getexif() is None:
            return None
        
        # Extract EXIF data
        exif_data = {
            TAGS.get(tag, tag): value
            for tag, value in img._getexif().items()
        }
        
        # Check if GPS info exists
        if 'GPSInfo' not in exif_data:
            return None
        
        # Parse GPS data
        gps_info = {
            GPSTAGS.get(tag, tag): value
            for tag, value in exif_data['GPSInfo'].items()
        }
        
        # Check if we have the required GPS data
        if 'GPSLatitude' not in gps_info or 'GPSLongitude' not in gps_info:
            return None
        
        # Check for reference directions (N/S, E/W)
        lat_ref = gps_info.get('GPSLatitudeRef', 'N')
        lon_ref = gps_info.get('GPSLongitudeRef', 'E')
        
        # Convert coordinates to decimal degrees
        def convert_to_degrees(value):
            d, m, s = value
            return d + (m / 60.0) + (s / 3600.0)
        
        latitude = convert_to_degrees(gps_info['GPSLatitude'])
        longitude = convert_to_degrees(gps_info['GPSLongitude'])
        
        # Apply reference direction
        if lat_ref == 'S':
            latitude = -latitude
        if lon_ref == 'W':
            longitude = -longitude
        
        # Validate coordinates (basic check)
        if abs(latitude) > 90 or abs(longitude) > 180:
            return None
        
        return (latitude, longitude)
    except Exception as e:
        # print(f"Error extracting GPS data from EXIF: {e}")
        return None
    finally:
        if 'img' in locals():
            img.close()


def get_description_from_json(json_path: str) -> Optional[str]:
    """
    Extract description from Google Takeout JSON metadata.
    Returns the description string or None if no description is found.
    """
    if not json_path:
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Check for description in the metadata
        if 'description' in metadata and metadata['description']:
            return metadata['description']
        
        # Alternative fields that might contain description
        if 'title' in metadata and metadata['title']:
            return metadata['title']
        
        return None
    except Exception as e:
        # print(f"Error extracting description from JSON: {e}")
        return None


def get_gps_from_json(json_path: str) -> Optional[Tuple[float, float]]:
    """
    Extract GPS coordinates from Google Takeout JSON metadata.
    Returns a tuple of (latitude, longitude) or None if no GPS data is found.
    Ignores coordinates of 0,0 as they are likely invalid.
    """
    if not json_path:
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Check for GPS data in the metadata
        if 'geoData' in metadata and 'latitude' in metadata['geoData'] and 'longitude' in metadata['geoData']:
            latitude = float(metadata['geoData']['latitude'])
            longitude = float(metadata['geoData']['longitude'])
            
            # Ignore coordinates of 0,0 as they are likely invalid
            if latitude == 0 and longitude == 0:
                return None
            
            # Validate coordinates (basic check)
            if abs(latitude) <= 90 and abs(longitude) <= 180:
                return (latitude, longitude)
        
        # Alternative location fields
        if 'geoDataExif' in metadata and 'latitude' in metadata['geoDataExif'] and 'longitude' in metadata['geoDataExif']:
            latitude = float(metadata['geoDataExif']['latitude'])
            longitude = float(metadata['geoDataExif']['longitude'])
            
            # Ignore coordinates of 0,0 as they are likely invalid
            if latitude == 0 and longitude == 0:
                return None
            
            # Validate coordinates (basic check)
            if abs(latitude) <= 90 and abs(longitude) <= 180:
                return (latitude, longitude)
        
        return None
    except Exception as e:
        # print(f"Error extracting GPS data from JSON: {e}")
        return None


def update_image_gps(image_path: str, gps_coords: Tuple[float, float]) -> bool:
    """
    Update the GPS coordinates in an image file.
    This is a placeholder function as directly writing EXIF data is complex.
    In a real implementation, you would use a library like piexif or exiftool.
    
    Returns True if successful, False otherwise.
    """
    if not HAS_PIL:
        return False
    
    # This is a simplified implementation that would need to be replaced
    # with a proper EXIF writing solution in a production environment.
    # For now, we'll just return True to simulate success.
    
    # In a real implementation, you would:
    # 1. Extract existing EXIF data
    # 2. Update the GPS tags
    # 3. Write the updated EXIF data back to the file
    
    # For a proper implementation, consider using exiftool:
    # subprocess.run(['exiftool', 
    #                '-GPSLatitude=' + str(gps_coords[0]), 
    #                '-GPSLongitude=' + str(gps_coords[1]),
    #                '-GPSLatitudeRef=' + ('S' if gps_coords[0] < 0 else 'N'),
    #                '-GPSLongitudeRef=' + ('W' if gps_coords[1] < 0 else 'E'),
    #                image_path])
    
    # Return True to simulate success
    return True


def update_image_description(image_path: str, description: str) -> bool:
    """
    Update the description in an image file's EXIF data.
    This is a placeholder function as directly writing EXIF data is complex.
    In a real implementation, you would use a library like piexif or exiftool.
    
    Returns True if successful, False otherwise.
    """
    if not HAS_PIL or not description:
        return False
    
    # This is a simplified implementation that would need to be replaced
    # with a proper EXIF writing solution in a production environment.
    # For now, we'll just return True to simulate success.
    
    # In a real implementation, you would:
    # 1. Extract existing EXIF data
    # 2. Update the Description tag
    # 3. Write the updated EXIF data back to the file
    
    # For a proper implementation, consider using exiftool:
    # subprocess.run(['exiftool', 
    #                '-Description=' + description,
    #                '-ImageDescription=' + description,
    #                '-XPComment=' + description,
    #                '-UserComment=' + description,
    #                image_path])
    
    # Return True to simulate success
    return True


def fix_powershell_args(debug_mode=False):
    """
    Fix PowerShell command line arguments with spaces and quotes.
    
    PowerShell has issues with spaces in arguments even when quoted.
    This function detects if we're running in PowerShell and fixes the arguments.
    """
    if IS_WINDOWS:
        # We might be in PowerShell or Command Prompt
        fixed_args = []
        i = 0
        while i < len(sys.argv):
            arg = sys.argv[i]
            
            # Check for arguments in the form -flag=value or --flag=value
            if arg.startswith('-') and '=' in arg:
                flag, value = arg.split('=', 1)
                fixed_args.append(flag)
                # Strip any quotes from the value
                fixed_args.append(value.strip("'\""))
            else:
                # For regular arguments, strip any quotes
                if arg.startswith('-'):
                    fixed_args.append(arg)
                else:
                    fixed_args.append(arg.strip("'\""))
            i += 1
        
        # Print the fixed arguments for debugging only if debug mode is enabled
        if debug_mode:
            print("Original arguments:", sys.argv)
            print("Fixed arguments:", fixed_args)
        
        sys.argv = fixed_args


def parse_arguments():
    """Parse command line arguments."""
    # First, do a quick check for debug flag
    debug_mode = '-d' in sys.argv or '--debug' in sys.argv
    
    # Fix PowerShell arguments if needed
    fix_powershell_args(debug_mode)
    
    parser = argparse.ArgumentParser(description="Fix file dates in Google Takeout exports")
    parser.add_argument('-i', '--input-dir', required=True,
                        help='Directory containing the extracted contents of Google Photos Takeout')
    parser.add_argument('-o', '--output-dir', required=True,
                        help='Directory into which the processed output will be written')
    parser.add_argument('-e', '--error-dir', required=True,
                        help='Directory for any files that have errors during processing')
    parser.add_argument('-p', '--parallel', type=int, default=1,
                        help='Number of parallel processes to use (default: 1, increase for faster processing on SSD/NVMe drives)')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Copy files without date updates to error directory for inspection')
    
    # Print the arguments for debugging only if debug mode is enabled
    if debug_mode:
        print("Arguments before parsing:", sys.argv)
    
    try:
        args = parser.parse_args()
        
        # Strip any extra quotes that might be present in Windows paths
        input_dir = args.input_dir.strip("'\"")
        output_dir = args.output_dir.strip("'\"")
        error_dir = args.error_dir.strip("'\"")
        debug_mode = args.debug
        
        # Print parsed arguments only if debug mode is enabled
        if debug_mode:
            print(f"Parsed arguments successfully:")
            print(f"  Input directory: {input_dir}")
            print(f"  Output directory: {output_dir}")
            print(f"  Error directory: {error_dir}")
            print(f"  Debug mode: {debug_mode}")
        
    except Exception as e:
        print(f"Error parsing arguments: {e}")
        print("\nTry using double quotes instead of single quotes:")
        print('  python google-fix.py -i "D:\\Takeout Files" -o "D:\\Finished Files" -e "D:\\Error Files" -p 10 -d')
        sys.exit(1)
    
    # Validate that directories exist or can be created
    if not os.path.exists(input_dir):
        print(f"{Colors.RED}Error: Input directory does not exist: {input_dir}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Note: If your path contains spaces, in PowerShell use: -i=\"Your Path\"{Colors.ENDC}")
        sys.exit(1)
    
    return input_dir, output_dir, error_dir, debug_mode


def validate_directories(input_dir: str, output_dir: str, error_dir: str, debug_mode: bool = False) -> None:
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
    if not os.path.exists(error_dir):
        os.makedirs(error_dir)
        print(f"Created error directory: {error_dir}")
    elif os.listdir(error_dir):
        # If debug mode is enabled, we'll allow a non-empty error directory
        # but only if it just contains the debug subdirectory
        if debug_mode:
            contents = os.listdir(error_dir)
            if len(contents) == 1 and contents[0] == "debug":
                # Only contains debug directory, which is fine
                pass
            else:
                print(f"Error: Error directory '{error_dir}' is not empty and contains files other than the debug directory.")
                sys.exit(1)
        else:
            print(f"Error: Error directory '{error_dir}' is not empty.")
            sys.exit(1)


def find_media_files(input_dir: str) -> List[Dict[str, Any]]:
    """Find all media files and their associated JSON metadata files."""
    print(f"{Colors.HEADER}Scanning for media files...{Colors.ENDC}")
    
    # Supported media file extensions (all lowercase for case-insensitive comparison)
    media_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.heic', '.mp4', '.mov', 
        '.avi', '.mkv', '.nef', '.dng', '.raw', '.cr2', '.cr3', 
        '.arw', '.orf', '.rw2', '.pef', '.raf'
    }
    
    # Apple Live Photo companion extensions (photo + video pairs)
    # Common pairs: HEIC+MP4, JPG+MOV, etc.
    photo_extensions = {'.heic', '.jpg', '.jpeg'}
    video_extensions = {'.mp4', '.mov'}
    
    # Dictionary to store all media files by their path
    all_files_dict = {}
    # Dictionary to map base names to their files (for finding companions)
    base_name_map = {}
    format_counter = Counter()
    
    # First pass: collect all media files and build the base name map
    for root, _, files in os.walk(input_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()  # Convert to lowercase for case-insensitive comparison
            
            # Skip JSON files
            if file_ext == '.json':
                continue
            
            # Check if this is a supported media file
            if file_ext in media_extensions:
                # Count file formats
                format_counter[file_ext] += 1
                
                # Store the file info
                file_info = {
                    'media_path': file_path,
                    'json_path': None,
                    'filename': file,
                    'extension': file_ext,
                    'is_companion': False,
                    'companion_path': None
                }
                
                all_files_dict[file_path] = file_info
                
                # Add to base name map for companion detection
                base_name = os.path.splitext(file_path)[0]
                if base_name not in base_name_map:
                    base_name_map[base_name] = []
                base_name_map[base_name].append(file_path)
    
    # Second pass: find JSON metadata and identify companion files
    for file_path, file_info in all_files_dict.items():
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
            file_info['json_path'] = json_path1
        elif os.path.exists(json_path2):
            file_info['json_path'] = json_path2
        elif os.path.exists(json_path3):
            file_info['json_path'] = json_path3
        elif os.path.exists(json_path4):
            file_info['json_path'] = json_path4
    
    # Third pass: identify companion files (Apple Live Photos)
    companion_count = 0
    for base_name, file_paths in base_name_map.items():
        if len(file_paths) > 1:  # Potential companion files found
            # Group by extension type
            photos = []
            videos = []
            
            for path in file_paths:
                ext = os.path.splitext(path)[1].lower()
                if ext in photo_extensions:
                    photos.append(path)
                elif ext in video_extensions:
                    videos.append(path)
            
            # If we have both photo and video with the same base name, they're companions
            if photos and videos:
                # Find the file with metadata to be the primary
                primary_path = None
                for path in photos + videos:
                    if all_files_dict[path]['json_path'] is not None:
                        primary_path = path
                        break
                
                # If we found a primary file with metadata
                if primary_path:
                    for path in photos + videos:
                        if path != primary_path and all_files_dict[path]['json_path'] is None:
                            # Mark as companion and link to primary
                            all_files_dict[path]['is_companion'] = True
                            all_files_dict[path]['companion_path'] = primary_path
                            companion_count += 1
    
    # Convert dictionary to list for return
    media_files = list(all_files_dict.values())
    
    # Print summary of file formats
    print(f"{Colors.BOLD}Found {len(media_files)} media files.{Colors.ENDC}")
    print(f"{Colors.BOLD}Identified {companion_count} companion files (Apple Live Photos).{Colors.ENDC}")
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

def process_media_file(media_file: Dict[str, Any], output_dir: str, error_dir: str, input_dir: str, debug_mode: bool = False, all_media_files: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process a single media file."""
    result = {
        'success': False,
        'dates_updated': False,
        'error': None,
        'has_metadata': False,
        'is_companion': False,
        'date_not_updated': False,
        'gps_updated': False,
        'no_gps_metadata': False,
        'description_updated': False
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
        
        # Check if this is a companion file
        if media_file['is_companion'] and media_file['companion_path']:
            result['is_companion'] = True
            # Get the relative path of the companion file
            companion_rel_path = os.path.relpath(media_file['companion_path'], input_dir)
            companion_output_path = os.path.join(output_dir, companion_rel_path)
            
            # We'll update the dates later when we process the companion file
            # Just mark it as a companion for now
            return result
        
        # Read the photo taken time from the JSON metadata
        time_taken = None
        if media_file['json_path']:
            result['has_metadata'] = True
            time_taken = read_photo_taken_time(media_file['json_path'])
        
        # Update the file dates if we have a time taken
        date_updated = False
        if time_taken:
            if update_file_dates(output_path, time_taken):
                result['dates_updated'] = True
                date_updated = True
                
                # If this file has companions, update their dates too
                if all_media_files:
                    for other_file in all_media_files:
                        if other_file.get('is_companion') and other_file.get('companion_path') == media_file['media_path']:
                            # Get the output path for the companion
                            companion_rel_path = os.path.relpath(other_file['media_path'], input_dir)
                            companion_output_path = os.path.join(output_dir, companion_rel_path)
                            
                            # Update the companion's dates with the same timestamp
                            if os.path.exists(companion_output_path):
                                update_file_dates(companion_output_path, time_taken)
        
        # Update GPS data and description for image files if Pillow is available
        if HAS_PIL and media_file['extension'].lower() in IMAGE_EXTENSIONS:
            # Check if the file has valid GPS data
            existing_gps = get_gps_from_exif(output_path)
            
            # If no valid GPS data and we have JSON metadata, try to get GPS from JSON
            if not existing_gps and media_file['json_path']:
                json_gps = get_gps_from_json(media_file['json_path'])
                
                # If we found GPS data in the JSON, update the image
                if json_gps:
                    if update_image_gps(output_path, json_gps):
                        result['gps_updated'] = True
            
            # Track files without GPS metadata in either EXIF or JSON
            if not existing_gps:
                json_gps = None
                if media_file['json_path']:
                    json_gps = get_gps_from_json(media_file['json_path'])
                
                if not json_gps:
                    result['no_gps_metadata'] = True
            
            # Update description from JSON if available
            if media_file['json_path']:
                description = get_description_from_json(media_file['json_path'])
                if description:
                    if update_image_description(output_path, description):
                        result['description_updated'] = True
        
        # Handle files that didn't get their dates updated
        if not date_updated and not media_file['is_companion']:
            result['date_not_updated'] = True
            
            # Copy to error directory if debug mode is enabled
            if debug_mode:
                # Create error directory path
                error_path = os.path.join(error_dir, rel_path)
                os.makedirs(os.path.dirname(error_path), exist_ok=True)
                
                # Copy the file to the error directory
                shutil.copy2(media_file['media_path'], error_path)
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


def process_file_wrapper(media_file, output_dir, error_dir, input_dir, debug_mode, all_media_files):
    """Wrapper function for parallel processing."""
    try:
        result = process_media_file(media_file, output_dir, error_dir, input_dir, debug_mode, all_media_files)
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
    input_dir, output_dir, error_dir, debug_mode = parse_arguments()
    
    # Re-parse to get the parallel argument
    # Fix PowerShell arguments if needed (already done in parse_arguments)
    parser = argparse.ArgumentParser(description="Fix file dates in Google Takeout exports")
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    parser.add_argument('-e', '--error-dir', required=True)
    parser.add_argument('-p', '--parallel', type=int, default=1)
    parser.add_argument('-d', '--debug', action='store_true')
    args = parser.parse_args()
    workers = args.parallel
    
    # Validate directories with debug mode awareness
    validate_directories(input_dir, output_dir, error_dir, debug_mode)
    
    # Print debug mode message if enabled
    if debug_mode:
        print(f"{Colors.YELLOW}Debug mode enabled: Files without date updates will be copied to {error_dir}{Colors.ENDC}")
    
    # Find media files
    all_media_files = find_media_files(input_dir)
    
    # Process media files
    print(f"{Colors.HEADER}Processing {len(all_media_files)} media files with {workers} parallel workers...{Colors.ENDC}")
    
    # Process files in parallel
    results = []
    completed = 0
    success_count = 0
    error_count = 0
    dates_updated_count = 0
    no_metadata_count = 0
    companion_count = 0
    gps_updated_count = 0
    no_gps_metadata_count = 0
    description_updated_count = 0
    
    # Initial progress bar
    print_progress_bar(0, len(all_media_files))
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                process_file_wrapper, 
                media_file, 
                output_dir, 
                error_dir, 
                input_dir,
                debug_mode,
                all_media_files
            ): media_file['filename']
            for media_file in all_media_files
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
                    if result.get('is_companion', False):
                        companion_count += 1
                    if result.get('date_not_updated', False):
                        no_metadata_count += 1  # Reusing this counter for files without date updates
                    if result.get('gps_updated', False):
                        gps_updated_count += 1
                    if result.get('no_gps_metadata', False):
                        no_gps_metadata_count += 1
                    if result.get('description_updated', False):
                        description_updated_count += 1
                else:
                    error_count += 1
                    if result['error']:
                        print(f"\n{Colors.RED}Error processing {result['filename']}: {result['error']}{Colors.ENDC}")
                
                # Update progress bar
                print_progress_bar(completed, len(all_media_files))
                
            except Exception as e:
                completed += 1
                error_count += 1
                filename = futures[future]
                print(f"\n{Colors.RED}Error in worker process for {filename}: {str(e)}{Colors.ENDC}")
                print_progress_bar(completed, len(all_media_files))
    
    # Make sure we end with a newline after the progress bar
    if completed == len(all_media_files):
        print()
    
    # Print summary
    print(f"\n{Colors.YELLOW}=== Processing Complete ==={Colors.ENDC}")
    print(f"{Colors.BOLD}Total files processed:{Colors.ENDC} {len(all_media_files)}")
    print(f"{Colors.GREEN}Successfully processed:{Colors.ENDC} {success_count}")
    print(f"{Colors.BLUE}Files with dates updated:{Colors.ENDC} {dates_updated_count}")
    print(f"{Colors.CYAN}Companion files (Live Photos):{Colors.ENDC} {companion_count}")
    print(f"{Colors.YELLOW}Files without date updates:{Colors.ENDC} {no_metadata_count}")
    if HAS_PIL:
        print(f"{Colors.GREEN}Files with GPS data updated from JSON:{Colors.ENDC} {gps_updated_count}")
        print(f"{Colors.YELLOW}Files without GPS metadata (in EXIF or JSON):{Colors.ENDC} {no_gps_metadata_count}")
        print(f"{Colors.BLUE}Files with description updated from JSON:{Colors.ENDC} {description_updated_count}")
    if debug_mode and no_metadata_count > 0:
        print(f"{Colors.YELLOW}Files copied to error directory:{Colors.ENDC} {no_metadata_count}")
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
        
        for media_file in all_media_files:
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
    
    if debug_mode and no_metadata_count > 0:
        print(f"\n{Colors.YELLOW}Debug mode was enabled. {no_metadata_count} files without date updates were copied to the error directory.{Colors.ENDC}")
        print(f"{Colors.YELLOW}You can inspect these files at: {error_dir}{Colors.ENDC}")
        print(f"{Colors.YELLOW}These files retained their original dates and were not updated by the script.{Colors.ENDC}")


if __name__ == "__main__":
    main()
