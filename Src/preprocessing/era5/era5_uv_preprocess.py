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

由于重投影和重采样(10m)精度过高总是存在显示异常，且压缩率不如A如此GIS Pro高(川西地区10m分辨率仅300MB)
因此这里不进行这两步操作，仅输出为WGS84坐标系的geotiff文件(0.25°)

我目前是使用ArcGIS Pro的模型构建器进行处理;
但QGIS其实有专门的工具实现这一操作: 对齐栅格(包括重采样和重投影)
"""

import os
import sys
import rasterio
from rasterio.plot import show
from glob import glob
from osgeo import gdal
import netCDF4 as nc
import numpy as np
import zipfile  # 解压zip文件

from qiezi import write_tiff
from qiezi.stats import wind_direction_cal
from qiezi.common import zip2nc

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import geotransform_from_center_coords


# 准备
in_dir = r'I:\DataHub\ERA5\ERA5\pressure_level\multi_var'
out_uv_dir = r'G:\GeoProjects\dry_hot_valley\u_v\0.25deg'
out_directon_dir = r'G:\GeoProjects\dry_hot_valley\wind_direction\0.25deg'
img_ref_path = r"G:\GeoProjects\dry_hot_valley\geo_factor\DEM\xinan\elevation_10m_proj_xinan_region.tif"
start_year = 2019
end_year = 2025
out_nc_dir = os.path.dirname(in_dir)
start_month = 5  # 5月份
end_month = 9  # 9月份
start_month_ix = start_month - 1
end_month_ix = end_month - 1
proj4_str = '+proj=longlat +datum=WGS84 +no_defs'

# 遍历zip文件
zip_wildcard = os.path.join(in_dir, '*.zip')
zip_paths = glob(zip_wildcard)
for cur_zip_path in zip_paths:
    # 解压zip文件
    out_nc_name = os.path.basename(cur_zip_path).replace('.zip', '.nc')
    zip2nc(cur_zip_path, out_dir=out_nc_dir, nc_name=out_nc_name)

# 计算多年际+多月份的uv加权均值
u_numerator_sum = None  # u方向的分子加权和, shape=(pressure_level, rows, cols)
v_numerator_sum = None  # v方向的分子加权和, shape=(pressure_level, rows, cols)
wind_speed_denominator_sum = None  # 风速分母和, shape=(pressure_level, rows, cols)
geo_transform = None  # 地理变换参数, 基于ERA5像元中心坐标换算到左上角
lon = None  # 经度
lat = None  # 纬度
pressure_levels = None  # 压力层级, shape=(pressure_level,)
for cur_year in range(start_year, end_year+1):
    # 获取当前年份的nc文件路径
    nc_wildcard = os.path.join(out_nc_dir, f'{cur_year}*.nc')
    cur_nc_paths = glob(nc_wildcard)
    if len(cur_nc_paths) != 1:
        print(f'Year {cur_year} has {len(cur_nc_paths)} nc files, skip.')
        continue
    cur_nc_path = cur_nc_paths[0]

    # 读取nc文件
    with nc.Dataset(cur_nc_path, 'r') as ds:
        # 读取指定月份区间的 u 和 v, shape=(month, pressure_level, rows, cols)
        u_cur = ds.variables['u'][start_month_ix:end_month_ix+1, :, :, :]
        v_cur = ds.variables['v'][start_month_ix:end_month_ix+1, :, :, :]
        
        # 只在第一年获取和保留地理参数和层级信息
        if geo_transform is None:
            lon = ds.variables['longitude'][:]
            lat = ds.variables['latitude'][:]
            geo_transform = geotransform_from_center_coords(lon, lat)
            
            pressure_levels = ds.variables['pressure_level'][:]
            pressure_levels = [f'{_p:.0f}' for _p in pressure_levels]

    # 计算当前时间块的风速 (作为权重), shape=(month, pressure_level, rows, cols)
    V_cur = np.sqrt(u_cur**2 + v_cur**2)
    
    # 将时间维度(第一维: month)合并加总到分子和分母中
    if u_numerator_sum is None:
        u_numerator_sum = np.sum(u_cur * V_cur, axis=0)
        v_numerator_sum = np.sum(v_cur * V_cur, axis=0)
        wind_speed_denominator_sum = np.sum(V_cur, axis=0)
    else:
        u_numerator_sum += np.sum(u_cur * V_cur, axis=0)
        v_numerator_sum += np.sum(v_cur * V_cur, axis=0)
        wind_speed_denominator_sum += np.sum(V_cur, axis=0)

    print(f'Year {cur_year} processed.')

# 计算最终的生长季/多年 u和v均值，shape=(pressure_level, rows, cols)
valid_mask = wind_speed_denominator_sum > 0  # 避免分母为0的情况（无风）
u_grow = np.zeros_like(u_numerator_sum)
v_grow = np.zeros_like(v_numerator_sum)
u_grow[valid_mask] = u_numerator_sum[valid_mask] / wind_speed_denominator_sum[valid_mask]
v_grow[valid_mask] = v_numerator_sum[valid_mask] / wind_speed_denominator_sum[valid_mask]

# 输出
for pressure_ix, pressure_level in enumerate(pressure_levels):
    cur_u_grow = u_grow[pressure_ix, :, :]
    cur_v_grow = v_grow[pressure_ix, :, :]
    # 计算生长季/多年的风向
    cur_dir_grow = wind_direction_cal(cur_u_grow, cur_v_grow)

    # 输出为地理坐标系下的u和v
    cur_u_path = os.path.join(out_uv_dir, f'u_{pressure_level}hPa_0.25deg.tif')
    cur_v_path = os.path.join(out_uv_dir, f'v_{pressure_level}hPa_0.25deg.tif')
    cur_dir_path = os.path.join(out_directon_dir, f'wind_dir_{pressure_level}hPa_0.25deg.tif')
    write_tiff(cur_u_path, cur_u_grow, geo_transform, proj4_str=proj4_str, band_names=[pressure_level])
    write_tiff(cur_v_path, cur_v_grow, geo_transform, proj4_str=proj4_str, band_names=[pressure_level])
    write_tiff(cur_dir_path, cur_dir_grow, geo_transform, proj4_str=proj4_str, band_names=[pressure_level])
    # # 投影转换
    # out_u_path = os.path.join(out_dir, f'u_{pressure_level}hPa_10m_projected.tif')
    # out_v_path = os.path.join(out_dir, f'v_{pressure_level}hPa_10m_projected.tif')
    # warp_by_tiff(out_u_path, u_temp_path, img_ref_path)
    # warp_by_tiff(out_v_path, v_temp_path, img_ref_path)

    # temp_paths.append(u_temp_path)
    # temp_paths.append(v_temp_path)
    print(f'Pressure level {pressure_level} processed.')

print(f'Projection completed.')
