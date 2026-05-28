# @Author  : ChaoQiezi
# @Time    : 2026/3/13 下午2:31
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_mean_total.py

"""
This script is used to 基于NDVI年际均值栅格, 分别计算迎风坡和背风坡的NDVI均值

console output:

NDVI mean: 0.7345
WW mean: 0.7111
LW mean: 0.7570
"""

import rasterio as rio
import rioxarray as rxr
from dask.distributed import Client, LocalCluster

# 准备
ndvi_path = r"E:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif"
dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_10m_projected.tif"
direction_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"  # 二值栅格: 1=迎风坡, 2=背风坡
out_path = r'E:\GeoProjects\dry_hot_valley\Output\Table\NDVI_elevation_gradient.xlsx'
WINDWARD_VAL = 1
LEEWARD_VAL = 2
chunk_size = {'x': 4096, 'y': 4096}

if __name__ == '__main__':
    # ------ 初始化Dask集群 ------
    cluster = LocalCluster(n_workers=6, threads_per_worker=8, memory_limit='6GB')
    client = Client(cluster)
    print(f'Dask dashboard: {client.dashboard_link}')

    # 读取
    da_ndvi = rxr.open_rasterio(ndvi_path, masked=True, chunks=chunk_size)
    da_direction = rxr.open_rasterio(direction_path, masked=True, chunks=chunk_size)

    # 计算迎风坡和背风坡的均值
    ndvi_mean = da_ndvi.mean().compute()
    ww_mean = da_ndvi.where(da_direction == WINDWARD_VAL).mean().compute()
    lw_mean = da_ndvi.where(da_direction == LEEWARD_VAL).mean().compute()

    # 输出
    print(f'NDVI mean: {ndvi_mean:.4f}')
    print(f'WW mean: {ww_mean:.4f}')
    print(f'LW mean: {lw_mean:.4f}')

    # 释放资源
    client.close()
    cluster.close()

"""
console output:

WW mean: 0.7111
LW mean: 0.7570
"""

