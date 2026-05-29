"""
Check if the GeoPackage WITHOUT spatial index is identical across platforms.

Computes an MD5 hash of the entire file. If this differs across platforms,
there are additional sources of non-determinism beyond the R-tree.
"""

import hashlib
from pathlib import Path

OUTPUT = Path("test.gpkg")

if not OUTPUT.exists():
    raise FileNotFoundError(f"{OUTPUT} not found. Run create_gpkg.py first.")

md5 = hashlib.md5(OUTPUT.read_bytes()).hexdigest()
print(f"File: {OUTPUT}")
print(f"Size: {OUTPUT.stat().st_size} bytes")
print(f"MD5:  {md5}")
