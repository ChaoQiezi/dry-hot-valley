# @Author  : ChaoQiezi
# @Time    : 2026/3/23 下午3:21
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_altitude_analysis.py

"""
This script is used to 高度维度分析: 以50m为海拔梯度, 计算不同高程梯度下各分量的NDVI统计值;

2026/4/13-ps: 加入河谷内外侧的维度限制进行分析

分析模式 (ANALYSIS_MODE):
  - "wind_only":    仅在迎风坡/背风坡维度进行分析 (限定在河谷区域内)
  - "valley_only":  仅在河谷内侧/外侧维度进行分析 (不区分迎/背风坡)
  - "combined":     综合两个维度, 产出四个分量:
                    河谷内侧迎风坡、河谷内侧背风坡、河谷外侧迎风坡、河谷外侧背风坡

河谷栅格编码:
  十位数: 1=大渡河, 2=岷江, 3=金沙江, 4=雅磨江
  个位数: 1=outer, 2=inner

输入:
  - NDVI年际均值栅格 (NDVI_interannual_mean.tif)
  - DEM栅格 (elevation_10m_projected.tif)
  - 迎风坡/背风坡二值栅格 (windward_leeward.tif)
  - 河谷区域栅格 (valley_chuanxi_clip.tif)
  注: 四者分辨率/范围/CRS已统一 (UTM 47N, 10m)

输出:
  - Excel表格, 包含每个高程梯度带内各分量的 mean, std, count

高程梯度带: 每50m一个bin, 范围自动从DEM中获取
"""

import os

import dask.array as da
from dask.diagnostics import ProgressBar
from dask.distributed import Client, LocalCluster
import numpy as np
import pandas as pd
import rioxarray as rxr

# 准备
ndvi_path = r"E:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif"
# dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_10m_projected.tif"
dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_10m_projected_valley_clip.tif"  # 有效区域为河谷区域
direction_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"  # 二值栅格: 1=迎风坡, 2=背风坡
valley_path = r"E:\GeoProjects\dry_hot_valley\valley_area\valley_chuanxi\valley_chuanxi_clip.tif"
out_dir = r'E:\GeoProjects\dry_hot_valley\Output\Table'

# 分析模式: "wind_only" | "valley_only" | "combined"
ANALYSIS_MODE = "combined"

chunk_size = {'x': 4096, 'y': 4096}
elev_step = 50  # 高程梯度间隔(m)

# 迎风坡/背风坡像元值
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
    return os.path.join(out_dir, f'NDVI_elevation_gradient{suffix}.xlsx')


def load_checkpoint(in_path):
    """加载已计算结果用于断点续算."""
    if os.path.exists(in_path):
        df = pd.read_excel(in_path)
        done = df['elev_center'].values
        print(f'[Checkpoint] Loaded {len(done)} completed bins from {os.path.basename(in_path)}')
        return done, df
    else:
        print('[Checkpoint] No previous results found, starting fresh')
        return np.array([]), pd.DataFrame()


def save_checkpoint(df, out_path):
    """保存当前进度到Excel."""
    df_sorted = df.sort_values('elev_center').reset_index(drop=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_sorted.to_excel(out_path, index=False)


if __name__ == '__main__':
    # 验证模式参数
    assert ANALYSIS_MODE in ("wind_only", "valley_only", "combined"), \
        f"Invalid ANALYSIS_MODE: '{ANALYSIS_MODE}'. Must be 'wind_only', 'valley_only', or 'combined'."
    print(f"Analysis mode: {ANALYSIS_MODE}")

    out_path = get_output_path(out_dir, ANALYSIS_MODE)
    print(f"Output path: {out_path}")

    # 加载已计算结果
    done_set, done_df = load_checkpoint(out_path)

    # ------ 初始化Dask集群 ------
    cluster = LocalCluster(n_workers=6, threads_per_worker=8, memory_limit='6GB')
    client = Client(cluster)
    print(f'Dask dashboard: {client.dashboard_link}')

    # ------ 读取数据 (延迟加载) ------
    print('Loading datasets (lazy)...')
    ndvi_da = rxr.open_rasterio(
        ndvi_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    dem_da = rxr.open_rasterio(
        dem_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    dir_da = rxr.open_rasterio(
        direction_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    valley_da = rxr.open_rasterio(
        valley_path, chunks=chunk_size, masked=True
    ).squeeze().drop_vars('band')

    print(f'  NDVI   shape: {ndvi_da.shape}')
    print(f'  DEM    shape: {dem_da.shape}')
    print(f'  DIR    shape: {dir_da.shape}')
    print(f'  Valley shape: {valley_da.shape}')

    # 校验空间一致性
    shapes = {
        'NDVI': ndvi_da.shape,
        'DEM': dem_da.shape,
        'DIR': dir_da.shape,
        'Valley': valley_da.shape,
    }
    unique_shapes = set(shapes.values())
    assert len(unique_shapes) == 1, \
        f"Shape mismatch among input rasters: {shapes}. Ensure all inputs are co-registered."

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
    valley_masks = build_valley_masks_xr(valley_da)

    # ------ 根据模式定义分析分量 ------
    # 每个分量: (名称前缀, 布尔掩膜)
    if ANALYSIS_MODE == "wind_only":
        components = [
            ('windward', windward_mask & valley_masks['all']),
            ('leeward', leeward_mask & valley_masks['all']),
        ]
    elif ANALYSIS_MODE == "valley_only":
        components = [
            ('inner', valley_masks['inner']),
            ('outer', valley_masks['outer']),
        ]
    elif ANALYSIS_MODE == "combined":
        components = [
            ('inner_windward', valley_masks['inner'] & windward_mask),
            ('inner_leeward', valley_masks['inner'] & leeward_mask),
            ('outer_windward', valley_masks['outer'] & windward_mask),
            ('outer_leeward', valley_masks['outer'] & leeward_mask),
        ]

    print(f"Components: {[c[0] for c in components]}")

    # ------ 逐高程带计算统计量 ------
    records = done_df.to_dict(orient='records') if len(done_df) > 0 else []
    try:
        for i in range(n_bins):
            lo = elev_edges[i]
            hi = elev_edges[i + 1]
            center = (lo + hi) / 2.0

            if len(done_set) > 0 and np.isclose(done_set, center).any():
                print(f'  [{lo:5.0f}, {hi:5.0f}) m  |  Skipped (center={center:.2f})')
                continue

            # 当前高程带掩膜
            elev_mask = (dem_da >= lo) & (dem_da < hi)

            row = {
                'elev_lo': lo,
                'elev_hi': hi,
                'elev_center': center,
            }

            log_parts = [f'[{lo:5.0f}, {hi:5.0f}) m']

            for comp_name, comp_mask in components:
                pixels = ndvi_da.where(elev_mask & comp_mask)
                count = int(pixels.count().compute())
                if count > 0:
                    mean_val = float(pixels.mean().compute())
                    std_val = float(pixels.std().compute())
                else:
                    mean_val, std_val = np.nan, np.nan

                row[f'{comp_name}_mean'] = mean_val
                row[f'{comp_name}_std'] = std_val
                row[f'{comp_name}_count'] = count

                log_parts.append(f'{comp_name}: n={count:>10,}, mean={mean_val:.4f}')

            records.append(row)
            done_set = np.append(done_set, center)
            print(f'  {"  |  ".join(log_parts)}')

    except KeyboardInterrupt:
        print(f'\n[Interrupted] Progress saved to: {out_path}')
        print(f'Total completed: {len(records)} / {n_bins} bins')
        print('Re-run this script to continue from where you left off.')
    except Exception as e:
        print(f'\n[Error] {e}')
        print(f'Progress saved to: {out_path}')
        print(f'Total completed: {len(records)} / {n_bins} bins')
        print(f'Re-run this script to continue from where you left off.')
    finally:
        # 保存当前进度
        if len(records) > 0:
            save_checkpoint(pd.DataFrame(records), out_path)
        # ------ 关闭Dask集群 ------
        client.close()
        cluster.close()

    # ------ 输出Excel ------
    df = pd.DataFrame(records).sort_values('elev_center').reset_index(drop=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f'\nOutput saved to: {out_path}')

    # 统计各分量非空bin数
    summary_parts = [f'Total bins: {len(df)}']
    for comp_name, _ in components:
        col = f'{comp_name}_count'
        if col in df.columns:
            non_empty = df[col].gt(0).sum()
            summary_parts.append(f'non-empty {comp_name}: {non_empty}')
    print(', '.join(summary_parts))