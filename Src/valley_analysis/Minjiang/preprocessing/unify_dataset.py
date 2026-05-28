# @Author  : ChaoQiezi
# @Time    : 2026/4/21 下午4:48
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: unify_dataset.py

"""
将西南地区(Albers)数据集裁剪到岷江干热河谷范围, 进行空间统一

包括:
1. DEM栅格 (西南地区10m Albers)
2. NDVI年栅格 (2019–2025)
3. NDVI年际均值 (多年平均)
4. 迎背风坡二分类栅格
"""

from glob import glob
import os

import arcpy

# 0. Configuration
dem_path = r"G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_10m_proj_xinan_region.tif"
ndvi_dir = r"E:\GeoProjects\dry_hot_valley\NDVI\Yearly"
aspect_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"
minjiang_path = r"E:\GeoProjects\dry_hot_valley\valley_area\Chuanxi\Minjiang_valley.shp"
out_dir = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang"
arcpy.env.overwriteOutput = True
clipping_geometry = False  # 裁剪时是否按shp边界掩膜 (False = 外接矩形)

# 1. Output paths
ndvi_paths = glob(os.path.join(ndvi_dir, "NDVI_*.tif"))
if clipping_geometry:
    out_dem_path = os.path.join(out_dir, "geo_factor", "elevation_10m_projected.tif")
    out_aspect_path = os.path.join(out_dir, "geo_factor", os.path.basename(aspect_path))
    out_ndvi_paths = [
        os.path.join(out_dir, "NDVI", "Yearly", os.path.basename(p))
        for p in ndvi_paths
    ]
else:
    out_dem_path = os.path.join(out_dir, "geo_factor", "elevation_10m_projected_region.tif")
    out_aspect_path = os.path.join(out_dir, "geo_factor",
                                   os.path.basename(aspect_path).replace(".tif", "_region.tif"))
    out_ndvi_paths = [
        os.path.join(out_dir, "NDVI", "Yearly",
                     os.path.basename(p).replace(".tif", "_region.tif"))
        for p in ndvi_paths
    ]

# 2. Clip
# DEM
arcpy.management.Clip(
    dem_path, out_raster=out_dem_path,
    in_template_dataset=minjiang_path, clipping_geometry=clipping_geometry,
)
print("finish: DEM;")

# NDVI (逐年)
for ndvi_path, out_ndvi_path in zip(ndvi_paths, out_ndvi_paths):
    arcpy.management.Clip(
        ndvi_path, out_raster=out_ndvi_path,
        in_template_dataset=minjiang_path, clipping_geometry=clipping_geometry,
    )
    print("finish: {}".format(os.path.basename(out_ndvi_path)))

# windward_leeward
arcpy.management.Clip(
    aspect_path, out_raster=out_aspect_path,
    in_template_dataset=minjiang_path, clipping_geometry=clipping_geometry,
)
print("finish: windward_leeward")

print("\nAll done. Output dir: {}".format(out_dir))
