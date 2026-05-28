# @Author  : ChaoQiezi
# @Time    : 2026/5/8
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_spatial_distribution_buffer.py

"""
批量计算四条干热河谷的4km河道buffer内3km网格VAI

整合大渡河、金沙江、岷江、雅砻江, 一次运行完成所有河谷的 VAI 3km buffer 计算。
输出栅格存放于各河谷的 VAI 目录下, 文件名与单河谷版本一致。
"""

import os
import time
import warnings

import numpy as np
from pyproj import CRS, Transformer
import rasterio as rio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.windows import Window
from scipy.stats import ttest_ind
import shapefile
from shapely.geometry import LineString
from shapely.ops import unary_union

warnings.filterwarnings("ignore")

# 0. Configuration
BASE = r"E:\GeoProjects\dry_hot_valley\valley_analysis"
CENTERLINE_ROOT = r"E:\GeoProjects\dry_hot_valley\river_net\xinan\valley_centerlines"

GRID_SIZE_M = 3000
PIXEL_SIZE_M = 10
GRID_PIXELS = GRID_SIZE_M // PIXEL_SIZE_M

BUFFER_RADIUS_M = 4000

WINDWARD_VAL = 1
LEEWARD_VAL = 2

MIN_PIXEL_THRESHOLD = 50
NDVI_MIN = 0.1
MIN_VALLEY_PIXELS = MIN_PIXEL_THRESHOLD * 2

VALLEY_CONFIGS = [
    {
        "name_filter": "大渡河干旱河谷",
        "label": "大渡河",
        "centerline_path": os.path.join(CENTERLINE_ROOT, "Daduhe_centerline.shp"),
        "ndvi_path": os.path.join(BASE, r"Daduhe\NDVI\Interannual\NDVI_interannual_mean_region.tif"),
        "direction_path": os.path.join(BASE, r"Daduhe\geo_factor\windward_leeward_region.tif"),
        "dem_path": os.path.join(BASE, r"Daduhe\geo_factor\elevation_10m_projected_region.tif"),
        "out_dir": os.path.join(BASE, r"Daduhe\VAI"),
    },
    {
        "name_filter": "金沙江干旱河谷",
        "label": "金沙江",
        "centerline_path": os.path.join(CENTERLINE_ROOT, "Jinshajiang_centerline.shp"),
        "ndvi_path": os.path.join(BASE, r"Jinshajiang\NDVI\Interannual\NDVI_interannual_mean_region.tif"),
        "direction_path": os.path.join(BASE, r"Jinshajiang\geo_factor\windward_leeward_region.tif"),
        "dem_path": os.path.join(BASE, r"Jinshajiang\geo_factor\elevation_10m_projected_region.tif"),
        "out_dir": os.path.join(BASE, r"Jinshajiang\VAI"),
    },
    {
        "name_filter": "岷江干旱河谷",
        "label": "岷江",
        "centerline_path": os.path.join(CENTERLINE_ROOT, "Minjiang_centerline.shp"),
        "ndvi_path": os.path.join(BASE, r"Minjiang\NDVI\Interannual\NDVI_interannual_mean_region.tif"),
        "direction_path": os.path.join(BASE, r"Minjiang\geo_factor\windward_leeward_region.tif"),
        "dem_path": os.path.join(BASE, r"Minjiang\geo_factor\elevation_10m_projected_region.tif"),
        "out_dir": os.path.join(BASE, r"Minjiang\VAI"),
    },
    {
        "name_filter": "雅砻江干旱河谷",
        "label": "雅砻江",
        "centerline_path": os.path.join(CENTERLINE_ROOT, "Yalongjiang_centerline.shp"),
        "ndvi_path": os.path.join(BASE, r"Yalongjiang\NDVI\Interannual\NDVI_interannual_mean_region.tif"),
        "direction_path": os.path.join(BASE, r"Yalongjiang\geo_factor\windward_leeward_region.tif"),
        "dem_path": os.path.join(BASE, r"Yalongjiang\geo_factor\elevation_10m_projected_region.tif"),
        "out_dir": os.path.join(BASE, r"Yalongjiang\VAI"),
    },
]


# 1. Helpers
def iter_parts(shape):
    """从 pyshp shape 对象中逐段 yield 折线顶点坐标"""
    parts = list(shape.parts) + [len(shape.points)]
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i + 1]]
        if len(pts) >= 2:
            yield pts


def load_centerline_lines(shp_path, name_filter, dst_crs):
    """读取指定河谷的中心线 shapefile，投影到目标 CRS，返回 LineString 列表"""
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
    """对 LineStrings 并集做缓冲区并栅格化为 10 m 二值掩膜"""
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


# 2. Per-valley processor
def process_valley(cfg):
    """处理单个河谷的 4 km 河道 buffer 内 3 km 网格 VAI 计算
    
    对每个 3 km 网格分别统计迎风坡/背风坡 NDVI 均值，计算 VAI、p 值并输出栅格。
    参数:
    cfg: 河谷配置字典，包含 label, ndvi_path, direction_path, dem_path, out_dir 等
    返回:
    dict: 包含 label, valid_count, elapsed_min, n_total_grids 的结果汇总
    """
    label = cfg["label"]
    ndvi_path = cfg["ndvi_path"]
    direction_path = cfg["direction_path"]
    dem_path = cfg["dem_path"]
    out_dir = cfg["out_dir"]
    name_filter = cfg["name_filter"]

    out_vai_path = os.path.join(out_dir, "VAI_3km_buffer.tif")
    out_pval_path = os.path.join(out_dir, "VAI_pvalue_3km_buffer.tif")
    out_ww_mean_path = os.path.join(out_dir, "NDVI_windward_3km_buffer.tif")
    out_lw_mean_path = os.path.join(out_dir, "NDVI_leeward_3km_buffer.tif")
    out_ww_cnt_path = os.path.join(out_dir, "windward_count_3km_buffer.tif")
    out_lw_cnt_path = os.path.join(out_dir, "leeward_count_3km_buffer.tif")
    out_dem_path = os.path.join(out_dir, "DEM_3km_buffer.tif")
    out_frac_path = os.path.join(out_dir, "valley_fraction_3km_buffer.tif")
    os.makedirs(out_dir, exist_ok=True)

    t_start = time.time()
    print(f"\n{'=' * 60}")
    print(f"  {label} — {name_filter}")
    print(f"{'=' * 60}")

    with rio.open(ndvi_path, "r") as src:
        ref_transform = src.transform
        ref_crs = src.crs
        ref_height = src.height
        ref_width = src.width
        ndvi_nodata = src.nodata
        print(f"  NDVI raster: {ref_height} x {ref_width}, CRS={ref_crs}")
    with rio.open(dem_path, "r") as src:
        dem_nodata = src.nodata
    with rio.open(direction_path, "r") as src:
        dir_nodata = src.nodata

    centerline_path = cfg["centerline_path"]
    print(f"  Centerline: {centerline_path}, filter={name_filter!r}")
    lines = load_centerline_lines(centerline_path, name_filter, ref_crs)
    print(f"  Centerline parts: {len(lines)}")
    print(f"  Building {BUFFER_RADIUS_M / 1000:.1f} km buffer mask ...")
    buffer_mask = build_buffer_mask_10m(
        lines, BUFFER_RADIUS_M, ref_height, ref_width, ref_transform,
    )
    print(f"  Buffer pixels: {int(buffer_mask.sum()):,}")

    n_grid_rows = ref_height // GRID_PIXELS
    n_grid_cols = ref_width // GRID_PIXELS
    print(f"  3km grid: {n_grid_rows} x {n_grid_cols} = {n_grid_rows * n_grid_cols} cells")

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

    print("  Processing 3km grids ...")
    src_ndvi = rio.open(ndvi_path, "r")
    src_dir = rio.open(direction_path, "r")
    src_dem = rio.open(dem_path, "r")

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
                f"    Row {gi + 1}/{n_grid_rows} ({pct:.1f}%)  "
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

    for path, data, profile, desc in [
        (out_vai_path, vai_arr, float_profile, "VAI"),
        (out_pval_path, pval_arr, float_profile, "p-value"),
        (out_ww_mean_path, ww_mean_arr, float_profile, "NDVI_windward"),
        (out_lw_mean_path, lw_mean_arr, float_profile, "NDVI_leeward"),
        (out_dem_path, dem_arr, float_profile, "DEM_buffer"),
        (out_frac_path, frac_arr, float_profile, "buffer_fraction"),
        (out_ww_cnt_path, ww_cnt_arr, int_profile, "windward_count"),
        (out_lw_cnt_path, lw_cnt_arr, int_profile, "leeward_count"),
    ]:
        with rio.open(path, "w", **profile) as dst:
            dst.write(data.astype(profile["dtype"]), 1)
        print(f"    {desc} -> {path}")

    elapsed = time.time() - t_start
    vai_valid = vai_arr[np.isfinite(vai_arr)]
    pval_valid = pval_arr[np.isfinite(pval_arr)]
    print(f"  {label} done in {elapsed / 60:.1f} min")
    print(f"  Valid cells: {valid_count}, low_frac: {skipped_low_frac}, low_pixel: {skipped_low_pixel}")
    if len(vai_valid) > 0:
        print(f"  VAI: [{vai_valid.min():.3f}, {vai_valid.max():.3f}]%, "
              f">0: {(vai_valid > 0).mean() * 100:.1f}%")
    if len(pval_valid) > 0:
        print(f"  Sig (p<0.05): {(pval_valid < 0.05).mean() * 100:.1f}%")

    return {
        "label": label,
        "valid_count": valid_count,
        "elapsed_min": elapsed / 60,
        "n_total_grids": n_grid_rows * n_grid_cols,
    }


# 3. Main
if __name__ == "__main__":
    t_all = time.time()
    print("=" * 60)
    print("  Batch 3km buffer VAI — all four dry-hot valleys")
    print("=" * 60)

    results = []
    for cfg in VALLEY_CONFIGS:
        result = process_valley(cfg)
        results.append(result)

    total_elapsed = time.time() - t_all
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    for r in results:
        print(f"  {r['label']}: {r['valid_count']}/{r['n_total_grids']} valid "
              f"({r['elapsed_min']:.1f} min)")
    print(f"  Total time: {total_elapsed / 60:.1f} min")
    print("Done.")
