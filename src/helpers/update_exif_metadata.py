"""
Module for updating EXIF metadata.
"""
import os
import shutil
import piexif
from datetime import datetime
from typing import Dict, Any

from .does_file_support_exif import does_file_support_exif
from ..formats import is_piexif_compatible


def update_exif_metadata(file_info: Dict[str, Any], time_taken: str, error_dir: str) -> None:
    """
    Update the EXIF metadata of a file.
    
    For JPEG, TIFF, and HEIC files, uses piexif library.
    For RAW formats, falls back to updating file modification date only.
    """
    if not does_file_support_exif(file_info['output_file_path']):
        return

    try:
        # Convert ISO format to EXIF format (YYYY:MM:DD HH:MM:SS)
        dt = datetime.fromisoformat(time_taken)
        exif_date = dt.strftime("%Y:%m:%d %H:%M:%S")

        # Check if the file extension is compatible with piexif
        file_extension = os.path.splitext(file_info['output_file_path'])[1]
        
        if is_piexif_compatible(file_extension):
            # Use piexif for compatible formats
            try:
                exif_dict = piexif.load(file_info['output_file_path'])
            except Exception:
                # If there's an error loading the EXIF data, create a new EXIF dictionary
                exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}

            # Update the DateTimeOriginal tag (when the photo was taken)
            exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date.encode('utf-8')
            
            # Update the DateTimeDigitized tag (when the photo was created/digitized)
            exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date.encode('utf-8')
            
            # Update the DateTime tag (general modification date)
            exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_date.encode('utf-8')

            # Save the updated EXIF data
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, file_info['output_file_path'])
        else:
            # For RAW formats and other formats not supported by piexif,
            # we'll rely on the file modification date update that happens elsewhere
            # This is handled by update_file_modification_date function
            pass

    except Exception as e:
        # Create the error directory with the same relative path
        error_dir_with_relative_path = os.path.join(error_dir, file_info['relative_path'])
        os.makedirs(error_dir_with_relative_path, exist_ok=True)
        
        # Copy the file to the error directory, preserving the folder structure
        shutil.copy2(file_info['output_file_path'], os.path.join(error_dir_with_relative_path, file_info['output_file_name']))
        
        # Also copy the JSON file if it exists
        if file_info['json_file_exists'] and file_info['json_file_name'] and file_info['json_file_path']:
            shutil.copy2(file_info['json_file_path'], os.path.join(error_dir_with_relative_path, file_info['json_file_name']))
