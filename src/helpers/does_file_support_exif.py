"""
Module for checking if a file supports EXIF metadata.
"""
import os
from ..formats import extension_supports_exif


def does_file_support_exif(file_path: str) -> bool:
    """
    Check if a file supports EXIF metadata based on its extension.
    """
    extension = os.path.splitext(file_path)[1]
    return extension_supports_exif(extension)
