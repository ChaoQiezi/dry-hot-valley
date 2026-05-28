# @Author  : ChaoQiezi
# @Time    : 2026/3/18 上午1:39
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: windward_leeward_divide.py

"""
This script is used to 基于 SAGA GIS 计算的 wind effect 风效应指数进行二分类, 获得
生长季内迎风坡和背风坡的二分类结果: 1 为迎风坡, 2 为背风坡, 255 为排除或无效值.
"""

import os
import shutil

import numpy as np
import rasterio as rio

from qiezi.geo import build_overviews


def raster_is_aligned(src, ref_shape, ref_crs, ref_transform):
    return src.shape == ref_shape and src.crs == ref_crs and src.transform == ref_transform


def valid_float_block(block, extra_nodata=None):
    data = np.asarray(block.data)
    valid = ~np.ma.getmaskarray(block) & np.isfinite(data)
    if extra_nodata is not None:
        valid &= data != extra_nodata
    return data, valid


if __name__ == '__main__':
    # Configuration
    wind_effect_path = r'G:\GeoProjects\dry_hot_valley\wind_effect\wind_effect.tif'
    wind_dir_path = r'G:\GeoProjects\dry_hot_valley\wind_direction\10m\wind_dir_600hPa_10m.tif'
    slope_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\Slope\xinan\slope_10m_proj_xinan_region.tif'
    out_path = r'E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif'
    mirror_out_path = r'G:\GeoProjects\dry_hot_valley\windward_leeward\windward_leeward.tif'

    slope_threshold = 5.0
    neutral_tolerance = 1e-6
    saga_nodata = -99999.0
    chunks = 4096

    # 验证输入对齐
    with rio.open(wind_effect_path) as src:
        we_profile = src.profile.copy()
        we_shape = src.shape
        we_crs = src.crs
        we_transform = src.transform
        block_windows = list(src.block_windows(1))

    for path, label in [
        (wind_dir_path, 'Wind direction'),
        (slope_path, 'Slope'),
    ]:
        with rio.open(path) as src:
            if not raster_is_aligned(src, we_shape, we_crs, we_transform):
                raise RuntimeError(f'{label} raster is not aligned with wind effect raster.')

    # 输出参数
    out_profile = we_profile.copy()
    out_profile['tiled'] = True
    out_profile['compress'] = out_profile.get('compress', 'lzw')
    out_profile['predictor'] = 2
    out_profile['blockxsize'] = chunks
    out_profile['blockysize'] = chunks
    out_profile['dtype'] = 'uint8'
    out_profile['nodata'] = 255
    out_profile['bigtiff'] = 'YES'

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 删除旧文件, 避免残留损坏文件影响写入
    if os.path.exists(out_path):
        os.remove(out_path)

    print('Classifying windward/leeward (sequential block processing) ...')
    with rio.open(wind_effect_path) as we_src, \
         rio.open(wind_dir_path) as wind_src, \
         rio.open(slope_path) as slope_src:
        with rio.open(out_path, 'w', **out_profile) as dst:
            for _ji, window in block_windows:
                we_block = we_src.read(1, window=window, masked=True)
                wind_block = wind_src.read(1, window=window, masked=True)
                slope_block = slope_src.read(1, window=window, masked=True)

                we_data, we_valid = valid_float_block(we_block, extra_nodata=saga_nodata)
                _wind_data, wind_valid = valid_float_block(wind_block)
                slope_data, slope_valid = valid_float_block(slope_block)

                valid = (
                    we_valid
                    & wind_valid
                    & slope_valid
                    & (slope_data > slope_threshold)
                    & (np.abs(we_data - 1.0) > neutral_tolerance)
                )

                class_block = np.full(we_data.shape, 255, dtype=np.uint8)
                class_block[valid & (we_data > 1.0)] = 1
                class_block[valid & (we_data < 1.0)] = 2

                dst.write(class_block, window=window, indexes=1)

    # Mirror 到 G 盘
    os.makedirs(os.path.dirname(mirror_out_path), exist_ok=True)
    shutil.copy2(out_path, mirror_out_path)
    build_overviews(out_path)
    build_overviews(mirror_out_path)

    print(f'Output: {out_path}')
    print(f'Mirror: {mirror_out_path}')
    print('Done.')
