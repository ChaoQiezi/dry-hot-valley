# @Author  : ChaoQiezi
# @Time    : 2026/5/15
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_uv_reproject_to_10m.py

"""
This script is used to 将生长季(5-9月)ERA5 0.25° u/v 重投影+重采样到10m Albers 等面积圆锥投影,
替代此前 ArcGIS Pro 手动操作。
"""

import os

from osgeo import gdal, gdalconst

from qiezi.geo import bound_from_transform, build_overviews

gdal.DontUseExceptions()

# Configuration
in_dir = r'G:\GeoProjects\dry_hot_valley\u_v\0.25deg'
out_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\unmasked'
ref_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_10m_proj_xinan_region.tif'
pressure_levels = [500, 600, 700, 800]
overwrite = True

os.makedirs(out_dir, exist_ok=True)

# 读取参考图像的地理参数
ref_ds = gdal.Open(ref_path)
ref_srs = ref_ds.GetProjection()
ref_width = ref_ds.RasterXSize
ref_height = ref_ds.RasterYSize
ref_transform = ref_ds.GetGeoTransform()
ref_bounds = bound_from_transform(ref_transform, ref_width, ref_height)
ref_ds = None

creation_options = [
    'BIGTIFF=YES',
    'TILED=YES',
    'BLOCKXSIZE=4096',
    'BLOCKYSIZE=4096',
    'COMPRESS=DEFLATE',
    'PREDICTOR=3',
    'SPARSE_OK=TRUE',
    'NUM_THREADS=ALL_CPUS',
]

for pressure_level in pressure_levels:
    for var_name in ['u', 'v']:
        in_path = os.path.join(in_dir, f'{var_name}_{pressure_level}hPa_0.25deg.tif')
        out_path = os.path.join(out_dir, f'{var_name}_{pressure_level}hPa_10m.tif')

        if not os.path.exists(in_path):
            print(f'Input not found: {in_path}, skip.')
            continue
        if os.path.exists(out_path) and not overwrite:
            print(f'Output exists: {out_path}, skip.')
            continue

        print(f'Reprojecting {var_name}_{pressure_level}hPa ...')

        warp_options = gdal.WarpOptions(
            format='GTiff',
            width=ref_width,
            height=ref_height,
            outputBounds=ref_bounds,
            dstSRS=ref_srs,
            dstNodata=-32768,
            outputType=gdalconst.GDT_Float32,
            resampleAlg=gdal.GRA_Bilinear,
            creationOptions=creation_options,
            multithread=True,
        )
        gdal.Warp(out_path, in_path, options=warp_options)

        build_overviews(out_path)
        print(f'  -> {out_path} done.')

print('All reprojections completed.')
