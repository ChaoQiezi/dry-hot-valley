# @Author  : ChaoQiezi
# @Time    : 2026/3/18 上午1:39
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: windward_leeward_divide.py

"""
This script is used to 基于SAGA GIS计算的wind effect(windward, leeward)风效应指数进行二分类, 获得
生长季内迎风坡和背风坡的二分类结果: 1为迎风坡, 2为背风坡
"""

import rasterio as rio
import numpy as np
import xarray as xr
import rioxarray as rxr
from dask.distributed import Client, LocalCluster, Lock

from qiezi import build_overviews


if __name__ == '__main__':
    # 准备
    cluster = LocalCluster(n_workers=4, threads_per_worker=4, memory_limit='8GB')
    client = Client(cluster)
    print('Client:', client.dashboard_link)
    wind_effect_path = r'G:\GeoProjects\dry_hot_valley\wind_effect\wind_effect.tif'
    out_path = r'G:\GeoProjects\dry_hot_valley\windward_leeward\windward_leeward.tif'
    chunks = 1024 * 2


    # 读取
    wind_effect = rxr.open_rasterio(wind_effect_path, chunks=chunks, masked=True)
    with rio.open(wind_effect_path) as src:
        origin_profile = src.profile.copy()
    out_profile = {  # 输出参数
                _k: _v for _k, _v in origin_profile.items()
                if _k not in ['transform', 'crs', 'dtype', 'nodata', 'height', 'width', 'count']  # 该部分参数rxr会自行进行更新
            }
    out_profile['tiled'] = True
    out_profile['blockxsize'] = chunks
    out_profile['blockysize'] = chunks
    out_profile['compress'] = out_profile.get('compress', 'lzw')
    # 二分类
    wind_effect_class = xr.where(wind_effect > 1, 1, 2)
    wind_effect_class = xr.where(wind_effect.isnull(), 255, wind_effect_class)  # 无效值设置
    wind_effect_class = wind_effect_class.astype(np.uint8)
    wind_effect_class.rio.write_crs(wind_effect.rio.crs, inplace=True)  # 防止部分元数据丢失
    wind_effect_class.rio.write_nodata(255, encoded=True, inplace=True)

    # 输出
    wind_effect_class.rio.to_raster(
        out_path,
        windowed=True,  # 窗口写入，避免内存溢出
        lock=Lock("rio-write-lock"),
        **out_profile
    )
    build_overviews(out_path)  # 创建金字塔
