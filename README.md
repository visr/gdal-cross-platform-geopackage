# GeoPackage R-tree cross-platform non-determinism (GDAL ≥ 3.8)

Minimal reproducer showing that GDAL's GeoPackage spatial index creation
produces different binary output on Windows vs Linux for identical input data.

Reported in https://github.com/OSGeo/gdal/issues/14685, fixed in https://github.com/OSGeo/gdal/pull/14687, which is likely available from GDAL 3.13.1.

## Quick start

```bash
pixi install
pixi run -e default reproduce   # create → index → check
```

Run on both Windows and Linux. If the R-tree MD5 differs, the bug is confirmed.

## Problem

Creating a spatial index on the same GeoPackage data produces different R-tree
binary data on Windows vs Linux (WSL). The entries within R-tree nodes are
reordered — the same set of bounding boxes appears, but in a different sequence.

## Root cause

GDAL's `gdal_sqlite_rtree_bl_from_feature_table` (used by `CreateSpatialIndex`)
builds the R-tree via sequential insertion. When a leaf node overflows, it is
split using the R*-tree algorithm in `node_split_rstartree`, which sorts entries
by axis using `std::sort`:

```cpp
std::sort(aSorted[0], aSorted[0] + nodeOri.count,
    [&nodeOri](const SortType& a, const SortType& b) {
        return nodeOri.rects[a.i].min[0] < nodeOri.rects[b.i].min[0] ||
               (nodeOri.rects[a.i].min[0] == nodeOri.rects[b.i].min[0] &&
                nodeOri.rects[a.i].max[0] < nodeOri.rects[b.i].max[0]);
    });
```

When entries have identical bounding box coordinates on the sort axis (e.g.
points sharing an X or Y value in a grid), they compare equal. `std::sort` is
unstable, meaning the relative order of equal elements is unspecified — but
"unspecified" does not by itself mean "platform-dependent".

The reason this is **platform-dependent** is that different C++ standard library
implementations use fundamentally different sorting algorithms:

- **MSVC** (Windows): uses introsort with a specific median-of-three pivot
  selection and insertion sort fallback.
- **libstdc++** (Linux/GCC): uses introsort with a different pivot strategy and
  different thresholds for switching to insertion sort.

These algorithmic differences cause equal elements to end up in different
positions depending on the platform — even for the same input in the same order.
The result is that the R-tree node splits produce different child assignments,
propagating into different tree structures and different binary output.

## Affected versions

GDAL **3.8.0** and later. The in-memory R-tree bulk loader was introduced in
commit [`f20aa62`](https://github.com/OSGeo/gdal/commit/f20aa62f227976ad2f8981fcfa2e70f24db1a888)
(Oct 22, 2023) with the changelog entry "GeoPackage: much faster spatial index
creation (~ 3-4 times faster)". Prior to 3.8.0, GDAL used row-by-row R-tree
insertion via SQLite's virtual table mechanism, which is deterministic.

## Environment

- GDAL ≥ 3.8.0 (tested with 3.13.0 from conda-forge)
- Pixi for cross-platform environment management

## Reproducer

```bash
pixi install

# All-in-one (GDAL ≥ 3.8, affected):
pixi run -e default reproduce

# Or step by step:
pixi run -e default create      # → test.gpkg (200 points, no spatial index)
pixi run -e default index       # → test_indexed.gpkg (spatial index added)
pixi run -e default check       # → prints R-tree MD5 hash

# Verify the base file (without index) is identical cross-platform:
pixi run -e default check-gpkg  # → prints whole-file MD5 of test.gpkg

# Compare with GDAL 3.7 (unaffected, row-by-row R-tree insertion):
pixi run -e gdal37 reproduce
```

Run on both Windows and Linux/WSL. The R-tree hash from `check` will
differ across platforms in the default environment; the whole-file hash from
`check-gpkg` will match. With the `gdal37` environment, everything matches.

## What was tried

- `OGR_GPKG_MAX_RAM_USAGE_RTREE=0`: Forces in-memory path. Same code path on
  both platforms, but still different ordering (the sort instability is in the
  bulk loader, not the RAM path selection).
- `OGR_CURRENT_DATE`: Fixes timestamps in `gpkg_contents.last_change`.
  Without this the GeoPackage differs per-run even without an R-tree.
  With this set, the file *without* spatial index is byte-identical cross-platform.
- `SPATIAL_INDEX=NO` + `OGR_CURRENT_DATE`: Produces identical files. This
  confirms the R-tree is the only remaining source of non-determinism.

## Cross-platform results

### GDAL 3.13 (affected — bulk R-tree loader)

| File | Windows | Linux (WSL) | Match? |
|------|---------|-------------|--------|
| test.gpkg (no index) | `47a3c841862471f3d8be801efa7a9937` | `47a3c841862471f3d8be801efa7a9937` | ✅ |
| R-tree nodes | `4473809c35ae48ef910e6decd20c3376` | `1595194743a5d67bb7b4ffc6e3559af7` | ❌ |

### GDAL 3.7 (unaffected — row-by-row R-tree insertion)

| File | Windows | Linux (WSL) | Match? |
|------|---------|-------------|--------|
| test.gpkg (no index) | `c3082c15417e6525d5b45e8ebded9fae` | `c3082c15417e6525d5b45e8ebded9fae` | ✅ |
| R-tree nodes | `1c4882d44c47fd1986e777608a758b12` | `1c4882d44c47fd1986e777608a758b12` | ✅ |

Test with GDAL 3.7 yourself: `pixi run -e gdal37 reproduce`

This confirms:
- The base GeoPackage (without spatial index) is byte-identical on all platforms
  and GDAL versions (when `OGR_CURRENT_DATE` is fixed).
- The 32-bit float R-tree coordinates are identical across platforms — only the
  *ordering* within nodes differs.
- GDAL 3.7's row-by-row R-tree insertion was fully deterministic.
- The regression was introduced in GDAL 3.8.0 with the bulk R-tree loader.

## Impact

This causes binary-different GeoPackage files across platforms for identical
input data, which breaks reproducibility in CI/CD pipelines and cross-platform
workflows (e.g. Ribasim: https://github.com/Deltares/Ribasim/issues/3079).

## Suggested fix

Use `std::stable_sort` instead of `std::sort` in `node_split_rstartree`, or add
a tiebreaker to the comparator (e.g. the original array index `a.i < b.i`) so
that equal elements have a deterministic order regardless of the sort algorithm.

The tiebreaker approach is preferred: zero extra memory, same algorithm, and it
makes the intent explicit. Performance is not a concern — the sort operates on a
single overflowing node (≤51 elements), so the difference is nanoseconds.

## Workarounds

1. **Strip the spatial index** from canonical/checked-in files and recreate it
   at deployment time (single platform).
2. **Create without spatial index** (`SPATIAL_INDEX=NO`) and add it in a
   post-processing step on the target platform.
3. **Compare semantically** rather than byte-for-byte (query the R-tree table
   and compare the set of entries, ignoring order within nodes).

## Source location

- **GDAL repo**: [`ogr/ogrsf_frmts/sqlite/sqlite_rtree_bulk_load/sqlite_rtree_bulk_load.c`](https://github.com/OSGeo/gdal/blob/master/ogr/ogrsf_frmts/sqlite/sqlite_rtree_bulk_load/sqlite_rtree_bulk_load.c)
- **Upstream repo**: https://github.com/rouault/sqlite_rtree_bulk_load
- The file is compiled as C++ via `wrapper.cpp`, which also applies a
  `gdal_` prefix to all symbols via `#define SQLITE_RTREE_BL_SYMBOL(x) gdal_##x`.
