# @Author  : ChaoQiezi
# @Time    : 2026/4/2 上午5:48
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dem_reclass.py

"""
This script is used to 对DEM进行重分类

dem梯度为1000m
"""

import os
import warnings

import numpy as np
import rasterio as rio
from qiezi import build_overviews
from rasterio.enums import Resampling

warnings.filterwarnings('ignore')

# 准备
dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_10m_projected.tif"
out_dir = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM"
out_reclass_path = os.path.join(out_dir, "elevation_reclass_1000m.tif")
dem_gradient = 1000
nodata = 255

os.makedirs(out_dir, exist_ok=True)


if __name__ == '__main__':
    # 读取
    with rio.open(dem_path, 'r') as src:
        dem = src.read(1, masked=True)
        src_profile = src.profile
    # 重分类
    valid_mask = ~dem.mask
    dem[valid_mask] = (dem[valid_mask] // dem_gradient) + 1  # Mathematical reclassification (e.g., 0-999m -> 1, 1000-1999m -> 2)
    # 无效值和数据类型
    dem = dem.filled(nodata).astype(np.uint8)

    # 输出
    out_profile = {
        k: v for k, v in src_profile.items()
        if k not in ['nodata', 'compress', 'dtype']
    }
    out_profile['nodata'] = nodata
    out_profile['dtype'] = np.uint8
    out_profile['compress'] = 'lzw'
    with rio.open(out_reclass_path, 'w', **out_profile) as dst:
        dst.write(dem, 1)

    # 创建金字塔
    build_overviews(out_reclass_path)
