package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"
)

// Node represents a file or directory in the tree.
type Node struct {
	Path       string
	Name       string
	IsDir      bool
	Size       int64
	ModTime    time.Time
	Children   []*Node
	Hash       string // file: SHA-256 of content; dir: Merkle hash of children (hash1)
	StructHash string // dir only: hash of immediate children names+sizes (hash2)
}

// CacheEntry stores a cached file hash with mtime+size for validation.
type CacheEntry struct {
	Hash    string `json:"hash"`
	Size    int64  `json:"size"`
	ModNano int64  `json:"mod_nano"`
}

// Cache is a thread-safe file hash cache.
type Cache struct {
	Entries map[string]CacheEntry `json:"entries"`
	mu      sync.RWMutex
}

// SavedState stores hashes from the previous run for change detection.
type SavedState struct {
	Files     map[string]string      `json:"files"`
	Folders   map[string][2]string   `json:"folders"`
	Timestamp float64                `json:"timestamp"`
}

const cacheFile = ".syntegrity_cache.json"

func main() {
	paths := os.Args[1:]
	if len(paths) == 0 {
		fmt.Fprintln(os.Stderr, "Usage: syntegrity <path> [path...]")
		os.Exit(1)
	}

	cache := loadCache()
	start := time.Now()

	for _, p := range paths {
		info, err := os.Stat(p)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			continue
		}
		if info.IsDir() {
			processDir(p, cache)
		} else {
			h := hashFile(p, cache)
			if h != "" {
				fmt.Printf("File hash: %s: %s\n", p, h)
			}
		}
		fmt.Println()
	}

	saveCache(cache)
	fmt.Printf("Total processing time: %.2fs\n", time.Since(start).Seconds())
}

// buildTree walks the directory once and builds an in-memory tree.
func buildTree(dir string) (*Node, error) {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return nil, err
	}

	info, err := os.Stat(abs)
	if err != nil {
		return nil, err
	}

	root := &Node{
		Path:    abs,
		Name:    filepath.Base(abs),
		IsDir:   true,
		ModTime: info.ModTime(),
	}

	nodes := map[string]*Node{abs: root}

	err = filepath.WalkDir(abs, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			fmt.Fprintf(os.Stderr, "walk: %s: %v\n", path, err)
			return nil
		}
		if path == abs {
			return nil
		}

		info, err := d.Info()
		if err != nil {
			fmt.Fprintf(os.Stderr, "stat: %s: %v\n", path, err)
			return nil
		}

		n := &Node{
			Path:    path,
			Name:    d.Name(),
			IsDir:   d.IsDir(),
			Size:    info.Size(),
			ModTime: info.ModTime(),
		}

		if parent, ok := nodes[filepath.Dir(path)]; ok {
			parent.Children = append(parent.Children, n)
		}
		if d.IsDir() {
			nodes[path] = n
		}
		return nil
	})

	sortTree(root)
	return root, err
}

func sortTree(n *Node) {
	sort.Slice(n.Children, func(i, j int) bool {
		return n.Children[i].Name < n.Children[j].Name
	})
	for _, c := range n.Children {
		if c.IsDir {
			sortTree(c)
		}
	}
}

// hashAllFiles hashes every file in the tree concurrently.
func hashAllFiles(root *Node, cache *Cache) {
	var files []*Node
	collectFiles(root, &files)

	workers := runtime.NumCPU()
	if workers > 16 {
		workers = 16
	}

	sem := make(chan struct{}, workers)
	var wg sync.WaitGroup

	for _, f := range files {
		wg.Add(1)
		go func(node *Node) {
			sem <- struct{}{}
			defer func() { <-sem; wg.Done() }()
			node.Hash = hashFile(node.Path, cache)
		}(f)
	}
	wg.Wait()
}

func collectFiles(n *Node, out *[]*Node) {
	if !n.IsDir {
		*out = append(*out, n)
		return
	}
	for _, c := range n.Children {
		collectFiles(c, out)
	}
}

// hashFile computes SHA-256 of a file, using cache when mtime+size match.
func hashFile(path string, cache *Cache) string {
	info, err := os.Stat(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "stat: %s: %v\n", path, err)
		return ""
	}

	modNano := info.ModTime().UnixNano()
	size := info.Size()

	cache.mu.RLock()
	if e, ok := cache.Entries[path]; ok && e.Size == size && e.ModNano == modNano {
		cache.mu.RUnlock()
		return e.Hash
	}
	cache.mu.RUnlock()

	f, err := os.Open(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "open: %s: %v\n", path, err)
		return ""
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		fmt.Fprintf(os.Stderr, "read: %s: %v\n", path, err)
		return ""
	}

	hash := hex.EncodeToString(h.Sum(nil))

	cache.mu.Lock()
	cache.Entries[path] = CacheEntry{Hash: hash, Size: size, ModNano: modNano}
	cache.mu.Unlock()

	return hash
}

// computeFolderHashes computes hash1 (content Merkle) and hash2 (structure) bottom-up.
func computeFolderHashes(n *Node) {
	if !n.IsDir {
		return
	}

	for _, c := range n.Children {
		computeFolderHashes(c)
	}

	// hash1: Merkle hash — SHA-256 of sorted "type:name:childHash" entries
	var parts []string
	for _, c := range n.Children {
		if c.IsDir {
			parts = append(parts, "folder:"+c.Name+":"+c.Hash)
		} else {
			parts = append(parts, "file:"+c.Name+":"+c.Hash)
		}
	}
	sort.Strings(parts)

	h1 := sha256.New()
	if len(parts) > 0 {
		h1.Write([]byte(strings.Join(parts, "|")))
	}
	n.Hash = hex.EncodeToString(h1.Sum(nil))

	// hash2: structure hash — names + sizes only (no mtime, avoids false positives)
	var sp []string
	for _, c := range n.Children {
		if c.IsDir {
			sp = append(sp, "dir:"+c.Name)
		} else {
			sp = append(sp, fmt.Sprintf("file:%s:%d", c.Name, c.Size))
		}
	}
	sort.Strings(sp)

	h2 := sha256.New()
	if len(sp) > 0 {
		h2.Write([]byte(strings.Join(sp, "|")))
	}
	n.StructHash = hex.EncodeToString(h2.Sum(nil))
}

// processDir handles a single directory: build tree, hash, print results, detect changes.
func processDir(dir string, cache *Cache) {
	fmt.Printf("Processing directory: %s\n", dir)
	fmt.Println(strings.Repeat("-", 50))

	root, err := buildTree(dir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return
	}

	hashAllFiles(root, cache)
	computeFolderHashes(root)

	// Print file results
	fmt.Println("Processing files:")
	var fileCount int
	walkTree(root, func(n *Node) {
		if !n.IsDir && n.Hash != "" {
			fmt.Printf("%s: %s\n", n.Path, n.Hash)
			fileCount++
		}
	})
	fmt.Printf("Processed %d files\n\n", fileCount)

	// Print folder results
	fmt.Println("Processing folders:")
	var folderCount int
	walkTree(root, func(n *Node) {
		if n.IsDir {
			fmt.Printf("%s:[%s];[%s]\n", n.Name, n.Hash, n.StructHash)
			folderCount++
		}
	})
	fmt.Printf("Processed %d folders\n\n", folderCount)

	// Hierarchical structure
	fmt.Println("Hierarchical Structure:")
	fmt.Println(strings.Repeat("-", 50))
	fmt.Println(hierString(root))
	fmt.Println()

	// Change detection
	absDir, _ := filepath.Abs(dir)
	fileResults, folderResults := collectResults(root, absDir)
	changes := detectChanges(absDir, fileResults, folderResults)

	fmt.Println("Change Detection:")
	fmt.Println(strings.Repeat("-", 50))
	if len(changes) > 0 {
		fmt.Println("Changes detected:")
		for _, c := range changes {
			fmt.Printf("  \u2022 %s\n", c)
		}
	} else {
		fmt.Println("No changes detected since last run.")
	}
	fmt.Println()

	saveState(absDir, fileResults, folderResults)
}

func walkTree(n *Node, fn func(*Node)) {
	fn(n)
	for _, c := range n.Children {
		walkTree(c, fn)
	}
}

// hierString builds the hierarchical bracket notation for the root.
// Root: [hash1[children]]
func hierString(n *Node) string {
	inner := dirContents(n)
	return fmt.Sprintf("[%s[%s]]", n.Hash, inner)
}

// dirContents builds the inner content string for a directory.
// Files: just hash. Dirs: hash[children]. Separated by /.
func dirContents(n *Node) string {
	var parts []string
	for _, c := range n.Children {
		if c.IsDir {
			sub := dirContents(c)
			parts = append(parts, fmt.Sprintf("%s[%s]", c.Hash, sub))
		} else {
			parts = append(parts, c.Hash)
		}
	}
	return strings.Join(parts, "/")
}

// collectResults gathers file and folder hashes with paths relative to baseDir.
func collectResults(root *Node, baseDir string) (map[string]string, map[string][2]string) {
	files := make(map[string]string)
	folders := make(map[string][2]string)

	walkTree(root, func(n *Node) {
		rel, err := filepath.Rel(baseDir, n.Path)
		if err != nil {
			return
		}
		if n.IsDir {
			folders[rel] = [2]string{n.Hash, n.StructHash}
		} else if n.Hash != "" {
			files[rel] = n.Hash
		}
	})
	return files, folders
}

// --- Change Detection ---

func stateFile(dir string) string {
	safe := strings.ReplaceAll(dir, string(os.PathSeparator), "_")
	return safe + "_state.json"
}

func loadState(dir string) (map[string]string, map[string][2]string) {
	f, err := os.Open(stateFile(dir))
	if err != nil {
		return nil, nil
	}
	defer f.Close()

	var s SavedState
	if err := json.NewDecoder(f).Decode(&s); err != nil {
		return nil, nil
	}

	folders := make(map[string][2]string)
	for k, v := range s.Folders {
		folders[k] = v
	}
	return s.Files, folders
}

func saveState(dir string, files map[string]string, folders map[string][2]string) {
	s := SavedState{
		Files:     files,
		Folders:   make(map[string][2]string),
		Timestamp: float64(time.Now().Unix()),
	}
	for k, v := range folders {
		s.Folders[k] = v
	}

	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "save state: %v\n", err)
		return
	}
	if err := os.WriteFile(stateFile(dir), data, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "write state: %v\n", err)
	}
}

func detectChanges(dir string, currentFiles map[string]string, currentFolders map[string][2]string) []string {
	prevFiles, prevFolders := loadState(dir)
	if prevFiles == nil && prevFolders == nil {
		return nil
	}

	type change struct {
		priority int
		msg      string
	}
	var changes []change

	for p := range prevFiles {
		if _, ok := currentFiles[p]; !ok {
			changes = append(changes, change{1, "DELETED_FILE: " + p})
		}
	}
	for p := range prevFolders {
		if _, ok := currentFolders[p]; !ok {
			changes = append(changes, change{2, "DELETED_FOLDER: " + p})
		}
	}
	for p, h := range currentFiles {
		if prev, ok := prevFiles[p]; ok && h != prev {
			changes = append(changes, change{3, "MODIFIED_FILE: " + p})
		}
	}
	for p := range currentFolders {
		if _, ok := prevFolders[p]; !ok {
			changes = append(changes, change{4, "NEW_FOLDER: " + p})
		}
	}
	for p := range currentFiles {
		if _, ok := prevFiles[p]; !ok {
			changes = append(changes, change{5, "NEW_FILE: " + p})
		}
	}
	for p, curr := range currentFolders {
		if prev, ok := prevFolders[p]; ok {
			if curr[0] != prev[0] {
				changes = append(changes, change{6, "FOLDER_CONTENTS_CHANGED: " + p})
			}
			if curr[1] != prev[1] {
				changes = append(changes, change{7, "FOLDER_STRUCTURE_CHANGED: " + p})
			}
		}
	}

	sort.Slice(changes, func(i, j int) bool { return changes[i].priority < changes[j].priority })

	result := make([]string, len(changes))
	for i, c := range changes {
		result[i] = c.msg
	}
	return result
}

// --- Cache Persistence ---

func loadCache() *Cache {
	c := &Cache{Entries: make(map[string]CacheEntry)}
	f, err := os.Open(cacheFile)
	if err != nil {
		return c
	}
	defer f.Close()

	if err := json.NewDecoder(f).Decode(c); err != nil {
		c.Entries = make(map[string]CacheEntry)
	}
	return c
}

func saveCache(c *Cache) {
	data, err := json.Marshal(c)
	if err != nil {
		fmt.Fprintf(os.Stderr, "save cache: %v\n", err)
		return
	}
	if err := os.WriteFile(cacheFile, data, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "write cache: %v\n", err)
	}
}
