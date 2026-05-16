# @Author  : ChaoQiezi
# @Time    : 2026/3/15 上午11:35
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: classify_windward_leeward.py

"""
This script is used to 基于SAGA GIS计算的Wind Effect(Windard, Leeward)风效应指数进行迎风坡和背风坡的划分
"""

from glob import glob
import rasterio as rio


# 准备
in_dir = r'G:\GeoProjects\dry_hot_valley\wind_effect'


# 检索
wildcard = 'wind_effect_*.tif'
wind_effect_paths = glob(os.path.join(in_dir, wildcard))

# 划分迎风坡和背风坡
for cur_path in wind_effect_paths:
    # 读取风效应指数
    with rio.open(cur_path, 'r') as ds:
        wind_effect = ds.read(masked=True)
        out_profile = ds.profile.copy()

    # 划分迎风坡和背风坡
