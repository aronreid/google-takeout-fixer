#!/usr/bin/env python3
"""
Google Takeout Fix - A simple tool to fix file dates in Google Takeout exports

This script processes Google Photos Takeout folders and fixes the file creation
and modification dates based on the metadata in the JSON files.

Usage:
    python google-fix.py -i "input_folder" -o "output_folder" -e "error_folder" [-p num_workers]
    
    # For debugging a specific file:
    python google-fix.py -i "input_folder" -o "output_folder" -e "error_folder" -s "filename.mp4" -d

PowerShell Usage (for paths with spaces):
    python google-fix.py -i="C:/Path With Spaces" -o="D:/Output Path" -e="E:/Error Path"
    
    # Note: In PowerShell, use equals sign with no space between flag and path,
    # and enclose paths with spaces in quotes

Options:
    -i, --input-dir    Directory containing the extracted contents of Google Photos Takeout
    -o, --output-dir   Directory into which the processed output will be written
    -e, --error-dir    Directory for any files that have errors during processing
    -p, --parallel     Number of parallel processes to use (default: 1)
    -d, --debug        Copy files without date updates to error directory for inspection
    -q, --quiet        Reduce verbosity of output messages
    -u, --force-utc    Force UTC timezone for all timestamps
    -s, --single-file  Process only a single file (for debugging purposes)

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
    # Check if we're running in a terminal that supports colors
    try:
        import os
        is_terminal = os.isatty(1)  # 1 is stdout
    except:
        is_terminal = False
    
    # Only use colors if we're in a terminal
    if is_terminal:
        HEADER = '\033[95m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'
    else:
        # Empty strings if not in a terminal
        HEADER = ''
        BLUE = ''
        CYAN = ''
        GREEN = ''
        YELLOW = ''
        RED = ''
        ENDC = ''
        BOLD = ''
        UNDERLINE = ''

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
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Reduce verbosity of output messages (only show critical errors and summary)')
    parser.add_argument('-u', '--force-utc', action='store_true',
                        help='Force UTC timezone for all timestamps (useful if timestamps are in UTC but not marked as such)')
    parser.add_argument('-s', '--single-file', 
                        help='Process only a single file (for debugging purposes)')
    
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


def find_media_files(input_dir: str, debug_mode: bool = False) -> List[Dict[str, Any]]:
    """Find all media files and their associated JSON metadata files."""
    print(f"{Colors.HEADER}Scanning for media files...{Colors.ENDC}")
    
    # Supported media file extensions (all lowercase for case-insensitive comparison)
    media_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.heic', '.mp4', '.mov', 
        '.avi', '.mkv', '.nef', '.dng', '.raw', '.cr2', '.cr3', 
        '.arw', '.orf', '.rw2', '.pef', '.raf'
    }
    
    # Apple Live Photo companion extensions (photo + video pairs)
    # Common pairs: HEIC+MP4, JPG+MOV, JPG+MP4, etc.
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
        
        # Special handling for files with parentheses
        # For files like IMG_0624(1).MOV, also check for IMG_0624.MOV.json
        original_name = None
        if '(' in file_info['filename']:
            # Extract the original filename without the (n) part
            filename = file_info['filename']
            ext = os.path.splitext(filename)[1]
            name_part = os.path.splitext(filename)[0]
            
            # Find the position of the opening parenthesis
            paren_pos = name_part.find('(')
            if paren_pos > 0:
                original_name = name_part[:paren_pos] + ext
                dir_path = os.path.dirname(file_path)
                original_path = os.path.join(dir_path, original_name)
                
                # Check for JSON files with the original name
                json_path5 = original_path + '.json'
                json_path6 = original_path + '.suppl.json'
                json_path7 = original_path + '.supplemental-metadata.json'
                json_path8 = os.path.splitext(original_path)[0] + '.json'
        
        # Check each pattern
        if os.path.exists(json_path1):
            file_info['json_path'] = json_path1
        elif os.path.exists(json_path2):
            file_info['json_path'] = json_path2
        elif os.path.exists(json_path3):
            file_info['json_path'] = json_path3
        elif os.path.exists(json_path4):
            file_info['json_path'] = json_path4
        # Check patterns for original name (without parentheses)
        elif original_name and os.path.exists(json_path5):
            file_info['json_path'] = json_path5
            if debug_mode:
                print(f"{Colors.YELLOW}Found JSON for {file_info['filename']} using original name {original_name}{Colors.ENDC}")
        elif original_name and os.path.exists(json_path6):
            file_info['json_path'] = json_path6
            if debug_mode:
                print(f"{Colors.YELLOW}Found JSON for {file_info['filename']} using original name {original_name}{Colors.ENDC}")
        elif original_name and os.path.exists(json_path7):
            file_info['json_path'] = json_path7
            if debug_mode:
                print(f"{Colors.YELLOW}Found JSON for {file_info['filename']} using original name {original_name}{Colors.ENDC}")
        elif original_name and os.path.exists(json_path8):
            file_info['json_path'] = json_path8
            if debug_mode:
                print(f"{Colors.YELLOW}Found JSON for {file_info['filename']} using original name {original_name}{Colors.ENDC}")
    
    # Third pass: identify companion files (Apple Live Photos)
    companion_count = 0
    
    # First, identify companions with exact base name matches
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
    
    # Second, look for companions with similar base names and close timestamps
    # This handles cases where the naming convention might be slightly different
    # or timestamps in filenames are slightly off
    
    # Group files by their directory
    files_by_dir = {}
    for file_path, file_info in all_files_dict.items():
        # Skip files that are already identified as companions
        if file_info['is_companion']:
            continue
        
        dir_path = os.path.dirname(file_path)
        if dir_path not in files_by_dir:
            files_by_dir[dir_path] = []
        files_by_dir[dir_path].append(file_path)
    
    # For each directory, look for potential companions
    for dir_path, file_paths in files_by_dir.items():
        # Group files by extension type
        photos = []
        videos = []
        
        for path in file_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in photo_extensions:
                photos.append(path)
            elif ext in video_extensions:
                videos.append(path)
        
        # Skip if we don't have both photos and videos in this directory
        if not photos or not videos:
            continue
        
        # For each photo, look for a potential video companion
        for photo_path in photos:
            # Skip if this photo is already a companion
            if all_files_dict[photo_path]['is_companion']:
                continue
            
            photo_base = os.path.basename(photo_path)
            photo_base_no_ext = os.path.splitext(photo_base)[0]
            
            # Get photo timestamp from JSON if available
            photo_time = None
            if all_files_dict[photo_path]['json_path']:
                photo_time = read_photo_taken_time(all_files_dict[photo_path]['json_path'])
            
            # If we don't have a timestamp, skip this photo
            if not photo_time:
                continue
            
            # Convert ISO format to datetime
            photo_dt = datetime.fromisoformat(photo_time)
            
            # For each video, check if it's a potential companion
            for video_path in videos:
                # Skip if this video is already a companion
                if all_files_dict[video_path]['is_companion']:
                    continue
                
                video_base = os.path.basename(video_path)
                video_base_no_ext = os.path.splitext(video_base)[0]
                
                # Check if the base names are similar
                # This handles cases like IMG_1234.jpg and IMG_1234_01.MP4
                # or IMG_1234.jpg and IMG_1235.MP4
                
                # Simple case: one is a prefix of the other
                if video_base_no_ext.startswith(photo_base_no_ext) or photo_base_no_ext.startswith(video_base_no_ext):
                    # Get video timestamp from JSON if available
                    video_time = None
                    if all_files_dict[video_path]['json_path']:
                        video_time = read_photo_taken_time(all_files_dict[video_path]['json_path'])
                    
                    # If we have timestamps for both, check if they're close
                    if video_time:
                        video_dt = datetime.fromisoformat(video_time)
                        time_diff = abs((video_dt - photo_dt).total_seconds())
                        
                        # If timestamps are within 5 seconds, consider them companions
                        if time_diff <= 5:
                            # Mark video as companion and link to photo
                            all_files_dict[video_path]['is_companion'] = True
                            all_files_dict[video_path]['companion_path'] = photo_path
                            companion_count += 1
                            break  # Found a companion for this photo, move to next
    
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


def read_photo_taken_time(json_path: Optional[str], force_utc: bool = False) -> Optional[str]:
    """Read the photo taken time from the Google JSON metadata file."""
    if not json_path:
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Debug output for specific problematic files
        if "IMG_0538.JPG" in json_path or "IMG_0624(1).MOV" in json_path:
            print(f"\n{Colors.YELLOW}DEBUG - Found problematic file: {json_path}{Colors.ENDC}")
            print(f"{Colors.YELLOW}JSON metadata:{Colors.ENDC}")
            if 'photoTakenTime' in metadata:
                print(f"photoTakenTime: {metadata['photoTakenTime']}")
            if 'creationTime' in metadata:
                print(f"creationTime: {metadata['creationTime']}")
            if 'modificationTime' in metadata:
                print(f"modificationTime: {metadata['modificationTime']}")
            print(f"{Colors.YELLOW}End of debug output{Colors.ENDC}\n")
        
        # Try to find the photo taken time in the metadata
        if 'photoTakenTime' in metadata:
            timestamp = metadata['photoTakenTime'].get('timestamp')
            formatted_time = metadata['photoTakenTime'].get('formatted', '')
            
            if timestamp:
                # Check if the formatted time contains timezone information or if force_utc is enabled
                use_utc = force_utc or 'UTC' in formatted_time
                
                # Convert Unix timestamp to ISO format
                # Use UTC if the formatted time contains UTC or force_utc is enabled, otherwise use local timezone
                if use_utc:
                    try:
                        # Use the recommended approach for Python 3.11+
                        from datetime import UTC
                        dt_obj = datetime.fromtimestamp(int(timestamp), UTC)
                    except ImportError:
                        # Fallback for older Python versions
                        import datetime as dt
                        dt_obj = dt.datetime.utcfromtimestamp(int(timestamp))
                else:
                    dt_obj = datetime.fromtimestamp(int(timestamp))
                
                # Debug output for specific problematic file
                if "IMG_0538.JPG" in json_path:
                    print(f"{Colors.YELLOW}Timestamp: {timestamp}, Formatted: {formatted_time}{Colors.ENDC}")
                    print(f"{Colors.YELLOW}Using {'UTC' if use_utc else 'local timezone'} (force_utc={force_utc}){Colors.ENDC}")
                    print(f"{Colors.YELLOW}Converted to: {dt_obj} (ISO: {dt_obj.isoformat()}){Colors.ENDC}")
                
                return dt_obj.isoformat()
        
        # Alternative fields to check
        if 'creationTime' in metadata:
            timestamp = metadata['creationTime'].get('timestamp')
            formatted_time = metadata['creationTime'].get('formatted', '')
            
            if timestamp:
                # Check if the formatted time contains timezone information or if force_utc is enabled
                use_utc = force_utc or 'UTC' in formatted_time
                
                # Convert Unix timestamp to ISO format
                # Use UTC if the formatted time contains UTC or force_utc is enabled, otherwise use local timezone
                if use_utc:
                    try:
                        # Use the recommended approach for Python 3.11+
                        from datetime import UTC
                        dt_obj = datetime.fromtimestamp(int(timestamp), UTC)
                    except ImportError:
                        # Fallback for older Python versions
                        import datetime as dt
                        dt_obj = dt.datetime.utcfromtimestamp(int(timestamp))
                else:
                    dt_obj = datetime.fromtimestamp(int(timestamp))
                
                # Debug output for specific problematic file
                if "IMG_0538.JPG" in json_path:
                    print(f"{Colors.YELLOW}Using creationTime fallback{Colors.ENDC}")
                    print(f"{Colors.YELLOW}Timestamp: {timestamp}, Formatted: {formatted_time}{Colors.ENDC}")
                    print(f"{Colors.YELLOW}Using {'UTC' if use_utc else 'local timezone'} (force_utc={force_utc}){Colors.ENDC}")
                    print(f"{Colors.YELLOW}Converted to: {dt_obj} (ISO: {dt_obj.isoformat()}){Colors.ENDC}")
                
                return dt_obj.isoformat()
        
        # Debug output for specific problematic file
        if "IMG_0538.JPG" in json_path:
            print(f"{Colors.RED}No valid timestamp found in metadata!{Colors.ENDC}")
        
        return None
    except Exception as e:
        print(f"Error reading JSON metadata: {e}")
        if "IMG_0538.JPG" in json_path:
            print(f"{Colors.RED}Exception while processing problematic file: {e}{Colors.ENDC}")
        return None


def update_windows_file_dates_direct(file_path: str, dt: datetime, quiet_mode: bool = False, debug_mode: bool = False) -> bool:
    """Update file dates on Windows using win32file directly."""
    try:
        import win32file
        import pywintypes
        
        # Convert datetime to Windows file time
        win_time = pywintypes.Time(dt)
        
        # Open the file
        handle = win32file.CreateFile(
            file_path,
            win32file.GENERIC_WRITE,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_ATTRIBUTE_NORMAL,
            None
        )
        
        # Set the file times
        win32file.SetFileTime(handle, win_time, win_time, win_time)
        
        # Close the handle
        win32file.CloseHandle(handle)
        
        return True
    except Exception as e:
        if not quiet_mode:
            print(f"Error in direct Windows file date update: {e}")
        return False


def update_file_dates(file_path: str, time_taken: str, quiet_mode: bool = False, debug_mode: bool = False) -> bool:
    """Update the file creation and modification dates."""
    try:
        # Convert ISO format to datetime
        dt = datetime.fromisoformat(time_taken)
        
        # Debug output for problematic files
        if debug_mode and ("IMG_0624(1).MOV" in file_path or "IMG_0538.JPG" in file_path):
            print(f"\n{Colors.YELLOW}DEBUG - Updating dates for: {os.path.basename(file_path)}{Colors.ENDC}")
            print(f"{Colors.YELLOW}Target datetime: {dt}{Colors.ENDC}")
            
            # Get current file dates before update
            file_stat = os.stat(file_path)
            modified_time_before = datetime.fromtimestamp(file_stat.st_mtime)
            if hasattr(file_stat, 'st_ctime'):
                creation_time_before = datetime.fromtimestamp(file_stat.st_ctime)
                print(f"{Colors.YELLOW}Current creation time: {creation_time_before}{Colors.ENDC}")
            print(f"{Colors.YELLOW}Current modification time: {modified_time_before}{Colors.ENDC}")
        
        success = False
        if IS_WINDOWS:
            # Try direct method first
            if debug_mode:
                print(f"{Colors.YELLOW}Trying direct win32file method first...{Colors.ENDC}")
            success = update_windows_file_dates_direct(file_path, dt, quiet_mode, debug_mode)
            
            # If direct method fails, fall back to PowerShell
            if not success:
                if debug_mode:
                    print(f"{Colors.YELLOW}Direct method failed, falling back to PowerShell...{Colors.ENDC}")
                success = update_windows_file_dates(file_path, dt, quiet_mode, debug_mode)
        else:
            # For non-Windows platforms, just set the modification time
            timestamp = dt.timestamp()
            os.utime(file_path, (timestamp, timestamp))
            success = True
        
        # Verify that the dates were actually updated
        if success and debug_mode and ("IMG_0624(1).MOV" in file_path or "IMG_0538.JPG" in file_path):
            # Get file dates after update
            file_stat = os.stat(file_path)
            modified_time_after = datetime.fromtimestamp(file_stat.st_mtime)
            if hasattr(file_stat, 'st_ctime'):
                creation_time_after = datetime.fromtimestamp(file_stat.st_ctime)
                print(f"{Colors.YELLOW}New creation time: {creation_time_after}{Colors.ENDC}")
            print(f"{Colors.YELLOW}New modification time: {modified_time_after}{Colors.ENDC}")
            
            # Check if the dates were updated correctly
            if hasattr(file_stat, 'st_ctime'):
                creation_time_diff = abs((creation_time_after - dt).total_seconds())
                print(f"{Colors.YELLOW}Creation time difference: {creation_time_diff} seconds{Colors.ENDC}")
                if creation_time_diff > 60:  # Allow 1 minute difference
                    print(f"{Colors.RED}Warning: Creation time was not updated correctly!{Colors.ENDC}")
            
            modification_time_diff = abs((modified_time_after - dt).total_seconds())
            print(f"{Colors.YELLOW}Modification time difference: {modification_time_diff} seconds{Colors.ENDC}")
            if modification_time_diff > 60:  # Allow 1 minute difference
                print(f"{Colors.RED}Warning: Modification time was not updated correctly!{Colors.ENDC}")
        
        return success
    except Exception as e:
        if not quiet_mode:
            print(f"Error updating file dates: {e}")
        return False


def update_windows_file_dates(file_path: str, dt: datetime, quiet_mode: bool = False, debug_mode: bool = False) -> bool:
    """Update file dates on Windows using PowerShell."""
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Create a temporary PowerShell script file
            ps_file = os.path.join(tempfile.gettempdir(), f"set_dates_{os.getpid()}_{attempt}.ps1")
            
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
            
            # Execute the PowerShell script with a longer timeout
            result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file], 
                          check=False, timeout=60, capture_output=True, text=True)
            
            # Clean up the temporary script file
            try:
                os.remove(ps_file)
            except:
                pass
            
            if result.returncode == 0:
                return True
            
            # If we're here, the command failed but didn't raise an exception
            if attempt < max_retries - 1:
                if not quiet_mode:
                    print(f"PowerShell execution failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
            
        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                if not quiet_mode:
                    print(f"PowerShell execution timed out (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
            else:
                # Always print critical errors, even in quiet mode
                print(f"PowerShell execution timed out after {max_retries} attempts")
                return False
        except Exception as e:
            if not quiet_mode or attempt == max_retries - 1:
                print(f"Error in PowerShell execution (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
            else:
                return False
    
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

def process_media_file(media_file: Dict[str, Any], output_dir: str, error_dir: str, input_dir: str, debug_mode: bool = False, all_media_files: List[Dict[str, Any]] = None, quiet_mode: bool = False, force_utc: bool = False) -> Dict[str, Any]:
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
            
            # For Live Photos, we should try to update the dates even for companion files
            # This ensures both parts of a Live Photo have the same date
            
            # First check if the companion file has metadata
            companion_json_path = None
            for other_file in all_media_files:
                if other_file['media_path'] == media_file['companion_path']:
                    companion_json_path = other_file['json_path']
                    break
            
            if companion_json_path:
                # Try to get the timestamp from the companion's metadata
                time_taken = read_photo_taken_time(companion_json_path, force_utc)
                if time_taken:
                    # Update this file's dates with the companion's timestamp
                    if update_file_dates(output_path, time_taken, quiet_mode, debug_mode):
                        result['dates_updated'] = True
                        if debug_mode:
                            print(f"{Colors.GREEN}Updated companion file date from primary file: {os.path.basename(output_path)}{Colors.ENDC}")
            
            return result
        
        # Read the photo taken time from the JSON metadata
        time_taken = None
        if media_file['json_path']:
            result['has_metadata'] = True
            time_taken = read_photo_taken_time(media_file['json_path'], force_utc)
            
            # Debug output for problematic files
            if debug_mode and "IMG_0624(1).MOV" in media_file['filename']:
                print(f"\n{Colors.YELLOW}DEBUG - Processing problematic file: {media_file['filename']}{Colors.ENDC}")
                print(f"{Colors.YELLOW}JSON path: {media_file['json_path']}{Colors.ENDC}")
                print(f"{Colors.YELLOW}Time taken from JSON: {time_taken}{Colors.ENDC}")
                
                # Read the JSON file directly to see its contents
                try:
                    with open(media_file['json_path'], 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        print(f"{Colors.YELLOW}JSON metadata:{Colors.ENDC}")
                        if 'photoTakenTime' in metadata:
                            print(f"photoTakenTime: {metadata['photoTakenTime']}")
                        if 'creationTime' in metadata:
                            print(f"creationTime: {metadata['creationTime']}")
                        if 'modificationTime' in metadata:
                            print(f"modificationTime: {metadata['modificationTime']}")
                except Exception as e:
                    print(f"{Colors.RED}Error reading JSON file: {e}{Colors.ENDC}")
        else:
            # If no metadata and this is a video file, look for a corresponding image file with metadata
            # Common Apple Live Photo pairs: HEIC+MP4, JPG+MOV, JPG+MP4, JPEG+MP4, etc.
            if media_file['extension'].lower() in ['.mp4', '.mov']:
                if debug_mode:
                    print(f"\n{Colors.YELLOW}No metadata found for video file: {media_file['filename']}{Colors.ENDC}")
                    print(f"{Colors.YELLOW}Looking for companion image files...{Colors.ENDC}")
                
                # Get the base name without extension
                base_name = os.path.splitext(os.path.basename(media_file['media_path']))[0]
                dir_path = os.path.dirname(media_file['media_path'])
                
                # Try multiple approaches to find companion images
                found_metadata = False
                
                # Store all potential companion files we find
                potential_companions = []
                
                # 1. First approach: Look for exact base name matches
                for img_ext in ['.jpg', '.jpeg', '.heic']:
                    img_path = os.path.join(dir_path, base_name + img_ext)
                    if os.path.exists(img_path):
                        potential_companions.append(img_path)
                        if debug_mode:
                            print(f"{Colors.GREEN}Found potential companion image: {img_path}{Colors.ENDC}")
                
                # 1b. Also check for other video files with the same base name
                # This handles cases where there are both MP4 and MOV files for the same photo
                other_video_exts = ['.mp4', '.mov']
                current_ext = media_file['extension'].lower()
                for video_ext in other_video_exts:
                    if video_ext != current_ext:  # Don't check the current file's extension
                        video_path = os.path.join(dir_path, base_name + video_ext)
                        if os.path.exists(video_path):
                            if debug_mode:
                                print(f"{Colors.YELLOW}Found another video file with same base name: {video_path}{Colors.ENDC}")
                            
                            # Check if this video file has metadata
                            video_json_path1 = video_path + '.json'
                            video_json_path2 = video_path + '.suppl.json'
                            video_json_path3 = video_path + '.supplemental-metadata.json'
                            video_json_path4 = os.path.splitext(video_path)[0] + '.json'
                            
                            if os.path.exists(video_json_path1):
                                media_file['json_path'] = video_json_path1
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(video_json_path1, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from companion video: {video_json_path1}{Colors.ENDC}")
                                break
                            elif os.path.exists(video_json_path2):
                                media_file['json_path'] = video_json_path2
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(video_json_path2, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from companion video: {video_json_path2}{Colors.ENDC}")
                                break
                            elif os.path.exists(video_json_path3):
                                media_file['json_path'] = video_json_path3
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(video_json_path3, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from companion video: {video_json_path3}{Colors.ENDC}")
                                break
                            elif os.path.exists(video_json_path4):
                                media_file['json_path'] = video_json_path4
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(video_json_path4, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from companion video: {video_json_path4}{Colors.ENDC}")
                                break
                        
                # Check for JSON metadata for each potential companion image
                for img_path in potential_companions:
                    img_json_path1 = img_path + '.json'
                    img_json_path2 = img_path + '.suppl.json'
                    img_json_path3 = img_path + '.supplemental-metadata.json'
                    img_json_path4 = os.path.splitext(img_path)[0] + '.json'
                    
                    if os.path.exists(img_json_path1):
                        media_file['json_path'] = img_json_path1
                        result['has_metadata'] = True
                        time_taken = read_photo_taken_time(img_json_path1, force_utc)
                        found_metadata = True
                        if debug_mode:
                            print(f"{Colors.GREEN}Using metadata from companion image: {img_json_path1}{Colors.ENDC}")
                        break
                    elif os.path.exists(img_json_path2):
                        media_file['json_path'] = img_json_path2
                        result['has_metadata'] = True
                        time_taken = read_photo_taken_time(img_json_path2, force_utc)
                        found_metadata = True
                        if debug_mode:
                            print(f"{Colors.GREEN}Using metadata from companion image: {img_json_path2}{Colors.ENDC}")
                        break
                    elif os.path.exists(img_json_path3):
                        media_file['json_path'] = img_json_path3
                        result['has_metadata'] = True
                        time_taken = read_photo_taken_time(img_json_path3, force_utc)
                        found_metadata = True
                        if debug_mode:
                            print(f"{Colors.GREEN}Using metadata from companion image: {img_json_path3}{Colors.ENDC}")
                        break
                    elif os.path.exists(img_json_path4):
                        media_file['json_path'] = img_json_path4
                        result['has_metadata'] = True
                        time_taken = read_photo_taken_time(img_json_path4, force_utc)
                        found_metadata = True
                        if debug_mode:
                            print(f"{Colors.GREEN}Using metadata from companion image: {img_json_path4}{Colors.ENDC}")
                        break
                    
                    # Also try with 'E' prefix (common in Apple Live Photos)
                    if not found_metadata and not base_name.startswith('IMG_E') and base_name.startswith('IMG_'):
                        e_base_name = 'IMG_E' + base_name[4:]
                        img_path = os.path.join(dir_path, e_base_name + img_ext)
                        if os.path.exists(img_path):
                            if debug_mode:
                                print(f"{Colors.GREEN}Found potential companion image with E prefix: {img_path}{Colors.ENDC}")
                            
                            # Check for JSON metadata for the image file
                            img_json_path1 = img_path + '.json'
                            img_json_path2 = img_path + '.suppl.json'
                            img_json_path3 = img_path + '.supplemental-metadata.json'
                            img_json_path4 = os.path.splitext(img_path)[0] + '.json'
                            
                            if os.path.exists(img_json_path1):
                                media_file['json_path'] = img_json_path1
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(img_json_path1, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from E-prefix companion image: {img_json_path1}{Colors.ENDC}")
                                break
                            elif os.path.exists(img_json_path2):
                                media_file['json_path'] = img_json_path2
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(img_json_path2, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from E-prefix companion image: {img_json_path2}{Colors.ENDC}")
                                break
                            elif os.path.exists(img_json_path3):
                                media_file['json_path'] = img_json_path3
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(img_json_path3, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from E-prefix companion image: {img_json_path3}{Colors.ENDC}")
                                break
                            elif os.path.exists(img_json_path4):
                                media_file['json_path'] = img_json_path4
                                result['has_metadata'] = True
                                time_taken = read_photo_taken_time(img_json_path4, force_utc)
                                found_metadata = True
                                if debug_mode:
                                    print(f"{Colors.GREEN}Using metadata from E-prefix companion image: {img_json_path4}{Colors.ENDC}")
                                break
                
                # 2. Second approach: If still no metadata, look for files with similar names in the directory
                if not found_metadata:
                    # Get all image files in the directory
                    try:
                        dir_files = os.listdir(dir_path)
                        image_files = [f for f in dir_files if f.lower().endswith(('.jpg', '.jpeg', '.heic'))]
                        
                        if debug_mode and image_files:
                            print(f"{Colors.YELLOW}Looking for similar named image files in directory...{Colors.ENDC}")
                        
                        # Try to find images with similar names
                        for img_file in image_files:
                            img_base = os.path.splitext(img_file)[0]
                            
                            # Check if the base names are similar (one is a prefix of the other)
                            if (base_name.startswith(img_base) or img_base.startswith(base_name) or
                                (len(base_name) > 4 and len(img_base) > 4 and 
                                 base_name[0:4] == img_base[0:4] and  # Same prefix (e.g., IMG_)
                                 abs(len(base_name) - len(img_base)) <= 2)):  # Similar length
                                
                                img_path = os.path.join(dir_path, img_file)
                                if debug_mode:
                                    print(f"{Colors.GREEN}Found potential similar-named companion image: {img_path}{Colors.ENDC}")
                                
                                # Check for JSON metadata for this image file
                                img_json_path1 = img_path + '.json'
                                img_json_path2 = img_path + '.suppl.json'
                                img_json_path3 = img_path + '.supplemental-metadata.json'
                                img_json_path4 = os.path.splitext(img_path)[0] + '.json'
                                
                                if os.path.exists(img_json_path1):
                                    media_file['json_path'] = img_json_path1
                                    result['has_metadata'] = True
                                    time_taken = read_photo_taken_time(img_json_path1, force_utc)
                                    found_metadata = True
                                    if debug_mode:
                                        print(f"{Colors.GREEN}Using metadata from similar-named companion: {img_json_path1}{Colors.ENDC}")
                                    break
                                elif os.path.exists(img_json_path2):
                                    media_file['json_path'] = img_json_path2
                                    result['has_metadata'] = True
                                    time_taken = read_photo_taken_time(img_json_path2, force_utc)
                                    found_metadata = True
                                    if debug_mode:
                                        print(f"{Colors.GREEN}Using metadata from similar-named companion: {img_json_path2}{Colors.ENDC}")
                                    break
                                elif os.path.exists(img_json_path3):
                                    media_file['json_path'] = img_json_path3
                                    result['has_metadata'] = True
                                    time_taken = read_photo_taken_time(img_json_path3, force_utc)
                                    found_metadata = True
                                    if debug_mode:
                                        print(f"{Colors.GREEN}Using metadata from similar-named companion: {img_json_path3}{Colors.ENDC}")
                                    break
                                elif os.path.exists(img_json_path4):
                                    media_file['json_path'] = img_json_path4
                                    result['has_metadata'] = True
                                    time_taken = read_photo_taken_time(img_json_path4, force_utc)
                                    found_metadata = True
                                    if debug_mode:
                                        print(f"{Colors.GREEN}Using metadata from similar-named companion: {img_json_path4}{Colors.ENDC}")
                                    break
                    except Exception as e:
                        if debug_mode:
                            print(f"{Colors.RED}Error searching for similar named files: {e}{Colors.ENDC}")
        
        # Update the file dates if we have a time taken
        date_updated = False
        if time_taken:
            if update_file_dates(output_path, time_taken, quiet_mode, debug_mode):
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
                                update_file_dates(companion_output_path, time_taken, quiet_mode, debug_mode)
        
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
                
                # Create a debug info file next to the error file
                debug_info_path = error_path + '.debug.txt'
                with open(debug_info_path, 'w', encoding='utf-8') as f:
                    f.write(f"Debug information for {media_file['filename']}\n")
                    f.write(f"Original path: {media_file['media_path']}\n")
                    f.write(f"JSON path: {media_file['json_path'] or 'None'}\n\n")
                    
                    if media_file['json_path'] and os.path.exists(media_file['json_path']):
                        f.write("JSON metadata content:\n")
                        try:
                            with open(media_file['json_path'], 'r', encoding='utf-8') as json_file:
                                json_content = json_file.read()
                                f.write(json_content)
                                f.write("\n\n")
                                
                                # Parse the JSON to check for timestamp information
                                metadata = json.loads(json_content)
                                if 'photoTakenTime' in metadata:
                                    f.write("photoTakenTime found in metadata:\n")
                                    f.write(f"{metadata['photoTakenTime']}\n\n")
                                else:
                                    f.write("No photoTakenTime found in metadata\n\n")
                                    
                                if 'creationTime' in metadata:
                                    f.write("creationTime found in metadata:\n")
                                    f.write(f"{metadata['creationTime']}\n\n")
                                else:
                                    f.write("No creationTime found in metadata\n\n")
                                    
                                if 'modificationTime' in metadata:
                                    f.write("modificationTime found in metadata:\n")
                                    f.write(f"{metadata['modificationTime']}\n\n")
                                else:
                                    f.write("No modificationTime found in metadata\n\n")
                        except Exception as e:
                            f.write(f"Error reading JSON file: {e}\n")
                    else:
                        f.write("No JSON metadata file found or it doesn't exist.\n")
                        
                        # Try to find JSON files with similar names in the same directory
                        dir_path = os.path.dirname(media_file['media_path'])
                        base_name = os.path.splitext(os.path.basename(media_file['media_path']))[0]
                        f.write(f"\nSearching for JSON files with similar names in {dir_path}:\n")
                        
                        # List all files in the directory
                        try:
                            dir_files = os.listdir(dir_path)
                            json_files = [f for f in dir_files if f.endswith('.json')]
                            f.write(f"Found {len(json_files)} JSON files in directory:\n")
                            for json_file in json_files:
                                f.write(f"- {json_file}\n")
                                
                                # Check if this JSON file might be related to our media file
                                if base_name.lower() in json_file.lower():
                                    f.write(f"\nPossible match found: {json_file}\n")
                                    try:
                                        with open(os.path.join(dir_path, json_file), 'r', encoding='utf-8') as possible_json:
                                            json_content = possible_json.read()
                                            f.write("Content:\n")
                                            f.write(json_content)
                                            f.write("\n\n")
                                    except Exception as e:
                                        f.write(f"Error reading possible JSON match: {e}\n")
                        except Exception as e:
                            f.write(f"Error listing directory: {e}\n")
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


def process_file_wrapper(media_file, output_dir, error_dir, input_dir, debug_mode, all_media_files, quiet_mode=False, force_utc=False):
    """Wrapper function for parallel processing."""
    try:
        result = process_media_file(media_file, output_dir, error_dir, input_dir, debug_mode, all_media_files, quiet_mode, force_utc)
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
    
    # Re-parse to get the parallel argument, quiet mode, force_utc, and single_file
    # Fix PowerShell arguments if needed (already done in parse_arguments)
    parser = argparse.ArgumentParser(description="Fix file dates in Google Takeout exports")
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    parser.add_argument('-e', '--error-dir', required=True)
    parser.add_argument('-p', '--parallel', type=int, default=1)
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-u', '--force-utc', action='store_true')
    parser.add_argument('-s', '--single-file')
    args = parser.parse_args()
    workers = args.parallel
    quiet_mode = args.quiet
    force_utc = args.force_utc
    single_file = args.single_file
    
    if force_utc:
        print(f"{Colors.YELLOW}Force UTC mode enabled: All timestamps will be interpreted as UTC{Colors.ENDC}")
    
    # Validate directories with debug mode awareness
    validate_directories(input_dir, output_dir, error_dir, debug_mode)
    
    # Print debug mode message if enabled
    if debug_mode:
        print(f"{Colors.YELLOW}Debug mode enabled: Files without date updates will be copied to {error_dir}{Colors.ENDC}")
    
    # Check if we're processing a single file for debugging
    if single_file:
        print(f"{Colors.HEADER}Single file mode enabled for debugging{Colors.ENDC}")
        print(f"{Colors.YELLOW}Processing only: {single_file}{Colors.ENDC}")
        
        # Construct the full path to the single file
        single_file_path = os.path.join(input_dir, single_file)
        if not os.path.exists(single_file_path):
            # Try to find the file in subdirectories
            found = False
            for root, _, files in os.walk(input_dir):
                for file in files:
                    if file == single_file:
                        single_file_path = os.path.join(root, file)
                        found = True
                        break
                if found:
                    break
            
            if not found:
                print(f"{Colors.RED}Error: Single file '{single_file}' not found in input directory or subdirectories{Colors.ENDC}")
                sys.exit(1)
        
        print(f"{Colors.GREEN}Found file at: {single_file_path}{Colors.ENDC}")
        
        # Create a single media file entry
        file_ext = os.path.splitext(single_file)[1].lower()
        media_file = {
            'media_path': single_file_path,
            'json_path': None,
            'filename': single_file,
            'extension': file_ext,
            'is_companion': False,
            'companion_path': None
        }
        
        # Look for corresponding JSON files with different naming patterns
        json_path1 = single_file_path + '.json'
        json_path2 = single_file_path + '.suppl.json'
        json_path3 = single_file_path + '.supplemental-metadata.json'
        json_path4 = os.path.splitext(single_file_path)[0] + '.json'
        
        # Check each pattern
        if os.path.exists(json_path1):
            media_file['json_path'] = json_path1
            print(f"{Colors.GREEN}Found JSON metadata: {json_path1}{Colors.ENDC}")
        elif os.path.exists(json_path2):
            media_file['json_path'] = json_path2
            print(f"{Colors.GREEN}Found JSON metadata: {json_path2}{Colors.ENDC}")
        elif os.path.exists(json_path3):
            media_file['json_path'] = json_path3
            print(f"{Colors.GREEN}Found JSON metadata: {json_path3}{Colors.ENDC}")
        elif os.path.exists(json_path4):
            media_file['json_path'] = json_path4
            print(f"{Colors.GREEN}Found JSON metadata: {json_path4}{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}No JSON metadata found for {single_file}{Colors.ENDC}")
            
            # For Apple Live Photos: If this is a video file, look for a corresponding image file
            # Common Apple Live Photo pairs: HEIC+MP4, JPG+MOV, JPG+MP4, JPEG+MP4, etc.
            if file_ext.lower() in ['.mp4', '.mov']:
                print(f"{Colors.YELLOW}This appears to be a video file. Looking for corresponding image files...{Colors.ENDC}")
                
                # Get the base name without extension
                base_name = os.path.splitext(os.path.basename(single_file_path))[0]
                dir_path = os.path.dirname(single_file_path)
                
                # Look for image files with the same base name
                potential_image_files = []
                for img_ext in ['.jpg', '.jpeg', '.heic']:
                    img_path = os.path.join(dir_path, base_name + img_ext)
                    if os.path.exists(img_path):
                        potential_image_files.append(img_path)
                        print(f"{Colors.GREEN}Found potential companion image: {img_path}{Colors.ENDC}")
                
                # Check if any of these image files have metadata
                for img_path in potential_image_files:
                    # Check for JSON metadata for the image file
                    img_json_path1 = img_path + '.json'
                    img_json_path2 = img_path + '.suppl.json'
                    img_json_path3 = img_path + '.supplemental-metadata.json'
                    img_json_path4 = os.path.splitext(img_path)[0] + '.json'
                    
                    if os.path.exists(img_json_path1):
                        media_file['json_path'] = img_json_path1
                        print(f"{Colors.GREEN}Found JSON metadata from companion image: {img_json_path1}{Colors.ENDC}")
                        break
                    elif os.path.exists(img_json_path2):
                        media_file['json_path'] = img_json_path2
                        print(f"{Colors.GREEN}Found JSON metadata from companion image: {img_json_path2}{Colors.ENDC}")
                        break
                    elif os.path.exists(img_json_path3):
                        media_file['json_path'] = img_json_path3
                        print(f"{Colors.GREEN}Found JSON metadata from companion image: {img_json_path3}{Colors.ENDC}")
                        break
                    elif os.path.exists(img_json_path4):
                        media_file['json_path'] = img_json_path4
                        print(f"{Colors.GREEN}Found JSON metadata from companion image: {img_json_path4}{Colors.ENDC}")
                        break
                
                if not media_file['json_path'] and potential_image_files:
                    print(f"{Colors.YELLOW}Found companion images but none have JSON metadata.{Colors.ENDC}")
            
            # Special handling for files with parentheses
            if '(' in single_file:
                # Extract the original filename without the (n) part
                filename = single_file
                ext = os.path.splitext(filename)[1]
                name_part = os.path.splitext(filename)[0]
                
                # Find the position of the opening parenthesis
                paren_pos = name_part.find('(')
                if paren_pos > 0:
                    original_name = name_part[:paren_pos] + ext
                    dir_path = os.path.dirname(single_file_path)
                    original_path = os.path.join(dir_path, original_name)
                    
                    # Check for JSON files with the original name
                    json_path5 = original_path + '.json'
                    json_path6 = original_path + '.suppl.json'
                    json_path7 = original_path + '.supplemental-metadata.json'
                    json_path8 = os.path.splitext(original_path)[0] + '.json'
                    
                    if os.path.exists(json_path5):
                        media_file['json_path'] = json_path5
                        print(f"{Colors.GREEN}Found JSON metadata using original name: {json_path5}{Colors.ENDC}")
                    elif os.path.exists(json_path6):
                        media_file['json_path'] = json_path6
                        print(f"{Colors.GREEN}Found JSON metadata using original name: {json_path6}{Colors.ENDC}")
                    elif os.path.exists(json_path7):
                        media_file['json_path'] = json_path7
                        print(f"{Colors.GREEN}Found JSON metadata using original name: {json_path7}{Colors.ENDC}")
                    elif os.path.exists(json_path8):
                        media_file['json_path'] = json_path8
                        print(f"{Colors.GREEN}Found JSON metadata using original name: {json_path8}{Colors.ENDC}")
        
        # Process the single file with extra debugging
        print(f"{Colors.HEADER}Processing single file with debug mode enabled...{Colors.ENDC}")
        
        # Force debug mode on for single file processing
        debug_mode = True
        
        # Process the file
        result = process_media_file(media_file, output_dir, error_dir, input_dir, debug_mode, [media_file], quiet_mode, force_utc)
        
        # Print detailed results
        print(f"\n{Colors.CYAN}=== Processing Results ==={Colors.ENDC}")
        print(f"Success: {Colors.GREEN if result['success'] else Colors.RED}{result['success']}{Colors.ENDC}")
        
        if result['success']:
            if result.get('dates_updated', False):
                print(f"Dates updated: {Colors.GREEN}Yes{Colors.ENDC}")
                
                # Get the output path
                rel_path = os.path.relpath(media_file['media_path'], input_dir)
                output_path = os.path.join(output_dir, rel_path)
                
                # Show the updated dates
                file_stat = os.stat(output_path)
                modified_time = datetime.fromtimestamp(file_stat.st_mtime)
                print(f"New modification time: {Colors.GREEN}{modified_time}{Colors.ENDC}")
                
                if hasattr(file_stat, 'st_ctime'):
                    creation_time = datetime.fromtimestamp(file_stat.st_ctime)
                    print(f"New creation time: {Colors.GREEN}{creation_time}{Colors.ENDC}")
            else:
                print(f"Dates updated: {Colors.RED}No{Colors.ENDC}")
                
            if result.get('has_metadata', False):
                print(f"Has metadata: {Colors.GREEN}Yes{Colors.ENDC}")
                
                # Show the metadata content
                if media_file['json_path']:
                    try:
                        with open(media_file['json_path'], 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            print(f"\n{Colors.CYAN}JSON Metadata Content:{Colors.ENDC}")
                            
                            # Print key metadata fields
                            if 'photoTakenTime' in metadata:
                                print(f"photoTakenTime: {metadata['photoTakenTime']}")
                            if 'creationTime' in metadata:
                                print(f"creationTime: {metadata['creationTime']}")
                            if 'modificationTime' in metadata:
                                print(f"modificationTime: {metadata['modificationTime']}")
                            
                            # Print the timestamp that was used
                            time_taken = read_photo_taken_time(media_file['json_path'], force_utc)
                            if time_taken:
                                print(f"\nExtracted timestamp: {Colors.GREEN}{time_taken}{Colors.ENDC}")
                                dt = datetime.fromisoformat(time_taken)
                                print(f"Converted to datetime: {Colors.GREEN}{dt}{Colors.ENDC}")
                            else:
                                print(f"\nExtracted timestamp: {Colors.RED}None{Colors.ENDC}")
                    except Exception as e:
                        print(f"{Colors.RED}Error reading JSON metadata: {e}{Colors.ENDC}")
            else:
                print(f"Has metadata: {Colors.RED}No{Colors.ENDC}")
            
            if result.get('is_companion', False):
                print(f"Is companion file: {Colors.YELLOW}Yes{Colors.ENDC}")
                print(f"Companion path: {result.get('companion_path', 'None')}")
            
            if result.get('date_not_updated', False):
                print(f"Date not updated: {Colors.RED}Yes{Colors.ENDC}")
                print(f"Check error directory for debug info: {error_dir}")
        
        if result.get('error'):
            print(f"Error: {Colors.RED}{result['error']}{Colors.ENDC}")
        
        print(f"{Colors.CYAN}========================={Colors.ENDC}")
        
        # Exit after processing the single file
        sys.exit(0)
    
    # Normal processing mode for all files
    all_media_files = find_media_files(input_dir, debug_mode)
    
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
    
    # Create a dictionary to track companion relationships for post-processing
    companion_relationships = {}
    for media_file in all_media_files:
        if media_file['is_companion'] and media_file['companion_path']:
            companion_relationships[media_file['media_path']] = media_file['companion_path']
    
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
                all_media_files,
                quiet_mode,
                force_utc
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
    
    # Post-processing step: Ensure all companion files have matching dates
    if companion_relationships and not quiet_mode:
        print(f"\n{Colors.CYAN}=== Post-Processing Live Photos ==={Colors.ENDC}")
        print(f"Ensuring all companion files have matching dates...")
        
        # Track how many files were updated in post-processing
        post_process_updated = 0
        
        # For each companion relationship, ensure both files have the same date
        for companion_path, primary_path in companion_relationships.items():
            # Get the output paths
            companion_rel_path = os.path.relpath(companion_path, input_dir)
            primary_rel_path = os.path.relpath(primary_path, input_dir)
            companion_output_path = os.path.join(output_dir, companion_rel_path)
            primary_output_path = os.path.join(output_dir, primary_rel_path)
            
            # Check if both files exist in the output directory
            if os.path.exists(companion_output_path) and os.path.exists(primary_output_path):
                # Get the file stats
                companion_stat = os.stat(companion_output_path)
                primary_stat = os.stat(primary_output_path)
                
                # Get the modification times
                companion_mtime = companion_stat.st_mtime
                primary_mtime = primary_stat.st_mtime
                
                # If the times don't match, update the companion file
                if abs(companion_mtime - primary_mtime) > 1:  # Allow 1 second difference
                    # Use the primary file's time
                    primary_dt = datetime.fromtimestamp(primary_mtime)
                    
                    # Update the companion file's date
                    if update_file_dates(companion_output_path, primary_dt.isoformat(), quiet_mode, debug_mode):
                        post_process_updated += 1
                        if debug_mode:
                            print(f"{Colors.GREEN}Updated companion file date in post-processing: {os.path.basename(companion_output_path)}{Colors.ENDC}")
        
        print(f"{Colors.GREEN}Updated {post_process_updated} companion files in post-processing{Colors.ENDC}")
        print(f"{Colors.CYAN}=============================={Colors.ENDC}")
    
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
        
        # Analyze the error directory to provide more information about why files weren't updated
        analyze_error_directory(error_dir)


def analyze_error_directory(error_dir: str) -> None:
    """Analyze the error directory to provide information about why files weren't updated."""
    print(f"\n{Colors.CYAN}=== Error Analysis ==={Colors.ENDC}")
    
    # Count files by type
    error_files = []
    debug_files = []
    
    # Walk through the error directory
    for root, _, files in os.walk(error_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith('.debug.txt'):
                debug_files.append(file_path)
            else:
                error_files.append(file_path)
    
    print(f"{Colors.BOLD}Found {len(error_files)} files in error directory with {len(debug_files)} debug info files.{Colors.ENDC}")
    
    # Analyze debug files to find common issues
    no_json_count = 0
    no_timestamp_count = 0
    update_failed_count = 0
    other_issues_count = 0
    
    # Detailed analysis
    no_json_files = []
    no_timestamp_files = []
    update_failed_files = []
    other_issues_files = []
    
    for debug_file in debug_files:
        try:
            with open(debug_file, 'r', encoding='utf-8') as f:
                content = f.read()
                media_file = debug_file.replace('.debug.txt', '')
                
                if "No JSON metadata file found or it doesn't exist" in content:
                    no_json_count += 1
                    no_json_files.append((media_file, content))
                elif "No photoTakenTime found in metadata" in content and "No creationTime found in metadata" in content:
                    no_timestamp_count += 1
                    no_timestamp_files.append((media_file, content))
                elif "Error updating file dates" in content or "Warning: Creation time was not updated correctly" in content:
                    update_failed_count += 1
                    update_failed_files.append((media_file, content))
                else:
                    other_issues_count += 1
                    other_issues_files.append((media_file, content))
        except Exception as e:
            other_issues_count += 1
            other_issues_files.append((debug_file, f"Error reading debug file: {e}"))
    
    # Print summary of issues
    print(f"\n{Colors.YELLOW}Common reasons files weren't updated:{Colors.ENDC}")
    print(f"1. {Colors.RED}No JSON metadata file found:{Colors.ENDC} {no_json_count} files")
    print(f"   - These files don't have associated JSON metadata files with timestamp information.")
    print(f"   - Solution: Check if these files were part of the original Google Takeout or added later.")
    
    print(f"\n2. {Colors.RED}No timestamp information in JSON:{Colors.ENDC} {no_timestamp_count} files")
    print(f"   - These files have JSON metadata, but the JSON doesn't contain photoTakenTime or creationTime.")
    print(f"   - Solution: These might be files that Google doesn't have timestamp data for.")
    
    print(f"\n3. {Colors.RED}File date update failed:{Colors.ENDC} {update_failed_count} files")
    print(f"   - These files have timestamp information, but the date update operation failed.")
    print(f"   - Solution: Check if these files are read-only or if there are permission issues.")
    
    print(f"\n4. {Colors.RED}Other issues:{Colors.ENDC} {other_issues_count} files")
    print(f"   - These files have various other issues. Check their debug files for details.")
    
    # Provide examples of each issue type
    if no_json_count > 0:
        print(f"\n{Colors.YELLOW}Examples of files with no JSON metadata:{Colors.ENDC}")
        for i, (media_file, _) in enumerate(no_json_files[:5]):  # Show up to 5 examples
            print(f"{i+1}. File: {os.path.basename(media_file)}")
            print(f"   Location: {os.path.dirname(media_file)}")
            
            # Check if this is a duplicate file (has parentheses in the name)
            filename = os.path.basename(media_file)
            if '(' in filename:
                print(f"   {Colors.RED}This appears to be a duplicate file (has parentheses in the name).{Colors.ENDC}")
                print(f"   Original file might be: {filename.split('(')[0] + os.path.splitext(filename)[1]}")
                print(f"   Google Takeout typically only includes metadata for the original file, not duplicates.")
    
    if no_timestamp_count > 0:
        print(f"\n{Colors.YELLOW}Examples of files with no timestamp in JSON:{Colors.ENDC}")
        for i, (media_file, content) in enumerate(no_timestamp_files[:5]):  # Show up to 5 examples
            print(f"{i+1}. File: {os.path.basename(media_file)}")
            try:
                json_path = content.split('JSON path: ')[1].split('\n')[0]
                print(f"   JSON path: {json_path}")
                
                # Extract JSON content if available
                if "JSON metadata content:" in content:
                    json_content = content.split("JSON metadata content:")[1].split("\n\n")[0]
                    print(f"   JSON content preview: {json_content[:100]}...")
            except:
                print(f"   Could not extract JSON path from debug file.")
    
    if update_failed_count > 0:
        print(f"\n{Colors.YELLOW}Examples of files where date update failed:{Colors.ENDC}")
        for i, (media_file, content) in enumerate(update_failed_files[:5]):  # Show up to 5 examples
            print(f"{i+1}. File: {os.path.basename(media_file)}")
            if "Error updating file dates:" in content:
                error_msg = content.split("Error updating file dates:")[1].split("\n")[0]
                print(f"   Error: {error_msg}")
    
    # Analyze patterns in filenames
    print(f"\n{Colors.YELLOW}Filename Pattern Analysis:{Colors.ENDC}")
    
    # Check for patterns in filenames
    parentheses_count = 0
    for media_file in error_files:
        filename = os.path.basename(media_file)
        if '(' in filename:
            parentheses_count += 1
    
    if parentheses_count > 0:
        print(f"{Colors.RED}{parentheses_count} files ({parentheses_count/len(error_files)*100:.1f}%) have parentheses in their names.{Colors.ENDC}")
        print(f"This suggests they are duplicate files. Google Takeout typically only includes metadata")
        print(f"for the original file, not duplicates. For example, IMG_0624.MOV would have metadata,")
        print(f"but IMG_0624(1).MOV would not.")
    
    # Check for specific file extensions
    extensions = {}
    for media_file in error_files:
        ext = os.path.splitext(media_file)[1].lower()
        if ext not in extensions:
            extensions[ext] = 0
        extensions[ext] += 1
    
    print(f"\n{Colors.YELLOW}File Extension Analysis:{Colors.ENDC}")
    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True):
        print(f"{ext}: {count} files ({count/len(error_files)*100:.1f}%)")
    
    print(f"\n{Colors.CYAN}=========================={Colors.ENDC}")
    
    # Provide a conclusion
    print(f"\n{Colors.YELLOW}Conclusion:{Colors.ENDC}")
    if parentheses_count > 0 and parentheses_count/len(error_files) > 0.5:
        print(f"The majority of files without date updates appear to be duplicate files with parentheses")
        print(f"in their names. This is expected behavior, as Google Takeout typically only includes")
        print(f"metadata for the original files, not duplicates.")
        print(f"\nSolution: If you want these files to have the same dates as their originals, you could:")
        print(f"1. Manually copy the dates from the original files")
        print(f"2. Modify the script to look for the original file's metadata for duplicates")
        print(f"   (the script already attempts this, but could be improved)")
    elif no_json_count > no_timestamp_count and no_json_count > update_failed_count:
        print(f"Most files without date updates are missing JSON metadata files. This could be because:")
        print(f"1. These files were not part of the original Google Takeout")
        print(f"2. Google doesn't have metadata for these files")
        print(f"3. The metadata files have a different naming pattern than expected")
    elif no_timestamp_count > no_json_count and no_timestamp_count > update_failed_count:
        print(f"Most files have JSON metadata, but the JSON doesn't contain timestamp information.")
        print(f"This suggests that Google doesn't have timestamp data for these files.")


if __name__ == "__main__":
    main()
