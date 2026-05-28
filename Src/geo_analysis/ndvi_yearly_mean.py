# @Author  : ChaoQiezi
# @Time    : 2026/3/25 上午10:59
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_yearly_mean.py

"""
This script is used to 进行年尺度的NDVI值计算(时间上)

计算每一年栅格矩阵的NDVI均值, 要记得计算标准差;
"""

import os
from glob import glob

import numpy as np
import pandas as pd
import rasterio as rio
import rioxarray as rxr
import xarray as xr
from dask.diagnostics import ProgressBar
from dask.distributed import Client, LocalCluster
from qiezi import build_overviews, compute_statistics

# 准备
in_dir = r'G:\GeoProjects\dry_hot_valley\NDVI\Yearly'
out_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_yearly_mean.xlsx'
start_year = 2019
end_year = 2025
chunk_size = {'x': 4096, 'y': 4096}

if __name__ == '__main__':
    # 初始化Dask集群
    cluster = LocalCluster(n_workers=4, threads_per_worker=4, memory_limit='8GB')
    client = Client(cluster)
    print(f'client url: {client.dashboard_link}')

    # 迭代处理每年数据集
    records = []
    for cur_year in range(start_year, end_year + 1):
        # 当前年份文件路径
        cur_path = os.path.join(in_dir, f'NDVI_{cur_year}.tif')
        if not os.path.exists(cur_path):
            print(f'File {os.path.basename(cur_path)} not found, skip')
            continue

        # 读取数据
        with rxr.open_rasterio(cur_path, chunks=chunk_size, masked=True) as rds:

            # 计算均值
            pixel_mean = rds.mean().compute().item()
            # 计算标准差
            pixel_std = rds.std().compute().item()
            # 计算变异系数
            pixel_cv = pixel_std / pixel_mean

            # 存储
            records.append({
                'year': cur_year,
                'mean': pixel_mean,
                'std': pixel_std,
                'cv': pixel_cv,
            })

    # 关闭Dask集群
    client.close()
    cluster.close()

    # 输出为excel文件
    df = pd.DataFrame(records)
    df.to_excel(out_path, index=False)





