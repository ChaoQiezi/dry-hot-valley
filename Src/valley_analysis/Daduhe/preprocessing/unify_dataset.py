# @Author  : ChaoQiezi
# @Time    : 2026/4/21 下午4:48
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: unify_dataset.py

"""
This script is used to 将原先整个川西的数据集进行裁剪掩膜, 进行空间统一, 得到大渡河区域的数据集

包括:
1. DEM栅格(以它为基准进行空间统一)
2. NDVI栅格(年均值+年际均值)
3. 迎背风坡二分类栅格

"""

import os
from glob import glob
import arcpy

# 准备
dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_10m_projected.tif"
ndvi_dir = r'E:\GeoProjects\dry_hot_valley\NDVI\Yearly'  # NDVI_{year}.tif
ndvi_mean_path = r'E:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif'
aspect_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"  # 迎风坡背风坡二分类栅格
daduhe_path = r"E:\GeoProjects\dry_hot_valley\valley_area\西南干旱河谷范围\Daduhe_valley.shp"  # 边界矢量
out_dir = r'E:\GeoProjects\dry_hot_valleyalley_analysis\Daduhe'
arcpy.env.overwriteOutput = True  # 允许覆盖输出文件
clipping_geometry = False  # 裁剪时是否按shp进行掩膜

# 输出设置
ndvi_paths = glob(os.path.join(ndvi_dir, 'NDVI_*.tif'))
if clipping_geometry:
    out_dem_path = os.path.join(out_dir, 'geo_factor', 'elevation_10m_projected.tif')
    out_ndvi_mean_path = os.path.join(out_dir, 'NDVI', 'Interannual', 'NDVI_interannual_mean.tif')
    out_ndvi_paths = [os.path.join(out_dir, 'NDVI', 'Yearly', os.path.basename(ndvi_path)) for ndvi_path in ndvi_paths]
    out_aspect_path = os.path.join(out_dir, 'geo_factor', os.path.basename(aspect_path))
else:
    out_dem_path = os.path.join(out_dir, 'geo_factor', 'elevation_10m_projected_region.tif')
    out_ndvi_mean_path = os.path.join(out_dir, 'NDVI', 'Interannual', 'NDVI_interannual_mean_region.tif')
    out_ndvi_paths = [os.path.join(out_dir, 'NDVI', 'Yearly', os.path.basename(ndvi_path).replace('.tif', '_region.tif')) for ndvi_path in ndvi_paths]
    out_aspect_path = os.path.join(out_dir, 'geo_factor', os.path.basename(aspect_path).replace('.tif', '_region.tif'))
all_outputs = [out_dem_path, out_ndvi_mean_path, out_aspect_path] + out_ndvi_paths
for fp in set(all_outputs):
    os.makedirs(os.path.dirname(fp), exist_ok=True)

# DEM处理
arcpy.management.Clip(dem_path, out_raster=out_dem_path, in_template_dataset=daduhe_path, clipping_geometry=clipping_geometry)
print('finish: DEM;')
# NDVI年际均值处理
arcpy.management.Clip(ndvi_mean_path, out_raster=out_ndvi_mean_path, in_template_dataset=daduhe_path, clipping_geometry=clipping_geometry)
print('finish: NDVI年际均值;')
# NDVI处理
for ndvi_path, out_ndvi_path in zip(ndvi_paths, out_ndvi_paths):
    arcpy.management.Clip(ndvi_path, out_raster=out_ndvi_path, in_template_dataset=daduhe_path, clipping_geometry=clipping_geometry)
    print('finish: {}'.format(os.path.basename(out_ndvi_path)))
# aspect处理
arcpy.management.Clip(aspect_path, out_raster=out_aspect_path, in_template_dataset=daduhe_path, clipping_geometry=clipping_geometry)
print('finish: aspect')


