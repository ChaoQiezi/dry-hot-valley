# @Author  : ChaoQiezi
# @Time    : 2026/3/25 上午11:00
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_spatial_distribution_interannual.py

"""
This script is used to 进行年际尺度的NDVI计算(空间上)
"""

import os
from glob import glob

import numpy as np
import rasterio as rio
import rioxarray as rxr
import xarray as xr
from dask.diagnostics import ProgressBar
from dask.distributed import Client, LocalCluster
from qiezi import build_overviews, compute_statistics

# 准备
in_dir = r'G:\GeoProjects\dry_hot_valley\NDVI\Yearly'
out_path = r'G:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif'
chunk_size = 4096

if __name__ == '__main__':
    # 初始化Dask集群
    cluster = LocalCluster(n_workers=2, threads_per_worker=1, memory_limit='12GB')
    client = Client(cluster)
    print(f'client url: {client.dashboard_link}')
    # 检索
    img_paths = glob(os.path.join(in_dir, '*.tif'))

    # 整合
    src_imgs = []
    for cur_img_path in img_paths:
        cur_img = rxr.open_rasterio(cur_img_path, chunks=chunk_size, masked=True)
        cur_img = cur_img.squeeze().drop_vars(['band'])  # 剔除band维度
        src_imgs.append(cur_img)
    cube = xr.concat(src_imgs, dim='time')  # 合并时间维度
    # 获取地理等参数
    with rio.open(img_paths[0], 'r') as src:
        out_profile = src.profile.copy()
    out_profile.update(
        {
            "bigtiff": "yes",       # 大文件支持
            "tiled": True,          # 开启内部切片
            "blockxsize": chunk_size,  # 设置切片宽度
            "blockysize": chunk_size,  # 设置切片高度
            "compress": "deflate",   # 压缩算法 (小写字符串)
        }
    )
    # 计算均值
    mean_img = cube.mean(dim='time')

    # 输出
    mean_img.rio.write_nodata(out_profile['nodata'], encoded=True, inplace=True)  # 写入无效值, 进行均值处理后无效值为None
    with ProgressBar():
        mean_img.rio.to_raster(
            out_path,
            windowed=True,
            lock=True,
            **out_profile,
        )

    # 后处理
    build_overviews(out_path)
    compute_statistics(out_path)

    print(f'Output {os.path.basename(out_path)} done')
