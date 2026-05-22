# @Author  : ChaoQiezi
# @Time    : 2026/5/19
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dem_reproject_resample.py

r"""
DEM 投影转换 (WGS84 -> 自定义 Albers 等面积圆锥投影) 并重采样至 10m,
然后基于 10m DEM 计算坡度和坡向.

输入: G:/GeoProjects/dry_hot_valley/geo_factor/DEM/xinan/elevation_30m_geo_xinan_region.tif
输出: G:/GeoProjects/dry_hot_valley/geo_factor/DEM/xinan/elevation_10m_proj_xinan_region.tif
      G:/GeoProjects/dry_hot_valley/geo_factor/DEM/xinan/elevation_100m_proj_xinan_region.tif
      G:/GeoProjects/dry_hot_valley/geo_factor/Slope/xinan/slope_10m_proj_xinan_region.tif
      G:/GeoProjects/dry_hot_valley/geo_factor/Aspect/xinan/aspect_10m_proj_xinan_region.tif

投影: 自定义 Albers 等面积圆锥投影 (方案 A)
  中央经线: 99.35degE, 标准纬线: 24degN / 34degN, 起始纬度: 29degN, 基准面: WGS84

注意:
- 坡度和坡向直接从 10m 投影 DEM 计算 (gdaldem), 而非对 Viz 文件重采样,
  以避免角度数据的插值畸变和在重采样中引入的额外误差.
- 此脚本计算量极大 (西南地区 10m DEM 约 20 Gpix), 预计运行数小时.
"""

import os
from osgeo import gdal, gdalconst

from qiezi.geo import build_overviews

gdal.DontUseExceptions()

# ======================== Configuration ========================
in_root = r'G:\GeoProjects\dry_hot_valley\geo_factor'
out_root = in_root

# 自定义 Albers 等面积圆锥投影 (针对西南地区 92.1°E-106.6°E, 22.4°N-35.6°N)
albers_proj4 = (
    '+proj=aea '
    '+lat_1=24 +lat_2=34 '
    '+lat_0=29 +lon_0=99.35 '
    '+datum=WGS84 +units=m +no_defs'
)

# 输入文件 (step 2 输出)
dem_30m_path = os.path.join(in_root, 'DEM', 'xinan', 'elevation_30m_geo_xinan_region.tif')

# 输出文件
dem_10m_path = os.path.join(out_root, 'DEM', 'xinan', 'elevation_10m_proj_xinan_region.tif')
slope_10m_path = os.path.join(out_root, 'Slope', 'xinan', 'slope_10m_proj_xinan_region.tif')
aspect_10m_path = os.path.join(out_root, 'Aspect', 'xinan', 'aspect_10m_proj_xinan_region.tif')

overwrite = False
# ================================================================

creation_options = [
    'BIGTIFF=YES',
    'TILED=YES',
    'BLOCKXSIZE=4096',
    'BLOCKYSIZE=4096',
    'COMPRESS=DEFLATE',
    'PREDICTOR=3',
    'NUM_THREADS=ALL_CPUS',
]

# ================================================================
# Step 1: DEM 重投影 + 重采样 (30m WGS84 → 10m Albers)
# ================================================================
if os.path.exists(dem_10m_path) and not overwrite:
    print(f'DEM 10m exists: {dem_10m_path}, skip.')
else:
    os.makedirs(os.path.dirname(dem_10m_path), exist_ok=True)
    print('Step 1/3: Reprojecting + resampling DEM to 10m Albers ...')
    print(f'  Input:  {dem_30m_path}')
    print(f'  Output: {dem_10m_path}')

    if not os.path.exists(dem_30m_path):
        raise FileNotFoundError(f'Source DEM not found: {dem_30m_path}. '
                                f'Run dem_mosaic_clip.py first.')

    warp_options = gdal.WarpOptions(
        format='GTiff',
        dstSRS=albers_proj4,
        srcSRS='EPSG:4326',
        srcNodata=float('nan'),
        dstNodata=float('nan'),
        xRes=10,
        yRes=10,
        resampleAlg=gdal.GRA_Bilinear,
        creationOptions=creation_options,
        multithread=True,
        warpMemoryLimit=3072,
    )
    gdal.Warp(dem_10m_path, dem_30m_path, options=warp_options)
    build_overviews(dem_10m_path)
    print(f'  -> {dem_10m_path}')

# ================================================================
# Step 2: DEM 下采样至 100m (10m → 100m, 供 SAGA Wind Effect 使用)
# ================================================================
dem_100m_path = os.path.join(out_root, 'DEM', 'xinan', 'elevation_100m_proj_xinan_region.tif')
if os.path.exists(dem_100m_path) and not overwrite:
    print(f'DEM 100m exists: {dem_100m_path}, skip.')
else:
    os.makedirs(os.path.dirname(dem_100m_path), exist_ok=True)
    print('Step 2/4: Downsampling DEM to 100m (for SAGA Wind Effect) ...')
    print(f'  Input:  {dem_10m_path}')
    print(f'  Output: {dem_100m_path}')

    downsample_options = gdal.WarpOptions(
        format='GTiff',
        xRes=100,
        yRes=100,
        resampleAlg=gdal.GRA_Average,
        srcNodata=float('nan'),
        dstNodata=float('nan'),
        creationOptions=creation_options,
        multithread=True,
    )
    gdal.Warp(dem_100m_path, dem_10m_path, options=downsample_options)
    build_overviews(dem_100m_path)
    print(f'  -> {dem_100m_path}')

# ================================================================
# Step 3: 计算坡度 (gdaldem slope)
# ================================================================
if os.path.exists(slope_10m_path) and not overwrite:
    print(f'Slope 10m exists: {slope_10m_path}, skip.')
else:
    os.makedirs(os.path.dirname(slope_10m_path), exist_ok=True)
    print('Step 3/4: Computing slope from 10m DEM (gdaldem) ...')

    slope_options = gdal.DEMProcessingOptions(
        format='GTiff',
        slopeFormat='degree',
        computeEdges=True,
        creationOptions=creation_options,
    )
    gdal.DEMProcessing(slope_10m_path, dem_10m_path, 'slope', options=slope_options)
    build_overviews(slope_10m_path)
    print(f'  -> {slope_10m_path}')

# ================================================================
# Step 3: 计算坡向 (gdaldem aspect)
# ================================================================
if os.path.exists(aspect_10m_path) and not overwrite:
    print(f'Aspect 10m exists: {aspect_10m_path}, skip.')
else:
    os.makedirs(os.path.dirname(aspect_10m_path), exist_ok=True)
    print('Step 4/4: Computing aspect from 10m DEM (gdaldem) ...')

    aspect_options = gdal.DEMProcessingOptions(
        format='GTiff',
        computeEdges=True,
        creationOptions=creation_options,
    )
    gdal.DEMProcessing(aspect_10m_path, dem_10m_path, 'aspect', options=aspect_options)
    build_overviews(aspect_10m_path)
    print(f'  -> {aspect_10m_path}')

print('\nAll DEM reprojection + resample + slope/aspect completed.')
