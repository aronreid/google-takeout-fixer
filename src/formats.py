"""
File format configurations for the Google Photos EXIF tool.
This file serves as a single source of truth for all file format related configurations.
"""

# List of all supported media file types
SUPPORTED_MEDIA_FILE_TYPES = [
    # Standard image formats
    {'extension': '.jpeg', 'supports_exif': True},
    {'extension': '.jpg', 'supports_exif': True},
    {'extension': '.heic', 'supports_exif': True},
    {'extension': '.gif', 'supports_exif': True},
    {'extension': '.png', 'supports_exif': True},
    
    # Video formats
    {'extension': '.mp4', 'supports_exif': True},
    {'extension': '.avi', 'supports_exif': True},
    {'extension': '.mov', 'supports_exif': True},
    {'extension': '.mkv', 'supports_exif': True},
    
    # RAW image formats
    {'extension': '.nef', 'supports_exif': True},  # Nikon
    {'extension': '.dng', 'supports_exif': True},  # Digital Negative
    {'extension': '.raw', 'supports_exif': True},  # General RAW
    {'extension': '.cr2', 'supports_exif': True},  # Canon Raw 2
    {'extension': '.cr3', 'supports_exif': True},  # Canon Raw 3
    {'extension': '.arw', 'supports_exif': True},  # Sony
    {'extension': '.orf', 'supports_exif': True},  # Olympus
    {'extension': '.rw2', 'supports_exif': True},  # Panasonic
    {'extension': '.pef', 'supports_exif': True},  # Pentax
    {'extension': '.raf', 'supports_exif': True},  # Fujifilm
]

# List of file extensions that are known to work with piexif library
PIEXIF_COMPATIBLE_EXTENSIONS = ['.jpeg', '.jpg', '.tiff', '.tif', '.heic']

# Helper function to get all supported extensions as a list
def get_all_supported_extensions():
    """
    Returns a list of all supported file extensions.
    """
    return [file_type['extension'] for file_type in SUPPORTED_MEDIA_FILE_TYPES]

# Helper function to check if a file extension supports EXIF
def extension_supports_exif(extension):
    """
    Check if a file extension supports EXIF metadata.
    """
    extension = extension.lower()
    for file_type in SUPPORTED_MEDIA_FILE_TYPES:
        if file_type['extension'].lower() == extension:
            return file_type['supports_exif']
    return False

# Helper function to check if a file extension is compatible with piexif
def is_piexif_compatible(extension):
    """
    Check if a file extension is compatible with the piexif library.
    """
    return extension.lower() in PIEXIF_COMPATIBLE_EXTENSIONS
