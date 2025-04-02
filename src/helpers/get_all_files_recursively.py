"""
Module for recursively finding all files in a directory.
"""
import os
from typing import List


def get_all_files_recursively(directory: str) -> List[str]:
    """
    Get all files in a directory and its subdirectories.
    """
    all_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files
