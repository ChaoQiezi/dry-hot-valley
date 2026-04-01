# @Author  : ChaoQiezi
# @Time    : 2026/4/1
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: gai_spatial_stats.py

"""
This script is used to 计算迎风坡与背风坡的绿度不对称指数(GAI)空间分布

方法参考:
  - Xie et al. (2025, GRL): GAI = NDVI_west / NDVI_east, 3×3 km grid
  - Yin et al. (2023, AFM): GAI = NDVI_PFS / NDVI_EFS, 3×3 km grid

本研究:
  - GAI = NDVI_windward / NDVI_leeward
  - 3×3 km 非重叠网格 (UTM 47N, 10m分辨率 → 300×300 像素/网格)
  - 每个网格内: 分别提取迎风坡/背风坡的有效NDVI像素
  - 若任一侧有效像素 < 50, 该网格标记为nodata (保证统计稳健性)
  - 进行双样本t检验 (two-tailed), 检验迎风坡与背风坡NDVI均值差异的显著性

输入:
  - NDVI年际均值栅格 (NDVI_interannual_mean.tif), UTM 47N, 10m
  - 迎风坡/背风坡二值栅格 (windward_leeward.tif), 1=迎风坡, 2=背风坡
输出:
  - GAI GeoTIFF (3km分辨率)
  - p-value GeoTIFF (3km分辨率)
  - NDVI_windward GeoTIFF (3km分辨率, 网格内迎风坡均值)
  - NDVI_leeward GeoTIFF (3km分辨率, 网格内背风坡均值)
  - windward_count / leeward_count GeoTIFF (3km分辨率, 有效像素数)
"""

import os
import time
import numpy as np
import rasterio as rio
from rasterio.transform import from_origin
from rasterio.windows import Window
from scipy.stats import ttest_ind
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
ndvi_mean_path = r"E:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif"
direction_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"

out_dir = r"E:\GeoProjects\dry_hot_valley\GAI"
out_gai_path = os.path.join(out_dir, "GAI_3km.tif")
out_pval_path = os.path.join(out_dir, "GAI_pvalue_3km.tif")
out_ww_mean_path = os.path.join(out_dir, "NDVI_windward_3km.tif")
out_lw_mean_path = os.path.join(out_dir, "NDVI_leeward_3km.tif")

# 网格参数
GRID_SIZE_M = 3000      # 3 km
PIXEL_SIZE_M = 10       # 10 m
GRID_PIXELS = GRID_SIZE_M // PIXEL_SIZE_M  # 300 pixels

# 迎风坡/背风坡像元值
WINDWARD_VAL = 1
LEEWARD_VAL = 2

# 最小有效像素数阈值 (参考 Xie 2025, Yin 2023: <50 masked)
MIN_PIXEL_THRESHOLD = 50

# NDVI有效性阈值 (参考 Yin 2023: NDVI > 0.1)
NDVI_MIN = 0.1

# ============================================================
# 1. Read raster metadata
# ============================================================
if __name__ == '__main__':
    t_start = time.time()

    os.makedirs(out_dir, exist_ok=True)

    # 获取栅格信息
    with rio.open(ndvi_mean_path, 'r') as src:
        ndvi_profile = src.profile.copy()
        ndvi_transform = src.transform
        ndvi_crs = src.crs
        ndvi_nodata = src.nodata
        total_rows = src.height
        total_cols = src.width
        print(f"NDVI raster: {total_rows} × {total_cols}")
        print(f"CRS: {ndvi_crs}")
        print(f"Transform: {ndvi_transform}")

    # 计算网格维度
    n_grid_rows = total_rows // GRID_PIXELS
    n_grid_cols = total_cols // GRID_PIXELS
    print(f"Grid dimensions: {n_grid_rows} × {n_grid_cols} "
          f"({n_grid_rows * n_grid_cols} cells)")
    print(f"Grid cell: {GRID_PIXELS}×{GRID_PIXELS} pixels = "
          f"{GRID_SIZE_M/1000:.0f}×{GRID_SIZE_M/1000:.0f} km")

    # 输出栅格的transform (3km分辨率)
    # 原始transform的左上角坐标 + 新的像素尺寸
    out_transform = from_origin(
        ndvi_transform.c,                    # 左上角X
        ndvi_transform.f,                    # 左上角Y
        GRID_SIZE_M,                         # X像素宽度
        GRID_SIZE_M,                         # Y像素高度
    )

    # ============================================================
    # 2. 初始化输出数组
    # ============================================================
    gai = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    pval = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    ww_mean_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    lw_mean_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)

    # ============================================================
    # 3. 逐网格计算
    # ============================================================
    print("\nProcessing grids...")
    src_ndvi = rio.open(ndvi_mean_path, 'r')
    src_dir = rio.open(direction_path, 'r')

    valid_count = 0
    masked_count = 0

    for gi in range(n_grid_rows):
        for gj in range(n_grid_cols):
            # 当前网格的像素范围
            row_start = gi * GRID_PIXELS
            col_start = gj * GRID_PIXELS
            window = Window(
                col_start, row_start,
                GRID_PIXELS, GRID_PIXELS
            )

            # 读取
            ndvi_block = src_ndvi.read(1, window=window).astype(np.float64)
            dir_block = src_dir.read(1, window=window)

            # 有效NDVI掩膜
            valid_mask = np.isfinite(ndvi_block) & (ndvi_block > NDVI_MIN)
            if ndvi_nodata is not None:
                valid_mask &= (ndvi_block != ndvi_nodata)

            # 分方向提取
            ww_mask = valid_mask & (dir_block == WINDWARD_VAL)
            lw_mask = valid_mask & (dir_block == LEEWARD_VAL)
            ww_vals = ndvi_block[ww_mask]
            lw_vals = ndvi_block[lw_mask]

            # 阈值检查
            if (len(ww_vals) < MIN_PIXEL_THRESHOLD) or (len(lw_vals) < MIN_PIXEL_THRESHOLD):
                masked_count += 1
                continue

            # 统计
            ww_m = np.mean(ww_vals)
            lw_m = np.mean(lw_vals)

            # GAI
            if lw_m > 0:
                gai[gi, gj] = ww_m / lw_m
            else:
                masked_count += 1
                continue

            # 均值存储
            ww_mean_arr[gi, gj] = ww_m
            lw_mean_arr[gi, gj] = lw_m

            # 双样本 t 检验 (two-tailed, 不假设等方差)
            t_stat, p_value = ttest_ind(ww_vals, lw_vals, equal_var=False)
            pval[gi, gj] = p_value

            valid_count += 1

        # 进度
        if (gi + 1) % 20 == 0 or gi == n_grid_rows - 1:
            pct = (gi + 1) / n_grid_rows * 100
            print(f"  Row {gi + 1}/{n_grid_rows} ({pct:.1f}%)  "
                  f"valid={valid_count}, masked={masked_count}")

    src_ndvi.close()
    src_dir.close()

    # ============================================================
    # 4. 输出GeoTIFF
    # ============================================================
    out_profile = {
        'driver': 'GTiff',
        'dtype': 'float32',
        'width': n_grid_cols,
        'height': n_grid_rows,
        'count': 1,
        'crs': ndvi_crs,
        'transform': out_transform,
        'nodata': np.nan,
        'compress': 'deflate',
        'tiled': True,
        'blockxsize': 256,
        'blockysize': 256,
    }

    for path, data, name in [
        (out_gai_path, gai, 'GAI'),
        (out_pval_path, pval, 'p-value'),
        (out_ww_mean_path, ww_mean_arr, 'NDVI_windward'),
        (out_lw_mean_path, lw_mean_arr, 'NDVI_leeward'),
    ]:
        with rio.open(path, 'w', **out_profile) as dst:
            dst.write(data, 1)
        print(f"  {name} → {path}")

    # ============================================================
    # 5. Summary
    # ============================================================
    elapsed = time.time() - t_start
    gai_valid = gai[np.isfinite(gai)]
    pval_valid = pval[np.isfinite(pval)]

    print(f"\n{'=' * 60}")
    print(f"Total time: {elapsed / 60:.1f} min")
    print(f"Grid cells: {n_grid_rows * n_grid_cols} total, "
          f"{valid_count} valid, {masked_count} masked")
    if len(gai_valid) > 0:
        print(f"GAI range: [{gai_valid.min():.4f}, {gai_valid.max():.4f}]")
        print(f"GAI > 1 (windward greener): "
              f"{(gai_valid > 1).sum()} / {len(gai_valid)} "
              f"({(gai_valid > 1).mean() * 100:.1f}%)")
        print(f"GAI < 1 (leeward greener):  "
              f"{(gai_valid < 1).sum()} / {len(gai_valid)} "
              f"({(gai_valid < 1).mean() * 100:.1f}%)")
    if len(pval_valid) > 0:
        print(f"Significant (p < 0.05): "
              f"{(pval_valid < 0.05).sum()} / {len(pval_valid)} "
              f"({(pval_valid < 0.05).mean() * 100:.1f}%)")
        print(f"Significant (p < 0.01): "
              f"{(pval_valid < 0.01).sum()} / {len(pval_valid)} "
              f"({(pval_valid < 0.01).mean() * 100:.1f}%)")
    print("Done.")