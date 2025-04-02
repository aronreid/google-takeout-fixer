"""
Module for checking if a file has an EXIF date.
"""
import os
import piexif
from .does_file_support_exif import does_file_support_exif
from ..formats import is_piexif_compatible

def does_file_have_exif_date(file_path: str) -> bool:
    """
    Check if a file has an EXIF date.
    
    For JPEG, TIFF, and HEIC files, uses piexif library.
    For RAW formats, always returns False to ensure we update the date.
    """
    if not does_file_support_exif(file_path):
        return False

    # Check if the file extension is compatible with piexif
    file_extension = os.path.splitext(file_path)[1]
    
    if not is_piexif_compatible(file_extension):
        # For RAW formats and other formats not supported by piexif,
        # return False to ensure we update the file modification date
        return False

    try:
        exif_dict = piexif.load(file_path)
        # Check if the DateTimeOriginal tag (0x9003) exists in the EXIF IFD
        return 'Exif' in exif_dict and piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']
    except Exception:
        # If there's an error reading the EXIF data, assume there's no date
        return False
