# @Author  : ChaoQiezi
# @Time    : 2026/5/15
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: run_growing_season_pipeline.py

"""
生长季(5-9月)风场数据全链条重算 —— 顺序执行 Step 0 → Step 1 → ... → Step 5

Step 0: era5_u_v_preprocess.py         → 0.25° u/v/wind_dir (ERA5 NC → 5-9月加权平均)
Step 1: era5_uv_reproject_to_10m.py    → 10m u/v unmasked (重投影+重采样)
Step 2: era5_u_v_postgis_preprocess.py → 10m u/v masked (DEM掩膜)
Step 3: wind_direction_cal.py          → 10m 风向 (4个气压层)
Step 4: saga_wind_effect.py            → SAGA Wind Effect (仅600hPa)
Step 5: windward_leeward_divide.py     → 迎风/背风二分类

在 PyCharm 中运行此脚本，可观察每一步的进度和输出。
"""

import os
import sys
import subprocess
import time

# ======================== Configuration ========================
python_exe = r'D:/Softwares/Anaconda3/envs/geo/python.exe'
project_src = r'F:\PyProJect\dry_hot_valley\Src\preprocessing'

# 各步骤脚本路径
step0_script = os.path.join(project_src, 'era5', 'era5_u_v_preprocess.py')
step1_script = os.path.join(project_src, 'era5', 'era5_uv_reproject_to_10m.py')
step2_script = os.path.join(project_src, 'era5', 'era5_u_v_postgis_preprocess.py')
step3_script = os.path.join(project_src, 'wind', 'wind_direction_cal.py')
step4_script = os.path.join(project_src, 'wind', 'saga_wind_effect.py')
step5_script = os.path.join(project_src, 'wind', 'windward_leeward_divide.py')

# SAGA 相关 (用于 Step 4 的智能导出判断)
wind_effect_tif = r'G:\GeoProjects\dry_hot_valley\wind_effect\wind_effect.tif'
wind_effect_sgrd = r'G:\GeoProjects\dry_hot_valley\wind_effect\wind_effect.sgrd'
saga_cmd = r'D:\Softwares\saga-9.11.3_msw\saga_cmd.exe'

# 是否强制全部重跑 (False = 跳过已存在的输出)
force_rerun = True
# ================================================================


def run_python_script(script_path, description):
    """运行 Python 脚本并等待完成, 返回 True/False"""
    print(f'\n{"="*60}')
    print(f'[{time.strftime("%H:%M:%S")}] {description}')
    print(f'  Script: {os.path.basename(script_path)}')
    print(f'{"="*60}')
    sys.stdout.flush()
    result = subprocess.run([python_exe, script_path], cwd=os.path.dirname(script_path))
    if result.returncode != 0:
        print(f'\n[ERROR] {description} FAILED (exit code {result.returncode})')
        return False
    print(f'[{time.strftime("%H:%M:%S")}] {description} -- OK')
    return True


def check_outputs_exist(file_patterns, description):
    """检查一组输出文件是否都存在"""
    missing = [f for f in file_patterns if not os.path.exists(f)]
    if missing:
        print(f'  [{description}] MISSING: {len(missing)} files, e.g. {os.path.basename(missing[0])}')
        return False
    print(f'  [{description}] All {len(file_patterns)} files present.')
    return True


def get_step_outputs():
    """定义各步骤的预期输出文件列表"""
    base = r'G:\GeoProjects\dry_hot_valley'
    levels = [500, 600, 700, 800]

    return {
        0: (
            [os.path.join(base, 'u_v', '0.25deg', f'{var}_{lev}hPa_0.25deg.tif')
             for var in ['u', 'v'] for lev in levels] +
            [os.path.join(base, 'wind_direction', '0.25deg', f'wind_dir_{lev}hPa_0.25deg.tif')
             for lev in levels],
            'ERA5 0.25° u/v/wind_dir'
        ),
        1: (
            [os.path.join(base, 'u_v', '10m', 'unmasked', f'{var}_{lev}hPa_10m.tif')
             for var in ['u', 'v'] for lev in levels],
            '10m u/v unmasked'
        ),
        2: (
            [os.path.join(base, 'u_v', '10m', 'masked', f'{var}_{lev}hPa_10m.tif')
             for var in ['u', 'v'] for lev in levels],
            '10m u/v masked'
        ),
        3: (
            [os.path.join(base, 'wind_direction', '10m', f'wind_dir_{lev}hPa_10m.tif')
             for lev in levels],
            '10m wind direction'
        ),
        4: ([wind_effect_tif], 'wind_effect.tif'),
        5: (
            [r'E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif'],
            'windward_leeward.tif'
        ),
    }


def run_saga_export_only():
    """仅导出已有的 wind_effect.sgrd → wind_effect.tif (跳过计算)"""
    if not os.path.exists(wind_effect_sgrd):
        print('  wind_effect.sgrd not found, need full run.')
        return False

    if os.path.exists(wind_effect_tif):
        os.remove(wind_effect_tif)

    print('  Exporting wind_effect.sgrd → wind_effect.tif ...')
    cmd = [saga_cmd, 'io_gdal', '2',
           '-GRIDS', wind_effect_sgrd,
           '-FILE', wind_effect_tif]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  Export failed: {result.stderr[-300:]}')
        return False
    print(f'  -> {wind_effect_tif}')
    return True


def main():
    print(f'Pipeline started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Python: {python_exe}')
    print(f'Force rerun: {force_rerun}')

    steps_outputs = get_step_outputs()
    steps = [
        (0, step0_script, 'Step 0: ERA5 0.25° u/v/wind_dir'),
        (1, step1_script, 'Step 1: Reproject 0.25° → 10m u/v'),
        (2, step2_script, 'Step 2: DEM mask 10m u/v'),
        (3, step3_script, 'Step 3: Wind direction 10m'),
        (4, step4_script, 'Step 4: SAGA Wind Effect'),
        (5, step5_script, 'Step 5: Windward/Leeward classification'),
    ]

    upstream_was_run = False  # 链式触发: 上游重跑则下游必须重跑

    for step_num, script_path, description in steps:
        files, label = steps_outputs[step_num]

        # 检查是否跳过 (上游重跑过则下游不能跳过)
        if not force_rerun and not upstream_was_run:
            if check_outputs_exist(files, label):
                print(f'[{time.strftime("%H:%M:%S")}] {description} -- outputs exist, SKIP.')
                continue

        # Step 4 特殊处理: wind_effect.sdat 已最新 → 仅导出
        if step_num == 4 and not force_rerun and not upstream_was_run:
            wind_dir_sdat = os.path.join(os.path.dirname(wind_effect_sgrd), 'wind_dir.sdat')
            wind_effect_sdat = os.path.join(os.path.dirname(wind_effect_sgrd), 'wind_effect.sdat')
            if os.path.exists(wind_effect_sdat) and os.path.exists(wind_dir_sdat):
                if os.path.getmtime(wind_effect_sdat) > os.path.getmtime(wind_dir_sdat):
                    print(f'\n[{time.strftime("%H:%M:%S")}] wind_effect.sdat is newer → export only')
                    if run_saga_export_only():
                        print(f'[{time.strftime("%H:%M:%S")}] Step 4 (export only) -- OK')
                        continue
                    print('  Export failed, falling back to full SAGA run.')

        # 执行
        if not run_python_script(script_path, description):
            print(f'\n[FATAL] Pipeline stopped at {description}.')
            print(f'  Fix the error and re-run. Steps before this are done and will be skipped.')
            return

        upstream_was_run = True  # 标记: 下游步骤必须重跑

    print(f'\n{"="*60}')
    print(f'Pipeline SUCCESS: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
