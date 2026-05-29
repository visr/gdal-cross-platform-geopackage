"""Check R-tree node data and print an MD5 hash for cross-platform comparison."""

import hashlib
import sqlite3
from pathlib import Path

OUTPUT = Path("test_indexed.gpkg")

if not OUTPUT.exists():
    raise FileNotFoundError(f"{OUTPUT} not found. Run create_index.py first.")

conn = sqlite3.connect(str(OUTPUT))
cursor = conn.cursor()

# Get all R-tree node data
cursor.execute("SELECT nodeno, data FROM rtree_Node_geom_node ORDER BY nodeno")
rows = cursor.fetchall()

# Compute hash of all node data
hasher = hashlib.md5()
for nodeno, data in rows:
    hasher.update(nodeno.to_bytes(8, "little"))
    hasher.update(data)
rtree_hash = hasher.hexdigest()

conn.close()

print(f"R-tree nodes: {len(rows)}")
print(f"R-tree MD5:   {rtree_hash}")
print()
print("If this hash differs between Windows and Linux,")
print("it confirms the cross-platform R-tree non-determinism.")
