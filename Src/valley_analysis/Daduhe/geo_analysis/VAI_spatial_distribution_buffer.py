# @Author  : ChaoQiezi
# @Time    : 2026/5/7
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_spatial_distribution_buffer.py

"""
This script is used to 在大渡河河道4km缓冲区内重算3km网格VAI

与 VAI_strict_valley_3km.py(基于人为认定的干热河谷polygon)不同:
  - 河谷区域定义改为"河道中心线 ±4 km buffer"
  - 优点: 不依赖主观polygon delineation, 4 km 与典型河谷半宽接近
  - 横向覆盖 8 km, 略宽于 3 km grid 单元 (≥1 网格对全覆盖)

输入:
  - NDVI 年际均值栅格 (NDVI_interannual_mean_region.tif), UTM 47N, 10m
  - 迎风/背风二值栅格 (windward_leeward_region.tif), 1=迎风, 2=背风
  - DEM 栅格 (elevation_10m_projected_region.tif)
  - 河道中心线 (centerline_final.shp, 筛选 Daduhe 特征)
输出:
  - VAI_3km_buffer.tif 等 8 个栅格 (与 _strict 同套字段)
"""

import os
import time
import warnings

import numpy as np
import rasterio as rio
import shapefile
from pyproj import CRS, Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.windows import Window
from scipy.stats import ttest_ind
from shapely.geometry import LineString
from shapely.ops import unary_union

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
NDVI_PATH = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\NDVI\Interannual\NDVI_interannual_mean_region.tif"
DIRECTION_PATH = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\geo_factor\windward_leeward_region.tif"
DEM_PATH = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\geo_factor\elevation_10m_projected_region.tif"
CENTERLINE_PATH = r"E:\GeoProjects\dry_hot_valley\valley_area\river_net\centerline_final.shp"

OUT_DIR = r"E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\VAI"
OUT_VAI_PATH = os.path.join(OUT_DIR, "VAI_3km_buffer.tif")
OUT_PVAL_PATH = os.path.join(OUT_DIR, "VAI_pvalue_3km_buffer.tif")
OUT_WW_MEAN_PATH = os.path.join(OUT_DIR, "NDVI_windward_3km_buffer.tif")
OUT_LW_MEAN_PATH = os.path.join(OUT_DIR, "NDVI_leeward_3km_buffer.tif")
OUT_WW_CNT_PATH = os.path.join(OUT_DIR, "windward_count_3km_buffer.tif")
OUT_LW_CNT_PATH = os.path.join(OUT_DIR, "leeward_count_3km_buffer.tif")
OUT_DEM_PATH = os.path.join(OUT_DIR, "DEM_3km_buffer.tif")
OUT_FRAC_PATH = os.path.join(OUT_DIR, "valley_fraction_3km_buffer.tif")
os.makedirs(OUT_DIR, exist_ok=True)

# 网格参数
GRID_SIZE_M = 3000      # 3 km
PIXEL_SIZE_M = 10       # 10 m
GRID_PIXELS = GRID_SIZE_M // PIXEL_SIZE_M  # 300 pixels

# 河道 buffer 半径
BUFFER_RADIUS_M = 4000

# 河道筛选
DADUHE_NAME = "大渡河干旱河谷"

WINDWARD_VAL = 1
LEEWARD_VAL = 2

MIN_PIXEL_THRESHOLD = 50
NDVI_MIN = 0.1
MIN_VALLEY_PIXELS = MIN_PIXEL_THRESHOLD * 2


# ============================================================
# 1. Helpers
# ============================================================
def iter_parts(shape):
    parts = list(shape.parts) + [len(shape.points)]
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i + 1]]
        if len(pts) >= 2:
            yield pts


def load_centerline_lines(shp_path, name_filter, dst_crs):
    """读取 centerline_final 中目标河谷的所有 LineString, 投影到 dst_crs."""
    prj_path = os.path.splitext(shp_path)[0] + ".prj"
    with open(prj_path, "r", errors="ignore") as f:
        src_crs = CRS.from_wkt(f.read())
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    same_crs = src_crs == dst_crs

    lines = []
    reader = shapefile.Reader(str(shp_path))
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec.get("Name") != name_filter:
            continue
        for pts in iter_parts(sr.shape):
            xs, ys = zip(*pts)
            if not same_crs:
                xs, ys = transformer.transform(xs, ys)
            lines.append(LineString(zip(xs, ys)))
    if not lines:
        raise RuntimeError(f"No centerline parts matched Name={name_filter!r}")
    return lines


def build_buffer_mask_10m(lines, buffer_m, ref_height, ref_width, ref_transform):
    """对 LineStrings 取 union+buffer, 栅格化为 10m mask (1=in buffer, 0=out)."""
    union_buffered = unary_union(lines).buffer(buffer_m)
    geom = union_buffered.__geo_interface__
    mask = rasterize(
        [(geom, 1)],
        out_shape=(ref_height, ref_width),
        transform=ref_transform,
        fill=0,
        dtype="uint8",
    )
    return mask


# ============================================================
# 2. Main
# ============================================================
if __name__ == "__main__":
    t_start = time.time()

    with rio.open(NDVI_PATH, "r") as src:
        ref_transform = src.transform
        ref_crs = src.crs
        ref_height = src.height
        ref_width = src.width
        ndvi_nodata = src.nodata
        print(f"NDVI raster: {ref_height} × {ref_width}, CRS={ref_crs}")
    with rio.open(DEM_PATH, "r") as src:
        dem_nodata = src.nodata
    with rio.open(DIRECTION_PATH, "r") as src:
        dir_nodata = src.nodata

    print(f"Loading centerline: {CENTERLINE_PATH}")
    print(f"  filter Name = {DADUHE_NAME!r}")
    lines = load_centerline_lines(CENTERLINE_PATH, DADUHE_NAME, ref_crs)
    print(f"  centerline parts: {len(lines)}")
    print(f"Building {BUFFER_RADIUS_M / 1000:.1f} km buffer mask ...")
    buffer_mask = build_buffer_mask_10m(
        lines, BUFFER_RADIUS_M, ref_height, ref_width, ref_transform,
    )
    print(f"  buffer pixels: {int(buffer_mask.sum()):,}")

    n_grid_rows = ref_height // GRID_PIXELS
    n_grid_cols = ref_width // GRID_PIXELS
    print(f"3km grid: {n_grid_rows} × {n_grid_cols} = {n_grid_rows * n_grid_cols} cells")

    out_transform = from_origin(
        ref_transform.c, ref_transform.f, GRID_SIZE_M, GRID_SIZE_M,
    )

    vai_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    pval_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    ww_mean_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    lw_mean_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    ww_cnt_arr = np.zeros((n_grid_rows, n_grid_cols), dtype=np.int32)
    lw_cnt_arr = np.zeros((n_grid_rows, n_grid_cols), dtype=np.int32)
    dem_arr = np.full((n_grid_rows, n_grid_cols), np.nan, dtype=np.float32)
    frac_arr = np.zeros((n_grid_rows, n_grid_cols), dtype=np.float32)

    print("\nProcessing 3km grids ...")
    src_ndvi = rio.open(NDVI_PATH, "r")
    src_dir = rio.open(DIRECTION_PATH, "r")
    src_dem = rio.open(DEM_PATH, "r")

    valid_count = 0
    skipped_low_frac = 0
    skipped_low_pixel = 0

    for gi in range(n_grid_rows):
        for gj in range(n_grid_cols):
            row_start = gi * GRID_PIXELS
            col_start = gj * GRID_PIXELS
            window = Window(col_start, row_start, GRID_PIXELS, GRID_PIXELS)

            buf_block = buffer_mask[
                row_start:row_start + GRID_PIXELS,
                col_start:col_start + GRID_PIXELS,
            ]
            buffer_pixel_count = int(buf_block.sum())
            frac_arr[gi, gj] = buffer_pixel_count / (GRID_PIXELS * GRID_PIXELS)

            if buffer_pixel_count < MIN_VALLEY_PIXELS:
                skipped_low_frac += 1
                continue

            ndvi_block = src_ndvi.read(1, window=window).astype(np.float64)
            dir_block = src_dir.read(1, window=window)
            dem_block = src_dem.read(1, window=window).astype(np.float64)

            valid_mask = (buf_block == 1)
            valid_mask &= np.isfinite(ndvi_block) & (ndvi_block > NDVI_MIN)
            if ndvi_nodata is not None:
                valid_mask &= ~np.isclose(ndvi_block, ndvi_nodata)
            valid_mask &= np.isfinite(dem_block) & (dem_block > 0)
            if dem_nodata is not None:
                valid_mask &= ~np.isclose(dem_block, dem_nodata)
            valid_mask &= (dir_block == WINDWARD_VAL) | (dir_block == LEEWARD_VAL)

            ww_mask = valid_mask & (dir_block == WINDWARD_VAL)
            lw_mask = valid_mask & (dir_block == LEEWARD_VAL)
            n_ww = int(ww_mask.sum())
            n_lw = int(lw_mask.sum())
            ww_cnt_arr[gi, gj] = n_ww
            lw_cnt_arr[gi, gj] = n_lw

            if n_ww < MIN_PIXEL_THRESHOLD or n_lw < MIN_PIXEL_THRESHOLD:
                skipped_low_pixel += 1
                continue

            ww_vals = ndvi_block[ww_mask]
            lw_vals = ndvi_block[lw_mask]
            ww_m = float(ww_vals.mean())
            lw_m = float(lw_vals.mean())

            mean_wl = (ww_m + lw_m) / 2.0
            if mean_wl <= 0:
                continue

            vai_arr[gi, gj] = (ww_m - lw_m) / mean_wl * 100.0
            ww_mean_arr[gi, gj] = ww_m
            lw_mean_arr[gi, gj] = lw_m
            dem_arr[gi, gj] = float(dem_block[valid_mask].mean())

            _, p_value = ttest_ind(ww_vals, lw_vals, equal_var=False)
            pval_arr[gi, gj] = p_value

            valid_count += 1

        if (gi + 1) % 10 == 0 or gi == n_grid_rows - 1:
            pct = (gi + 1) / n_grid_rows * 100.0
            print(
                f"  Row {gi + 1}/{n_grid_rows} ({pct:.1f}%)  "
                f"valid={valid_count}, low_frac={skipped_low_frac}, "
                f"low_pixel={skipped_low_pixel}"
            )

    src_ndvi.close()
    src_dir.close()
    src_dem.close()

    base_profile = {
        "driver": "GTiff",
        "width": n_grid_cols,
        "height": n_grid_rows,
        "count": 1,
        "crs": ref_crs,
        "transform": out_transform,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    float_profile = {**base_profile, "dtype": "float32", "nodata": np.nan}
    int_profile = {**base_profile, "dtype": "int32", "nodata": -1}

    for path, data, profile, label in [
        (OUT_VAI_PATH, vai_arr, float_profile, "VAI"),
        (OUT_PVAL_PATH, pval_arr, float_profile, "p-value"),
        (OUT_WW_MEAN_PATH, ww_mean_arr, float_profile, "NDVI_windward"),
        (OUT_LW_MEAN_PATH, lw_mean_arr, float_profile, "NDVI_leeward"),
        (OUT_DEM_PATH, dem_arr, float_profile, "DEM_buffer"),
        (OUT_FRAC_PATH, frac_arr, float_profile, "buffer_fraction"),
        (OUT_WW_CNT_PATH, ww_cnt_arr, int_profile, "windward_count"),
        (OUT_LW_CNT_PATH, lw_cnt_arr, int_profile, "leeward_count"),
    ]:
        with rio.open(path, "w", **profile) as dst:
            dst.write(data.astype(profile["dtype"]), 1)
        print(f"  {label} -> {path}")

    elapsed = time.time() - t_start
    vai_valid = vai_arr[np.isfinite(vai_arr)]
    pval_valid = pval_arr[np.isfinite(pval_arr)]
    print(f"\n{'=' * 60}")
    print(f"Total time: {elapsed / 60:.1f} min")
    print(
        f"3km grids total={n_grid_rows * n_grid_cols}, valid={valid_count}, "
        f"low_frac={skipped_low_frac}, low_pixel={skipped_low_pixel}"
    )
    if len(vai_valid) > 0:
        print(f"VAI range: [{vai_valid.min():.3f}, {vai_valid.max():.3f}] %")
        print(
            f"VAI > 0: {(vai_valid > 0).sum()}/{len(vai_valid)} "
            f"({(vai_valid > 0).mean() * 100:.1f}%)"
        )
        print(
            f"VAI < 0: {(vai_valid < 0).sum()}/{len(vai_valid)} "
            f"({(vai_valid < 0).mean() * 100:.1f}%)"
        )
    if len(pval_valid) > 0:
        print(
            f"Significant (p<0.05): "
            f"{(pval_valid < 0.05).sum()}/{len(pval_valid)} "
            f"({(pval_valid < 0.05).mean() * 100:.1f}%)"
        )
    print("Done.")
