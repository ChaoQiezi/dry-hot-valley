# @Author  : ChaoQiezi
# @Time    : 2026/3/18 上午1:39
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: windward_leeward_divide.py

"""
This script is used to 基于SAGA GIS计算的wind effect(windward, leeward)风效应指数进行二分类, 获得
生长季内迎风坡和背风坡的二分类结果: 1为迎风坡, 2为背风坡, 255为排除(slope<=5°或无效值)
"""

import rasterio as rio
import numpy as np
import os
import shutil

from qiezi.geo import build_overviews


if __name__ == '__main__':
    # ======================== Configuration ========================
    wind_effect_path = r'G:\GeoProjects\dry_hot_valley\wind_effect\wind_effect.tif'
    slope_path = r'E:\GeoProjects\dry_hot_valley\GeoFactor\Slope\slope_10m_projected.tif'
    out_path = r'E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif'
    mirror_out_path = r'G:\GeoProjects\dry_hot_valley\windward_leeward\windward_leeward.tif'
    slope_threshold = 5.0
    # ================================================================

    # 验证输入对齐
    with rio.open(wind_effect_path) as src:
        we_profile = src.profile.copy()
        we_shape = src.shape
        we_crs = src.crs
        we_transform = src.transform
        block_windows = list(src.block_windows())
    with rio.open(slope_path) as src:
        if src.shape != we_shape or src.crs != we_crs or src.transform != we_transform:
            raise RuntimeError('Slope raster is not aligned with wind effect raster.')

    # 输出参数
    out_profile = we_profile.copy()
    out_profile['tiled'] = True
    out_profile['compress'] = out_profile.get('compress', 'lzw')
    out_profile['predictor'] = out_profile.get('predictor', 3)
    out_profile['dtype'] = 'uint8'
    out_profile['nodata'] = 255

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 逐块处理
    print('Classifying windward/leeward (sequential block processing) ...')
    with rio.open(wind_effect_path, 'r') as we_src, \
         rio.open(slope_path, 'r') as slope_src:
        with rio.open(out_path, 'w', **out_profile) as dst:
            for _ji, window in block_windows:
                we_block = we_src.read(1, window=window, masked=True)
                slope_block = slope_src.read(1, window=window, masked=True)

                # 分类: wind_effect > 1 → 1(迎风), <= 1 → 2(背风)
                class_block = np.where(we_block > 1, 1, 2).astype(np.uint8)
                # 无效值
                class_block[we_block.mask] = 255
                # slope <= threshold → 排除
                exclude = slope_block.mask | (slope_block <= slope_threshold)
                class_block[exclude] = 255

                dst.write(class_block, window=window, indexes=1)

    # Mirror到G盘
    os.makedirs(os.path.dirname(mirror_out_path), exist_ok=True)
    shutil.copy2(out_path, mirror_out_path)
    build_overviews(out_path)
    build_overviews(mirror_out_path)

    print(f'Output: {out_path}')
    print(f'Mirror: {mirror_out_path}')
    print('Done.')
