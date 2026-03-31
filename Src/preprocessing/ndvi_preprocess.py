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
import dask
import rasterio as rio
import rioxarray as rxr
from osgeo import gdal
from dask.distributed import Client, LocalCluster, Lock
from dask.utils import SerializableLock
from dask.diagnostics import ProgressBar
from glob import glob

from qiezi import img_reproject, warp_by_tiff, build_overviews, compute_statistics, extract_nodata_value

write_lock = SerializableLock()  # 其保证的是每一个进程同一时刻只有一个线程在写入文件(避免多进程, 否则报错)
# write_lock = Lock('remove_invalid_values_lock')
def remove_invalid_values(img_path):
    # 输出设置
    chunk_size = 4096
    dst_out_path = img_path.replace('.tif', '_valid.tif')
    with rio.open(img_path, 'r') as src:
        out_profile = src.profile.copy()
        src_nodata = src.nodata

    # 读取栅格和元数据
    # rds = rxr.open_rasterio(img_path, chunks=chunk_size, masked=True, lock=False)
    rds = rxr.open_rasterio(img_path, chunks=chunk_size, lock=False)
    rds = rds.squeeze().drop_vars(['band'])  # 剔除band维度s

    # 剔除无效值
    nodata_value = extract_nodata_value(rds.dtype)
    # # 原本的掩膜
    # rds = rds.where(rds != src_nodata, nodata_value)
    # 剔除小于0.1的NDVI
    rds = rds.where(rds > 0.1, nodata_value)  # 剔除无效值

    # 输出
    out_profile.update({
        "tiled": True,
        "nodata": nodata_value,
        "compress": 'deflate',
        'bigtiff': 'yes',  # 超过4GB需设置为BIGTIFF文件
        "predictor": 3,
        "zlevel": 9,
        "sparse_ok": True,})
    rds.rio.write_nodata(nodata_value, encoded=True, inplace=True)  # 写入无效值
    import threading
    with dask.config.set(scheduler="synchronous"): # 在此范围内的代码执行均只在线程中进行.
        with ProgressBar():
            rds.rio.to_raster(
                dst_out_path,
                windowed=True,
                lock=threading.Lock(),
                **out_profile,
            )
    rds.close()

    build_overviews(dst_out_path)
    compute_statistics(dst_out_path)

    return dst_out_path

# 准备
in_dir = r'I:\DataWorkspace\NDVI\Sentinel-2\Chuanxi'
out_dir = r'G:\GeoProjects\dry_hot_valley\NDVI\Yearly\Temp'
ref_path = r"G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif"
out_res = 10  # 米/m
start_year = 2019
end_year = 2025
with rio.open(ref_path) as src:
    ref_meta = src.meta
    ref_srs = ref_meta['crs'].to_epsg()

if __name__ == '__main__':
    cluster = LocalCluster(n_workers=4, threads_per_worker=4, memory_limit='20GB')
    client = Client(cluster)
    print(f'client url: {client.dashboard_link}')

    # 迭代处理每年数据集
    for year in range(start_year, end_year + 1):
        # 输出设置
        dst_path = os.path.join(out_dir, f'NDVI_{year}.tif')
        if os.path.exists(dst_path):
            remove_invalid_values(dst_path)
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
                     compute_statistics=True, scale_factor=0.0001, post_process_hook=remove_invalid_values)
        # 删除镶嵌VRT文件
        os.remove(cur_mosaic_path)

        print(f'Year {year} done')
