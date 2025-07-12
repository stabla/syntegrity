# Syntegrity 

Project is currently under development.

A fast Python tool that computes cryptographic hashes for files and folders to check system integrity. It generates two different hashes for each folder - one for content and one for structure.

## What it does

Syntegrity scans directories recursively and computes:
- Individual file hashes (SHA-256)
- Folder content hashes (hash1) - combines all file and subfolder hashes
- Folder structure hashes (hash2) - based on folder metadata and organization

This lets you detect both content changes and structural modifications in your file system.

## Features

- **Fast processing** - Uses parallel processing and memory mapping for large files
- **Smart caching** - Saves computed hashes to avoid re-processing unchanged files
- **Dual hash system** - Separate hashes for content vs structure integrity
- **Recursive scanning** - Processes entire directory trees automatically
- **Error handling** - Gracefully handles permission errors and missing files

## Quick start

```bash
# Run the analyzer
python3 analyzer.py
```

## Output format

The tool outputs file hashes and folder hashes in this format:

```
Processing files:
/home/test-syntegrity/file1: 32c66107f0f4f2053128e519681fc8e88806d0d2b17607ce9f2362aff66ad6c7
/home/test-syntegrity/file2: 85df9a7c92f2e8c562629361ed51d54efb76e0f12ffd2a588f25f93a29d2a43e

Processing folders:
test-syntegrity:[content_hash];[structure_hash]
folder1:[content_hash];[structure_hash]
```

For folders, the format is: `foldername:[hash1];[hash2]`

- **hash1** = content integrity (all files and subfolders)
- **hash2** = structure integrity (folder metadata and organization)

## How it works

### Hash1 (Content Hash)
Computes a hash of all file hashes within the folder, recursively. This detects when any file content changes.

### Hash2 (Structure Hash)  
Computes a hash of the folder's immediate structure - file names, sizes, subfolder names, and modification times. This detects structural changes like renames, moves, or permission changes.

### Performance optimizations
- Uses multiprocessing to utilize all CPU cores
- Memory maps large files (>1MB) for faster reading
- Caches results to avoid re-computing unchanged files
- Single-pass directory discovery reduces I/O operations

## Configuration

Edit the directories list in `main()`:

```python
directories_to_process = [
    "/home/test-syntegrity",
    "/etc/config", 
    "/var/log"
]
```

## Use cases

### System monitoring
```bash
# Create baseline
python3 analyzer.py > baseline.txt

# Later check for changes
python3 analyzer.py > current.txt
diff baseline.txt current.txt
```

### File integrity checking
- Detect unauthorized file modifications
- Monitor system configuration changes  
- Verify backup integrity
- Ensure build artifacts haven't changed

## Troubleshooting

### Empty hash collisions
If you see the same hash for different files/folders, clear the cache:
```bash
rm .hash_cache.pkl
```

### Permission errors
The script handles permission errors gracefully and logs them to stderr. Check the error output for details.

### Performance tuning
Adjust the worker count based on your system:
```python
max_workers = min(cpu_count(), 8)  # Default max 8 workers
```

## Technical details

- **Time complexity**: O(n) where n = number of files
- **Space complexity**: O(p) where p = number of parallel workers
- **Hash algorithm**: SHA-256
- **Cache location**: `.hash_cache.pkl`

The script adapts its approach based on file size:
- Small files (<1MB): Chunked reading
- Large files (1-10MB): Memory mapping
- Very large files (>10MB): Chunked memory mapping

## Requirements

- Python 3.7+
- Linux/Unix system (for optimal performance)
- Standard library modules only (no external dependencies)

## License

MIT License - see LICENSE file for details.