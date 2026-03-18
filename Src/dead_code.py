# @Author  : ChaoQiezi
# @Time    : 2026/3/13 下午2:31
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dead_code.py

"""
This script is used to 
"""

import rasterio

img_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif'

with rasterio.open(img_path) as src:
    print([src.overviews(i) for i in src.indexes])
