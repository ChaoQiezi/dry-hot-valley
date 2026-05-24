# -*- coding: utf-8 -*-
"""
岷江单河谷的相对河床高程分层 VAI 试验。

目的:
1. 保持旧方法的 4 km 河道 buffer 和 3 km 网格，以便比较。
2. 在网格内部先按逐像元相对河床高程筛选，再计算 VAI，诊断全高度
   聚合是否造成正负信号抵消。
3. 仅生成试验产物，不覆盖现有主线 VAI 栅格。

重要限制:
- 旧的 centerline_final.shp 当前不在磁盘布局中。本试验将现存西南河网
  river_net.shp 与岷江 polygon 相交后得到的河段作为临时河道基准。
- 因此本脚本结果只能用于检验方法方向，不能直接作为最终科学结果。
"""

import os
import time
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
from rasterio.features import rasterize
from rasterio.windows import Window
from scipy.spatial import cKDTree
from scipy.stats import ttest_ind, wilcoxon
from shapely.geometry import LineString, MultiLineString, mapping
from shapely.ops import unary_union

warnings.filterwarnings("ignore")
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
        "axes.unicode_minus": False,
    }
)

# ============================================================
# 0. Configuration: legacy Minjiang method trial only
# ============================================================
VALLEY_LABEL = "岷江"

NDVI_PATH = (
    r"G:\GeoProjects\dry_hot_valley_old\Minjiang\NDVI\Interannual"
    r"\NDVI_interannual_mean_region.tif"
)
DEM_PATH = (
    r"G:\GeoProjects\dry_hot_valley_old\Minjiang\geo_factor"
    r"\elevation_10m_projected_region.tif"
)
DIRECTION_PATH = (
    r"E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\geo_factor"
    r"\windward_leeward_region.tif"
)
RIVER_NETWORK_PATH = r"E:\GeoProjects\dry_hot_valley\river_net\river_net.shp"
VALLEY_POLYGON_PATH = (
    r"E:\GeoProjects\dry_hot_valley\valley_area\Chuanxi\Minjiang_valley.shp"
)

OUT_DIR = r"E:\MyTEMP\dry_hot_valley\height_band_trial\minjiang"
OUT_CELLS = os.path.join(OUT_DIR, "VAI_height_band_cells.csv")
OUT_SUMMARY = os.path.join(OUT_DIR, "VAI_height_band_summary.csv")
OUT_PAIRED = os.path.join(OUT_DIR, "VAI_height_cap_paired_vs_full.csv")
OUT_CHANNELS = os.path.join(OUT_DIR, "candidate_channel_segments.geojson")
OUT_FIG = os.path.join(OUT_DIR, "VAI_height_band_diagnostic.png")

GRID_SIZE_M = 3000
PIXEL_SIZE_M = 10
GRID_PIXELS = GRID_SIZE_M // PIXEL_SIZE_M
BUFFER_RADIUS_M = 4000

# 西南河网已按汇流阈值提取。岷江 polygon 内仅有 grid_code=1/2 的五段河线；
# 试验先保留全部交线段，以免仅保留最高级会截断河谷北段。
MIN_GRID_CODE = 1
CHANNEL_SAMPLE_STEP_M = 10

WINDWARD_VAL = 1
LEEWARD_VAL = 2
NDVI_MIN = 0.1
MIN_PIXEL_THRESHOLD = 50
MIN_BUFFER_PIXELS = MIN_PIXEL_THRESHOLD * 2

# 河道像元与 DEM/线位存在小量配准误差，容许略低于采样河床的像元进入近河带。
RELATIVE_HEIGHT_TOLERANCE_M = 20
HEIGHT_CAPS_M = [200, 300, 400, 500, 1000]
HEIGHT_INTERVALS = [
    ("full_buffer", "full", np.nan, np.nan),
    *[(f"cap_0_{height}m", "cap", 0, height) for height in HEIGHT_CAPS_M],
    ("band_0_200m", "band", 0, 200),
    ("band_200_300m", "band", 200, 300),
    ("band_300_400m", "band", 300, 400),
    ("band_400_500m", "band", 400, 500),
    ("band_500_1000m", "band", 500, 1000),
    ("band_1000_1500m", "band", 1000, 1500),
    ("band_1500_2000m", "band", 1500, 2000),
    ("band_2000plus_m", "band", 2000, None),
]
HEIGHT_ORDER = [item[0] for item in HEIGHT_INTERVALS]
N_BOOT = 1000
RNG_SEED = 20260524


# ============================================================
# 1. Geometry and validation
# ============================================================
def validate_raster_alignment(paths):
    metadata = []
    for path in paths:
        with rio.open(path) as src:
            metadata.append((src.shape, src.transform, src.crs))
    if len(set(metadata)) != 1:
        raise RuntimeError("NDVI, DEM, and windward/leeward rasters are not aligned.")


def load_candidate_channel(raster_crs):
    river = gpd.read_file(RIVER_NETWORK_PATH)
    valley = gpd.read_file(VALLEY_POLYGON_PATH).to_crs(river.crs)
    river = river[river["grid_code"] >= MIN_GRID_CODE].copy()
    clipped = gpd.clip(river, valley[["geometry"]], keep_geom_type=True)
    clipped = clipped[~clipped.geometry.is_empty].copy()
    if clipped.empty:
        raise RuntimeError("No river segments intersect the Minjiang polygon.")

    clipped["length_m"] = clipped.length
    os.makedirs(OUT_DIR, exist_ok=True)
    clipped.to_file(OUT_CHANNELS, driver="GeoJSON")

    print("Candidate channel segments used in this trial:")
    print(
        clipped.groupby("grid_code")["length_m"]
        .agg(["count", "sum"])
        .round(1)
        .to_string()
    )
    channel = unary_union(clipped.to_crs(raster_crs).geometry)
    return channel


def iter_lines(geometry):
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms
    else:
        for geom in geometry.geoms:
            yield from iter_lines(geom)


def build_channel_tree(channel_geometry, dem_path):
    points = []
    for line in iter_lines(channel_geometry):
        distances = np.arange(0.0, line.length, CHANNEL_SAMPLE_STEP_M)
        distances = np.append(distances, line.length)
        points.extend(line.interpolate(float(distance)) for distance in distances)

    coords = np.asarray([(point.x, point.y) for point in points], dtype=np.float64)
    with rio.open(dem_path) as src:
        nodata = src.nodata
        elevations = np.asarray(
            [float(value[0]) for value in src.sample(coords)], dtype=np.float64
        )
    valid = np.isfinite(elevations) & (elevations > 0)
    if nodata is not None:
        valid &= ~np.isclose(elevations, nodata)
    if valid.sum() == 0:
        raise RuntimeError("Candidate channel does not overlap valid DEM pixels.")
    print(f"Channel DEM samples: {valid.sum():,}/{len(elevations):,} valid")
    return cKDTree(coords[valid]), elevations[valid]


def build_buffer_mask(channel_geometry, shape, transform):
    buffer_geom = channel_geometry.buffer(BUFFER_RADIUS_M)
    return rasterize(
        [(mapping(buffer_geom), 1)],
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="uint8",
    )


# ============================================================
# 2. Cell calculation
# ============================================================
def interval_mask(valid_mask, relative_height, interval_type, lo_m, hi_m):
    if interval_type == "full":
        return valid_mask
    if interval_type == "cap":
        return (
            valid_mask
            & (relative_height >= -RELATIVE_HEIGHT_TOLERANCE_M)
            & (relative_height <= hi_m)
        )
    lower_bound = -RELATIVE_HEIGHT_TOLERANCE_M if lo_m == 0 else lo_m
    if hi_m is None:
        return valid_mask & (relative_height >= lower_bound)
    return valid_mask & (relative_height >= lower_bound) & (relative_height < hi_m)


def calculate_vai(ndvi, dem, relative_height, direction, mask):
    ww_mask = mask & (direction == WINDWARD_VAL)
    lw_mask = mask & (direction == LEEWARD_VAL)
    n_ww = int(ww_mask.sum())
    n_lw = int(lw_mask.sum())
    if n_ww < MIN_PIXEL_THRESHOLD or n_lw < MIN_PIXEL_THRESHOLD:
        return None

    ww_values = ndvi[ww_mask]
    lw_values = ndvi[lw_mask]
    ww_mean = float(ww_values.mean())
    lw_mean = float(lw_values.mean())
    mean_wl = (ww_mean + lw_mean) / 2.0
    if mean_wl <= 0:
        return None

    _, p_value = ttest_ind(ww_values, lw_values, equal_var=False)
    rel_values = relative_height[mask & np.isfinite(relative_height)]
    return {
        "VAI": (ww_mean - lw_mean) / mean_wl * 100.0,
        "abs_VAI": abs((ww_mean - lw_mean) / mean_wl * 100.0),
        "p_value": float(p_value),
        "windward_count": n_ww,
        "leeward_count": n_lw,
        "windward_ndvi": ww_mean,
        "leeward_ndvi": lw_mean,
        "mean_dem_m": float(dem[mask].mean()),
        "median_relative_height_m": (
            float(np.nanmedian(rel_values)) if len(rel_values) else np.nan
        ),
    }


def calculate_cells(channel_geometry, channel_tree, channel_elevations):
    with rio.open(NDVI_PATH) as src_ndvi, rio.open(DEM_PATH) as src_dem, rio.open(
        DIRECTION_PATH
    ) as src_direction:
        transform = src_ndvi.transform
        height = src_ndvi.height
        width = src_ndvi.width
        ndvi_nodata = src_ndvi.nodata
        dem_nodata = src_dem.nodata

        buffer_mask = build_buffer_mask(channel_geometry, (height, width), transform)
        print(f"4 km candidate-channel buffer pixels: {int(buffer_mask.sum()):,}")

        n_rows = height // GRID_PIXELS
        n_cols = width // GRID_PIXELS
        records = []
        for grid_row in range(n_rows):
            for grid_col in range(n_cols):
                row_start = grid_row * GRID_PIXELS
                col_start = grid_col * GRID_PIXELS
                window = Window(col_start, row_start, GRID_PIXELS, GRID_PIXELS)
                buf = buffer_mask[
                    row_start : row_start + GRID_PIXELS,
                    col_start : col_start + GRID_PIXELS,
                ]
                if int(buf.sum()) < MIN_BUFFER_PIXELS:
                    continue

                ndvi = src_ndvi.read(1, window=window).astype(np.float64)
                dem = src_dem.read(1, window=window).astype(np.float64)
                direction = src_direction.read(1, window=window)

                valid = buf == 1
                valid &= np.isfinite(ndvi) & (ndvi > NDVI_MIN)
                valid &= np.isfinite(dem) & (dem > 0)
                if ndvi_nodata is not None:
                    valid &= ~np.isclose(ndvi, ndvi_nodata)
                if dem_nodata is not None:
                    valid &= ~np.isclose(dem, dem_nodata)
                valid &= (direction == WINDWARD_VAL) | (direction == LEEWARD_VAL)
                if not valid.any():
                    continue

                rr, cc = np.where(valid)
                xs = transform.c + (col_start + cc + 0.5) * transform.a
                ys = transform.f + (row_start + rr + 0.5) * transform.e
                _, near_index = channel_tree.query(np.column_stack([xs, ys]), k=1)
                relative_height = np.full(ndvi.shape, np.nan, dtype=np.float64)
                relative_height[rr, cc] = dem[rr, cc] - channel_elevations[near_index]

                center_x = transform.c + (col_start + GRID_PIXELS / 2) * transform.a
                center_y = transform.f + (row_start + GRID_PIXELS / 2) * transform.e
                grid_id = f"r{grid_row:03d}_c{grid_col:03d}"
                for label, interval_type, lo_m, hi_m in HEIGHT_INTERVALS:
                    mask = interval_mask(valid, relative_height, interval_type, lo_m, hi_m)
                    stats = calculate_vai(ndvi, dem, relative_height, direction, mask)
                    if stats is None:
                        continue
                    records.append(
                        {
                            "grid_id": grid_id,
                            "grid_row": grid_row,
                            "grid_col": grid_col,
                            "center_x": center_x,
                            "center_y": center_y,
                            "height_class": label,
                            "interval_type": interval_type,
                            "height_lo_m": lo_m,
                            "height_hi_m": hi_m,
                            **stats,
                        }
                    )
            if (grid_row + 1) % 10 == 0 or grid_row == n_rows - 1:
                print(f"Processed grid row {grid_row + 1}/{n_rows}")
    return pd.DataFrame(records)


# ============================================================
# 3. Summary and plot
# ============================================================
def bootstrap_median_ci(values, seed):
    values = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(N_BOOT, len(values)), replace=True)
    medians = np.median(samples, axis=1)
    return float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))


def summarize_cells(cells):
    rows = []
    for idx, label in enumerate(HEIGHT_ORDER):
        group = cells[cells["height_class"] == label]
        if group.empty:
            continue
        lo95, hi95 = bootstrap_median_ci(group["VAI"].to_numpy(), RNG_SEED + idx)
        rows.append(
            {
                "height_class": label,
                "interval_type": group["interval_type"].iloc[0],
                "valid_cells": len(group),
                "VAI_median": group["VAI"].median(),
                "VAI_median_lo95": lo95,
                "VAI_median_hi95": hi95,
                "VAI_mean": group["VAI"].mean(),
                "pct_VAI_gt0": float((group["VAI"] > 0).mean() * 100),
                "abs_VAI_median": group["abs_VAI"].median(),
                "abs_VAI_mean": group["abs_VAI"].mean(),
                "significant_pct": float((group["p_value"] < 0.05).mean() * 100),
                "windward_pixels": int(group["windward_count"].sum()),
                "leeward_pixels": int(group["leeward_count"].sum()),
            }
        )
    summary = pd.DataFrame(rows)
    summary["height_class"] = pd.Categorical(
        summary["height_class"], HEIGHT_ORDER, ordered=True
    )
    return summary.sort_values("height_class").reset_index(drop=True)


def summarize_paired_caps(cells):
    baseline = cells[cells["height_class"] == "full_buffer"][
        ["grid_id", "VAI", "abs_VAI"]
    ].rename(columns={"VAI": "VAI_full", "abs_VAI": "abs_VAI_full"})
    rows = []
    for idx, cap in enumerate(HEIGHT_CAPS_M):
        label = f"cap_0_{cap}m"
        trial = cells[cells["height_class"] == label][
            ["grid_id", "VAI", "abs_VAI"]
        ].rename(columns={"VAI": "VAI_cap", "abs_VAI": "abs_VAI_cap"})
        paired = baseline.merge(trial, on="grid_id", how="inner")
        if paired.empty:
            rows.append({"height_class": label, "paired_cells": 0})
            continue
        gain = paired["abs_VAI_cap"] - paired["abs_VAI_full"]
        nonzero = gain[~np.isclose(gain, 0)]
        p_value = (
            float(wilcoxon(nonzero).pvalue) if len(nonzero) > 0 else np.nan
        )
        gain_lo95, gain_hi95 = bootstrap_median_ci(gain.to_numpy(), RNG_SEED + idx)
        rows.append(
            {
                "height_class": label,
                "paired_cells": len(paired),
                "abs_VAI_full_median": paired["abs_VAI_full"].median(),
                "abs_VAI_cap_median": paired["abs_VAI_cap"].median(),
                "median_abs_gain": gain.median(),
                "median_abs_gain_lo95": gain_lo95,
                "median_abs_gain_hi95": gain_hi95,
                "pct_abs_gain_gt0": float((gain > 0).mean() * 100),
                "pct_sign_changed": float(
                    (np.sign(paired["VAI_full"]) != np.sign(paired["VAI_cap"])).mean()
                    * 100
                ),
                "wilcoxon_p_value": p_value,
            }
        )
    return pd.DataFrame(rows)


def plot_diagnostics(cells, summary, paired):
    cap_labels = ["full_buffer", *[f"cap_0_{height}m" for height in HEIGHT_CAPS_M]]
    band_labels = [label for label in HEIGHT_ORDER if label.startswith("band_")]
    band_tick_labels = {
        "band_0_200m": "0-200",
        "band_200_300m": "200-300",
        "band_300_400m": "300-400",
        "band_400_500m": "400-500",
        "band_500_1000m": "500-1000",
        "band_1000_1500m": "1000-1500",
        "band_1500_2000m": "1500-2000",
        "band_2000plus_m": ">=2000",
    }
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))

    box_data = [
        cells.loc[cells["height_class"] == label, "abs_VAI"].to_numpy()
        for label in cap_labels
    ]
    axes[0].boxplot(box_data, labels=["全部", "200", "300", "400", "500", "1000"])
    axes[0].set_xlabel("累计相对高程上限 (m)")
    axes[0].set_ylabel("|VAI| (%)")
    axes[0].set_title("A. 信号强度")
    axes[0].grid(axis="y", alpha=0.3)

    band = summary[summary["height_class"].isin(band_labels)]
    axes[1].errorbar(
        np.arange(len(band)),
        band["VAI_median"],
        yerr=[
            band["VAI_median"] - band["VAI_median_lo95"],
            band["VAI_median_hi95"] - band["VAI_median"],
        ],
        marker="o",
        color="#1B7837",
        capsize=3,
    )
    axes[1].axhline(0, color="#333333", linestyle=":", linewidth=1)
    axes[1].set_xticks(np.arange(len(band)))
    axes[1].set_xticklabels(
        [band_tick_labels[label] for label in band["height_class"].astype(str)],
        rotation=30,
        ha="right",
    )
    axes[1].set_xlabel("互斥相对高程带 (m)")
    axes[1].set_ylabel("VAI 中位数 (%)")
    axes[1].set_title("B. 信号方向")
    axes[1].grid(axis="y", alpha=0.3)

    axes[2].bar(
        np.arange(len(paired)),
        paired["median_abs_gain"],
        color="#D95F02",
        alpha=0.8,
    )
    axes[2].axhline(0, color="#333333", linestyle=":", linewidth=1)
    axes[2].set_xticks(np.arange(len(paired)))
    axes[2].set_xticklabels(["200", "300", "400", "500", "1000"])
    axes[2].set_xlabel("累计相对高程上限 (m)")
    axes[2].set_ylabel("配对 |VAI| 中位增量 (%)")
    axes[2].set_title("C. 相对全高度增量")
    axes[2].grid(axis="y", alpha=0.3)

    fig.suptitle("岷江相对河床高程分层 VAI 方法试验 (临时河道基准)", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=300)
    plt.close(fig)


# ============================================================
# 4. Main
# ============================================================
def main():
    start = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    validate_raster_alignment([NDVI_PATH, DEM_PATH, DIRECTION_PATH])

    with rio.open(NDVI_PATH) as src:
        raster_crs = src.crs
    channel = load_candidate_channel(raster_crs)
    channel_tree, channel_elevations = build_channel_tree(channel, DEM_PATH)
    cells = calculate_cells(channel, channel_tree, channel_elevations)
    if cells.empty:
        raise RuntimeError("No grid cells met the valid-pixel thresholds.")

    summary = summarize_cells(cells)
    paired = summarize_paired_caps(cells)
    cells.to_csv(OUT_CELLS, index=False, encoding="utf-8-sig", float_format="%.4f")
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig", float_format="%.4f")
    paired.to_csv(OUT_PAIRED, index=False, encoding="utf-8-sig", float_format="%.4f")
    plot_diagnostics(cells, summary, paired)

    print("\nHeight-band summary:")
    print(summary.to_string(index=False))
    print("\nPaired cumulative caps vs full-buffer VAI:")
    print(paired.to_string(index=False))
    print(f"\nOutputs written to: {OUT_DIR}")
    print(f"Elapsed: {(time.time() - start) / 60:.1f} min")


if __name__ == "__main__":
    main()
