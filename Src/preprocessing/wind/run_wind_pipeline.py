# @Author  : ChaoQiezi
# @Time    : 2026/5/28
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: run_wind_pipeline.py

"""
Wind 文件夹全链条 —— 顺序执行 wind_direction_cal → saga_wind_effect → windward_leeward_divide

前置条件: ERA5 u/v 10m unmasked 数据已存在 (由 run_growing_season_pipeline.py Step 0-1 产出)

Step 2: wind_direction_cal.py          → 10m 风向 (4个气压层)
Step 3: saga_wind_effect.py            → SAGA Wind Effect (仅600hPa, 100m计算→10m回升)
Step 4: windward_leeward_divide.py     → 迎风/背风二分类
"""

import os
import subprocess
import sys
import time

# 准备
python_exe = r'D:/Softwares/Anaconda3/envs/geo/python.exe'
project_src = os.path.dirname(os.path.abspath(__file__))
data_base = r'G:\GeoProjects\dry_hot_valley'

# 各步骤脚本路径
step2_script = os.path.join(project_src, 'wind_direction_cal.py')
step3_script = os.path.join(project_src, 'saga_wind_effect.py')
step4_script = os.path.join(project_src, 'windward_leeward_divide.py')

# 是否强制全部重跑 (False = 跳过已存在的输出)
force_rerun = True


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


def check_outputs_exist(file_patterns, description, dependencies=None):
    """检查一组输出文件是否都存在且不旧于依赖文件"""
    missing = [f for f in file_patterns if not os.path.exists(f)]
    if missing:
        print(f'  [{description}] MISSING: {len(missing)} files, e.g. {os.path.basename(missing[0])}')
        return False

    if dependencies:
        existing_dependencies = [f for f in dependencies if os.path.exists(f)]
        if existing_dependencies:
            newest_dependency_time = max(os.path.getmtime(f) for f in existing_dependencies)
            stale = [f for f in file_patterns if os.path.getmtime(f) < newest_dependency_time]
            if stale:
                print(f'  [{description}] STALE: {len(stale)} files, e.g. {os.path.basename(stale[0])}')
                return False

    print(f'  [{description}] All {len(file_patterns)} files present.')
    return True


def get_step_outputs():
    """定义各步骤的预期输出文件列表"""
    pressure_levels = [500, 600, 700, 800]

    outputs = {
        2: (
            [os.path.join(data_base, 'wind_direction', '10m', f'wind_dir_{lev}hPa_10m.tif')
             for lev in pressure_levels],
            '10m wind direction (4 levels)'
        ),
        3: ([os.path.join(data_base, 'wind_effect', 'wind_effect.tif')], 'wind_effect.tif (10m)'),
        4: (
            [r'E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif'],
            'windward_leeward.tif'
        ),
    }
    dependencies = {
        2: [step2_script],
        3: [step3_script] + outputs[2][0],
        4: [step4_script] + outputs[3][0],
    }
    return {
        step_num: (files, label, dependencies[step_num])
        for step_num, (files, label) in outputs.items()
    }


def main():
    print(f'Wind Pipeline started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Python: {python_exe}')
    print(f'Force rerun: {force_rerun}')

    steps_outputs = get_step_outputs()
    steps = [
        (2, step2_script, 'Step 2: Wind direction 10m (500/600/700/800 hPa)'),
        (3, step3_script, 'Step 3: SAGA Wind Effect (100m → 10m)'),
        (4, step4_script, 'Step 4: Windward/Leeward classification'),
    ]

    upstream_was_run = False  # 链式触发: 上游重跑则下游必须重跑

    for step_num, script_path, description in steps:
        files, label, dependencies = steps_outputs[step_num]

        # 检查是否跳过 (上游重跑过则下游不能跳过)
        if not force_rerun and not upstream_was_run:
            if check_outputs_exist(files, label, dependencies):
                print(f'[{time.strftime("%H:%M:%S")}] {description} -- outputs exist, SKIP.')
                continue

        # 执行
        if not run_python_script(script_path, description):
            print(f'\n[FATAL] Pipeline stopped at {description}.')
            print(f'  Fix the error and re-run. Steps before this are done and will be skipped.')
            return

        upstream_was_run = True  # 标记: 下游步骤必须重跑

    print(f'\n{"="*60}')
    print(f'Wind Pipeline SUCCESS: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
