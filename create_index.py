"""
Create the spatial index on a copy of test.gpkg using GDAL's CreateSpatialIndex.

This mimics: ogrinfo -update test_indexed.gpkg -sql "SELECT CreateSpatialIndex('Node', 'geom');"

The OGR_CURRENT_DATE is fixed to ensure the last_change timestamp doesn't
introduce binary differences.
"""

import shutil
from pathlib import Path

from osgeo import gdal, ogr

gdal.UseExceptions()

INPUT = Path("test.gpkg")
OUTPUT = Path("test_indexed.gpkg")

if not INPUT.exists():
    raise FileNotFoundError(f"{INPUT} not found. Run create_gpkg.py first.")

# Copy the base GeoPackage
shutil.copy2(INPUT, OUTPUT)

# Fix the timestamp for reproducibility
gdal.SetConfigOption("OGR_CURRENT_DATE", "2025-01-01T00:00:00.000Z")
# Force the same R-tree code path regardless of available RAM
gdal.SetConfigOption("OGR_GPKG_MAX_RAM_USAGE_RTREE", "0")

# Open and create spatial index
ds = ogr.Open(str(OUTPUT), update=True)
ds.ExecuteSQL("SELECT CreateSpatialIndex('Node', 'geom')")
ds = None

print(f"Created spatial index on {OUTPUT}")
print(f"File size: {OUTPUT.stat().st_size} bytes")
