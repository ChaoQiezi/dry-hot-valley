# @Author  : ChaoQiezi
# @Time    : 2026/5/22
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: saga_wind_effect.py

"""
SAGA GIS Wind Effect 计算 — 100m DEM 降采样方案

西南地区 10m DEM ~206 亿像素, SAGA Wind Effect 需要 ~85 GB 内存, 不可行.
ERA5 风向为 0.25° (~25 km), 100m DEM 已为 250 倍过采样.

流程:
  1. 风向 10m → 100m 降采样 (gdal.Warp, Bilinear)
  2. SAGA Wind Effect 在 100m 上计算 (DEM 100m + wind_dir 100m)
  3. Wind Effect 100m → 10m 回升 (gdal.Warp, Bilinear, 以 10m DEM 为参考网格)

参考文献: Böhner & Antonić (2009), Geomorphometry, Elsevier.
"""

import os
import subprocess
from osgeo import gdal

# ======================== Configuration ========================
saga_cmd = r'D:\Softwares\saga-9.11.3_msw\saga_cmd.exe'
dem_100m_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_100m_proj_xinan_region.tif'
dem_10m_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_10m_proj_xinan_region.tif'
wind_dir_10m_path = r'G:\GeoProjects\dry_hot_valley\wind_direction\10m\wind_dir_600hPa_10m.tif'
wind_effect_dir = r'G:\GeoProjects\dry_hot_valley\wind_effect'
wind_effect_10m_tif = os.path.join(wind_effect_dir, 'wind_effect.tif')

# SAGA 临时格式文件
dem_sgrd = os.path.join(wind_effect_dir, 'dem')
wind_dir_sgrd = os.path.join(wind_effect_dir, 'wind_dir')
wind_effect_sgrd = os.path.join(wind_effect_dir, 'wind_effect')

# 临时 100m 文件
wind_dir_100m_tif = os.path.join(wind_effect_dir, 'wind_dir_100m.tif')
wind_effect_100m_tif = os.path.join(wind_effect_dir, 'wind_effect_100m.tif')

max_dist = 300.0    # 搜索距离 [km]
accel = 1.5          # 加速度因子
# ================================================================

os.makedirs(wind_effect_dir, exist_ok=True)


def run_saga(tool_args, description='SAGA command'):
    """运行 SAGA 命令并检查返回值"""
    cmd = [saga_cmd] + tool_args
    print(f'Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'[WARNING] {description} returned {result.returncode}')
        if result.stderr.strip():
            print(result.stderr.strip()[-500:])
    else:
        print(f'  -> OK')
    return result


# ================================================================
# Step 0: 读取参考栅格参数 (100m DEM, 10m DEM)
# ================================================================
# 100m DEM — 风向降采样的目标网格
ref100_ds = gdal.Open(dem_100m_path)
ref100_srs = ref100_ds.GetProjection()
ref100_w = ref100_ds.RasterXSize
ref100_h = ref100_ds.RasterYSize
ref100_gt = ref100_ds.GetGeoTransform()
ref100_xmin = ref100_gt[0]
ref100_ymax = ref100_gt[3]
ref100_xmax = ref100_xmin + ref100_gt[1] * ref100_w
ref100_ymin = ref100_ymax + ref100_gt[5] * ref100_h
ref100_ds = None

# 10m DEM — 最终输出的参考网格
ref10_ds = gdal.Open(dem_10m_path)
ref10_srs = ref10_ds.GetProjection()
ref10_w = ref10_ds.RasterXSize
ref10_h = ref10_ds.RasterYSize
ref10_gt = ref10_ds.GetGeoTransform()
ref10_xmin = ref10_gt[0]
ref10_ymax = ref10_gt[3]
ref10_xmax = ref10_xmin + ref10_gt[1] * ref10_w
ref10_ymin = ref10_ymax + ref10_gt[5] * ref10_h
ref10_ds = None

# ================================================================
# Step 1: 风向 10m → 100m 降采样 (与 100m DEM 严格对齐)
# ================================================================
if not os.path.exists(wind_dir_10m_path):
    raise FileNotFoundError(f'Wind direction not found: {wind_dir_10m_path}')

print('=== Step 1/6: Downsample wind direction 10m → 100m ===')
print(f'  Input:  {wind_dir_10m_path}')
print(f'  Output: {wind_dir_100m_tif}')

warp_options = gdal.WarpOptions(
    format='GTiff',
    width=ref100_w,
    height=ref100_h,
    outputBounds=[ref100_xmin, ref100_ymin, ref100_xmax, ref100_ymax],
    dstSRS=ref100_srs,
    resampleAlg=gdal.GRA_Bilinear,
    srcNodata=float('nan'),
    dstNodata=float('nan'),
    creationOptions=['BIGTIFF=YES', 'COMPRESS=LZW', 'PREDICTOR=3', 'TILED=YES'],
    multithread=True,
)
gdal.Warp(wind_dir_100m_tif, wind_dir_10m_path, options=warp_options)
print(f'  -> {wind_dir_100m_tif}')

# ================================================================
# Step 2: 导入 DEM (100m) 到 SAGA 格式
# ================================================================
print('\n=== Step 2/6: Import DEM (100m) to SAGA format ===')
run_saga(
    ['io_gdal', '0', '-FILES', dem_100m_path, '-GRIDS', dem_sgrd],
    'Import DEM'
)

# ================================================================
# Step 3: 导入风向 (100m) 到 SAGA 格式
# ================================================================
print('\n=== Step 3/6: Import wind direction (100m) to SAGA format ===')
run_saga(
    ['io_gdal', '0', '-FILES', wind_dir_100m_tif, '-GRIDS', wind_dir_sgrd],
    'Import wind direction'
)

# ================================================================
# Step 4: Wind Effect 计算 (100m)
# ================================================================
print('\n=== Step 4/6: Compute Wind Effect on 100m grids ===')
run_saga(
    ['ta_morphometry', '15',
     '-DEM', f'{dem_sgrd}.sgrd',
     '-DIR', f'{wind_dir_sgrd}.sgrd',
     '-DIR_UNITS', '1',
     '-MAXDIST', str(max_dist),
     '-ACCEL', str(accel),
     '-EFFECT', f'{wind_effect_sgrd}.sgrd'],
    'Wind Effect'
)

# ================================================================
# Step 5: 导出 Wind Effect → 100m GeoTIFF
# ================================================================
print('\n=== Step 5/6: Export Wind Effect to 100m GeoTIFF ===')
if os.path.exists(wind_effect_100m_tif):
    os.remove(wind_effect_100m_tif)
run_saga(
    ['io_gdal', '2',
     '-GRIDS', f'{wind_effect_sgrd}.sgrd',
     '-FILE', wind_effect_100m_tif],
    'Export 100m GeoTIFF'
)

# ================================================================
# Step 6: Wind Effect 100m → 10m 回升 (与 10m DEM 严格对齐)
# ================================================================
print('\n=== Step 6/6: Upsample Wind Effect 100m → 10m ===')
if os.path.exists(wind_effect_10m_tif):
    os.remove(wind_effect_10m_tif)
print(f'  Input:  {wind_effect_100m_tif}')
print(f'  Ref:    {dem_10m_path}')
print(f'  Output: {wind_effect_10m_tif}')

upsample_options = gdal.WarpOptions(
    format='GTiff',
    width=ref10_w,
    height=ref10_h,
    outputBounds=[ref10_xmin, ref10_ymin, ref10_xmax, ref10_ymax],
    dstSRS=ref10_srs,
    resampleAlg=gdal.GRA_Bilinear,
    srcNodata=float('nan'),
    dstNodata=float('nan'),
    creationOptions=['BIGTIFF=YES', 'COMPRESS=LZW', 'PREDICTOR=3', 'TILED=YES'],
    multithread=True,
)
gdal.Warp(wind_effect_10m_tif, wind_effect_100m_tif, options=upsample_options)
print(f'  -> {wind_effect_10m_tif}')

# 清理 100m 中间文件
for tmp in [wind_dir_100m_tif, wind_effect_100m_tif]:
    if os.path.exists(tmp):
        os.remove(tmp)
        print(f'  Cleaned: {tmp}')

print(f'\nWind effect output: {wind_effect_10m_tif}')
print('Done.')
