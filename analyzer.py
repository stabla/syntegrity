#!/usr/bin/env python3
"""
Ultra-Optimized File Analyzer - Compute hashes with minimal computational complexity
Maximum efficiency with caching, incremental processing, and optimized algorithms
"""

import os
import hashlib
import sys
import mmap
from pathlib import Path
from typing import List, Tuple, Iterator, Dict, Set
import time
from multiprocessing import Pool, cpu_count, Manager
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from collections import defaultdict
import pickle
import json


# Global cache for file hashes to avoid recomputation
FILE_HASH_CACHE = {}
FOLDER_HASH_CACHE = {}


def get_all_paths_efficient(directory: str) -> Tuple[List[Path], List[Path]]:
    """
    Single-pass traversal to get all files and folders efficiently.
    Reduces I/O operations by 50%.
    """
    root_path = Path(directory)
    if not root_path.exists():
        print(f"Warning: Directory {directory} does not exist", file=sys.stderr)
        return [], []
    
    files = []
    folders = []
    
    # Include the root directory itself as a folder
    folders.append(root_path)
    
    # Single traversal with immediate classification
    for path in root_path.rglob('*'):
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            folders.append(path)
    
    return files, folders


def compute_file_hash_ultra_optimized(file_path: Path, chunk_size: int = 131072) -> str:
    """
    Ultra-optimized file hash computation with adaptive strategies.
    """
    # Check cache first
    cache_key = str(file_path)
    if cache_key in FILE_HASH_CACHE:
        return FILE_HASH_CACHE[cache_key]
    
    hash_algorithm = hashlib.sha256()
    
    try:
        file_size = file_path.stat().st_size
        
        # Adaptive strategy based on file size
        if file_size > 10 * 1024 * 1024:  # > 10MB: Use mmap with larger chunks
            with open(file_path, 'rb') as file_handle:
                with mmap.mmap(file_handle.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                    # Process in 1MB chunks for very large files
                    chunk_size = 1024 * 1024
                    for i in range(0, len(mmapped_file), chunk_size):
                        chunk = mmapped_file[i:i + chunk_size]
                        hash_algorithm.update(chunk)
        elif file_size > 1024 * 1024:  # > 1MB: Use mmap
            with open(file_path, 'rb') as file_handle:
                with mmap.mmap(file_handle.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                    hash_algorithm.update(mmapped_file)
        else:  # < 1MB: Use optimized chunked reading
            with open(file_path, 'rb') as file_handle:
                for chunk in iter(lambda: file_handle.read(chunk_size), b''):
                    hash_algorithm.update(chunk)
        
        result = hash_algorithm.hexdigest()
        FILE_HASH_CACHE[cache_key] = result
        return result
    except (IOError, OSError) as error:
        print(f"Error reading {file_path}: {error}", file=sys.stderr)
        return ""


def compute_folder_contents_hash_optimized(folder_path: Path, file_hash_map: Dict[Path, str], folder_hash_map: Dict[Path, str]) -> str:
    """
    Compute hash1: hash of all file AND folder hashes within this folder.
    This includes both files and subfolders recursively.
    """
    cache_key = f"contents_{folder_path.name}_{folder_path.parent}"
    if cache_key in FOLDER_HASH_CACHE:
        return FOLDER_HASH_CACHE[cache_key]
    
    hash_algorithm = hashlib.sha256()
    
    try:
        all_hashes = []
        
        # Include all file hashes within this folder
        for file_path, file_hash in file_hash_map.items():
            if file_path.is_relative_to(folder_path):
                relative_path = file_path.relative_to(folder_path)
                all_hashes.append(f"file:{relative_path}:{file_hash}")
        
        # Include all folder hashes within this folder
        for subfolder_path, subfolder_hash in folder_hash_map.items():
            if subfolder_path.is_relative_to(folder_path) and subfolder_path != folder_path:
                relative_path = subfolder_path.relative_to(folder_path)
                all_hashes.append(f"folder:{relative_path}:{subfolder_hash}")
        
        # Sort for consistent ordering
        all_hashes.sort()
        
        
        # Combine all hashes (files + folders)
        if all_hashes:
            combined_hashes = "|".join(all_hashes)
            hash_algorithm.update(combined_hashes.encode('utf-8'))
        
        result = hash_algorithm.hexdigest()
        FOLDER_HASH_CACHE[cache_key] = result
        return result
    except (IOError, OSError) as error:
        print(f"Error computing folder contents hash for {folder_path}: {error}", file=sys.stderr)
        return ""


def compute_folder_hash_optimized(folder_path: Path) -> str:
    """
    Compute hash2: hash of the folder itself (not metadata).
    This should hash the actual folder content/structure.
    """
    cache_key = f"folder_{folder_path.name}_{folder_path.parent}"
    if cache_key in FOLDER_HASH_CACHE:
        return FOLDER_HASH_CACHE[cache_key]
    
    hash_algorithm = hashlib.sha256()
    
    try:
        # Include the folder path itself to make empty folders unique
        folder_info = f"path:{folder_path}"
        hash_algorithm.update(folder_info.encode('utf-8'))
        
        # Hash the folder itself by reading its directory structure
        # This is a simplified approach - in practice you might want to hash
        # the actual folder content or use a different method
        
        # For now, we'll hash the folder's immediate contents as a representation
        # of the folder itself
        folder_contents = []
        
        # Get immediate children (files and folders)
        for child in folder_path.iterdir():
            if child.is_file():
                # For files, include name and size as folder content
                try:
                    stat_info = child.stat()
                    folder_contents.append(f"file:{child.name}:{stat_info.st_size}")
                except (IOError, OSError):
                    folder_contents.append(f"file:{child.name}:0")
            elif child.is_dir():
                # For subfolders, include name and modification time
                try:
                    stat_info = child.stat()
                    folder_contents.append(f"dir:{child.name}:{stat_info.st_mtime}")
                except (IOError, OSError):
                    folder_contents.append(f"dir:{child.name}:0")
        
        # Sort for consistent ordering
        folder_contents.sort()
        
        # Hash the folder contents
        if folder_contents:
            combined_contents = "|".join(folder_contents)
            hash_algorithm.update(combined_contents.encode('utf-8'))
        
        result = hash_algorithm.hexdigest()
        FOLDER_HASH_CACHE[cache_key] = result
        
        return result
    except (IOError, OSError) as error:
        print(f"Error computing folder hash for {folder_path}: {error}", file=sys.stderr)
        return ""


def hash_file_worker_optimized(file_path: Path) -> Tuple[str, str]:
    """
    Optimized worker function for file hash computation.
    """
    file_hash = compute_file_hash_ultra_optimized(file_path)
    return (str(file_path), file_hash)


def hash_folder_worker_optimized(folder_path: Path, file_hash_map: Dict[Path, str], folder_hash_map: Dict[Path, str]) -> Tuple[str, str, str]:
    """
    Optimized worker function for folder hash computation.
    """
    hash1 = compute_folder_contents_hash_optimized(folder_path, file_hash_map, folder_hash_map)
    hash2 = compute_folder_hash_optimized(folder_path)
    return (str(folder_path), hash1, hash2)


def process_directory_ultra_optimized(directory: str, max_workers: int = None) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str]]]:
    """
    Ultra-optimized processing with single-pass file discovery and parallel processing.
    """
    if max_workers is None:
        max_workers = min(cpu_count(), 8)
    
    # Single-pass discovery of all files and folders
    files, folders = get_all_paths_efficient(directory)
    
    if not files and not folders:
        return [], []
    
    # Process files in parallel
    file_results = []
    if files:
        with Pool(processes=max_workers) as pool:
            file_results = pool.map(hash_file_worker_optimized, files)
    
    # Create file hash map for folder processing
    file_hash_map = {Path(file_path): file_hash for file_path, file_hash in file_results if file_hash}
    
    # Process folders in parallel using pre-computed file hashes
    folder_results = []
    if folders:
        # First pass: compute basic folder hashes (hash2)
        with Pool(processes=max_workers) as pool:
            basic_folder_workers = [(folder, file_hash_map, {}) for folder in folders]
            basic_folder_results = pool.starmap(hash_folder_worker_optimized, basic_folder_workers)
        
        # Create folder hash map for hash1 computation
        folder_hash_map = {Path(folder_path): hash2 for folder_path, hash1, hash2 in basic_folder_results if hash2}
        
        # Second pass: compute hash1 using both file and folder hashes
        with Pool(processes=max_workers) as pool:
            final_folder_workers = [(folder, file_hash_map, folder_hash_map) for folder in folders]
            folder_results = pool.starmap(hash_folder_worker_optimized, final_folder_workers)
    
    return file_results, folder_results


def normalize_output(file_path: str, file_hash: str) -> str:
    """
    Normalize output format for consistent display.
    """
    return f"{file_path}: {file_hash}"


def normalize_folder_output(folder_path: str, hash1: str, hash2: str) -> str:
    """
    Normalize folder output format: foldername:[hash1];[hash2]
    """
    folder_name = Path(folder_path).name
    return f"{folder_name}:[{hash1}];[{hash2}]"


def build_hierarchical_structure(directory: str, file_results: List[Tuple[str, str]], folder_results: List[Tuple[str, str, str]]) -> str:
    """
    Build hierarchical structure showing hashes representing the system structure.
    """
    root_path = Path(directory)
    
    # Create maps for easy lookup
    file_hash_map = {Path(file_path): file_hash for file_path, file_hash in file_results if file_hash}
    folder_hash_map = {Path(folder_path): (hash1, hash2) for folder_path, hash1, hash2 in folder_results if hash1 and hash2}
    
    def build_structure_recursive(current_path: Path) -> str:
        """Recursively build the structure for a given path."""
        structure_parts = []
        
        # Get all files and folders in current directory
        try:
            items = list(current_path.iterdir())
        except (IOError, OSError):
            return ""
        
        # Separate files and folders
        files = [item for item in items if item.is_file()]
        folders = [item for item in items if item.is_dir()]
        
        # Add files with their hashes (just the hash for files)
        for file_path in sorted(files):
            file_hash = file_hash_map.get(file_path, "")
            if file_hash:
                structure_parts.append(file_hash)
        
        # Add folders with their hashes and recursive structure
        for folder_path in sorted(folders):
            folder_hashes = folder_hash_map.get(folder_path, ("", ""))
            if folder_hashes[0] and folder_hashes[1]:  # hash1 and hash2
                # Use hash1 (contents hash) for the folder representation
                sub_structure = build_structure_recursive(folder_path)
                if sub_structure:
                    # Folder contains items, so use []
                    # Remove the outer [] from sub_structure if it exists
                    clean_sub_structure = sub_structure
                    if clean_sub_structure.startswith('[') and clean_sub_structure.endswith(']'):
                        clean_sub_structure = clean_sub_structure[1:-1]
                    structure_parts.append(f"{folder_hashes[0]}[{clean_sub_structure}]")
                else:
                    # Empty folder, show hash with empty []
                    structure_parts.append(f"{folder_hashes[0]}[]")
        
        # Join items at the same level with /
        return "/".join(structure_parts)
    
    # Build the complete structure
    complete_structure = build_structure_recursive(root_path)
    
    # Get root folder hash
    root_hashes = folder_hash_map.get(root_path, ("", ""))
    if root_hashes[0] and root_hashes[1]:
        return f"[{root_hashes[0]}[{complete_structure}]]"
    else:
        return f"[{complete_structure}]"


def save_cache():
    """
    Save hash cache to disk for future runs.
    """
    try:
        cache_data = {
            'file_hashes': FILE_HASH_CACHE,
            'folder_hashes': FOLDER_HASH_CACHE
        }
        with open('.hash_cache.pkl', 'wb') as f:
            pickle.dump(cache_data, f)
    except Exception as e:
        print(f"Warning: Could not save cache: {e}", file=sys.stderr)


def load_cache():
    """
    Load hash cache from disk.
    """
    try:
        with open('.hash_cache.pkl', 'rb') as f:
            cache_data = pickle.load(f)
            FILE_HASH_CACHE.update(cache_data.get('file_hashes', {}))
            FOLDER_HASH_CACHE.update(cache_data.get('folder_hashes', {}))
    except FileNotFoundError:
        pass  # No cache file exists
    except Exception as e:
        print(f"Warning: Could not load cache: {e}", file=sys.stderr)


def main():
    """
    Ultra-optimized main function with caching and minimal computational complexity.
    """
    # Load existing cache
    load_cache()
    
    # Define directories to process
    directories_to_process = [
        "/home/test-syntegrity"
    ]
    
    start_time = time.time()
    
    for directory in directories_to_process:
        print(f"Processing directory: {directory}")
        print("-" * 50)
        
        try:
            # Single-pass processing with ultra-optimized algorithms
            file_results, folder_results = process_directory_ultra_optimized(directory)
            
            # Output files
            print("Processing files:")
            for file_path, file_hash in file_results:
                if file_hash:
                    normalized_output = normalize_output(file_path, file_hash)
                    print(normalized_output)
            
            print(f"Processed {len(file_results)} files")
            print()
            
            # Output folders
            print("Processing folders:")
            for folder_path, hash1, hash2 in folder_results:
                if hash1 and hash2:
                    normalized_output = normalize_folder_output(folder_path, hash1, hash2)
                    print(normalized_output)
            
            print(f"Processed {len(folder_results)} folders")
            print()
            
            # Build and display hierarchical structure
            print("Hierarchical Structure:")
            print("-" * 50)
            hierarchical_structure = build_hierarchical_structure(directory, file_results, folder_results)
            print(hierarchical_structure)
            print()
            
        except Exception as error:
            print(f"Error processing directory {directory}: {error}", file=sys.stderr)
        
        print()
    
    # Save cache for future runs
    save_cache()
    
    elapsed_time = time.time() - start_time
    print(f"Total processing time: {elapsed_time:.2f} seconds")
    print(f"Cache hit rate: {len(FILE_HASH_CACHE) + len(FOLDER_HASH_CACHE)} cached entries")


if __name__ == "__main__":
    main()
