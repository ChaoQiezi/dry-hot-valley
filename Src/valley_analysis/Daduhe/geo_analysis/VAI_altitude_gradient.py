# @Author  : ChaoQiezi
# @Time    : 2026/4/27 下午8:04
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_altitude_gradient.py

"""
This script is used to 计算不同高程梯度下VAI的统计值

VAI_3km_region.tif 和 DEM_3km_region.tif 已在VAI空间分布计算阶段同步生成,
二者分辨率/范围/CRS完全一致, 直接读取配对即可.

按高程梯度(50m)分bin, 统计每个bin内的:
  - VAI均值、标准差、中位数
  - VAI>0比例 (迎风坡更绿)、VAI<0比例 (背风坡更绿)
  - 网格数量

输入:
  - VAI GeoTIFF (3km分辨率)
  - DEM GeoTIFF (3km分辨率, 网格内平均高程)
输出:
  - Excel表格
"""

import os
import numpy as np
import pandas as pd
import rasterio as rio

# ============================================================
# 0. Configuration
# ============================================================
vai_path = r"E:\GeoProjects\dry_hot_valley\Daduhe\VAI\VAI_3km_region.tif"
dem_path = r"E:\GeoProjects\dry_hot_valley\Daduhe\VAI\DEM_3km_region.tif"
out_path = r"E:\GeoProjects\dry_hot_valley\Daduhe\Result\Table\VAI_altitude_gradient.xlsx"

elev_step = 100  # 高程梯度间隔(m)


def load_checkpoint(in_path):
    if os.path.exists(in_path):
        df = pd.read_excel(in_path)
        done = set()
        for _, row in df.iterrows():
            done.add(row['elev_center'])
        print(f'[Checkpoint] Loaded {len(done)} completed bins from {os.path.basename(in_path)}')
        return done, df
    else:
        print('[Checkpoint] No previous results found, starting fresh')
        return set(), pd.DataFrame()


def save_checkpoint(df, out_path):
    df_sorted = df.sort_values('elev_center').reset_index(drop=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_sorted.to_excel(out_path, index=False)


# ============================================================
# 1. Read data
# ============================================================
if __name__ == '__main__':
    print("Reading VAI_3km...")
    with rio.open(vai_path, 'r') as src:
        vai_data = src.read(1).astype(np.float64)
        vai_nodata = src.nodata
    if vai_nodata is not None:
        vai_data[vai_data == vai_nodata] = np.nan

    print("Reading DEM_3km...")
    with rio.open(dem_path, 'r') as src:
        dem_data = src.read(1).astype(np.float64)
        dem_nodata = src.nodata
    if dem_nodata is not None:
        dem_data[dem_data == dem_nodata] = np.nan

    print(f"  Shape: {vai_data.shape}")
    done_set, done_df = load_checkpoint(out_path)

    # ============================================================
    # 2. Paired valid data
    # ============================================================
    both_valid = np.isfinite(vai_data) & np.isfinite(dem_data)
    vai_flat = vai_data[both_valid]
    elev_flat = dem_data[both_valid]
    print(f"  Valid grid cells: {both_valid.sum()}")
    print(f"  Elevation range: [{elev_flat.min():.0f}, {elev_flat.max():.0f}] m")
    print(f"  VAI range: [{vai_flat.min():.4f}, {vai_flat.max():.4f}]")

    # ============================================================
    # 3. Bin by elevation
    # ============================================================
    elev_lo = int(np.floor(elev_flat.min() / elev_step) * elev_step)
    elev_hi = int(np.ceil(elev_flat.max() / elev_step) * elev_step)
    elev_edges = np.arange(elev_lo, elev_hi + elev_step, elev_step)
    n_bins = len(elev_edges) - 1
    print(f"  Elevation bins: {n_bins}, {elev_lo}m → {elev_hi}m (step={elev_step}m)")

    bin_idx = np.digitize(elev_flat, elev_edges) - 1
    bin_idx = np.clip(bin_idx, 0, n_bins - 1)

    records = done_df.to_dict(orient='records') if len(done_df) > 0 else []
    try:
        for i in range(n_bins):
            lo = elev_edges[i]
            hi = elev_edges[i + 1]
            center = (lo + hi) / 2.0

            if center in done_set:
                print(f'  [{lo:5.0f}, {hi:5.0f}) m  |  Skipped (center={center:.0f})')
                continue

            mask = bin_idx == i
            cnt = mask.sum()

            if cnt == 0:
                records.append({
                    'elev_lo': lo, 'elev_hi': hi, 'elev_center': center,
                    'vai_mean': np.nan, 'vai_std': np.nan, 'vai_median': np.nan,
                    'pct_gt0': np.nan, 'pct_lt0': np.nan, 'count': 0,
                })
                done_set.add(center)
                continue

            vai_bin = vai_flat[mask]
            records.append({
                'elev_lo': lo,
                'elev_hi': hi,
                'elev_center': center,
                'vai_mean': np.mean(vai_bin),
                'vai_std': np.std(vai_bin),
                'vai_median': np.median(vai_bin),
                'pct_gt0': (vai_bin > 0).mean() * 100,
                'pct_lt0': (vai_bin < 0).mean() * 100,
                'count': cnt,
            })
            done_set.add(center)
            print(f'  [{lo:5.0f}, {hi:5.0f}) m  |  n={cnt:>6,}, mean={np.mean(vai_bin):.4f}, '
                  f'gt0={((vai_bin > 0).mean() * 100):.1f}%, lt0={((vai_bin < 0).mean() * 100):.1f}%')
    except KeyboardInterrupt:
        print(f'\n[Interrupted] Progress saved to: {out_path}')
        print(f'Total completed: {len(done_set)} / {n_bins} bins')
        print('Re-run this script to continue from where you left off.')
    except Exception as e:
        print(f'\n[Error] {e}')
        print(f'Progress saved to: {out_path}')
        print(f'Total completed: {len(done_set)} / {n_bins} bins')
    finally:
        if len(records) > 0:
            save_checkpoint(pd.DataFrame(records), out_path)

    # ============================================================
    # 4. Output
    # ============================================================
    df = pd.DataFrame(records).sort_values('elev_center').reset_index(drop=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_excel(out_path, index=False)

    print(f"\nOutput saved to: {out_path}")
    print(f"Bins with data: {(df['count'] > 0).sum()} / {n_bins}")
    print("Done.")
