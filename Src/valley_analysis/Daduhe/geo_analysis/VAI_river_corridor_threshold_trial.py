# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/6
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS范茄子
# @FileName: VAI_river_corridor_threshold_trial.py

"""
Daduhe-only trial for Zhao's "elevation threshold / height difference" question.

This script deliberately does not use the dry-hot-valley inner/outer buffer
classes. It tests whether the rectangular *_region VAI result still gives a
usable threshold after each 3 km VAI grid cell is tied to the nearest river
centerline point.

Core quantities:
  - river_distance_m: distance from the 3 km grid-cell centre to the nearest
    Daduhe centreline sample.
  - nearest_river_dem_m: 10 m DEM value sampled on that nearest centreline.
  - relative_height_m = DEM_3km - nearest_river_dem_m.

The trial compares:
  1. all valid *_region cells;
  2. cells within 30/20/10 km of the river centreline, with non-negative
     relative height.

If the VAI zero-crossing only appears in all *_region cells but disappears in
the river corridors, the old rectangle-based threshold is not a defensible
answer to Zhao's question.
"""

from pathlib import Path
import math
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
import shapefile
from rasterio.transform import xy
from scipy.spatial import cKDTree
from statsmodels.nonparametric.smoothers_lowess import lowess

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")

CENTERLINE_PATH = BASE_DIR / "valley_area" / "river_net" / "centerline_final.shp"
VAI_PATH = BASE_DIR / "Daduhe" / "VAI" / "VAI_3km_region.tif"
DEM3_PATH = BASE_DIR / "Daduhe" / "VAI" / "DEM_3km_region.tif"
DEM10_PATH = BASE_DIR / "Daduhe" / "geo_factor" / "elevation_10m_projected_region.tif"

OUT_TABLE_DIR = BASE_DIR / "Daduhe" / "Result" / "Table" / "altitude"
OUT_CHART_DIR = BASE_DIR / "Daduhe" / "Result" / "Chart" / "altitude"
OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
OUT_CHART_DIR.mkdir(parents=True, exist_ok=True)

OUT_CELLS = OUT_TABLE_DIR / "VAI_river_corridor_cells.csv"
OUT_ABS_GRADIENT = OUT_TABLE_DIR / "VAI_river_corridor_abs_elevation_gradient.csv"
OUT_REL_GRADIENT = OUT_TABLE_DIR / "VAI_river_corridor_relative_height_gradient.csv"
OUT_THRESHOLD = OUT_TABLE_DIR / "VAI_river_corridor_threshold_summary.csv"
OUT_SENSITIVITY = OUT_TABLE_DIR / "VAI_river_corridor_threshold_sensitivity.csv"
OUT_SEGMENT = OUT_TABLE_DIR / "VAI_river_segment_intensity_30km.csv"
OUT_FIG = OUT_CHART_DIR / "VAI_river_corridor_threshold_trial.png"

DADUHE_CENTERLINE_NAME = "大渡河干旱河谷"
CENTERLINE_SAMPLE_STEP_M = 100
SEGMENT_LENGTH_M = 30000
ELEV_BIN_M = 100
REL_HEIGHT_BIN_M = 100
LOWESS_FRAC = 0.35
MIN_BIN_COUNT = 30
THRESHOLD_BAND_M = 100
HIGH_CONF_LOW = 1500
HIGH_CONF_HIGH = 4500

SCOPES = [
    {
        "scope": "region_all",
        "label": "全部_region网格",
        "max_dist_m": None,
        "require_nonnegative_rel_height": False,
        "color": "#4D4D4D",
    },
    {
        "scope": "corridor_30km",
        "label": "距河道<=30 km",
        "max_dist_m": 30000,
        "require_nonnegative_rel_height": True,
        "color": "#D95F02",
    },
    {
        "scope": "corridor_20km",
        "label": "距河道<=20 km",
        "max_dist_m": 20000,
        "require_nonnegative_rel_height": True,
        "color": "#1B9E77",
    },
    {
        "scope": "corridor_10km",
        "label": "距河道<=10 km",
        "max_dist_m": 10000,
        "require_nonnegative_rel_height": True,
        "color": "#7570B3",
    },
]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "Arial", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.linewidth": 0.8,
    "axes.labelsize": 10,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
})


# ============================================================
# 1. Geometry helpers
# ============================================================
def iter_parts(shape):
    parts = list(shape.parts) + [len(shape.points)]
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i + 1]]
        if len(pts) >= 2:
            yield pts


def densify_polyline(points, step_m=CENTERLINE_SAMPLE_STEP_M):
    rows = []
    cum_dist = 0.0

    for p0, p1 in zip(points[:-1], points[1:]):
        x0, y0 = p0
        x1, y1 = p1
        dx = x1 - x0
        dy = y1 - y0
        seg_len = math.hypot(dx, dy)
        if seg_len == 0:
            continue

        n_steps = max(1, int(math.floor(seg_len / step_m)))
        for k in range(n_steps):
            t = k / n_steps
            rows.append((x0 + dx * t, y0 + dy * t, cum_dist + seg_len * t))
        cum_dist += seg_len

    x_last, y_last = points[-1]
    rows.append((x_last, y_last, cum_dist))
    return rows


def valid_dem_value(value, nodata):
    if not math.isfinite(value):
        return False
    if nodata is not None and np.isclose(value, nodata, rtol=0, atol=1e25):
        return False
    return value > 0


def valid_raster_array(arr, nodata):
    mask = np.isfinite(arr)
    if nodata is not None and np.isfinite(float(nodata)):
        mask &= ~np.isclose(arr, float(nodata))
    return mask


# ============================================================
# 2. Load centreline and grid cells
# ============================================================
def load_daduhe_centerline_samples():
    records = []
    reader = shapefile.Reader(str(CENTERLINE_PATH))
    feature_index = 0

    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec.get("Name") != DADUHE_CENTERLINE_NAME:
            continue

        feature_index += 1
        target_fid = int(rec.get("TARGET_FID"))
        arcid = int(rec.get("arcid"))
        feature_length_m = float(rec.get("LENGTH") or 0)

        for pts in iter_parts(sr.shape):
            for x_coord, y_coord, dist_along in densify_polyline(pts):
                segment_index = int(dist_along // SEGMENT_LENGTH_M)
                records.append({
                    "feature_index": feature_index,
                    "target_fid": target_fid,
                    "arcid": arcid,
                    "x": x_coord,
                    "y": y_coord,
                    "feature_length_m": feature_length_m,
                    "dist_along_feature_m": dist_along,
                    "segment_index": segment_index,
                    "segment_id": f"Daduhe_f{feature_index:03d}_s{segment_index:03d}",
                })

    samples = pd.DataFrame(records)
    if samples.empty:
        raise RuntimeError("No Daduhe centerline samples were found.")

    coords = list(zip(samples["x"].to_numpy(), samples["y"].to_numpy()))
    river_dem = []
    with rio.open(DEM10_PATH, "r") as src:
        nodata = src.nodata
        for item in src.sample(coords, masked=False):
            z = float(item[0])
            river_dem.append(z if valid_dem_value(z, nodata) else np.nan)

    samples["river_dem_m"] = river_dem
    samples = samples[np.isfinite(samples["river_dem_m"])].reset_index(drop=True)
    if samples.empty:
        raise RuntimeError("No valid 10 m DEM samples on Daduhe centerline.")

    return samples


def load_vai_grid_with_river_link(centerline_samples):
    with rio.open(VAI_PATH, "r") as src_vai, rio.open(DEM3_PATH, "r") as src_dem:
        vai = src_vai.read(1).astype(np.float64)
        dem = src_dem.read(1).astype(np.float64)

        valid = valid_raster_array(vai, src_vai.nodata)
        valid &= valid_raster_array(dem, src_dem.nodata)
        valid &= dem > 0
        valid &= np.abs(vai) <= 200

        rows, cols = np.where(valid)
        xs, ys = xy(src_vai.transform, rows, cols, offset="center")

    grid = pd.DataFrame({
        "row": rows,
        "col": cols,
        "x": np.asarray(xs, dtype=np.float64),
        "y": np.asarray(ys, dtype=np.float64),
        "VAI": vai[valid],
        "DEM_m": dem[valid],
    })

    tree = cKDTree(centerline_samples[["x", "y"]].to_numpy())
    river_dist, nearest_idx = tree.query(grid[["x", "y"]].to_numpy(), k=1)
    nearest = centerline_samples.iloc[nearest_idx].reset_index(drop=True)

    grid["river_distance_m"] = river_dist
    grid["nearest_river_dem_m"] = nearest["river_dem_m"].to_numpy()
    grid["relative_height_m"] = grid["DEM_m"] - grid["nearest_river_dem_m"]
    grid["nearest_feature_index"] = nearest["feature_index"].to_numpy()
    grid["nearest_target_fid"] = nearest["target_fid"].to_numpy()
    grid["nearest_arcid"] = nearest["arcid"].to_numpy()
    grid["segment_index"] = nearest["segment_index"].to_numpy()
    grid["segment_id"] = nearest["segment_id"].to_numpy()
    grid["abs_VAI"] = grid["VAI"].abs()
    grid["high_conf_elev"] = (
        (grid["DEM_m"] >= HIGH_CONF_LOW) &
        (grid["DEM_m"] <= HIGH_CONF_HIGH)
    )

    return grid


# ============================================================
# 3. Binning and threshold helpers
# ============================================================
def scope_mask(grid, scope_cfg):
    mask = np.ones(len(grid), dtype=bool)
    if scope_cfg["max_dist_m"] is not None:
        mask &= grid["river_distance_m"].to_numpy() <= scope_cfg["max_dist_m"]
    if scope_cfg["require_nonnegative_rel_height"]:
        mask &= grid["relative_height_m"].to_numpy() >= 0
    return mask


def binned_stats(df, value_col, bin_step, scope_name, axis_name):
    values = df[value_col].to_numpy()
    lo = int(np.floor(np.nanmin(values) / bin_step) * bin_step)
    hi = int(np.ceil(np.nanmax(values) / bin_step) * bin_step)
    edges = np.arange(lo, hi + bin_step, bin_step)
    if len(edges) < 2:
        return pd.DataFrame()

    bin_idx = np.digitize(values, edges) - 1
    bin_idx = np.clip(bin_idx, 0, len(edges) - 2)

    tmp = df.copy()
    tmp["bin_idx"] = bin_idx
    grouped = tmp.groupby("bin_idx", sort=True)

    rows = []
    for idx, group in grouped:
        elev_lo = edges[idx]
        elev_hi = edges[idx + 1]
        vai = group["VAI"].to_numpy()
        rows.append({
            "scope": scope_name,
            "axis": axis_name,
            "bin_lo": elev_lo,
            "bin_hi": elev_hi,
            "bin_center": (elev_lo + elev_hi) / 2,
            "vai_mean": np.mean(vai),
            "vai_median": np.median(vai),
            "vai_std": np.std(vai),
            "pct_gt0": (vai > 0).mean() * 100,
            "pct_lt0": (vai < 0).mean() * 100,
            "abs_vai_median": np.median(np.abs(vai)),
            "count": len(group),
        })

    return pd.DataFrame(rows)


def smooth_curve(
        df,
        x_min=None,
        x_max=None,
        min_bin_count=MIN_BIN_COUNT,
        lowess_frac=LOWESS_FRAC,
):
    valid = (
        np.isfinite(df["bin_center"]) &
        np.isfinite(df["vai_mean"]) &
        (df["count"] >= min_bin_count)
    )
    if x_min is not None:
        valid &= df["bin_center"] >= x_min
    if x_max is not None:
        valid &= df["bin_center"] <= x_max

    work = df.loc[valid].sort_values("bin_center")
    if len(work) < 4:
        return np.array([]), np.array([])

    frac = min(1.0, max(lowess_frac, 4 / len(work)))
    smoothed = lowess(
        work["vai_mean"].to_numpy(),
        work["bin_center"].to_numpy(),
        frac=frac,
        return_sorted=True,
    )
    return smoothed[:, 0], smoothed[:, 1]


def first_positive_to_negative_crossing(x, y):
    if len(x) < 2:
        return np.nan

    for i in range(len(x) - 1):
        y0 = y[i]
        y1 = y[i + 1]
        if y0 == 0 and i > 0 and y[i - 1] > 0:
            return x[i]
        if y0 > 0 and y1 < 0:
            return x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0)
    return np.nan


def summarize_thresholds(grid, abs_gradient, rel_gradient):
    rows = []

    for cfg in SCOPES:
        scope_name = cfg["scope"]
        mask = scope_mask(grid, cfg)
        scoped = grid.loc[mask].copy()

        abs_df = abs_gradient[abs_gradient["scope"] == scope_name]
        rel_df = rel_gradient[rel_gradient["scope"] == scope_name]

        x_abs, y_abs = smooth_curve(
            abs_df,
            x_min=HIGH_CONF_LOW,
            x_max=HIGH_CONF_HIGH,
        )
        x_rel, y_rel = smooth_curve(rel_df, x_min=0)

        abs_cross = first_positive_to_negative_crossing(x_abs, y_abs)
        rel_cross = first_positive_to_negative_crossing(x_rel, y_rel)

        if np.isfinite(abs_cross):
            band = scoped[np.abs(scoped["DEM_m"] - abs_cross) <= THRESHOLD_BAND_M]
        else:
            band = scoped.iloc[0:0]

        rows.append({
            "scope": scope_name,
            "label": cfg["label"],
            "max_dist_km": (
                np.nan if cfg["max_dist_m"] is None
                else cfg["max_dist_m"] / 1000
            ),
            "require_nonnegative_relative_height": cfg["require_nonnegative_rel_height"],
            "n_cells": len(scoped),
            "n_cells_high_conf_elev": int(scoped["high_conf_elev"].sum()),
            "river_distance_m_median": scoped["river_distance_m"].median(),
            "river_distance_m_p90": scoped["river_distance_m"].quantile(0.90),
            "relative_height_m_min": scoped["relative_height_m"].min(),
            "relative_height_m_median": scoped["relative_height_m"].median(),
            "relative_height_m_p90": scoped["relative_height_m"].quantile(0.90),
            "abs_elevation_crossing_m": abs_cross,
            "relative_height_crossing_m": rel_cross,
            "band_cells_within_abs_crossing_pm100m": len(band),
            "band_relative_height_m_median": band["relative_height_m"].median(),
            "band_relative_height_m_p25": band["relative_height_m"].quantile(0.25),
            "band_relative_height_m_p75": band["relative_height_m"].quantile(0.75),
            "band_nearest_river_dem_m_median": band["nearest_river_dem_m"].median(),
            "abs_gradient_bins_count_ge30": int(
                (abs_df["count"] >= MIN_BIN_COUNT).sum()
            ),
            "rel_gradient_bins_count_ge30": int(
                (rel_df["count"] >= MIN_BIN_COUNT).sum()
            ),
        })

    return pd.DataFrame(rows)


def threshold_from_gradient(
        gradient,
        x_min=None,
        x_max=None,
        min_bin_count=MIN_BIN_COUNT,
        lowess_frac=LOWESS_FRAC,
):
    x_vals, y_vals = smooth_curve(
        gradient,
        x_min=x_min,
        x_max=x_max,
        min_bin_count=min_bin_count,
        lowess_frac=lowess_frac,
    )
    return first_positive_to_negative_crossing(x_vals, y_vals), len(x_vals)


def summarize_threshold_sensitivity(grid):
    rows = []
    bin_sizes = [50, 100, 200]
    lowess_fracs = [0.25, 0.35, 0.45]

    for cfg in SCOPES:
        mask = scope_mask(grid, cfg)
        scoped = grid.loc[mask].copy()
        if scoped.empty:
            continue

        for bin_size in bin_sizes:
            abs_gradient = binned_stats(
                scoped,
                "DEM_m",
                bin_size,
                cfg["scope"],
                "absolute_elevation",
            )
            rel_gradient = binned_stats(
                scoped,
                "relative_height_m",
                bin_size,
                cfg["scope"],
                "relative_height",
            )

            for frac in lowess_fracs:
                abs_cross, n_abs = threshold_from_gradient(
                    abs_gradient,
                    x_min=HIGH_CONF_LOW,
                    x_max=HIGH_CONF_HIGH,
                    lowess_frac=frac,
                )
                rel_cross, n_rel = threshold_from_gradient(
                    rel_gradient,
                    x_min=0,
                    lowess_frac=frac,
                )

                rows.append({
                    "scope": cfg["scope"],
                    "bin_size_m": bin_size,
                    "lowess_frac": frac,
                    "n_cells": len(scoped),
                    "abs_crossing_m": abs_cross,
                    "relative_height_crossing_m": rel_cross,
                    "n_abs_smooth_points": n_abs,
                    "n_rel_smooth_points": n_rel,
                })

    return pd.DataFrame(rows)


def summarize_segment_intensity(grid):
    work = grid[
        (grid["river_distance_m"] <= 20000) &
        (grid["relative_height_m"] >= 0) &
        (grid["high_conf_elev"])
    ].copy()

    rows = []
    for segment_id, group in work.groupby("segment_id"):
        if len(group) < 10:
            continue

        rows.append({
            "segment_id": segment_id,
            "nearest_feature_index": int(group["nearest_feature_index"].mode().iloc[0]),
            "segment_index": int(group["segment_index"].mode().iloc[0]),
            "n_cells": len(group),
            "VAI_mean": group["VAI"].mean(),
            "VAI_median": group["VAI"].median(),
            "abs_VAI_median": group["abs_VAI"].median(),
            "abs_VAI_p90": group["abs_VAI"].quantile(0.90),
            "abs_VAI_ge10_pct": (group["abs_VAI"] >= 10).mean() * 100,
            "pct_VAI_gt0": (group["VAI"] > 0).mean() * 100,
            "DEM_m_median": group["DEM_m"].median(),
            "relative_height_m_median": group["relative_height_m"].median(),
            "river_distance_km_median": group["river_distance_m"].median() / 1000,
            "x_center": group["x"].median(),
            "y_center": group["y"].median(),
        })

    segment = pd.DataFrame(rows)
    if len(segment) == 0:
        return segment

    q33 = segment["abs_VAI_median"].quantile(1 / 3)
    q67 = segment["abs_VAI_median"].quantile(2 / 3)
    segment["strength_class"] = np.where(
        segment["abs_VAI_median"] >= q67,
        "strong",
        np.where(segment["abs_VAI_median"] <= q33, "weak", "moderate"),
    )
    segment["strength_q33"] = q33
    segment["strength_q67"] = q67
    return segment.sort_values(["nearest_feature_index", "segment_index"]).reset_index(drop=True)


# ============================================================
# 4. Plot
# ============================================================
def plot_trial(abs_gradient, rel_gradient, threshold_summary, segment):
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 7.6))
    ax_abs, ax_rel, ax_count, ax_seg = axes.ravel()

    for cfg in SCOPES:
        scope_name = cfg["scope"]
        color = cfg["color"]

        abs_df = abs_gradient[abs_gradient["scope"] == scope_name]
        rel_df = rel_gradient[rel_gradient["scope"] == scope_name]

        ax_abs.scatter(
            abs_df["bin_center"],
            abs_df["vai_mean"],
            s=np.clip(abs_df["count"] / 8, 8, 46),
            color=color,
            alpha=0.18,
            linewidth=0,
        )
        x_abs, y_abs = smooth_curve(
            abs_df,
            x_min=HIGH_CONF_LOW,
            x_max=HIGH_CONF_HIGH,
        )
        if len(x_abs):
            ax_abs.plot(x_abs, y_abs, color=color, lw=1.8, label=cfg["label"])

        ax_rel.scatter(
            rel_df["bin_center"],
            rel_df["vai_mean"],
            s=np.clip(rel_df["count"] / 8, 8, 46),
            color=color,
            alpha=0.18,
            linewidth=0,
        )
        x_rel, y_rel = smooth_curve(rel_df, x_min=0)
        if len(x_rel):
            ax_rel.plot(x_rel, y_rel, color=color, lw=1.8, label=cfg["label"])

        row = threshold_summary[threshold_summary["scope"] == scope_name].iloc[0]
        abs_cross = row["abs_elevation_crossing_m"]
        rel_cross = row["relative_height_crossing_m"]
        if np.isfinite(abs_cross):
            ax_abs.axvline(abs_cross, color=color, lw=1.0, ls="--", alpha=0.8)
        if np.isfinite(rel_cross):
            ax_rel.axvline(rel_cross, color=color, lw=1.0, ls="--", alpha=0.8)

        if scope_name in ["region_all", "corridor_20km"]:
            ax_count.plot(
                abs_df["bin_center"],
                abs_df["count"],
                color=color,
                lw=1.4,
                label=cfg["label"],
            )

    for ax in [ax_abs, ax_rel]:
        ax.axhline(0, color="#222222", lw=0.8, ls=":")
        ax.grid(color="#D9D9D9", lw=0.5, alpha=0.75)

    ax_abs.axvspan(HIGH_CONF_LOW, HIGH_CONF_HIGH, color="#F0F0F0", alpha=0.4, zorder=-1)
    ax_abs.set_xlabel("绝对海拔 (m)")
    ax_abs.set_ylabel("平均VAI (%)")
    ax_abs.set_title("A. 按绝对海拔识别VAI反转阈值")
    ax_abs.legend(frameon=False, fontsize=8, loc="best")

    ax_rel.set_xlabel("相对最近河道高差 (m)")
    ax_rel.set_ylabel("平均VAI (%)")
    ax_rel.set_title("B. 按相对河道高差识别VAI反转阈值")

    ax_count.axhline(MIN_BIN_COUNT, color="#B2182B", lw=0.9, ls="--", alpha=0.8)
    ax_count.set_xlabel("绝对海拔 (m)")
    ax_count.set_ylabel("每100 m海拔带的3 km网格数")
    ax_count.set_title("C. 样本量支撑")
    ax_count.grid(color="#D9D9D9", lw=0.5, alpha=0.75)
    ax_count.legend(frameon=False, fontsize=8, loc="best")

    if len(segment):
        segment_plot = segment.sort_values(["nearest_feature_index", "segment_index"]).reset_index(drop=True)
        xs = np.arange(len(segment_plot))
        class_colors = segment_plot["strength_class"].map({
            "strong": "#B2182B",
            "moderate": "#D95F02",
            "weak": "#999999",
        })
        ax_seg.bar(
            xs,
            segment_plot["abs_VAI_median"],
            color=class_colors,
            width=0.78,
            edgecolor="white",
            linewidth=0.3,
        )
        ax_seg.axhline(segment_plot["strength_q33"].iloc[0], color="#666666", lw=0.8, ls=":")
        ax_seg.axhline(segment_plot["strength_q67"].iloc[0], color="#B2182B", lw=0.8, ls="--")
        ax_seg.set_xlabel("30 km河段邻域序号")
        ax_seg.set_ylabel("|VAI|中位数 (%)")
    else:
        ax_seg.text(0.5, 0.5, "无>=10个网格的河段", ha="center", va="center")
        ax_seg.set_axis_off()
    ax_seg.set_title("D. 河段迎背风差异强弱诊断")
    ax_seg.grid(axis="y", color="#D9D9D9", lw=0.5, alpha=0.75)

    fig.suptitle("大渡河河道廊道VAI阈值试验", fontsize=13, y=0.985)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.08, top=0.93, wspace=0.26, hspace=0.34)
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 5. Main
# ============================================================
if __name__ == "__main__":
    print("=" * 72)
    print("Daduhe river-corridor VAI threshold trial")
    print("=" * 72)

    centerline = load_daduhe_centerline_samples()
    print(f"Centerline samples: {len(centerline)}")
    print(f"Centerline features: {centerline['feature_index'].nunique()}")
    print(
        "River DEM range: "
        f"{centerline['river_dem_m'].min():.1f}-"
        f"{centerline['river_dem_m'].max():.1f} m"
    )

    grid = load_vai_grid_with_river_link(centerline)
    grid.to_csv(OUT_CELLS, index=False, encoding="utf-8-sig", float_format="%.3f")
    print(f"Valid 3 km VAI cells: {len(grid)}")
    print(
        "River distance median / p90: "
        f"{grid['river_distance_m'].median() / 1000:.2f} / "
        f"{grid['river_distance_m'].quantile(0.90) / 1000:.2f} km"
    )
    print(
        "Relative height median / p90: "
        f"{grid['relative_height_m'].median():.1f} / "
        f"{grid['relative_height_m'].quantile(0.90):.1f} m"
    )

    abs_tables = []
    rel_tables = []
    for cfg in SCOPES:
        mask = scope_mask(grid, cfg)
        scoped = grid.loc[mask].copy()
        if scoped.empty:
            continue

        abs_tables.append(
            binned_stats(scoped, "DEM_m", ELEV_BIN_M, cfg["scope"], "absolute_elevation")
        )
        rel_tables.append(
            binned_stats(scoped, "relative_height_m", REL_HEIGHT_BIN_M, cfg["scope"], "relative_height")
        )
        print(f"{cfg['scope']}: {len(scoped)} cells")

    abs_gradient = pd.concat(abs_tables, ignore_index=True)
    rel_gradient = pd.concat(rel_tables, ignore_index=True)

    threshold_summary = summarize_thresholds(grid, abs_gradient, rel_gradient)
    sensitivity = summarize_threshold_sensitivity(grid)
    segment = summarize_segment_intensity(grid)

    abs_gradient.to_csv(OUT_ABS_GRADIENT, index=False, encoding="utf-8-sig", float_format="%.3f")
    rel_gradient.to_csv(OUT_REL_GRADIENT, index=False, encoding="utf-8-sig", float_format="%.3f")
    threshold_summary.to_csv(OUT_THRESHOLD, index=False, encoding="utf-8-sig", float_format="%.3f")
    sensitivity.to_csv(OUT_SENSITIVITY, index=False, encoding="utf-8-sig", float_format="%.3f")
    segment.to_csv(OUT_SEGMENT, index=False, encoding="utf-8-sig", float_format="%.3f")

    plot_trial(abs_gradient, rel_gradient, threshold_summary, segment)

    print("\nThreshold summary:")
    show_cols = [
        "scope",
        "n_cells",
        "abs_elevation_crossing_m",
        "relative_height_crossing_m",
        "band_relative_height_m_median",
        "abs_gradient_bins_count_ge30",
        "rel_gradient_bins_count_ge30",
    ]
    print(threshold_summary[show_cols].to_string(index=False))

    if len(segment):
        print("\nSegment strength class counts:")
        print(segment["strength_class"].value_counts().to_string())
        print("\nStrongest segments:")
        print(
            segment.sort_values("abs_VAI_median", ascending=False)
            .head(5)[["segment_id", "n_cells", "abs_VAI_median", "VAI_median", "relative_height_m_median"]]
            .to_string(index=False)
        )

    print("\nOutputs:")
    for path in [
        OUT_CELLS,
        OUT_ABS_GRADIENT,
        OUT_REL_GRADIENT,
        OUT_THRESHOLD,
        OUT_SENSITIVITY,
        OUT_SEGMENT,
        OUT_FIG,
    ]:
        print(f"  {path}")
