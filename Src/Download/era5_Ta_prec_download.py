# @Author  : ChaoQiezi
# @Time    : 2026/3/11 下午3:46
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_uv_download.py

"""
This script is used to 批量下载ERA5的2m气温数据集(temperature_2m)、总降水量数据集(total_precipitation)

2m气温数据集-月尺度:
总降水量数据集-月尺度:
"""

from datetime import datetime

from qiezi import download_era5

# 准备
out_dir = r'I:\DataHub\ERA5\ERA5_Land\multi_var'
era5_name = 'reanalysis-era5-land-monthly-means'
product_type = ["monthly_averaged_reanalysis"]
var_names = ["total_precipitation", "2m_temperature", ]
start_date = datetime(2019, 1, 1)
end_date = datetime(2025, 12, 31)
area_extent = [35.6, 92.1, 22.4, 106.6]  # 西南地区 (北, 西, 南, 东)

# 下载
year_range = range(start_date.year, end_date.year + 1)
for cur_year in year_range:
    cur_start_date = datetime(cur_year, 1, 1)
    cur_end_date = datetime(cur_year, 12, 31)
    cur_file_prefix = '{}_'.format(cur_year)
    download_era5(era5_name, product_type, var_names, cur_start_date, cur_end_date, out_dir, area_extent=area_extent,
                  split_month=False, split_var=False, download_format='zip',
                  file_prefix=cur_file_prefix, time=["00:00"])
