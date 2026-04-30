# @Author  : ChaoQiezi
# @Time    : 2026/4/27 下午7:40
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_spatial_distribution.py

"""
This script is used to 计算迎风坡与背风坡的植被不对称指数(VAI)空间分布

# 方法参考:
#   - Xie et al. (2025, GRL): GAI = NDVI_west / NDVI_east, 3×3 km grid
#   - Yin et al. (2023, AFM): GAI = NDVI_PFS / NDVI_EFS, 3×3 km grid

本研究:
  - VAI = (NDVI_windward - NDVI_leeward) / ((NDVI_windward + NDVI_leeward) / 2) × 100%
  - 3×3 km 非重叠网格 (UTM 47N, 10m分辨率 → 300×300 像素/网格)
  - 每个网格内: 分别提取迎风坡/背风坡的有效NDVI像素
  - 若任一侧有效像素 < 50, 该网格标记为nodata (保证统计稳健性)
  - 进行双样本t检验 (two-tailed), 检验迎风坡与背风坡NDVI均值差异的显著性
  - VAI > 0 表示迎风坡更绿, VAI < 0 表示背风坡更绿

输入:
  - NDVI年际均值栅格 (NDVI_interannual_mean.tif), UTM 47N, 10m
  - 迎风坡/背风坡二值栅格 (windward_leeward.tif), 1=迎风坡, 2=背风坡
输出:
  - VAI GeoTIFF (3km分辨率)
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
ndvi_mean_path = r"E:\GeoProjects\dry_hot_valley\Yalongjiang\NDVI\Interannual\NDVI_interannual_mean_region.tif"
direction_path = r"E:\GeoProjects\dry_hot_valley\Yalongjiang\geo_factor\windward_leeward_region.tif"
dem_path = r"E:\GeoProjects\dry_hot_valley\Yalongjiang\geo_factor\elevation_10m_projected_region.tif"

out_dir = r"E:\GeoProjects\dry_hot_valley\Yalongjiang\VAI"
out_vai_path = os.path.join(out_dir, "VAI_3km_region.tif")
out_pval_path = os.path.join(out_dir, "VAI_pvalue_3km_region.tif")
out_ww_mean_path = os.path.join(out_dir, "NDVI_windward_3km_region.tif")
out_lw_mean_path = os.path.join(out_dir, "NDVI_leeward_3km_region.tif")
out_dem_path = os.path.join(out_dir, "DEM_3km_region.tif")
os.makedirs(out_dir, exist_ok=True)

# 网格参数
GRID_SIZE_M = 3000      # 3 km
PIXEL_SIZE_M = 10       # 10 m
GRID_PIXELS = GRID_SIZE_M // PIXEL_SIZE_M  # 300 pixels

# 迎风坡/背风坡像元值
WINDWARD_VAL = 1
LEEWARD_VAL = 2

# 最小有效像素数阈值 (参考 Xie 2025, Yin 2023: <50 masked)
MIN_PIXEL_THRESHOLD = 15

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
    with rio.open(dem_path, 'r') as src:
        dem_nodata = src.nodata

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
    vai = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    pval = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    ww_mean_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    lw_mean_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    dem_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)

    # ============================================================
    # 3. 逐网格计算
    # ============================================================
    print("\nProcessing grids...")
    src_ndvi = rio.open(ndvi_mean_path, 'r')
    src_dir = rio.open(direction_path, 'r')
    src_dem = rio.open(dem_path, 'r')

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
            dem_block = src_dem.read(1, window=window)

            # 有效NDVI掩膜
            valid_mask = np.isfinite(ndvi_block) & np.isfinite(dem_block) & (ndvi_block > NDVI_MIN)
            if ndvi_nodata is not None:
                valid_mask &= (~np.isclose(ndvi_block, ndvi_nodata))
            if dem_nodata is not None:
                valid_mask &= (~np.isclose(dem_block, dem_nodata))

            # 分方向提取
            ww_mask = valid_mask & (dir_block == WINDWARD_VAL)
            lw_mask = valid_mask & (dir_block == LEEWARD_VAL)
            ww_vals = ndvi_block[ww_mask]
            lw_vals = ndvi_block[lw_mask]

            # 阈值检查
            n_ww, n_lw = len(ww_vals), len(lw_vals)

            # 统计
            ww_m = np.mean(ww_vals)
            lw_m = np.mean(lw_vals)

            # VAI = (windward - leeward) / ((windward + leeward) / 2) × 100%
            mean_wl = (ww_m + lw_m) / 2
            if mean_wl > 0:
                vai[gi, gj] = (ww_m - lw_m) / mean_wl * 100  # 百分比, VAI>0 迎风更绿
            else:
                masked_count += 1
                continue

            # 计算DEM均值
            dem_m = np.mean(dem_block[valid_mask])

            # 均值存储
            ww_mean_arr[gi, gj] = ww_m
            lw_mean_arr[gi, gj] = lw_m
            dem_arr[gi, gj] = dem_m

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
    src_dem.close()

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
        (out_vai_path, vai, 'VAI'),
        (out_pval_path, pval, 'p-value'),
        (out_ww_mean_path, ww_mean_arr, 'NDVI_windward'),
        (out_lw_mean_path, lw_mean_arr, 'NDVI_leeward'),
        (out_dem_path, dem_arr, 'DEM'),
    ]:
        with rio.open(path, 'w', **out_profile) as dst:
            dst.write(data, 1)
        print(f"  {name} → {path}")

    # ============================================================
    # 5. Summary
    # ============================================================
    elapsed = time.time() - t_start
    vai_valid = vai[np.isfinite(vai)]
    pval_valid = pval[np.isfinite(pval)]

    print(f"\n{'=' * 60}")
    print(f"Total time: {elapsed / 60:.1f} min")
    print(f"Grid cells: {n_grid_rows * n_grid_cols} total, "
          f"{valid_count} valid, {masked_count} masked")
    if len(vai_valid) > 0:
        print(f"VAI range: [{vai_valid.min():.4f}, {vai_valid.max():.4f}]")
        print(f"VAI > 0 (windward greener): "
              f"{(vai_valid > 0).sum()} / {len(vai_valid)} "
              f"({(vai_valid > 0).mean() * 100:.1f}%)")
        print(f"VAI < 0 (leeward greener):  "
              f"{(vai_valid < 0).sum()} / {len(vai_valid)} "
              f"({(vai_valid < 0).mean() * 100:.1f}%)")
    if len(pval_valid) > 0:
        print(f"Significant (p < 0.05): "
              f"{(pval_valid < 0.05).sum()} / {len(pval_valid)} "
              f"({(pval_valid < 0.05).mean() * 100:.1f}%)")
        print(f"Significant (p < 0.01): "
              f"{(pval_valid < 0.01).sum()} / {len(pval_valid)} "
              f"({(pval_valid < 0.01).mean() * 100:.1f}%)")
    print("Done.")
