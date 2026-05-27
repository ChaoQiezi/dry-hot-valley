# @Author  : ChaoQiezi
# @Time    : 2026/5/22
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: saga_wind_effect.py

"""
SAGA GIS Wind Effect 计算 - 100m DEM 降采样方案

西南地区 10m DEM ~206 亿像素, SAGA Wind Effect 需要 ~85 GB 内存, 不可行.
ERA5 风向为 0.25° (~25 km), 100m DEM 已为 250 倍过采样.

流程:
  1. 风向 10m -> 100m 降采样 (gdal.Warp, Bilinear)
  2. SAGA Wind Effect 在 100m 上直接读写 GeoTIFF
  3. Wind Effect 100m -> 10m 回升, 严格对齐 10m DEM

参考文献: Bohner & Antonic (2009), Geomorphometry, Elsevier.
"""

import os
import subprocess

from osgeo import gdal, gdalconst

from qiezi.geo import build_overviews

# ======================== Configuration ========================
saga_cmd = r'D:\Softwares\saga-9.11.3_msw\saga_cmd.exe'
dem_100m_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_100m_proj_xinan_region.tif'
dem_10m_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_10m_proj_xinan_region.tif'
wind_dir_10m_path = r'G:\GeoProjects\dry_hot_valley\wind_direction\10m\wind_dir_600hPa_10m.tif'
wind_effect_dir = r'G:\GeoProjects\dry_hot_valley\wind_effect'

wind_dir_100m_tif = os.path.join(wind_effect_dir, 'wind_dir_100m.tif')
wind_effect_100m_tif = os.path.join(wind_effect_dir, 'wind_effect_100m.tif')
wind_effect_10m_tif = os.path.join(wind_effect_dir, 'wind_effect.tif')

max_dist = 300.0    # 搜索距离 [km]
accel = 1.5         # 加速度因子
chunks = 4096
saga_nodata = -99999.0
# ================================================================

os.makedirs(wind_effect_dir, exist_ok=True)
gdal.DontUseExceptions()


def run_saga(tool_args, description='SAGA command'):
    """运行 SAGA 命令, 失败时立即停止, 避免继续使用旧输出。"""
    cmd = [saga_cmd] + tool_args
    print(f'Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'[ERROR] {description} returned {result.returncode}')
        if result.stdout.strip():
            print(result.stdout.strip()[-1000:])
        if result.stderr.strip():
            print(result.stderr.strip()[-1000:])
        raise RuntimeError(f'{description} failed.')

    print('  -> OK')
    return result


def read_grid_info(path):
    """读取 GDAL 栅格的尺寸、投影、transform 和 bounds。"""
    ds = gdal.Open(path)
    if ds is None:
        raise FileNotFoundError(path)

    width = ds.RasterXSize
    height = ds.RasterYSize
    transform = ds.GetGeoTransform()
    info = {
        'width': width,
        'height': height,
        'srs': ds.GetProjection(),
        'transform': transform,
        'bounds': [
            transform[0],
            transform[3] + transform[5] * height,
            transform[0] + transform[1] * width,
            transform[3],
        ],
    }
    ds = None
    return info


def remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)


def warp_or_raise(out_path, in_path, options, description):
    ds = gdal.Warp(out_path, in_path, options=options)
    if ds is None:
        raise RuntimeError(f'{description} failed.')
    ds = None


# ================================================================
# Step 0: 读取参考栅格参数 (100m DEM, 10m DEM)
# ================================================================
ref100 = read_grid_info(dem_100m_path)
ref10 = read_grid_info(dem_10m_path)

# ================================================================
# Step 1: 风向 10m -> 100m 降采样 (与 100m DEM 严格对齐)
# ================================================================
if not os.path.exists(wind_dir_10m_path):
    raise FileNotFoundError(f'Wind direction not found: {wind_dir_10m_path}')

print('=== Step 1/3: Downsample wind direction 10m -> 100m ===')
print(f'  Input:  {wind_dir_10m_path}')
print(f'  Output: {wind_dir_100m_tif}')

remove_if_exists(wind_dir_100m_tif)
warp_options = gdal.WarpOptions(
    format='GTiff',
    width=ref100['width'],
    height=ref100['height'],
    outputBounds=ref100['bounds'],
    dstSRS=ref100['srs'],
    resampleAlg=gdal.GRA_Bilinear,
    srcNodata=float('nan'),
    dstNodata=float('nan'),
    outputType=gdalconst.GDT_Float32,
    creationOptions=[
        'BIGTIFF=YES',
        'COMPRESS=LZW',
        'PREDICTOR=3',
        'TILED=YES',
    ],
    multithread=True,
)
warp_or_raise(wind_dir_100m_tif, wind_dir_10m_path, warp_options, 'Downsample wind direction')
print(f'  -> {wind_dir_100m_tif}')

# ================================================================
# Step 2: SAGA Wind Effect 计算 (100m GeoTIFF 直进直出)
# ================================================================
print('\n=== Step 2/3: Compute Wind Effect on 100m GeoTIFF grids ===')
remove_if_exists(wind_effect_100m_tif)
run_saga(
    ['ta_morphometry', '15',
     '-DEM', dem_100m_path,
     '-DIR', wind_dir_100m_tif,
     '-DIR_UNITS', '1',
     '-MAXDIST', str(max_dist),
     '-ACCEL', str(accel),
     '-EFFECT', wind_effect_100m_tif],
    'Wind Effect'
)

# ================================================================
# Step 3: Wind Effect 100m -> 10m 回升 (与 10m DEM 严格对齐)
# ================================================================
print('\n=== Step 3/3: Upsample Wind Effect 100m -> 10m ===')
remove_if_exists(wind_effect_10m_tif)
print(f'  Input:  {wind_effect_100m_tif}')
print(f'  Ref:    {dem_10m_path}')
print(f'  Output: {wind_effect_10m_tif}')

upsample_options = gdal.WarpOptions(
    format='GTiff',
    width=ref10['width'],
    height=ref10['height'],
    outputBounds=ref10['bounds'],
    dstSRS=ref10['srs'],
    resampleAlg=gdal.GRA_Bilinear,
    srcNodata=saga_nodata,
    dstNodata=float('nan'),
    outputType=gdalconst.GDT_Float32,
    creationOptions=[
        'BIGTIFF=YES',
        'COMPRESS=LZW',
        'PREDICTOR=3',
        'TILED=YES',
        f'BLOCKXSIZE={chunks}',
        f'BLOCKYSIZE={chunks}',
    ],
    multithread=True,
)
warp_or_raise(wind_effect_10m_tif, wind_effect_100m_tif, upsample_options, 'Upsample wind effect')
print(f'  -> {wind_effect_10m_tif}')

build_overviews(wind_effect_10m_tif)

print(f'\nWind effect output: {wind_effect_10m_tif}')
print('Done.')
