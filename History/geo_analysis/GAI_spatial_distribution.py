# @Author  : ChaoQiezi
# @Time    : 2026/4/1
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: gai_spatial_stats.py

"""
This script is used to 计算迎风坡与背风坡的绿度不对称指数(GAI)空间分布

2026/4/13-ps: 加入河谷内外侧的维度限制进行分析

方法参考:
  - Xie et al. (2025, GRL): GAI = NDVI_west / NDVI_east, 3×3 km grid
  - Yin et al. (2023, AFM): GAI = NDVI_PFS / NDVI_EFS, 3×3 km grid

本研究:
  - GAI = NDVI_windward / NDVI_leeward
  - 3×3 km 非重叠网格 (UTM 47N, 10m分辨率 → 300×300 像素/网格)
  - 每个网格内: 分别提取迎风坡/背风坡的有效NDVI像素
  - 若任一侧有效像素 < 50, 该网格标记为nodata (保证统计稳健性)
  - 进行双样本t检验 (two-tailed), 检验迎风坡与背风坡NDVI均值差异的显著性

河谷内外侧维度 (VALLEY_MODE):
  - "inner": 仅使用河谷内侧像元 (valley栅格个位数==2)
  - "outer": 仅使用河谷外侧像元 (valley栅格个位数==1)
  - "all":   使用河谷内外侧所有像元 (valley栅格有效值>0)

河谷栅格编码:
  十位数: 1=大渡河, 2=岷江, 3=金沙江, 4=雅磨江
  个位数: 1=outer, 2=inner

输入:
  - NDVI年际均值栅格 (NDVI_interannual_mean.tif), UTM 47N, 10m
  - 迎风坡/背风坡二值栅格 (windward_leeward.tif), 1=迎风坡, 2=背风坡
  - 河谷区域栅格 (valley_chuanxi_clip.tif), 编码见上
  - DEM栅格 (elevation_10m_projected.tif), UTM 47N, 10m
输出:
  - GAI GeoTIFF (3km分辨率)
  - p-value GeoTIFF (3km分辨率)
  - NDVI_windward GeoTIFF (3km分辨率, 网格内迎风坡均值)
  - NDVI_leeward GeoTIFF (3km分辨率, 网格内背风坡均值)
  - DEM GeoTIFF (3km分辨率, 网格内DEM均值)
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

# 准备
ndvi_mean_path = r"E:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif"
direction_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\windward_leeward\windward_leeward.tif"
dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_10m_projected.tif"
valley_path = r"E:\GeoProjects\dry_hot_valley\valley_area\valley_chuanxi\valley_chuanxi_clip.tif"

out_dir = r"E:\GeoProjects\dry_hot_valley\GAI"

# 河谷内外侧模式: "inner" | "outer" | "all"
# VALLEY_MODE = "inner"
# VALLEY_MODE = "outer"
VALLEY_MODE = "all"

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


def build_valley_mask(valley_block, valley_nodata, mode):
    """
    根据河谷栅格和模式构建布尔掩膜.

    Parameters
    ----------
    valley_block : np.ndarray
        河谷栅格数据块
    valley_nodata : float or None
        河谷栅格nodata值
    mode : str
        "inner" | "outer" | "all"

    Returns
    -------
    np.ndarray (bool)
        True表示该像元属于目标河谷区域
    """

    # 河谷栅格编码: 个位数 1=outer, 2=inner
    # 有效河谷值集合: {11, 12, 21, 22, 31, 32, 41, 42}
    VALLEY_VALID_VALUES = {11, 12, 21, 22, 31, 32, 41, 42}

    # 先排除nodata和非法值
    valid = np.zeros_like(valley_block, dtype=bool)
    for v in VALLEY_VALID_VALUES:
        valid |= (valley_block == v)
    if valley_nodata is not None:
        valid &= (~np.isclose(valley_block.astype(np.float64), float(valley_nodata)))

    if mode == "inner":
        # 个位数 == 2: 河谷内侧
        return valid & (valley_block % 10 == 2)
    elif mode == "outer":
        # 个位数 == 1: 河谷外侧
        return valid & (valley_block % 10 == 1)
    elif mode == "all":
        # 所有有效河谷像元
        return valid
    else:
        raise ValueError(f"Invalid VALLEY_MODE: '{mode}'. Must be 'inner', 'outer', or 'all'.")


def get_output_paths(out_dir, mode):
    """
    根据模式生成带后缀的输出路径.

    Parameters
    ----------
    out_dir : str
        输出目录
    mode : str
        "inner" | "outer" | "all"

    Returns
    -------
    dict
        包含各输出文件路径的字典
    """
    suffix = f"_valley_{mode}"
    return {
        'gai':     os.path.join(out_dir, f"GAI_3km{suffix}.tif"),
        'pval':    os.path.join(out_dir, f"GAI_pvalue_3km{suffix}.tif"),
        'ww_mean': os.path.join(out_dir, f"NDVI_windward_3km{suffix}.tif"),
        'lw_mean': os.path.join(out_dir, f"NDVI_leeward_3km{suffix}.tif"),
        'dem':     os.path.join(out_dir, f"DEM_3km{suffix}.tif"),
    }


if __name__ == '__main__':
    # ============================================================
    # 1. Read raster metadata
    # ============================================================
    t_start = time.time()

    # 验证模式参数
    assert VALLEY_MODE in ("inner", "outer", "all"), \
        f"Invalid VALLEY_MODE: '{VALLEY_MODE}'. Must be 'inner', 'outer', or 'all'."
    print(f"Valley mode: {VALLEY_MODE}")

    os.makedirs(out_dir, exist_ok=True)

    # 生成输出路径
    out_paths = get_output_paths(out_dir, VALLEY_MODE)
    print(f"Output directory: {out_dir}")
    for key, path in out_paths.items():
        print(f"  {key}: {os.path.basename(path)}")

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
    with rio.open(valley_path, 'r') as src:
        valley_nodata = src.nodata
        valley_rows = src.height
        valley_cols = src.width
        print(f"Valley raster: {valley_rows} × {valley_cols}")
        # 校验空间一致性
        assert valley_rows == total_rows and valley_cols == total_cols, \
            (f"Valley raster dimensions ({valley_rows}×{valley_cols}) "
             f"do not match NDVI raster ({total_rows}×{total_cols}). "
             f"Ensure all inputs are co-registered.")

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
    dem_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)

    # ============================================================
    # 3. 逐网格计算
    # ============================================================
    print(f"\nProcessing grids (valley_mode={VALLEY_MODE})...")
    src_ndvi = rio.open(ndvi_mean_path, 'r')
    src_dir = rio.open(direction_path, 'r')
    src_dem = rio.open(dem_path, 'r')
    src_valley = rio.open(valley_path, 'r')

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
            valley_block = src_valley.read(1, window=window)

            # 河谷区域掩膜
            valley_mask = build_valley_mask(valley_block, valley_nodata, VALLEY_MODE)

            # 有效NDVI掩膜 (在河谷掩膜基础上进一步约束)
            valid_mask = (
                np.isfinite(ndvi_block)
                & np.isfinite(dem_block)
                & (ndvi_block > NDVI_MIN)
                & valley_mask
            )
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
    src_valley.close()

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
        (out_paths['gai'], gai, 'GAI'),
        (out_paths['pval'], pval, 'p-value'),
        (out_paths['ww_mean'], ww_mean_arr, 'NDVI_windward'),
        (out_paths['lw_mean'], lw_mean_arr, 'NDVI_leeward'),
        (out_paths['dem'], dem_arr, 'DEM'),
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
    print(f"Valley mode: {VALLEY_MODE}")
    print(f"Total time: {elapsed / 60:.1f} min")
    print(f"Grid cells: {n_grid_rows * n_grid_cols} total, "
          f"{valid_count} valid, {masked_count} masked")
    if len(gai_valid) > 0:
        print(f"GAI range: [{gai_valid.min():.4f}, {gai_valid.max():.4f}]")
        print(f"GAI mean: {gai_valid.mean():.4f}, median: {np.median(gai_valid):.4f}")
        print(f"GAI > 1 (windward greener): "
              f"{(gai_valid > 1).sum()} / {len(gai_valid)} "
              f"({(gai_valid > 1).mean() * 100:.1f}%)")
        print(f"GAI < 1 (leeward greener):  "
              f"{(gai_valid < 1).sum()} / {len(gai_valid)} "
              f"({(gai_valid < 1).mean() * 100:.1f}%)")
    else:
        print("WARNING: No valid GAI cells computed. Check valley mask coverage and thresholds.")
    if len(pval_valid) > 0:
        print(f"Significant (p < 0.05): "
              f"{(pval_valid < 0.05).sum()} / {len(pval_valid)} "
              f"({(pval_valid < 0.05).mean() * 100:.1f}%)")
        print(f"Significant (p < 0.01): "
              f"{(pval_valid < 0.01).sum()} / {len(pval_valid)} "
              f"({(pval_valid < 0.01).mean() * 100:.1f}%)")
    print("Done.")