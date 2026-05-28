# @Author  : ChaoQiezi
# @Time    : 2026/3/28 下午3:06
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_yearly_mean_by_aspect_valley.py

"""
This script is used to 分别计算迎风坡和背风坡的NDVI年际均值(2019-2025)

2026/4/13-ps: 加入河谷内外侧的维度限制进行分析

分析模式 (ANALYSIS_MODE):
  - "wind_only":    仅在迎风坡/背风坡维度进行分析 (原始行为, 但限定在河谷区域内)
  - "valley_only":  仅在河谷内侧/外侧维度进行分析 (不区分迎/背风坡)
  - "combined":     综合两个维度, 产出四个分量:
                    河谷内侧迎风坡、河谷内侧背风坡、河谷外侧迎风坡、河谷外侧背风坡

河谷栅格编码:
  十位数: 1=大渡河, 2=岷江, 3=金沙江, 4=雅磨江
  个位数: 1=outer, 2=inner

输入:
  - 逐年NDVI栅格 (NDVI_{year}.tif)
  - 迎风坡/背风坡 二值栅格 (windward_leeward.tif), 1=迎风坡, 2=背风坡
  - 河谷区域栅格 (valley_chuanxi_clip.tif), 编码见上
输出:
  - Excel表格, 包含每年各分量的 mean, std, cv
"""

import os

import numpy as np
import pandas as pd
import rioxarray as rxr
import xarray as xr
from dask.distributed import Client, LocalCluster

# 准备
ndvi_dir = r'E:\GeoProjects\dry_hot_valley\NDVI\Yearly'
direction_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"  # 二值栅格: 1=迎风坡, 2=背风坡
valley_path = r"E:\GeoProjects\dry_hot_valley\valley_area\valley_chuanxi\valley_chuanxi_clip.tif"
out_dir = r'E:\GeoProjects\dry_hot_valley\Output\Table'

# 分析模式: "wind_only" | "valley_only" | "combined"
# ANALYSIS_MODE = "combined"
# ANALYSIS_MODE = "valley_only"
ANALYSIS_MODE = "wind_only"

start_year = 2019
end_year = 2025
chunk_size = {'x': 4096, 'y': 4096}

# 迎风坡/背风坡在二值栅格中的像元值
WINDWARD_VAL = 1
LEEWARD_VAL = 2

# 河谷栅格编码: 个位数 1=outer, 2=inner
# 有效河谷值集合: {11, 12, 21, 22, 31, 32, 41, 42}
VALLEY_VALID_VALUES = {11, 12, 21, 22, 31, 32, 41, 42}


def build_valley_masks_xr(valley_da):
    """
    从河谷xarray DataArray构建内侧/外侧/全部的布尔掩膜.

    Parameters
    ----------
    valley_da : xarray.DataArray
        河谷栅格数据 (dask-backed)

    Returns
    -------
    dict
        包含 'inner', 'outer', 'all' 三个布尔掩膜的字典
    """
    # 构建有效值掩膜 (逐值 OR)
    valid_mask = None
    for v in VALLEY_VALID_VALUES:
        m = (valley_da == v)
        valid_mask = m if valid_mask is None else (valid_mask | m)

    inner_mask = valid_mask & (valley_da % 10 == 2)
    outer_mask = valid_mask & (valley_da % 10 == 1)

    return {
        'inner': inner_mask,
        'outer': outer_mask,
        'all': valid_mask,
    }


def compute_stats(pixels_da):
    """
    计算像元统计量 (mean, std, cv), 使用dask延迟计算.

    Parameters
    ----------
    pixels_da : xarray.DataArray
        经掩膜后的NDVI数据 (含NaN)

    Returns
    -------
    tuple
        (mean, std, cv)
    """
    count = int(pixels_da.count().compute())
    if count == 0:
        return np.nan, np.nan, np.nan
    mean_val = float(pixels_da.mean().compute())
    std_val = float(pixels_da.std().compute())
    cv_val = std_val / mean_val if mean_val != 0 else np.nan
    return mean_val, std_val, cv_val


def get_output_path(out_dir, mode):
    """
    根据模式生成带后缀的输出文件路径.

    Parameters
    ----------
    out_dir : str
        输出目录
    mode : str
        "wind_only" | "valley_only" | "combined"

    Returns
    -------
    str
        输出Excel文件路径
    """
    suffix_map = {
        'wind_only': '_wind_only',
        'valley_only': '_valley_only',
        'combined': '_combined',
    }
    suffix = suffix_map[mode]
    return os.path.join(out_dir, f'NDVI_yearly_stats{suffix}.xlsx')


if __name__ == '__main__':
    # 验证模式参数
    assert ANALYSIS_MODE in ("wind_only", "valley_only", "combined"), \
        f"Invalid ANALYSIS_MODE: '{ANALYSIS_MODE}'. Must be 'wind_only', 'valley_only', or 'combined'."
    print(f"Analysis mode: {ANALYSIS_MODE}")

    out_path = get_output_path(out_dir, ANALYSIS_MODE)
    print(f"Output path: {out_path}")

    # ------ 初始化Dask集群 ------
    cluster = LocalCluster(n_workers=4, threads_per_worker=4, memory_limit='8GB')
    client = Client(cluster)
    print(f'Dask dashboard: {client.dashboard_link}')

    # ------ 读取迎风坡/背风坡掩膜 ------
    mask_da = rxr.open_rasterio(
        direction_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')
    print(f"Direction mask shape: {mask_da.shape}")

    # ------ 读取河谷掩膜 ------
    valley_da = rxr.open_rasterio(
        valley_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')
    print(f"Valley mask shape: {valley_da.shape}")

    # 校验空间一致性
    assert mask_da.shape == valley_da.shape, \
        (f"Shape mismatch: direction {mask_da.shape} vs valley {valley_da.shape}. "
         f"Ensure all inputs are co-registered.")

    # 构建布尔掩膜 (保持为dask数组, 延迟计算)
    windward_mask = (mask_da == WINDWARD_VAL)
    leeward_mask = (mask_da == LEEWARD_VAL)
    valley_masks = build_valley_masks_xr(valley_da)

    # ------ 根据模式定义分析分量 ------
    # 每个分量: (名称前缀, 布尔掩膜)
    if ANALYSIS_MODE == "wind_only":
        # 迎风坡/背风坡, 限定在河谷区域内 (inner + outer)
        components = [
            ('windward', windward_mask & valley_masks['all']),
            ('leeward', leeward_mask & valley_masks['all']),
        ]
    elif ANALYSIS_MODE == "valley_only":
        # 河谷内侧/外侧, 不区分迎/背风坡
        components = [
            ('inner', valley_masks['inner']),
            ('outer', valley_masks['outer']),
        ]
    elif ANALYSIS_MODE == "combined":
        # 四个分量: 河谷内侧×迎背风坡 + 河谷外侧×迎背风坡
        components = [
            ('inner_windward', valley_masks['inner'] & windward_mask),
            ('inner_leeward', valley_masks['inner'] & leeward_mask),
            ('outer_windward', valley_masks['outer'] & windward_mask),
            ('outer_leeward', valley_masks['outer'] & leeward_mask),
        ]

    print(f"Components: {[c[0] for c in components]}")

    # ------ 逐年计算 ------
    records = []
    for cur_year in range(start_year, end_year + 1):
        cur_path = os.path.join(ndvi_dir, f'NDVI_{cur_year}.tif')
        if not os.path.exists(cur_path):
            print(f'File NDVI_{cur_year}.tif not found, skip')
            continue

        print(f'Processing {cur_year}...')
        ndvi_da = rxr.open_rasterio(
            cur_path, chunks=chunk_size, masked=True
        ).squeeze().drop_vars('band')

        row = {'year': cur_year}

        for comp_name, comp_mask in components:
            pixels = ndvi_da.where(comp_mask)
            mean_val, std_val, cv_val = compute_stats(pixels)

            row[f'{comp_name}_mean'] = mean_val
            row[f'{comp_name}_std'] = std_val
            row[f'{comp_name}_cv'] = cv_val

            print(f'  {comp_name:>20s}: mean={mean_val:.4f}, std={std_val:.4f}, cv={cv_val:.4f}')

        records.append(row)

    # ------ 关闭Dask集群 ------
    client.close()
    cluster.close()

    # ------ 输出Excel ------
    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f'\nOutput saved to: {out_path}')
    print(df.to_string(index=False))