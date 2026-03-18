# @Author  : ChaoQiezi
# @Time    : 2026/3/11 下午9:20
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: wind_direction_cal.py

"""
This script is used to 基于u和v计算风向和风速

数据量大, 因此通过rioxarray和dask流式处理, 避免内存溢出
"""

import os
import rasterio as rio
from rasterio.enums import Resampling
import rioxarray as rxr
import numpy as np
import dask.array as da
from dask.distributed import Client, LocalCluster, Lock

from qiezi.stats import wind_direction_cal
from qiezi.geo import build_overviews

if __name__ == '__main__':
    # 准备
    # cluster = LocalCluster(threads_per_worker=4, n_workers=4, memory_limit='8GB')
    # client = Client(cluster)
    # print('client dashboard:', client.dashboard_link)
    in_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\masked'
    # out_dir = r'G:\GeoProjects\dry_hot_valley\wind_direction'
    out_dir = r'E:\MyTEMP\wind_direction'
    pressure_levels = [500, 600, 700, 800]  # 气压层: pressure level, 单位: hPa
    chunks = 4096 * 2

    # 检索
    for cur_pressure_level in pressure_levels:
        # uv路径和输出路径
        cur_u_path = os.path.join(in_dir, f'u_{cur_pressure_level:.0f}hPa_10m.tif')
        cur_v_path = os.path.join(in_dir, f'v_{cur_pressure_level:.0f}hPa_10m.tif')
        if not (os.path.exists(cur_u_path) and os.path.exists(cur_v_path)):
            print(f'Pressure level {cur_pressure_level:.0f}hPa: u or v not exists!')
            continue
        cur_out_filename = f'wind_dir_{cur_pressure_level:.0f}hPa_10m.tif'
        cur_out_path = os.path.join(out_dir, cur_out_filename)
        if os.path.exists(cur_out_path):
            # 添加无效值属性
            with rio.open(cur_out_path, 'r+') as dst:
                dst.nodata = np.nan
            # build_overviews(cur_out_path)
            print(f'Pressure level {cur_pressure_level:.0f}hPa: wind direction already exists!')
            continue

        # 读取u和v
        u_grow = rxr.open_rasterio(cur_u_path, chunks=chunks, masked=True)
        v_grow = rxr.open_rasterio(cur_v_path, chunks=chunks, masked=True)
        with rio.open(cur_u_path, 'r') as u_ds:
            origin_profile = u_ds.profile.copy()
        # 计算风向
        wind_dir_grow = wind_direction_cal(u_grow, v_grow)

        # 输出当前年份生长季的风向均值tif

        out_profile = {  # 输出参数
            _k: _v for _k, _v in origin_profile.items()
            if _k not in ['transform', 'crs', 'dtype', 'nodata', 'height', 'width', 'count']  # 该部分参数rxr会自行进行更新
        }
        out_profile['tiled'] = True
        out_profile['blockxsize'] = chunks
        out_profile['blockysize'] = chunks
        out_profile['compress'] = out_profile.get('compress', 'lzw')
        wind_dir_grow.rio.to_raster(
            cur_out_path,
            windowed=True,  # 窗口写入，避免内存溢出
            lock=Lock("rio-write-lock"),
            **out_profile
        )
        build_overviews(cur_out_path)

        print(f'Pressure level {cur_pressure_level:.0f}hPa: wind direction calculation done.')

