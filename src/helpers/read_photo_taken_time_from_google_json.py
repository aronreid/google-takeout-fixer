"""
Module for reading the photo taken time from a Google JSON file.
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional


def read_photo_taken_time_from_google_json(media_file: Dict[str, Any]) -> Optional[str]:
    """
    Read the photo taken time from a Google JSON file.
    """
    if not media_file['json_file_path'] or not media_file['json_file_exists']:
        return None

    try:
        with open(media_file['json_file_path'], 'r', encoding='utf-8') as json_file:
            google_json_metadata = json.load(json_file)

        if 'photoTakenTime' in google_json_metadata and 'timestamp' in google_json_metadata['photoTakenTime']:
            photo_taken_timestamp = int(google_json_metadata['photoTakenTime']['timestamp'])
            photo_taken_date = datetime.fromtimestamp(photo_taken_timestamp)
            return photo_taken_date.isoformat()
        else:
            return None
    except Exception:
        # If there's an error reading the JSON file, return None
        return None
