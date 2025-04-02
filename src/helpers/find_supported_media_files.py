"""
Module for finding supported media files in a directory.
"""
import os
from typing import Dict, List, Any

from ..formats import get_all_supported_extensions
from .does_file_support_exif import does_file_support_exif
from .get_all_files_recursively import get_all_files_recursively
from .generate_unique_output_file_name import generate_unique_output_file_name
from .get_companion_json_path_for_media_file import get_companion_json_path_for_media_file


def find_supported_media_files(input_dir: str, output_dir: str) -> List[Dict[str, Any]]:
    """
    Find all supported media files in the input directory and prepare their output paths.
    Preserves the folder structure from the input directory.
    """
    supported_media_file_extensions = get_all_supported_extensions()
    media_file_paths = find_files_with_extension_recursively(
        input_dir, supported_media_file_extensions)

    media_files = []
    all_used_output_files_by_dir = {}  # Dictionary to track used filenames per directory

    for media_file_path in media_file_paths:
        media_file_name = os.path.basename(media_file_path)
        media_file_extension = os.path.splitext(media_file_path)[1]
        supports_exif = does_file_support_exif(media_file_path)

        json_file_path = get_companion_json_path_for_media_file(media_file_path)
        json_file_name = os.path.basename(json_file_path) if json_file_path else None
        json_file_exists = os.path.exists(json_file_path) if json_file_path else False

        # Calculate the relative path from the input directory
        relative_path = os.path.relpath(os.path.dirname(media_file_path), input_dir)
        
        # Create the output directory structure if it doesn't exist
        output_dir_with_relative_path = os.path.join(output_dir, relative_path)
        os.makedirs(output_dir_with_relative_path, exist_ok=True)
        
        # Get or initialize the list of used filenames for this directory
        if relative_path not in all_used_output_files_by_dir:
            all_used_output_files_by_dir[relative_path] = []
        used_files_in_dir = all_used_output_files_by_dir[relative_path]
        
        # Generate a unique filename within this directory
        output_file_name = generate_unique_output_file_name(media_file_path, used_files_in_dir)
        output_file_path = os.path.join(output_dir_with_relative_path, output_file_name)

        media_files.append({
            'media_file_path': media_file_path,
            'media_file_name': media_file_name,
            'media_file_extension': media_file_extension,
            'supports_exif': supports_exif,
            'json_file_path': json_file_path,
            'json_file_name': json_file_name,
            'json_file_exists': json_file_exists,
            'relative_path': relative_path,
            'output_file_name': output_file_name,
            'output_file_path': output_file_path,
        })
        used_files_in_dir.append(output_file_name.lower())

    return media_files


def find_files_with_extension_recursively(dir_to_search: str, extensions_to_include: List[str]) -> List[str]:
    """
    Find all files with the specified extensions in the directory and its subdirectories.
    """
    all_files = get_all_files_recursively(dir_to_search)
    dir_is_empty = len(all_files) == 0
    if dir_is_empty:
        raise Exception(
            'The search directory is empty, so there is no work to do. Check that your --input-dir contains all of the Google Takeout data, and that any zips have been extracted before running this tool')

    matching_files = [
        file_path for file_path in all_files
        if os.path.splitext(file_path)[1].lower() in [ext.lower() for ext in extensions_to_include]
    ]
    return matching_files
