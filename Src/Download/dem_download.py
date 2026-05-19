# @Author  : ChaoQiezi
# @Time    : 2026/3/7 下午4:13
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: mcd12q1_download.py

"""
This script is used to 批量下载ALOS DEM数据集(废弃)

对于ALOS DEM数据集, 虽然其标注了12.5m分辨率的数据集, 但是实际上对于中国及其其他大部分区域, 都是基于SRTM数据集的
30m分辨率上采样得来的, 具体见官方文档(https://asf.alaska.edu/wp-content/uploads/2019/03/rtc_product_guide_v1.2.pdf):
Assets/Ref/rtc_product_guide_v1.2.pdf

因此实际上后续研究, 目前(2026/03/09)我们考虑的DEM数据集是使用GLO-30产品, 从OpenTopography下载(搜索GLO-30即可):
    https://portal.opentopography.org/dataCatalog
"""

import os
from pathlib import Path

from qiezi import DownloadManager

# DEM数据集下载
urls_path = '../../Assets/data_urls/ALOS_dem_urls.txt'
out_dir = r"I:\DataHub\ALOS_dem"
out_dir = os.path.join(out_dir, Path(urls_path).name.split('.')[0])
os.makedirs(out_dir, exist_ok=True)
status_path = Path(urls_path).parent / (os.path.basename(urls_path).split('.txt')[0] + '.json')
# 下载
downloader = DownloadManager(out_dir, urls_path, status_path, 10)
downloader.download()
