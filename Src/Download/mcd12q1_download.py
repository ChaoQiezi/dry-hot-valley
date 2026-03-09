# @Author  : ChaoQiezi
# @Time    : 2026/3/7 下午4:13
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: mcd12q1_download.py

"""
This script is used to 批量下载MCD12Q1数据集
"""

import os
from pathlib import Path

from qiezi import DownloadManager

# MOD12Q1(土地覆盖类型)数据集下载
urls_path = '../../Assets/data_urls/MCD12Q1_links.txt'
out_dir = r"I:\DataHub\MCD12Q1"
out_dir = os.path.join(out_dir, Path(urls_path).name.split('.')[0])
os.makedirs(out_dir, exist_ok=True)
status_path = Path(urls_path).parent / (os.path.basename(urls_path).split('.txt')[0] + '.json')
# 下载
downloader = DownloadManager(out_dir, urls_path, status_path, 10)
downloader.download()
