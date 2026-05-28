# @Author  : ChaoQiezi
# @Time    : 2026/5/16
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: run_vai_buffer_pipeline.py

"""
VAI buffer 分析全链条重算 —— 顺序执行 Step 1 → Step 2 → Step 3 → Step 4

Step 1: unify_dataset.py × 4       → 重新裁剪 windward_leeward_region.tif (ArcGISPro)
Step 2: VAI_spatial_distribution_buffer.py → 批量 buffer VAI 3km 计算 (geo)
Step 3: VAI_altitude_gradient_buffer.py    → 四河合并阈值 + bootstrap + 森林图 (geo)
Step 4: zhao_threshold_intensity.py         → 河段强弱分级 (geo, 可选)

在 PyCharm 中运行此脚本，可观察每一步的进度和输出。
"""

import os
import sys
import subprocess
import time

# 准备
python_geo = r'D:/Softwares/Anaconda3/envs/geo/python.exe'
python_arcpy = r'D:/Softwares/Anaconda3/envs/ArcGISPro/python.exe'
project_src = r'F:\PyProJect\dry_hot_valley\Src\valley_analysis'

# 各河谷 unify_dataset 脚本路径
unify_scripts = {
    'Daduhe':      os.path.join(project_src, 'Daduhe', 'preprocessing', 'unify_dataset.py'),
    'Jinshajiang': os.path.join(project_src, 'Jinshajiang', 'preprocessing', 'unify_dataset.py'),
    'Minjiang':    os.path.join(project_src, 'Minjiang', 'preprocessing', 'unify_dataset.py'),
    'Yalongjiang': os.path.join(project_src, 'Yalongjiang', 'preprocessing', 'unify_dataset.py'),
}

# 后续分析脚本
step2_script = os.path.join(project_src, 'geo_analysis', 'VAI_spatial_distribution_buffer.py')
step3_script = os.path.join(project_src, 'geo_analysis', 'VAI_altitude_gradient_buffer.py')
step4_script = os.path.join(project_src, 'geo_analysis', 'zhao_threshold_intensity.py')

# 输出文件 (用于检查是否存在)
windward_region_tifs = [
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\geo_factor\windward_leeward_region.tif',
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Jinshajiang\geo_factor\windward_leeward_region.tif',
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\geo_factor\windward_leeward_region.tif',
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Yalongjiang\geo_factor\windward_leeward_region.tif',
]
buffer_vai_tifs = [
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\VAI\VAI_3km_buffer.tif',
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Jinshajiang\VAI\VAI_3km_buffer.tif',
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\VAI\VAI_3km_buffer.tif',
    r'E:\GeoProjects\dry_hot_valley\valley_analysis\Yalongjiang\VAI\VAI_3km_buffer.tif',
]
combined_outputs = [
    r'E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_cells_all.csv',
    r'E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_threshold_summary_all.csv',
    r'E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_buffer_threshold_all.png',
]
zhao_outputs = [
    r'E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_segment_intensity_summary.csv',
    r'E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\Fig6_zhao_segment_intensity_30km.png',
]

# 是否强制全部重跑 (False = 跳过已存在的输出)
force_rerun = True

# 如果 Step 1 (unify_dataset) 是手动在 PyCharm 中逐个运行的, 跑完后将此标记设为 True.
# 这样即使 force_rerun=False, 下游也会因为上游已更新而自动重跑.
manual_step1_done = False


def run_script(python_exe, script_path, description):
    """运行 Python 脚本并等待完成, 返回 True/False"""
    print(f'\n{"="*60}')
    print(f'[{time.strftime("%H:%M:%S")}] {description}')
    print(f'  Script: {os.path.basename(script_path)}')
    print(f'  Python: {os.path.basename(python_exe)}')
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


def main():
    """按 Step 1-4 顺序执行 VAI buffer 分析全链条"""
    print(f'Pipeline started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Python (geo): {python_geo}')
    print(f'Python (ArcGISPro): {python_arcpy}')
    print(f'Force rerun: {force_rerun}')

    upstream_was_run = False  # 链式触发: 上游重跑则下游必须重跑

    # Step 1: unify_dataset.py × 4 — 重新裁剪 windward_leeward_region.tif
    # 注意: 此步需要 ArcGISPro 解释器, 且目前仅裁剪 windward_leeward
    # (DEM/NDVI 部分已在 unify_dataset.py 中注释).
    # 取消注释下方整块即可在管道中自动运行; 也可在 PyCharm 中手动逐个运行.

    for valley, script_path in unify_scripts.items():
        # 检查跳过
        cur_out = os.path.join(
            r'E:\GeoProjects\dry_hot_valley\valley_analysis', valley, 'geo_factor', 'windward_leeward_region.tif'
        )
        if not force_rerun and not upstream_was_run and os.path.exists(cur_out):
            print(f'[{time.strftime("%H:%M:%S")}] {valley} windward_leeward_region.tif exists, SKIP.')
            continue

        if not run_script(python_arcpy, script_path, f'Step 1: {valley} unify_dataset (windward_leeward)'):
            print(f'\n[FATAL] Pipeline stopped at Step 1 ({valley} unify_dataset).')
            return

    upstream_was_run = True
    print(f'[{time.strftime("%H:%M:%S")}] Step 1 (unify_dataset × 4) -- ALL OK')

    # print(f'[{time.strftime("%H:%M:%S")}] Step 1 (unify_dataset × 4) -- SKIPPED (commented out, run manually)')
    # IMPORTANT: 手动跑完 unify_dataset 后再运行此管道, 或取消上方注释让管道自动执行.
    if manual_step1_done:
        upstream_was_run = True
        print(f'  -> manual_step1_done=True, downstream will rerun.')

    # Step 2: VAI_spatial_distribution_buffer.py — 批量 buffer VAI 3km
    if not force_rerun and not upstream_was_run:
        if check_outputs_exist(buffer_vai_tifs, 'VAI_3km_buffer.tif'):
            print(f'[{time.strftime("%H:%M:%S")}] Step 2 (VAI_spatial_distribution_buffer) -- outputs exist, SKIP.')
        else:
            if not run_script(python_geo, step2_script, 'Step 2: Buffer VAI spatial distribution (all 4 valleys)'):
                print(f'\n[FATAL] Pipeline stopped at Step 2.')
                return
            upstream_was_run = True
    else:
        if not run_script(python_geo, step2_script, 'Step 2: Buffer VAI spatial distribution (all 4 valleys)'):
            print(f'\n[FATAL] Pipeline stopped at Step 2.')
            return
        upstream_was_run = True

    # Step 3: VAI_altitude_gradient_buffer.py — 四河合并阈值 + bootstrap + 森林图
    if not force_rerun and not upstream_was_run:
        if check_outputs_exist(combined_outputs, 'combined threshold outputs'):
            print(f'[{time.strftime("%H:%M:%S")}] Step 3 (VAI_altitude_gradient_buffer) -- outputs exist, SKIP.')
        else:
            if not run_script(python_geo, step3_script, 'Step 3: Combined threshold + forest plot'):
                print(f'\n[FATAL] Pipeline stopped at Step 3.')
                return
            upstream_was_run = True
    else:
        if not run_script(python_geo, step3_script, 'Step 3: Combined threshold + forest plot'):
            print(f'\n[FATAL] Pipeline stopped at Step 3.')
            return
        upstream_was_run = True

    # Step 4: zhao_threshold_intensity.py — 河段强弱分级 (可选)
    # TODO: 如需跑此步, 取消注释下方整块.
    # if not force_rerun and not upstream_was_run:
    #     if check_outputs_exist(zhao_outputs, 'zhao segment intensity'):
    #         print(f'[{time.strftime("%H:%M:%S")}] Step 4 (zhao_threshold_intensity) -- outputs exist, SKIP.')
    #     else:
    #         if not run_script(python_geo, step4_script, 'Step 4: Zhao segment intensity'):
    #             print(f'\n[FATAL] Pipeline stopped at Step 4.')
    #             return
    #         upstream_was_run = True
    # else:
    #     if not run_script(python_geo, step4_script, 'Step 4: Zhao segment intensity'):
    #         print(f'\n[FATAL] Pipeline stopped at Step 4.')
    #         return
    #     upstream_was_run = True

    print(f'\n{"="*60}')
    print(f'Pipeline SUCCESS: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
