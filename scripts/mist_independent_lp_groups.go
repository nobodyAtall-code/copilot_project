// Independent, read-only Go audit of liblp group descriptors and membership.
// Compiles alongside the PINNED third-party lpunpack-go super.go. The pinned
// parser validates geometry/header and partition extents; this additional
// auditor independently reads group maximum sizes and partition group indexes.
// This is NOT the official AOSP lpdump implementation or an OTA approval.
package main

import (
    "crypto/sha256"
    "encoding/binary"
    "encoding/json"
    "fmt"
    "os"
    "sort"
    "strings"
)

type groupReport struct {
    Name string `json:"name"`
    Flags uint32 `json:"flags"`
    MaximumSize uint64 `json:"maximum_size"`
    AllocatedBytes uint64 `json:"allocated_bytes"`
    Partitions []string `json:"partitions"`
}

func fail(err error) {
    fmt.Fprintln(os.Stderr, err)
    os.Exit(1)
}
func tableSlice(t []byte, d LpMetadataTableDescriptor, n uint32) ([]byte, error) {
    if n >= d.NumElements || d.ElementSize == 0 {
        return nil, fmt.Errorf("invalid descriptor index")
    }
    off := uint64(d.Offset) + uint64(n)*uint64(d.ElementSize)
    end := off + uint64(d.ElementSize)
    if end > uint64(len(t)) || end < off {
        return nil, fmt.Errorf("metadata descriptor out of bounds")
    }
    return t[off:end], nil
}

func main() {
    if len(os.Args) != 2 { fail(fmt.Errorf("usage: lp-groups IMAGE")) }
    sp, err := OpenSuperImage(os.Args[1], false)
    if err != nil { fail(err) }
    defer sp.Close()
    geo, goff, err := sp.findGeometry()
    if err != nil { fail(err) }
    if geo.MetadataSlotCount == 0 || geo.MetadataMaxSize > 1048576 {
        fail(fmt.Errorf("unsupported metadata geometry"))
    }
    start := primaryMetadataOffset(geo, goff, 0)
    buf := make([]byte, geo.MetadataMaxSize)
    if _, err := sp.file.ReadAt(buf, start); err != nil { fail(err) }
    h, err := parseHeader(buf)
    if err != nil { fail(err) }
    if uint64(h.HeaderSize)+uint64(h.TablesSize) > uint64(len(buf)) {
        fail(fmt.Errorf("metadata tables exceed slot"))
    }
    table := buf[h.HeaderSize:h.HeaderSize+h.TablesSize]
    if sha256.Sum256(table) != h.TablesChecksum {
        fail(fmt.Errorf("independent Go table SHA256 mismatch"))
    }
    if h.Groups.ElementSize != 48 || h.Partitions.ElementSize != 52 {
        fail(fmt.Errorf("unexpected group/partition element size: %d/%d",
            h.Groups.ElementSize, h.Partitions.ElementSize))
    }
    if h.Groups.NumElements == 0 || h.Groups.NumElements > 128 || h.Partitions.NumElements > 2048 {
        fail(fmt.Errorf("unsupported group/partition count"))
    }
    groups := make([]groupReport, 0, h.Groups.NumElements)
    for i := uint32(0); i < h.Groups.NumElements; i++ {
        entry, err := tableSlice(table, h.Groups, i)
        if err != nil { fail(err) }
        name := cString(entry[:36])
        if name == "" { fail(fmt.Errorf("empty LP group name")) }
        groups = append(groups, groupReport{
            Name: name,
            Flags: binary.LittleEndian.Uint32(entry[36:40]),
            MaximumSize: binary.LittleEndian.Uint64(entry[40:48]),
            Partitions: []string{},
        })
    }
    populated := map[string]uint64{}
    for _, p := range sp.Partitions {
        if _, exists := populated[p.Name]; exists { fail(fmt.Errorf("duplicate populated partition")) }
        populated[p.Name] = p.Size
    }
    seen := map[string]bool{}
    for i := uint32(0); i < h.Partitions.NumElements; i++ {
        entry, err := tableSlice(table, h.Partitions, i)
        if err != nil { fail(err) }
        name := cString(entry[:36])
        if name == "" { fail(fmt.Errorf("empty partition name")) }
        if binary.LittleEndian.Uint32(entry[36:40])&LP_PARTITION_ATTR_SLOT_SUFFIXED != 0 {
            name += "_a" // pinned reader's slot-0 convention
        }
        if seen[name] { fail(fmt.Errorf("duplicate partition: %s", name)) }
        seen[name] = true
        groupID := binary.LittleEndian.Uint32(entry[48:52])
        if groupID >= uint32(len(groups)) { fail(fmt.Errorf("invalid group index: %s", name)) }
        size := populated[name] // empty partitions intentionally zero
        groups[groupID].AllocatedBytes += size
        groups[groupID].Partitions = append(groups[groupID].Partitions, name)
    }
    for i := range groups {
        sort.Strings(groups[i].Partitions)
        if groups[i].MaximumSize != 0 && groups[i].AllocatedBytes > groups[i].MaximumSize {
            fail(fmt.Errorf("group %s exceeds maximum", groups[i].Name))
        }
    }
    // No output binary partition contents or private data.
    _ = strings.Join // keep imports deterministic for future extensions
    if err := json.NewEncoder(os.Stdout).Encode(groups); err != nil { fail(err) }
}
