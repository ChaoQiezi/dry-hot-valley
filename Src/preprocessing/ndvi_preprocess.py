# @Author  : ChaoQiezi
# @Time    : 2026/3/18 下午9:10
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_preprocess.py

"""
This script is used to 对GEE下载的NDVI数据进行预处理

预处理包括: 镶嵌、重投影和重采样、裁剪掩膜、比例缩放

目前的流程是:
1. 基于同年tif文件创建镶嵌VRT文件, 基于镶嵌的VRT文件进行重投影和重采样(横轴墨卡托, 10m);
2. 接着对获取得到的geotiff文件进行裁剪和掩膜(像元对齐), 同时进行比例缩放;
"""

import os
import rasterio as rio
import rioxarray as rxr
from dask.distributed import Client
from glob import glob

from qiezi import img_mosaic, img_agg


# 准备
in_dir = r'G:\GeoProjects\dry_hot_valley\NDVI\Yearly'
out_dir =
start_year = 2017
end_year = 2025

# 迭代处理每年数据集
for year in range(start_year, end_year + 1):
    # 检索
    cur_wildcard = os.path.join(in_dir, 'NDVI_*.tif')
    img_paths = glob(cur_wildcard)

    # 迭代
    for cur_path in img_paths:
