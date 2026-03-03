# Syntegrity

A fast file integrity checker written in Go. Computes cryptographic hashes for files and folders to detect content and structural changes. Uses a Merkle tree for folder hashing and concurrent goroutines for speed.

## What it does

Syntegrity scans directories recursively and computes:
- Individual file hashes (SHA-256)
- Folder content hashes (hash1) - Merkle tree of all children's hashes
- Folder structure hashes (hash2) - based on immediate children names and sizes

This lets you detect both content changes and structural modifications in your file system.

## Features

- **Fast** - Concurrent hashing with goroutines, ~6x faster than equivalent Python
- **Smart caching** - JSON-based cache with mtime+size validation, ~25x faster on repeat runs
- **Dual hash system** - Separate hashes for content vs structure integrity
- **Change detection** - Tracks file/folder additions, deletions, modifications between runs
- **Single binary** - No runtime dependencies, just build and run

## Quick start

```bash
go build -o syntegrity .
./syntegrity /path/to/directory
```

Supports multiple paths and individual files:

```bash
./syntegrity /etc/config /var/log /path/to/file.txt
```

## Output format

```
Processing files:
/home/data/file1: 32c66107f0f4f2053128e519681fc8e88806d0d2b17607ce9f2362aff66ad6c7
/home/data/file2: 85df9a7c92f2e8c562629361ed51d54efb76e0f12ffd2a588f25f93a29d2a43e

Processing folders:
data:[content_hash];[structure_hash]
subfolder:[content_hash];[structure_hash]

Hierarchical Structure:
[root_hash[file_hash/file_hash/subfolder_hash[child_hash]]]

Change Detection:
  • MODIFIED_FILE: file1
  • NEW_FILE: file3
```

For folders, the format is: `foldername:[hash1];[hash2]`

- **hash1** = content integrity (Merkle tree of all children)
- **hash2** = structure integrity (immediate children names and sizes)

## How it works

### Hash1 (Content Hash)
Merkle tree computed bottom-up: each folder's hash is the SHA-256 of its sorted children entries (`type:name:hash`). Any change in a descendant propagates up to the root.

### Hash2 (Structure Hash)
SHA-256 of immediate children names and sizes (for files) or names (for directories). Detects structural changes like renames, additions, or deletions without false positives from timestamp changes.

### Change Detection

Syntegrity saves state between runs and reports:

- Deleted, modified, and new files
- Deleted and new folders
- Folder content and structure changes

## Use cases

- Detect unauthorized file modifications

- Monitor system configuration changes
- Verify backup integrity
- Ensure build artifacts haven't changed

## Troubleshooting

### Cache issues

Clear the cache to force full recomputation:
```bash
rm .syntegrity_cache.json
```

### Permission errors

Permission errors are logged to stderr. The tool continues processing accessible files.

## Technical details

- **Hash algorithm**: SHA-256
- **Folder hashing**: O(n) Merkle tree (bottom-up)
- **Concurrency**: goroutine pool, up to `min(NumCPU, 16)` workers
- **Cache**: `.syntegrity_cache.json` with mtime+size validation
- **State**: `<dir>_state.json` for change detection between runs

## Requirements

- Go 1.21+
- Standard library only (no external dependencies)
