# @Author  : ChaoQiezi
# @Time    : 2026/3/11 下午9:20
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: wind_direction_cal.py

"""
This script is used to 基于u和v计算风向(5-9月生长季均值)
采用逐块顺序读写，避免dask并行写入在Windows下的兼容性问题
"""

import os
import rasterio as rio
import numpy as np
from qiezi.stats import wind_direction_cal as wdir_cal
from qiezi.geo import build_overviews

if __name__ == '__main__':
    # ======================== Configuration ========================
    in_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\masked'
    out_dir = r'G:\GeoProjects\dry_hot_valley\wind_direction\10m'
    pressure_levels = [500, 600, 700, 800]
    # ================================================================

    os.makedirs(out_dir, exist_ok=True)

    for cur_pressure_level in pressure_levels:
        cur_u_path = os.path.join(in_dir, f'u_{cur_pressure_level:.0f}hPa_10m.tif')
        cur_v_path = os.path.join(in_dir, f'v_{cur_pressure_level:.0f}hPa_10m.tif')
        if not (os.path.exists(cur_u_path) and os.path.exists(cur_v_path)):
            print(f'Pressure level {cur_pressure_level:.0f}hPa: u or v not exists!')
            continue

        cur_out_filename = f'wind_dir_{cur_pressure_level:.0f}hPa_10m.tif'
        cur_out_path = os.path.join(out_dir, cur_out_filename)
        if os.path.exists(cur_out_path):
            print(f'Pressure level {cur_pressure_level:.0f}hPa: wind direction already exists!')
            with rio.open(cur_out_path, 'r+') as dst:
                dst.nodata = np.nan
            build_overviews(cur_out_path)
            continue

        print(f'Computing wind direction for {cur_pressure_level:.0f}hPa ...')

        with rio.open(cur_u_path, 'r') as u_src, rio.open(cur_v_path, 'r') as v_src:
            out_profile = u_src.profile.copy()
            out_profile['tiled'] = True
            out_profile['compress'] = out_profile.get('compress', 'lzw')
            out_profile['predictor'] = out_profile.get('predictor', 3)
            out_profile['nodata'] = np.nan
            block_windows = list(u_src.block_windows())

            with rio.open(cur_out_path, 'w', **out_profile) as dst:
                for _ji, window in block_windows:
                    u_block = u_src.read(1, window=window, masked=True)
                    v_block = v_src.read(1, window=window, masked=True)
                    wdir_block = wdir_cal(u_block, v_block)
                    dst.write(wdir_block, window=window, indexes=1)

        # 设置nodata为NaN
        with rio.open(cur_out_path, 'r+') as dst:
            dst.nodata = np.nan
        build_overviews(cur_out_path)

        print(f'  -> {cur_out_filename} done.')

    print('All wind direction calculations completed.')
