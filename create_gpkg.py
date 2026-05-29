"""Create a synthetic GeoPackage with 200 Point geometries (no spatial index).

The grid layout causes many points to share X or Y coordinates, which triggers
the std::sort instability in GDAL's R*-tree node splitting when a spatial index
is later created (see create_index.py).
"""

import os
from pathlib import Path

from osgeo import gdal, ogr, osr

gdal.UseExceptions()

# Fix the timestamp stored in gpkg_contents.last_change so the file is
# byte-identical regardless of when/where it is created.
os.environ["OGR_CURRENT_DATE"] = "2025-01-01T00:00:00.000Z"

OUTPUT = Path("test.gpkg")

# Clean up previous run
if OUTPUT.exists():
    OUTPUT.unlink()

# Create GeoPackage
driver = ogr.GetDriverByName("GPKG")
ds = driver.CreateDataSource(
    str(OUTPUT),
    options=["VERSION=1.4"],
)

# Dutch RD New (EPSG:28992) - typical for Ribasim models
srs = osr.SpatialReference()
srs.ImportFromEPSG(28992)

# Create layer WITHOUT spatial index
layer = ds.CreateLayer(
    "Node",
    srs=srs,
    geom_type=ogr.wkbPoint,
    options=["SPATIAL_INDEX=NO", "FID=fid"],
)

# Add a dummy attribute
field_defn = ogr.FieldDefn("name", ogr.OFTString)
layer.CreateField(field_defn)

# 200 points in a 20x10 grid ensures a multi-level R-tree (max 51 entries/node).
n_points = 200
x_origin = 155000.0  # typical Dutch RD x
y_origin = 463000.0  # typical Dutch RD y
spacing = 50.0  # 50m spacing

fid = 1
for i in range(20):
    for j in range(10):
        x = x_origin + i * spacing
        y = y_origin + j * spacing
        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetFID(fid)
        feat.SetField("name", f"node_{fid}")
        geom = ogr.CreateGeometryFromWkt(f"POINT ({x} {y})")
        feat.SetGeometry(geom)
        layer.CreateFeature(feat)
        fid += 1

ds = None

print(f"Created {OUTPUT} with {n_points} points (no spatial index)")
print(f"File size: {OUTPUT.stat().st_size} bytes")
