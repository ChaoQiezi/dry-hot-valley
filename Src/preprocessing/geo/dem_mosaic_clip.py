# @Author  : ChaoQiezi
# @Time    : 2026/5/19
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dem_mosaic_clip.py

"""
GLO-30 DEM/slope/aspect VRT 拼接 + 裁剪至西南地区外接矩形 (WGS84, ~30m, 不掩膜).

输入: I:\DataHub\GLO-30_DEM\{dem,slope,aspect}\*.tif
输出: G:\GeoProjects\dry_hot_valley\geo_factor\{DEM,Slope,Aspect}\xinan\*_30m_geo_xinan_region.tif
"""

import os
from glob import glob
from osgeo import gdal, gdalconst

gdal.DontUseExceptions()

# ======================== Configuration ========================
in_root = r'I:\DataHub\GLO-30_DEM'
out_root = r'G:\GeoProjects\dry_hot_valley\geo_factor'
temp_vrt_dir = r'E:\MyTemp'

# 西南地区外接矩形 [W, S, E, N] (LOG.MD 2026-05-18)
xinan_bbox = [92.1, 22.4, 106.6, 35.6]

data_types = {
    'DEM': {'subfolder': 'dem', 'out_name': 'elevation_30m_geo_xinan_region.tif'},
    'Slope': {'subfolder': 'slope', 'out_name': 'slope_30m_geo_xinan_region.tif'},
    'Aspect': {'subfolder': 'aspect', 'out_name': 'aspect_30m_geo_xinan_region.tif'},
}

overwrite = False
# ================================================================

os.makedirs(temp_vrt_dir, exist_ok=True)

creation_options = [
    'BIGTIFF=YES',
    'TILED=YES',
    'BLOCKXSIZE=4096',
    'BLOCKYSIZE=4096',
    'COMPRESS=DEFLATE',
    'PREDICTOR=3',
    'NUM_THREADS=ALL_CPUS',
]

for dtype, info in data_types.items():
    in_dir = os.path.join(in_root, info['subfolder'])
    out_dir = os.path.join(out_root, dtype, 'xinan')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, info['out_name'])

    if os.path.exists(out_path) and not overwrite:
        print(f'[{dtype}] {info["out_name"]} exists, skip.')
        continue

    # 检索输入
    tif_paths = sorted(glob(os.path.join(in_dir, '*.tif')))
    if not tif_paths:
        print(f'[{dtype}] No tif files found in {in_dir}, skip.')
        continue
    print(f'[{dtype}] Found {len(tif_paths)} tiles.')

    # Step 1: Build VRT
    vrt_path = os.path.join(temp_vrt_dir, f'{dtype.lower()}_xinan.vrt')
    print(f'[{dtype}] Building VRT ...')
    vrt_options = gdal.BuildVRTOptions(
        outputBounds=xinan_bbox,
        resampleAlg=gdal.GRA_Bilinear if dtype in ('DEM', 'Slope') else gdal.GRA_NearestNeighbour,
    )
    gdal.BuildVRT(vrt_path, tif_paths, options=vrt_options)

    # Step 2: Warp/clip to Xinan bounding rectangle (WGS84, ~30m, 不掩膜)
    print(f'[{dtype}] Clipping to Xinan rectangle (WGS84, no mask) ...')
    warp_options = gdal.WarpOptions(
        format='GTiff',
        outputBounds=xinan_bbox,
        outputBoundsSRS='EPSG:4326',
        dstSRS='EPSG:4326',
        xRes=None,  # 保持原始分辨率 (~30m)
        yRes=None,
        resampleAlg=gdal.GRA_Bilinear if dtype in ('DEM', 'Slope') else gdal.GRA_NearestNeighbour,
        creationOptions=creation_options,
        multithread=True,
        warpMemoryLimit=2048,  # 限制内存，避免强制逐块 I/O 退化
    )
    gdal.Warp(out_path, vrt_path, options=warp_options)

    # 清理 VRT
    os.remove(vrt_path)
    print(f'[{dtype}] -> {out_path}')

print('\nAll mosaic + clip operations completed.')
