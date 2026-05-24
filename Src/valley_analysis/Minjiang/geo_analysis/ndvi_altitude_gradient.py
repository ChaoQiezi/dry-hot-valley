# @Author  : ChaoQiezi
# @Time    : 2026/4/21 下午8:39
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_altitude_gradient.py

"""
This script is used to 高度维度分析: 以50m为海拔梯度, 计算不同高程梯度下迎风坡和背风坡的NDVI统计值;

输入:
  - NDVI年际均值栅格 (NDVI_interannual_mean.tif)
  - DEM栅格 (elevation_10m_projected.tif)
  - 迎风坡/背风坡二值栅格 (direction.tif)
  注: 三者分辨率/范围/CRS已统一 (UTM 47N, 10m)

输出:
  - Excel表格, 包含每个高程梯度带内迎风坡/背风坡的 mean, std, count

高程梯度带: 每100m一个bin, 范围自动从DEM中获取
"""

import os
import numpy as np
import pandas as pd
from glob import glob
from dask.distributed import Client, LocalCluster
from dask.diagnostics import ProgressBar
import dask.array as da
import rioxarray as rxr

# ============================================================
# 0. Configuration
# ============================================================
# ndvi_path = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\NDVI\Interannual\NDVI_interannual_mean.tif"
ndvi_dir = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\NDVI\Yearly"
dem_path = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\geo_factor\elevation_10m_projected.tif"
aspect_path = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\geo_factor\windward_leeward.tif"  # 二值栅格: 1=迎风坡, 2=背风坡
interannual_ndvi_path = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\NDVI\Interannual\NDVI_interannual_mean.tif"
# out_path = r'E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\Result\Table\altitude\NDVI_elevation_gradient.xlsx'
out_dir = r'E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\Result\Table\altitude'

chunk_size = {'x': 4096, 'y': 4096}
elev_step = 50  # 高程梯度间隔(m)

# 迎风坡/背风坡像元值
WINDWARD_VAL = 1
LEEWARD_VAL = 2


def load_checkpoint(in_path):
    if os.path.exists(in_path):
        df = pd.read_excel(in_path)
        done = set(df['elev_center'].values)
        print(f'[Checkpoint] Loaded {len(done)} completed bins from {os.path.basename(in_path)}')
        return done, df
    else:
        print('[Checkpoint] No previous results found, starting fresh')
        return set(), pd.DataFrame()


def save_checkpoint(df, out_path) :
    df_sorted = df.sort_values('elev_center').reset_index(drop=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_sorted.to_excel(out_path, index=False)


def main(out_path, ndvi_path, dem_path, aspect_path):
    # 加载已计算结果
    done_set, done_df = load_checkpoint(out_path)

    # ------ 读取数据 (延迟加载) ------
    print('Loading datasets (lazy)...')
    ndvi_da = rxr.open_rasterio(
        ndvi_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    dem_da = rxr.open_rasterio(
        dem_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    dir_da = rxr.open_rasterio(
        aspect_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    print(f'  NDVI shape: {ndvi_da.shape}')
    print(f'  DEM  shape: {dem_da.shape}')
    print(f'  DIR  shape: {dir_da.shape}')

    # ------ 确定高程范围 ------
    print('Computing DEM range...')
    with ProgressBar():
        dem_min = float(dem_da.min().compute())
        dem_max = float(dem_da.max().compute())
    print(f'  DEM range: [{dem_min:.1f}, {dem_max:.1f}] m')

    # 向下/向上取整到elev_step的整数倍
    elev_lo = int(np.floor(dem_min / elev_step) * elev_step)
    elev_hi = int(np.ceil(dem_max / elev_step) * elev_step)
    elev_edges = np.arange(elev_lo, elev_hi + elev_step, elev_step)
    n_bins = len(elev_edges) - 1
    print(f'  Elevation bins: {n_bins} bins from {elev_lo}m to {elev_hi}m (step={elev_step}m)')

    # ------ 构建布尔掩膜 ------
    windward_mask = (dir_da == WINDWARD_VAL)
    leeward_mask = (dir_da == LEEWARD_VAL)

    # ------ 逐高程带计算统计量 ------
    records = done_df.to_dict(orient='records') if len(done_df) > 0 else []
    try:
        for i in range(n_bins):
            lo = elev_edges[i]
            hi = elev_edges[i + 1]
            center = (lo + hi) / 2.0

            if center in done_set:
                print(f'  [{lo:5.0f}, {hi:5.0f}) m  |  Skipped (center={center:.2f})')
                continue

            # 当前高程带掩膜
            elev_mask = (dem_da >= lo) & (dem_da < hi)

            # 迎风坡
            ww_pixels = ndvi_da.where(elev_mask & windward_mask)
            ww_count = int(ww_pixels.count().compute())
            if ww_count > 0:
                ww_mean = float(ww_pixels.mean().compute())
                ww_std = float(ww_pixels.std().compute())
            else:
                ww_mean, ww_std = np.nan, np.nan

            # 背风坡
            lw_pixels = ndvi_da.where(elev_mask & leeward_mask)
            lw_count = int(lw_pixels.count().compute())
            if lw_count > 0:
                lw_mean = float(lw_pixels.mean().compute())
                lw_std = float(lw_pixels.std().compute())
            else:
                lw_mean, lw_std = np.nan, np.nan

            records.append({
                'elev_lo': lo,
                'elev_hi': hi,
                'elev_center': center,
                'windward_mean': ww_mean,
                'windward_std': ww_std,
                'windward_count': ww_count,
                'leeward_mean': lw_mean,
                'leeward_std': lw_std,
                'leeward_count': lw_count,
            })
            done_set.add(center)
            print(f'  [{lo:5.0f}, {hi:5.0f}) m  |  '
                  f'WW: n={ww_count:>10,}, mean={ww_mean:.4f}  |  '
                  f'LW: n={lw_count:>10,}, mean={lw_mean:.4f}')
    except KeyboardInterrupt:
        # Ctrl+C 优雅退出: 上一个完成的bin已经写入磁盘
        print(f'Progress saved to: {out_path}')
        print(f'Total completed: {len(done_set)} / {n_bins} bins')
        print('Re-run this script to continue from where you left off.')
    except Exception as e:
        print(f'Error: {e}')
        print(f'Progress saved to: {out_path}')
        print(f'Total completed: {len(done_set)} / {n_bins} bins')
        print(f'Re-run this script to continue from where you left off. Got error {e}')
    finally:
        # 保存当前进度
        if len(records) > 0:
            save_checkpoint(pd.DataFrame(records), out_path)
    # ------ 输出Excel ------
    df = pd.DataFrame(records).sort_values('elev_center').reset_index(drop=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f'\nOutput saved to: {out_path}')
    print(f'Total bins: {len(df)}, non-empty windward: {df["windward_count"].gt(0).sum()}, '
          f'non-empty leeward: {df["leeward_count"].gt(0).sum()}')


if __name__ == '__main__':
    # ------ 初始化Dask集群 ------
    cluster = LocalCluster(n_workers=6, threads_per_worker=8, memory_limit='6GB')
    client = Client(cluster)
    print(f'Dask dashboard: {client.dashboard_link}')

    # 检索
    wildcard = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\NDVI\Yearly\NDVI_*_region.tif"
    ndvi_paths = glob(wildcard)

    # 迭代处理 (逐年)
    for ndvi_path in ndvi_paths:
        out_path = os.path.join(out_dir, os.path.basename(ndvi_path).replace('.tif', '_elevation_gradient.xlsx'))

        if os.path.exists(out_path):
            print(f'[Skip] Output already exists: {os.path.basename(out_path)}')
            continue

        main(out_path, ndvi_path, dem_path, aspect_path)
        print(f'Finished: {ndvi_path}')

    # 年际均值处理
    interannual_out_path = os.path.join(out_dir, 'NDVI_interannual_mean_elevation_gradient.xlsx')
    if os.path.exists(interannual_out_path):
        print(f'[Skip] Output already exists: {os.path.basename(interannual_out_path)}')
    else:
        main(interannual_out_path, interannual_ndvi_path, dem_path, aspect_path)
        print(f'Finished: {os.path.basename(interannual_ndvi_path)}')

    # ------ 关闭Dask集群 ------
    client.close()
    cluster.close()
    print('All done.')

