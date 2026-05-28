# @Author  : ChaoQiezi
# @Time    : 2026/4/2
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_t2m_tp_yearly.py

"""
This script is used to 从ERA5-Land的nc文件中计算年均t2m和年总tp, 输出为GeoTIFF文件

年尺度聚合方式:
- t2m(2米气温): 12个月的算术平均值 (°C)
- tp(总降水量): 12个月的累加和 (mm)

注意: 本脚本依赖era5_land_monthly.py已完成解压操作(zip -> nc)
如果nc文件尚未解压, 请先运行era5_land_monthly.py

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

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import geotransform_from_center_coords

# 准备
in_nc_dir = r'I:\DataHub\ERA5\ERA5-Land\Chuanxi\t2m_tp'
out_t2m_dir = r'E:\GeoProjects\dry_hot_valley\ERA5\t2m\yearly'
out_tp_dir = r'E:\GeoProjects\dry_hot_valley\ERA5\tp\yearly'
start_year = 2019
end_year = 2025
proj4_str = '+proj=longlat +datum=WGS84 +no_defs'

# 创建输出目录
os.makedirs(out_t2m_dir, exist_ok=True)
os.makedirs(out_tp_dir, exist_ok=True)

# 逐年计算年均t2m和年总tp
geo_transform = None  # 地理变换参数, 基于ERA5像元中心坐标换算到左上角
for cur_year in range(start_year, end_year + 1):
    # 获取当前年份的nc文件路径
    nc_wildcard = os.path.join(in_nc_dir, f'{cur_year}*.nc')
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

    # 年尺度聚合 + 单位转换
    t2m_yearly = np.nanmean(t2m_cur, axis=0) - 273.15  # 年均气温, K -> °C
    tp_yearly = np.nansum(tp_cur, axis=0) * 1000  # 年总降水量, m -> mm

    # 处理可能存在的NaN
    # 对于t2m: 如果某像元全年12个月都是NaN, nanmean会返回NaN(带RuntimeWarning)
    # 对于tp: nansum在全NaN时返回0, 需要额外处理
    all_nan_mask = np.all(np.isnan(t2m_cur), axis=0)  # 全年都是NaN的像元
    t2m_nodata = extract_nodata_value(t2m_cur.dtype)
    tp_nodata = extract_nodata_value(tp_cur.dtype)
    t2m_yearly = np.where(all_nan_mask, t2m_nodata, t2m_yearly)
    tp_yearly = np.where(all_nan_mask, tp_nodata, tp_yearly)

    # 输出年均t2m
    cur_t2m_path = os.path.join(out_t2m_dir, f't2m_{cur_year}_yearly_0.1deg.tif')
    write_tiff(cur_t2m_path, t2m_yearly, geo_transform, proj4_str=proj4_str,
               band_names=[str(cur_year)], nodata_value=t2m_nodata)

    # 输出年总tp
    cur_tp_path = os.path.join(out_tp_dir, f'tp_{cur_year}_yearly_0.1deg.tif')
    write_tiff(cur_tp_path, tp_yearly, geo_transform, proj4_str=proj4_str,
               band_names=[str(cur_year)], nodata_value=tp_nodata)

    print(f'Year {cur_year}: t2m_mean={t2m_yearly[t2m_yearly != t2m_nodata].mean():.2f}°C, '
          f'tp_sum={tp_yearly[tp_yearly != tp_nodata].mean():.1f}mm')

print('Yearly aggregation completed.')
