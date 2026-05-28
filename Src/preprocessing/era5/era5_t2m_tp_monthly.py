# @Author  : ChaoQiezi
# @Time    : 2026/4/2
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_t2m_tp_monthly.py

"""
This script is used to 将ERA5-Land的zip文件解压为nc文件, 并提取逐月的t2m和tp输出为GeoTIFF文件

ERA5-Land数据说明:
- 分辨率: 0.1°
- 变量: t2m(2米气温, 单位K), tp(总降水量, 单位m)
- 时间维度: 12个月(1-12月)
- 空间范围: 96°E-106°E, 24°N-36°N (川西及周边)

单位转换:
- t2m: K -> °C (减去273.15)
- tp: m -> mm (乘以1000)

由于重投影和重采样(10m)精度过高总是存在显示异常, 且压缩率不如ArcGIS Pro高
因此这里不进行这两步操作, 仅输出为WGS84坐标系的GeoTIFF文件(0.1°)
后续使用ArcGIS Pro的模型构建器或QGIS的对齐栅格工具进行重投影和重采样
"""

from glob import glob
import os
import sys

import netCDF4 as nc
import numpy as np

from qiezi import extract_nodata_value, write_tiff
from qiezi.common import zip2nc

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import geotransform_from_center_coords


# 准备
in_dir = r'I:\DataHub\ERA5\ERA5-Land\Chuanxi\t2m_tp'
out_t2m_dir = r'E:\GeoProjects\dry_hot_valley\ERA5\t2m\monthly'
out_tp_dir = r'E:\GeoProjects\dry_hot_valley\ERA5\tp\monthly'
start_year = 2019
end_year = 2025
out_nc_dir = in_dir  # 解压后的nc文件放在同目录下
proj4_str = '+proj=longlat +datum=WGS84 +no_defs'

# 创建输出目录
os.makedirs(out_t2m_dir, exist_ok=True)
os.makedirs(out_tp_dir, exist_ok=True)

# 遍历zip文件并解压
zip_wildcard = os.path.join(in_dir, '*.zip')
zip_paths = glob(zip_wildcard)
for cur_zip_path in zip_paths:
    # 解压zip文件
    out_nc_name = os.path.basename(cur_zip_path).replace('.zip', '.nc')
    out_nc_path = os.path.join(out_nc_dir, out_nc_name)
    if os.path.exists(out_nc_path):
        print(f'NC file already exists, skip: {out_nc_name}')
        continue
    zip2nc(cur_zip_path, out_dir=out_nc_dir, nc_name=out_nc_name)
    print(f'Unzipped: {out_nc_name}')

# 逐年提取月均t2m和tp
geo_transform = None  # 地理变换参数, 基于ERA5像元中心坐标换算到左上角
for cur_year in range(start_year, end_year + 1):
    # 获取当前年份的nc文件路径
    nc_wildcard = os.path.join(out_nc_dir, f'{cur_year}*.nc')
    cur_nc_paths = glob(nc_wildcard)
    if len(cur_nc_paths) != 1:
        print(f'Year {cur_year} has {len(cur_nc_paths)} nc files, skip.')
        continue
    cur_nc_path = cur_nc_paths[0]

    # 读取nc文件
    with nc.Dataset(cur_nc_path, 'r') as ds:
        # 读取全年12个月的t2m和tp, shape=(12, rows, cols)
        t2m_cur = ds.variables['t2m'][:]  # 单位: K
        tp_cur = ds.variables['tp'][:]  # 单位: m

        # 只在第一年获取和保留地理参数
        if geo_transform is None:
            lon = ds.variables['longitude'][:]
            lat = ds.variables['latitude'][:]
            geo_transform = geotransform_from_center_coords(lon, lat)

    # 单位转换
    t2m_cur = t2m_cur - 273.15  # K -> °C
    tp_cur = tp_cur * 1000  # m -> mm

    # 处理可能存在的NaN(ERA5-Land的_FillValue为NaN)
    t2m_nodata = extract_nodata_value(t2m_cur.dtype)
    tp_nodata = extract_nodata_value(tp_cur.dtype)
    t2m_cur = np.where(np.isnan(t2m_cur), t2m_nodata, t2m_cur)
    tp_cur = np.where(np.isnan(tp_cur), tp_nodata, tp_cur)

    # 逐月输出为GeoTIFF
    for month_ix in range(12):
        month_str = f'{month_ix + 1:02d}'  # 01, 02, ..., 12
        band_name = f'{cur_year}_{month_str}'

        # 输出t2m
        cur_t2m = t2m_cur[month_ix, :, :]  # shape=(rows, cols)
        cur_t2m_path = os.path.join(out_t2m_dir, f't2m_{cur_year}_{month_str}_0.1deg.tif')
        write_tiff(cur_t2m_path, cur_t2m, geo_transform, proj4_str=proj4_str,
                   band_names=[band_name], nodata_value=t2m_nodata)

        # 输出tp
        cur_tp = tp_cur[month_ix, :, :]  # shape=(rows, cols)
        cur_tp_path = os.path.join(out_tp_dir, f'tp_{cur_year}_{month_str}_0.1deg.tif')
        write_tiff(cur_tp_path, cur_tp, geo_transform, proj4_str=proj4_str,
                   band_names=[band_name], nodata_value=tp_nodata)

    print(f'Year {cur_year}: 12 months extracted for t2m and tp.')

print('Monthly extraction completed.')
