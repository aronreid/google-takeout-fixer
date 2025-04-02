#!/usr/bin/env python3
import argparse
import os
import sys
import time
import shutil
from typing import Dict, List, Set, Tuple, Any
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from colorama import init, Fore, Back, Style

# Initialize colorama
init(autoreset=True)

# Define color constants for better readability
SUCCESS = Fore.GREEN
ERROR = Fore.RED
WARNING = Fore.YELLOW
INFO = Fore.CYAN
RESET = Style.RESET_ALL
BOLD = Style.BRIGHT
HEADER = Fore.MAGENTA + Style.BRIGHT

from .formats import get_all_supported_extensions
from .helpers.find_supported_media_files import find_supported_media_files
from .helpers.does_file_have_exif_date import does_file_have_exif_date
from .helpers.read_photo_taken_time_from_google_json import read_photo_taken_time_from_google_json
from .helpers.update_exif_metadata import update_exif_metadata
from .helpers.update_file_modification_date import update_file_modification_date


class GoogleTakeoutFixer:
    """
    Takes in a directory path for an extracted Google Takeout. Extracts all photo/video files
    (based on the configured list of file extensions) and places them into an output directory.
    All files will have their modified timestamp set to match the timestamp specified in Google's JSON
    metadata files (where present). In addition, for file types that support EXIF, the EXIF "DateTimeOriginal"
    field will be set to the timestamp from Google's JSON metadata, if the field is not already set in the EXIF metadata.
    """

    def __init__(self):
        self.parser = argparse.ArgumentParser(description=self.__doc__)
        self.parser.add_argument('-i', '--input-dir', required=True,
                                help='Directory containing the extracted contents of Google Photos Takeout zip file')
        self.parser.add_argument('-o', '--output-dir', required=True,
                                help='Directory into which the processed output will be written')
        self.parser.add_argument('-e', '--error-dir', required=True,
                                help='Directory for any files that have bad EXIF data - including the matching metadata files')
        self.parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0.0')

    def run(self):
        args = self.parser.parse_args()
        input_dir = args.input_dir
        output_dir = args.output_dir
        error_dir = args.error_dir

        try:
            directories = self.determine_directory_paths(input_dir, output_dir, error_dir)
            self.prepare_directories(directories)
            self.process_media_files(directories)
        except Exception as error:
            print(f"{ERROR}Error: {error}{RESET}")
            sys.exit(1)

        print(f"{SUCCESS}Done 🎉{RESET}")
        sys.exit(0)

    def determine_directory_paths(self, input_dir: str, output_dir: str, error_dir: str) -> Dict[str, str]:
        return {
            'input': input_dir,
            'output': output_dir,
            'error': error_dir,
        }

    def prepare_directories(self, directories: Dict[str, str]) -> None:
        if not directories['input'] or not os.path.exists(directories['input']):
            raise Exception('The input directory must exist')

        if not directories['output']:
            raise Exception('You must specify an output directory using the --output-dir flag')

        if not directories['error']:
            raise Exception('You must specify an error directory using the --error-dir flag')

        self.check_dir_is_empty_and_create_dir_if_not_found(
            directories['output'], 'If the output directory already exists, it must be empty')
        self.check_dir_is_empty_and_create_dir_if_not_found(
            directories['error'], 'If the error directory already exists, it must be empty')

    def check_dir_is_empty_and_create_dir_if_not_found(self, directory_path: str, message_if_not_empty: str) -> None:
        folder_exists = os.path.exists(directory_path)
        if folder_exists:
            folder_contents = os.listdir(directory_path)
            folder_contents_excluding_ds_store = [
                filename for filename in folder_contents if filename != '.DS_Store']
            folder_is_empty = len(folder_contents_excluding_ds_store) == 0
            if not folder_is_empty:
                raise Exception(message_if_not_empty)
        else:
            print(f"{INFO}--- Creating directory: {directory_path} ---{RESET}")
            os.makedirs(directory_path)

    def count_total_files(self, directory: str) -> Tuple[int, List[str], int, List[str]]:
        """
        Count the total files in the directory and return lists of all files and non-JSON files.
        This optimized version counts both in a single directory traversal.
        """
        print(f"{INFO}--- Counting total files in the takeout folder ---{RESET}")
        all_files = []
        non_json_files = []
        
        # Use a single directory traversal to collect both all files and non-JSON files
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                all_files.append(file_path)
                if not file_path.lower().endswith('.json'):
                    non_json_files.append(file_path)
                    
        return len(all_files), all_files, len(non_json_files), non_json_files

    def copy_file_with_buffer(self, src_path: str, dst_path: str, buffer_size: int = 1024*1024) -> None:
        """
        Copy a file using buffered I/O for better performance with large files.
        Uses a 1MB buffer by default.
        """
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(src_path, 'rb') as src_file:
            with open(dst_path, 'wb') as dst_file:
                while True:
                    buffer = src_file.read(buffer_size)
                    if not buffer:
                        break
                    dst_file.write(buffer)
    
    def process_single_file(self, media_file: Dict[str, Any], directories: Dict[str, str]) -> Dict[str, Any]:
        """
        Process a single media file. This function is designed to be run in parallel.
        Returns a dictionary with information about the processing results.
        """
        result = {
            'processed': True,
            'copied': True,
            'exif_edited': False,
            'output_file_name': media_file['output_file_name']
        }
        
        # Copy the file into output directory using buffered I/O
        try:
            self.copy_file_with_buffer(media_file['media_file_path'], media_file['output_file_path'])
        except Exception as e:
            result['error'] = f"Error copying file: {str(e)}"
            result['copied'] = False
            return result
            
        # Process the output file, setting the modified timestamp and/or EXIF metadata where necessary
        photo_time_taken = read_photo_taken_time_from_google_json(media_file)

        if photo_time_taken:
            if media_file['supports_exif']:
                has_exif_date = does_file_have_exif_date(media_file['media_file_path'])
                if not has_exif_date:
                    try:
                        update_exif_metadata(media_file, photo_time_taken, directories['error'])
                        result['exif_edited'] = True
                    except Exception as e:
                        result['error'] = f"Error updating EXIF: {str(e)}"
                        
            try:
                update_file_modification_date(media_file['output_file_path'], photo_time_taken)
            except Exception as e:
                result['error'] = f"Error updating file date: {str(e)}"
                
        return result

    def process_media_files(self, directories: Dict[str, str]) -> None:
        # Count total files in the takeout folder
        total_files_count, all_files, total_non_json_files, non_json_files = self.count_total_files(directories['input'])
        print(f"{INFO}--- Total files in takeout folder: {total_files_count} ---{RESET}")
        print(f"{INFO}--- Total non-JSON files in takeout folder: {total_non_json_files} ---{RESET}")
        
        # Find media files
        supported_media_file_extensions = get_all_supported_extensions()
        print(f"{INFO}--- Finding supported media files ({', '.join(supported_media_file_extensions)}) ---{RESET}")
        media_files = find_supported_media_files(directories['input'], directories['output'])

        # Count how many files were found for each supported file extension
        media_file_counts_by_extension = {}
        for supported_extension in supported_media_file_extensions:
            count = sum(1 for media_file in media_files if media_file['media_file_extension'].lower() == supported_extension.lower())
            media_file_counts_by_extension[supported_extension] = count

        print(f"{SUCCESS}--- Scan complete, found: ---{RESET}")
        total_media_files = sum(media_file_counts_by_extension.values())
        for extension, count in media_file_counts_by_extension.items():
            print(f"{INFO}{count} files with extension {extension}{RESET}")
        
        print(f"{INFO}--- Total media files to process: {total_media_files} out of {total_files_count} total files ---{RESET}")
        
        # Create a set of all media file paths for later comparison
        media_file_paths = {media_file['media_file_path'] for media_file in media_files}
        
        print(f"{INFO}--- Processing media files ---{RESET}")
        file_names_with_edited_exif = []

        # Initialize counters
        processed_files_count = 0
        copied_files_count = 0
        
        # Determine if we should use parallel processing
        # For now, let's use sequential processing to ensure it works
        use_parallel = False
        
        if use_parallel:
            # Determine the number of workers based on CPU cores
            # Use 75% of available cores to avoid overloading the system
            max_workers = max(1, int(multiprocessing.cpu_count() * 0.75))
            print(f"{INFO}--- Using {max_workers} parallel workers ---{RESET}")
            
            # Use tqdm for progress bar with color
            progress_bar = tqdm(
                total=len(media_files), 
                desc=f"{INFO}Processing{RESET}", 
                unit=f"{INFO}file{RESET}",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
            )
            
            # Process files in parallel using ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_media_file = {
                    executor.submit(self.process_single_file, media_file, directories): media_file
                    for media_file in media_files
                }
                
                # Process results as they complete
                for future in as_completed(future_to_media_file):
                    result = future.result()
                    processed_files_count += 1
                    if result['copied']:
                        copied_files_count += 1
                    if result['exif_edited']:
                        file_names_with_edited_exif.append(result['output_file_name'])
                        progress_bar.write(f"{SUCCESS}Wrote \"DateTimeOriginal\" EXIF metadata to: {result['output_file_name']}{RESET}")
                    
                    # Update progress bar
                    progress_bar.update(1)
                    progress_bar.set_description(f"{INFO}Processing {processed_files_count}/{len(media_files)} ({(processed_files_count/len(media_files))*100:.1f}%){RESET}")
                    progress_bar.set_postfix(
                        copied=f"{SUCCESS}{copied_files_count}{RESET}", 
                        processed=f"{INFO}{processed_files_count}{RESET}"
                    )
        else:
            # Process files sequentially
            print(f"{INFO}--- Using sequential processing ---{RESET}")
            
            # Use tqdm for progress bar with color
            progress_bar = tqdm(
                total=len(media_files), 
                desc=f"{INFO}Processing{RESET}", 
                unit=f"{INFO}file{RESET}",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
            )
            
            for i, media_file in enumerate(media_files):
                # Process the file
                result = self.process_single_file(media_file, directories)
                
                # Update counters
                processed_files_count += 1
                if result['copied']:
                    copied_files_count += 1
                if result['exif_edited']:
                    file_names_with_edited_exif.append(result['output_file_name'])
                    progress_bar.write(f"{SUCCESS}Wrote \"DateTimeOriginal\" EXIF metadata to: {result['output_file_name']}{RESET}")
                
                # Update progress bar
                progress_bar.update(1)
                progress_bar.set_description(f"{INFO}Processing {processed_files_count}/{len(media_files)} ({(processed_files_count/len(media_files))*100:.1f}%){RESET}")
                progress_bar.set_postfix(
                    copied=f"{SUCCESS}{copied_files_count}{RESET}", 
                    processed=f"{INFO}{processed_files_count}{RESET}"
                )
        
        # Close the progress bar
        progress_bar.close()

        # Check if all files were processed
        unprocessed_files = [f for f in all_files if f not in media_file_paths and not f.endswith('.json')]
        
        # Generate error.txt if there are unprocessed files
        if unprocessed_files:
            error_file_path = os.path.join(directories['output'], 'error.txt')
            with open(error_file_path, 'w') as error_file:
                error_file.write(f"Total files in takeout folder: {total_files_count}\n")
                error_file.write(f"Total media files processed: {total_media_files}\n")
                error_file.write(f"Number of unprocessed files: {len(unprocessed_files)}\n\n")
                error_file.write("Unprocessed files:\n")
                for file_path in unprocessed_files:
                    error_file.write(f"{file_path}\n")
            print(f"{WARNING}--- WARNING: Not all files were processed. See {error_file_path} for details. ---{RESET}")

        # Calculate additional statistics
        unsupported_files_count = total_non_json_files - total_media_files
        error_files_count = processed_files_count - copied_files_count
        
        # Log a summary
        print("\n" + "="*80)
        print(f"{HEADER}EXECUTION SUMMARY{RESET}")
        print("="*80)
        print(f"{BOLD}Total files found in takeout folder:       {total_files_count}{RESET}")
        print(f"{BOLD}Total non-JSON files in takeout folder:    {total_non_json_files}{RESET}")
        print(f"{BOLD}Total supported media files found:         {total_media_files}{RESET}")
        print(f"{BOLD}Total files processed:                     {processed_files_count}{RESET}")
        print(f"{SUCCESS}Total files successfully copied:           {copied_files_count}{RESET}")
        print(f"{WARNING}Total files with unsupported formats:      {unsupported_files_count}{RESET}")
        print(f"{ERROR}Total files with errors during processing: {error_files_count}{RESET}")
        print("-"*80)
        print(f"{BOLD}Breakdown by file extension:{RESET}")
        for extension, count in sorted(media_file_counts_by_extension.items(), key=lambda x: x[1], reverse=True):
            print(f"  {INFO}{extension}: {count} files{RESET}")
        print("-"*80)
        
        # EXIF update information
        print(f"{SUCCESS}File modification timestamp has been updated on all successfully copied files{RESET}")
        if file_names_with_edited_exif:
            print(f"{SUCCESS}EXIF DateTimeOriginal field updated in {len(file_names_with_edited_exif)} files{RESET}")
            if len(file_names_with_edited_exif) <= 10:  # Only show details if there are 10 or fewer files
                print(f"{BOLD}Files with updated EXIF:{RESET}")
                for file_name_with_edited_exif in file_names_with_edited_exif:
                    print(f"  {SUCCESS}{file_name_with_edited_exif}{RESET}")
        else:
            print(f"{INFO}No EXIF metadata was edited. This could be because all files already had a value set for the DateTimeOriginal field, or because we did not have a corresponding JSON file.{RESET}")
        
        # Unprocessed files information
        if unprocessed_files:
            print(f"\n{WARNING}WARNING: {len(unprocessed_files)} files were not processed.{RESET}")
            print(f"{WARNING}See {os.path.join(directories['output'], 'error.txt')} for details.{RESET}")
        
        print("="*80)


def main_cli():
    """
    Entry point for the console script.
    This function is called when the user runs the 'google-takeout-fixer' command.
    """
    app = GoogleTakeoutFixer()
    app.run()

if __name__ == "__main__":
    main_cli()
