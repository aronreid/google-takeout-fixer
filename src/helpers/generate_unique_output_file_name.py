"""
Module for generating unique output file names.
"""
import os
from typing import List


def generate_unique_output_file_name(file_path: str, all_used_file_names_lower_cased: List[str]) -> str:
    """
    Given the name of a file that we want to copy to the output directory, generate a unique output filename.
    The function takes in the filename that we wish to copy and an array of all output files so far (all converted to lower case).

    If the filename doesn't already exist in the array, it just returns the original file name.

    If the filename already exists (e.g. its a duplicate), then add a numbered suffix to the end, counting up until
    the resultant filename is unique.

    For example if the array contains `picture.jpg` and `picture_1.jpg` then this will return `picture_2.jpg`
    """
    original_file_name = os.path.basename(file_path)
    original_file_extension = os.path.splitext(file_path)[1]
    original_file_name_without_extension = os.path.splitext(original_file_name)[0]
    counter = 1

    output_file_name = original_file_name
    while output_file_name.lower() in all_used_file_names_lower_cased:
        output_file_name = f"{original_file_name_without_extension}_{counter}{original_file_extension}"
        counter += 1
    return output_file_name
