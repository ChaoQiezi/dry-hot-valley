# @Author  : ChaoQiezi
# @Time    : 2026/3/28 下午3:06
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_windward_leeward_stats.py

"""
This script is used to 分别计算迎风坡和背风坡的NDVI年际均值(2019-2025)

输入:
  - 逐年NDVI栅格 (NDVI_{year}.tif)
  - 迎风坡/背风坡 二值栅格 (direction.tif), 假设: 1=迎风坡, 2=背风坡
输出:
  - Excel表格, 包含每年迎风坡/背风坡的 mean, std, cv
"""

import os
import numpy as np
import pandas as pd
import xarray as xr
from dask.distributed import Client, LocalCluster
import rioxarray as rxr

# ============================================================
# 0. Configuration
# ============================================================
ndvi_dir = r'E:\GeoProjects\dry_hot_valley\NDVI\Yearly'
direction_path = r"G:\GeoProjects\dry_hot_valley\windward_leeward\windward_leeward.tif"  # 二值栅格: 1=迎风坡, 2=背风坡
out_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_windward_leeward_yearly.xlsx'

start_year = 2019
end_year = 2025
chunk_size = {'x': 4096, 'y': 4096}

# 迎风坡/背风坡在二值栅格中的像元值 (根据实际情况修改)
WINDWARD_VAL = 1
LEEWARD_VAL = 2

if __name__ == '__main__':
    # ------ 初始化Dask集群 ------
    cluster = LocalCluster(n_workers=4, threads_per_worker=4, memory_limit='8GB')
    client = Client(cluster)
    print(f'Dask dashboard: {client.dashboard_link}')

    # ------ 读取迎风坡/背风坡掩膜 ------
    # direction.tif 与NDVI同分辨率同范围, 只需读取一次
    mask_da = rxr.open_rasterio(
        direction_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')
    print(f"Direction mask shape: {mask_da.shape}")

    # 构建布尔掩膜 (保持为dask数组, 延迟计算)
    windward_mask = (mask_da == WINDWARD_VAL)
    leeward_mask = (mask_da == LEEWARD_VAL)

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

        # --- 迎风坡统计 ---
        windward_pixels = ndvi_da.where(windward_mask)
        ww_mean = float(windward_pixels.mean().compute())
        ww_std = float(windward_pixels.std().compute())
        ww_cv = ww_std / ww_mean if ww_mean != 0 else np.nan

        # --- 背风坡统计 ---
        leeward_pixels = ndvi_da.where(leeward_mask)
        lw_mean = float(leeward_pixels.mean().compute())
        lw_std = float(leeward_pixels.std().compute())
        lw_cv = lw_std / lw_mean if lw_mean != 0 else np.nan

        records.append({
            'year': cur_year,
            'windward_mean': ww_mean,
            'windward_std': ww_std,
            'windward_cv': ww_cv,
            'leeward_mean': lw_mean,
            'leeward_std': lw_std,
            'leeward_cv': lw_cv,
        })
        print(f'  Windward: mean={ww_mean:.4f}, std={ww_std:.4f}, cv={ww_cv:.4f}')
        print(f'  Leeward:  mean={lw_mean:.4f}, std={lw_std:.4f}, cv={lw_cv:.4f}')

    # ------ 关闭Dask集群 ------
    client.close()
    cluster.close()

    # ------ 输出Excel ------
    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f'\nOutput saved to: {out_path}')
    print(df.to_string(index=False))