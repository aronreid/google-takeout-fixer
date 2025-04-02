"""
Module for finding the companion JSON file for a media file.
"""
import os
import re
from typing import Optional


def get_companion_json_path_for_media_file(media_file_path: str) -> Optional[str]:
    """
    Find the companion JSON file for a media file.
    """
    directory_path = os.path.dirname(media_file_path)
    media_file_extension = os.path.splitext(media_file_path)[1]
    media_file_name_without_extension = os.path.splitext(os.path.basename(media_file_path))[0]

    # Sometimes (if the photo has been edited inside Google Photos) we get files with a `-edited` suffix
    # These images don't have their own .json sidecars - for these we'd want to use the JSON sidecar for the original image
    # so we can ignore the "-edited" suffix if there is one
    media_file_name_without_extension = re.sub(r'[-]edited$', '', media_file_name_without_extension, flags=re.IGNORECASE)

    # The naming pattern for the JSON sidecar files provided by Google Takeout seem to be inconsistent. For `foo.jpg`,
    # the JSON file is sometimes `foo.json` but sometimes it's `foo.jpg.json`. Here we start building up a list of potential
    # JSON filenames so that we can try to find them later
    potential_json_file_names = [
        f"{media_file_name_without_extension}.json",
        f"{media_file_name_without_extension}{media_file_extension}.json",
    ]

    # Another edge case which seems to be quite inconsistent occurs when we have media files containing a number suffix for example "foo(1).jpg"
    # In this case, we don't get "foo(1).json" nor "foo(1).jpg.json". Instead, we strangely get "foo.jpg(1).json".
    # We can use a regex to look for this edge case and add that to the potential JSON filenames to look out for
    name_with_counter_match = re.search(r'(?P<name>.*)(?P<counter>\(\d+\))$', media_file_name_without_extension)
    if name_with_counter_match:
        name = name_with_counter_match.group('name')
        counter = name_with_counter_match.group('counter')
        potential_json_file_names.append(f"{name}{media_file_extension}{counter}.json")

    # Sometimes the media filename ends with extra dash (eg. filename_n-.jpg + filename_n.json)
    ends_with_extra_dash = media_file_name_without_extension.endswith('_n-')

    # Sometimes the media filename ends with extra `n` char (eg. filename_n.jpg + filename_.json)
    ends_with_extra_n_char = media_file_name_without_extension.endswith('_n')

    # And sometimes the media filename has extra underscore in it (e.g. filename_.jpg + filename.json)
    ends_with_extra_underscore = media_file_name_without_extension.endswith('_')

    if ends_with_extra_dash or ends_with_extra_n_char or ends_with_extra_underscore:
        # We need to remove that extra char at the end
        potential_json_file_names.append(f"{media_file_name_without_extension[:-1]}.json")

    # Now look to see if we have a JSON file in the same directory as the image for any of the potential JSON file names
    # that we identified earlier
    for potential_json_file_name in potential_json_file_names:
        json_file_path = os.path.join(directory_path, potential_json_file_name)
        if os.path.exists(json_file_path):
            return json_file_path

    # If no JSON file was found, just return None - we won't be able to adjust the date timestamps without finding a
    # suitable JSON sidecar file
    return None
