# @Author  : ChaoQiezi
# @Time    : 2026/3/11 下午3:46
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_uv_download.py

"""
This script is used to 批量下载ERA5的风向风俗数据集

小时尺度的数据集(暂不考虑, 需要自己聚合): https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels?tab=download
月尺度的数据集(暂使用此数据集): https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels-monthly-means?tab=download
"""

from datetime import datetime

from qiezi import download_era5

# 准备
era5_name = 'reanalysis-era5-pressure-levels-monthly-means'
product_type = ["monthly_averaged_reanalysis"]
var_names = ["geopotential",
             "u_component_of_wind",
             "v_component_of_wind"]
start_date = datetime(2017, 1, 1)
end_date = datetime(2025, 12, 31)
out_dir = r'I:\DataHub\ERA5\ERA5\pressure_level\multi_var\backup'
pressure_level = ['800', '700', '600', '500']  # 我的建议是600hPa风场数据比较适合川西地区
# 1000hPa约0m位置, 900hPa约1000m位置, 850hPa约1500m位置, 700hPa约3000m位置, 600hPa约4400m位置, 500hPa约5500m位置
area_extent = [35.6, 92.1, 22.4, 106.6]  # 西南地区 (北, 西, 南, 东)

# 下载
year_range = range(start_date.year, end_date.year + 1)
for cur_year in year_range:
    cur_start_date = datetime(cur_year, 1, 1)
    cur_end_date = datetime(cur_year, 12, 31)
    cur_file_prefix = '{}_'.format(cur_year)
    download_era5(era5_name, product_type, var_names, cur_start_date, cur_end_date, out_dir, area_extent=area_extent,
                  pressure_level=pressure_level, split_month=False, split_var=False, download_format='zip',
                  file_prefix=cur_file_prefix, hours=["00:00"])
