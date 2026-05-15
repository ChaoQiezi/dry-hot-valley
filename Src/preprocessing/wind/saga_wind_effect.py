# @Author  : ChaoQiezi
# @Time    : 2026/5/15
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: saga_wind_effect.py

"""
This script is used to 通过 SAGA GIS 命令行计算 Wind Effect (Windward / Leeward Index),
替代此前在 QGIS 中手动运行 SAGA 模块的操作。

SAGA 模块: ta_morphometry 15 — Wind Effect (Windward / Leeward Index)
参考文献: Böhner & Antonić (2009), Geomorphometry, Elsevier.
"""

import os
import subprocess
import shutil

# ======================== Configuration ========================
saga_cmd = r'D:\Softwares\saga-9.11.3_msw\saga_cmd.exe'
dem_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif'
wind_dir_path = r'G:\GeoProjects\dry_hot_valley\wind_direction\10m\wind_dir_600hPa_10m.tif'
wind_effect_dir = r'G:\GeoProjects\dry_hot_valley\wind_effect'
wind_effect_tif = os.path.join(wind_effect_dir, 'wind_effect.tif')

# SAGA 临时格式文件 (与输出目录一致)
dem_sgrd = os.path.join(wind_effect_dir, 'dem')
wind_dir_sgrd = os.path.join(wind_effect_dir, 'wind_dir')
wind_effect_sgrd = os.path.join(wind_effect_dir, 'wind_effect')

max_dist = 300.0    # 搜索距离 [km]
accel = 1.5          # 加速度因子
# ================================================================

os.makedirs(wind_effect_dir, exist_ok=True)


def run_saga(tool_args, description='SAGA command'):
    """运行 SAGA 命令并检查返回值"""
    cmd = [saga_cmd] + tool_args
    print(f'Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'[WARNING] {description} returned {result.returncode}')
        if result.stderr.strip():
            print(result.stderr.strip()[-500:])
    else:
        print(f'  -> OK')
    return result


# Step 1: 导入 DEM 到 SAGA 格式
print('\n=== Step 1/4: Import DEM to SAGA format ===')
run_saga(
    ['io_gdal', '0', '-FILES', dem_path, '-GRIDS', dem_sgrd],
    'Import DEM'
)

# Step 2: 导入风向栅格到 SAGA 格式
print('\n=== Step 2/4: Import wind direction to SAGA format ===')
run_saga(
    ['io_gdal', '0', '-FILES', wind_dir_path, '-GRIDS', wind_dir_sgrd],
    'Import wind direction'
)

# Step 3: 运行 Wind Effect 计算
print('\n=== Step 3/4: Compute Wind Effect (this may take hours for 10m DEM) ===')
run_saga(
    ['ta_morphometry', '15',
     '-DEM', f'{dem_sgrd}.sgrd',
     '-DIR', f'{wind_dir_sgrd}.sgrd',
     '-DIR_UNITS', '1',             # degree (0=radians, 1=degree)
     '-MAXDIST', str(max_dist),
     '-ACCEL', str(accel),
     '-EFFECT', f'{wind_effect_sgrd}.sgrd'],
    'Wind Effect'
)

# Step 4: 导出 Wind Effect 为 GeoTIFF
print('\n=== Step 4/4: Export Wind Effect to GeoTIFF ===')
# 如果旧 tif 存在则先删除 (SAGA 不会覆盖)
if os.path.exists(wind_effect_tif):
    os.remove(wind_effect_tif)
run_saga(
    ['io_gdal', '2',
     '-GRIDS', f'{wind_effect_sgrd}.sgrd',
     '-FILE', wind_effect_tif],
    'Export GeoTIFF'
)

print(f'\nWind effect output: {wind_effect_tif}')
print('Done.')
