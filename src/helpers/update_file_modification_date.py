"""
Module for updating file modification date.
"""
import os
from datetime import datetime


def update_file_modification_date(file_path: str, time_taken: str) -> None:
    """
    Update the modification date of a file.
    """
    time = datetime.fromisoformat(time_taken).timestamp()
    
    try:
        # Update the access and modification times of the file
        os.utime(file_path, (time, time))
    except Exception:
        # If there's an error updating the file times, try to create a new file
        # This is a fallback for some file systems that don't support utime
        with open(file_path, 'a'):
            os.utime(file_path, (time, time))
