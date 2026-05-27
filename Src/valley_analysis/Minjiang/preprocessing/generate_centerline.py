# @Author  : ChaoQiezi
# @Time    : 2026/5/24
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: generate_centerline.py

"""
从西南地区 river_net.shp 中提取岷江河段作为河道中心线

替代已删除的 centerline_final.shp, 通过空间相交 Minjiang_valley.shp 与
river_net.shp 筛选属于岷江干热河谷的河段, 保存为含 Name 字段的新 shapefile.
"""

import os
import shapefile
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import CRS, Transformer

# ============================================================
# 0. Configuration
# ============================================================
VALLEY_SHP = r"E:\GeoProjects\dry_hot_valley\valley_area\Chuanxi\Minjiang_valley.shp"
RIVER_NET_SHP = r"E:\GeoProjects\dry_hot_valley\river_net\river_net.shp"
OUT_SHP = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\geo_factor\Minjiang_centerline.shp"
VALLEY_NAME = "岷江干旱河谷"

# ============================================================
# 1. Load valley polygon, reproject to Albers
# ============================================================
print("Loading valley polygon ...")
reader_valley = shapefile.Reader(str(VALLEY_SHP))
valley_geom = shape(reader_valley.shape(0))
with open(os.path.splitext(VALLEY_SHP)[0] + ".prj", "r", errors="ignore") as f:
    valley_crs = CRS.from_wkt(f.read())
print(f"  Valley CRS: {valley_crs.name}")

# River net CRS (Albers)
with open(os.path.splitext(RIVER_NET_SHP)[0] + ".prj", "r", errors="ignore") as f:
    river_crs = CRS.from_wkt(f.read())
print(f"  River CRS: {river_crs.name}")

transformer = Transformer.from_crs(valley_crs, river_crs, always_xy=True)
valley_albers = transform(transformer.transform, valley_geom)
print(f"  Valley reprojected to Albers")

# ============================================================
# 2. Intersect with river_net
# ============================================================
print("Finding intersecting river segments ...")
reader_river = shapefile.Reader(str(RIVER_NET_SHP))
river_fields = [f[0] for f in reader_river.fields[1:]]

intersecting = []
for sr in reader_river.iterShapeRecords():
    river_geom = shape(sr.shape)
    rec = sr.record.as_dict()
    if valley_albers.intersects(river_geom):
        # Clip to valley interior for cleaner display
        clipped = valley_albers.intersection(river_geom)
        if not clipped.is_empty:
            intersecting.append((clipped, rec))

print(f"  Found {len(intersecting)} intersecting segments")

# ============================================================
# 3. Write output shapefile
# ============================================================
os.makedirs(os.path.dirname(OUT_SHP), exist_ok=True)

# Remove existing output files
for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
    fpath = os.path.splitext(OUT_SHP)[0] + ext
    if os.path.exists(fpath):
        os.remove(fpath)

writer = shapefile.Writer(str(OUT_SHP), shapeType=shapefile.POLYLINE)
writer.field("Name", "C", size=50)
writer.field("arcid", "N")
writer.field("grid_code", "N")

for geom, rec in intersecting:
    if geom.geom_type == "LineString":
        coords = list(geom.coords)
    elif geom.geom_type == "MultiLineString":
        coords = []
        for line in geom.geoms:
            coords.extend(line.coords)
    else:
        continue
    writer.line([coords])
    writer.record(VALLEY_NAME, rec.get("arcid", -1), rec.get("grid_code", -1))

# Write CRS and encoding
with open(os.path.splitext(OUT_SHP)[0] + ".prj", "w") as f:
    f.write(river_crs.to_wkt())
with open(os.path.splitext(OUT_SHP)[0] + ".cpg", "w") as f:
    f.write("UTF-8")

writer.close()
print(f"  Saved: {OUT_SHP}")
print(f"  Segments: {len(intersecting)}")
print("Done.")
