# @Author  : ChaoQiezi
# @Time    : 2026/3/12 上午9:58
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_u_v_preprocess.py

"""
This script is used to 将ERA5的zip文件解压为nc文件, 并对月均u和v分别求取加权平均后计算月均风向

加权平均: 风速大的赋予更高权重, 公式即为:
u_weighted = sum(u_i * V_i) / sum(V_i), V_i = sqrt(u_i^2 + v_i^2) = 风速
v_weighted = sum(v_i * V_i) / sum(V_i), V_i = sqrt(u_i^2 + v_i^2) = 风速
"""

import os
import rasterio
from rasterio.plot import  show
from glob import glob
import netCDF4 as nc
import numpy as np
import zipfile  # 解压zip文件

from qiezi import write_tiff
from qiezi.common import zip2nc
from qiezi.stats import wind_direction_cal


# 准备
in_dir = r'I:\DataHub\ERA5\ERA5\pressure_level\multi_var\backup'
out_dir = r'E:\Datasets\Objects\dry_hot_valley\wind_direction'
start_year = 2017
end_year = 2025
out_nc_dir = os.path.dirname(in_dir)
start_month = 6  # 6月份
end_month = 8  # 8月份
start_month_ix = start_month - 1
end_month_ix = end_month - 1
var_names = ['u', 'v']

# 遍历zip文件
zip_wildcard = os.path.join(in_dir, '*.zip')
zip_paths = glob(zip_wildcard)
for cur_zip_path in zip_paths:
    # 解压zip文件
    out_nc_name = os.path.basename(cur_zip_path).replace('.zip', '.nc')
    zip2nc(cur_zip_path, out_dir=out_nc_dir, nc_name=out_nc_name, cover=False)

# 计算月均u和v
for cur_year in range(start_year, end_year+1):
    # 获取当前年份的nc文件
    nc_wildcard = os.path.join(out_nc_dir, f'{cur_year}*.nc')
    cur_nc_path = glob(nc_wildcard)
    if len(cur_nc_path) != 1:
        print(f'Year {cur_year} has {len(cur_nc_path)} nc files, skip.')
        continue
    cur_nc_path = cur_nc_path[0]

    # 读取nc文件
    with nc.Dataset(cur_nc_path, 'r') as ds:
        # 读取u和v
        u = ds.variables['u'][start_month_ix:end_month_ix+1, :, :, :]  # shape=(month, pressure_level, rows, cols)
        v = ds.variables['v'][start_month_ix:end_month_ix+1, :, :, :]
        # 获取地理参数
        lon = ds.variables['longitude'][:]
        lat = ds.variables['latitude'][:]
        lon_res = lon[1] - lon[0]
        lat_res = lat[0] - lat[1]
        lon_min, lat_max = lon.min(), lat.max()
        geo_transform = (lon_min, lon_res, 0, lat_max, 0, -lat_res)  # gdal标准
        proj4_str = '+proj=longlat +datum=WGS84 +no_defs'
        # 获取pressure_level
        pressure_levels = ds.variables['pressure_level'][:]
        pressure_levels = pressure_levels.astype(str)
    # 计算风速
    V = np.sqrt(u**2 + v**2)
    V_sum = np.sum(V, axis=0)
    weight = V / V_sum[np.newaxis, :, :, :]
    # 计算生长季的u和v均值
    u_grow = np.sum(u * weight, axis=0)
    v_grow = np.sum(v * weight, axis=0)
    # 计算生长季的风向
    wind_dir_grow = wind_direction_cal(u_grow, v_grow)

    # 输出当前年份生长季的风向均值tif
    cur_out_filename = f'{cur_year}_{start_month:02d}_{end_month:02d}_wind_dir.tif'
    cur_out_path = os.path.join(out_dir, cur_out_filename)
    write_tiff(cur_out_path, wind_dir_grow, geo_transform, proj4_str=proj4_str, band_names=pressure_levels)

    print(f'{cur_year}: 已输出{cur_out_filename}')
