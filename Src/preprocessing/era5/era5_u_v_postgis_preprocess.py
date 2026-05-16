# @Author  : ChaoQiezi
# @Time    : 2026/3/16 上午11:36
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_u_v_postgis_preprocess.py

"""
This script is used to 将重投影和重采样后的的u、v数据集进行批量掩膜
(基于DEM有效范围剔除无效区域)
"""

import os.path
from glob import glob
import rasterio as rio
import numpy as np
from qiezi.geo import build_overviews

if __name__ == '__main__':
    # ======================== Configuration ========================
    in_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\unmasked'
    out_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\masked'
    ref_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif'
    # ================================================================

    os.makedirs(out_dir, exist_ok=True)

    # 检索待掩膜文件
    wildcard = '*_*hPa_10m.tif'
    wildcard = os.path.join(in_dir, wildcard)
    img_paths = glob(wildcard)
    print(f'Found {len(img_paths)} files to mask.')

    # 迭代掩膜
    for cur_path in img_paths:
        cur_out_name = os.path.basename(cur_path)
        cur_out_path = os.path.join(out_dir, cur_out_name)
        # if os.path.exists(cur_out_path):  # pipeline统一管理跳过, 单独运行时取消注释
        #     print(f'{cur_out_name} exists, skip.')
        #     build_overviews(cur_out_path)
        #     continue


        print(f'Masking {cur_out_name} ...')

        with rio.open(cur_path, 'r') as src:
            out_profile = src.profile.copy()
            out_profile['tiled'] = True
            out_profile['compress'] = out_profile.get('compress', 'lzw')
            out_profile['predictor'] = out_profile.get('predictor', 3)
            block_windows = list(src.block_windows())

            with rio.open(ref_path, 'r') as ref_src:
                with rio.open(cur_out_path, 'w', **out_profile) as dst:
                    for _ji, window in block_windows:
                        cur_block = src.read(1, window=window, masked=True)
                        ref_block = ref_src.read(1, window=window, masked=True)
                        cur_block.mask |= ref_block.mask
                        dst.write(cur_block, window=window, indexes=1)

        build_overviews(cur_out_path)
        print(f'  -> {cur_out_name} done.')

    print('All masking completed.')
