# @Author  : ChaoQiezi
# @Time    : 2026/3/18 下午9:10
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_preprocess.py

"""
This script is used to 对GEE下载的NDVI数据进行预处理

预处理包括: 镶嵌、重投影和重采样、裁剪掩膜、比例缩放

目前的流程是:
1. 基于同年tif文件创建镶嵌VRT文件, 基于镶嵌的VRT文件进行重投影和重采样(横轴墨卡托, 10m);
2. 接着对获取得到的geotiff文件进行裁剪和掩膜(像元对齐), 同时进行比例缩放;
"""

import os
import numpy as np
import rasterio as rio
from osgeo import gdal
from dask.distributed import Client, LocalCluster
from glob import glob

from qiezi import img_reproject, warp_by_tiff, build_overviews, compute_statistics, extract_nodata_value


def remove_invalid_values(img_path):
    """缩放(Int16→Float32, ×0.0001)并过滤 NDVI≤0.1 无效值, 原地替换 (逐块读写)"""
    temp_path = os.path.join(os.path.dirname(img_path), f'_tmp_{os.path.basename(img_path)}')
    if os.path.exists(temp_path):
        os.remove(temp_path)

    with rio.open(img_path, 'r') as src:
        out_profile = src.profile.copy()
        out_profile.update({
            "dtype": np.float32,
            "tiled": True,
            "nodata": np.nan,
            "compress": 'deflate',
            'bigtiff': 'yes',
            "predictor": 3,
            "zlevel": 9,
            "sparse_ok": True,
        })
        block_windows = list(src.block_windows())

        with rio.open(temp_path, 'w', **out_profile) as dst:
            for _ji, window in block_windows:
                block = src.read(1, window=window, masked=True)
                block = block.astype(np.float32) * 0.0001
                block = np.where(block > 0.1, block, np.nan)
                dst.write(block, window=window, indexes=1)

    os.remove(img_path)
    os.rename(temp_path, img_path)
    return img_path

# 准备
in_dir = r'I:\DataWorkspace\NDVI\Sentinel-2\Xinan'
out_dir = r'E:\GeoProjects\dry_hot_valley\NDVI\Yearly'
ref_path = r"G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_10m_proj_xinan_region.tif"
out_res = 10  # 米/m
start_year = 2019
end_year = 2019
force_rerun = True  # True: 强制重跑

if __name__ == '__main__':
    cluster = LocalCluster(n_workers=4, threads_per_worker=4, memory_limit='20GB')
    client = Client(cluster)
    print(f'client url: {client.dashboard_link}')

    # 迭代处理每年数据集
    for year in range(start_year, end_year + 1):
        # 输出设置
        dst_path = os.path.join(out_dir, f'NDVI_{year}.tif')
        if os.path.exists(dst_path) and not force_rerun:
            print(f'File {os.path.basename(dst_path)} already exists, skip')
            continue
        # 检索
        cur_wildcard = os.path.join(in_dir, f'NDVI_{year}*.tif')
        img_paths = glob(cur_wildcard)
        if len(img_paths) == 0:
            print(f'No image found for year {year}')
            continue

        # 镶嵌(VRT虚拟镶嵌)
        cur_mosaic_path = os.path.join(out_dir, f'ndvi_mosaic_{year}.VRT')
        vrt_options = gdal.BuildVRTOptions(
            resampleAlg=gdal.GRA_NearestNeighbour
        )
        gdal.BuildVRT(cur_mosaic_path, img_paths, options=vrt_options)
        # 空间统一
        warp_by_tiff(dst_path, cur_mosaic_path, ref_path, cover=True, bigtiff=True, overview=True,
                     compute_statistics=True, post_process_hook=remove_invalid_values)
        # 删除镶嵌VRT文件
        os.remove(cur_mosaic_path)

        print(f'Year {year} done')
