# @Author  : ChaoQiezi
# @Time    : 2026/3/13 下午2:31
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dead_code.py

"""
This script is used to 
"""

from pprint import pprint
from osgeo import gdal
from rasterio.enums import Resampling

img_path = r"E:\MyTEMP\NDVI_preprocessing\NDVI_2019_valid.tif"

ds = gdal.Open(img_path, gdal.GA_ReadOnly)
ds.BuildOverviews('NEAREST', [2, 4, 8, 16])
ds = None

