# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/5
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: zhao_threshold_intensity.py

"""
This script is used to 对齐赵导三句话的最小可行分析:

1. 用河流中心线 + 10 m DEM 估算每条河的河道海拔基准。
2. 将 LOWESS 反转阈值换算为相对河道/谷底的高差。
3. 用 3 km 局地窗口和 30 km 河段量化“有些山迎背风差异大,有些不大”。

注意:
  - 当前 *_region.tif 是河谷邻域窗口,不是干热河谷 polygon 精确掩膜。
  - 河段强弱是“沿河 30 km 邻域”的最小可行替代,不是正式山体单元。
"""

import math
import os
from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
from rasterio.transform import xy
from scipy.spatial import cKDTree
import shapefile

warnings.filterwarnings("ignore")

# 0. Configuration
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")
CENTERLINE_PATH = BASE_DIR / "valley_area" / "river_net" / "centerline_final.shp"
OUT_DIR = BASE_DIR / "Result" / "Chart" / "altitude"
os.makedirs(OUT_DIR, exist_ok=True)

VALLEYS = {
    "岷江": {
        "key": "Minjiang",
        "centerline_name": "岷江干旱河谷",
    },
    "大渡河": {
        "key": "Daduhe",
        "centerline_name": "大渡河干旱河谷",
    },
    "金沙江": {
        "key": "Jinshajiang",
        "centerline_name": "金沙江干旱河谷",
    },
    "雅砻江": {
        "key": "Yalongjiang",
        "centerline_name": "雅砻江干旱河谷",
    },
}
COLORS = {
    "岷江": "#1B9E77",
    "大渡河": "#D95F02",
    "金沙江": "#7570B3",
    "雅砻江": "#E7298A",
}

HIGH_CONF_LOW = 1500
HIGH_CONF_HIGH = 4500
CENTERLINE_SAMPLE_STEP_M = 100
SEGMENT_LENGTH_M = 30000
MAX_RIVER_DISTANCE_M = 30000
THRESHOLD_BAND_M = 100
MIN_GRID_PER_SEGMENT = 10

plt.rcParams.update({
    "font.sans-serif": [
        "SimHei",
        "Microsoft YaHei",
        "STHeiti",
        "WenQuanYi Micro Hei",
        "Noto Sans CJK SC",
        "sans-serif",
    ],
    "font.family": "sans-serif",
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.linewidth": 0.8,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 300,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
})


# 1. Geometry helpers
def iter_parts(shape):
    """Yield polyline parts from a pyshp shape."""
    parts = list(shape.parts) + [len(shape.points)]
    for i in range(len(parts) - 1):
        pts = shape.points[parts[i]:parts[i + 1]]
        if len(pts) >= 2:
            yield pts


def densify_polyline(points, step_m=CENTERLINE_SAMPLE_STEP_M):
    """Densify a polyline and keep distance along the current feature."""
    out = []
    cum_dist = 0.0
    for p0, p1 in zip(points[:-1], points[1:]):
        x0, y0 = p0
        x1, y1 = p1
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        if dist == 0:
            continue
        n_steps = max(1, int(math.floor(dist / step_m)))
        for k in range(n_steps):
            t = k / n_steps
            out.append((x0 + dx * t, y0 + dy * t, cum_dist + dist * t))
        cum_dist += dist
    x_last, y_last = points[-1]
    out.append((x_last, y_last, cum_dist))
    return out


def valid_raster_value(value, nodata):
    """判断栅格采样值是否有效（有限、非 nodata、大于 0）"""
    if not math.isfinite(value):
        return False
    if nodata is not None and np.isclose(value, nodata, rtol=0, atol=1e25):
        return False
    return value > 0


# 2. River baseline
def load_centerline_samples(valley_name, cfg):
    """Read one valley's centerline, densify it, and sample river elevation."""
    valley_key = cfg["key"]
    dem10_path = BASE_DIR / valley_key / "geo_factor" / "elevation_10m_projected_region.tif"

    rows = []
    reader = shapefile.Reader(str(CENTERLINE_PATH))
    feature_index = 0
    total_length = 0.0

    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec.get("Name") != cfg["centerline_name"]:
            continue

        feature_index += 1
        feature_length = float(rec.get("LENGTH") or 0.0)
        total_length += feature_length

        for pts in iter_parts(sr.shape):
            for x_coord, y_coord, dist_along in densify_polyline(pts):
                segment_index = int(dist_along // SEGMENT_LENGTH_M)
                rows.append({
                    "河谷": valley_name,
                    "valley": valley_key,
                    "x": x_coord,
                    "y": y_coord,
                    "feature_index": feature_index,
                    "segment_index": segment_index,
                    "segment_id": f"{valley_key}_f{feature_index:03d}_s{segment_index:03d}",
                    "dist_along_feature_m": dist_along,
                })

    samples = pd.DataFrame(rows)
    if samples.empty:
        raise RuntimeError(f"{valley_name}: centerline samples are empty.")

    coords = list(zip(samples["x"].to_numpy(), samples["y"].to_numpy()))
    dem_values = []
    with rio.open(dem10_path, "r") as src:
        nodata = src.nodata
        for sample in src.sample(coords, masked=False):
            z = float(sample[0])
            dem_values.append(z if valid_raster_value(z, nodata) else np.nan)

    samples["river_dem_m"] = dem_values
    samples = samples[np.isfinite(samples["river_dem_m"])].reset_index(drop=True)
    samples["centerline_length_km"] = total_length / 1000
    return samples


def summarize_river_baseline(centerline_samples):
    """汇总各河谷中心线 DEM 采样结果，输出河道海拔基准统计表"""
    rows = []
    for valley_name, df in centerline_samples.items():
        z = df["river_dem_m"].to_numpy()
        rows.append({
            "河谷": valley_name,
            "valley": df["valley"].iloc[0],
            "centerline_features": int(df["feature_index"].nunique()),
            "centerline_length_km": df["centerline_length_km"].iloc[0],
            "valid_dem_samples": len(df),
            "river_dem_min_m": np.percentile(z, 0),
            "river_dem_p05_m": np.percentile(z, 5),
            "river_dem_p10_m": np.percentile(z, 10),
            "river_dem_median_m": np.percentile(z, 50),
            "river_dem_p90_m": np.percentile(z, 90),
            "river_dem_max_m": np.percentile(z, 100),
        })
    out = pd.DataFrame(rows)
    out.to_csv(
        OUT_DIR / "river_centerline_dem_summary.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.1f",
    )
    return out


# 3. 3 km grid cells
def load_grid_cells(valley_name, cfg, river_samples):
    """Load valid 3 km VAI cells and attach nearest river elevation."""
    valley_key = cfg["key"]
    vai_path = BASE_DIR / valley_key / "VAI" / "VAI_3km_region.tif"
    dem3_path = BASE_DIR / valley_key / "VAI" / "DEM_3km_region.tif"

    with rio.open(vai_path, "r") as src_vai, rio.open(dem3_path, "r") as src_dem:
        vai = src_vai.read(1).astype(float)
        dem = src_dem.read(1).astype(float)
        valid = np.isfinite(vai) & np.isfinite(dem) & (dem > 0)
        rows, cols = np.where(valid)
        xs, ys = xy(src_vai.transform, rows, cols, offset="center")

    grid = pd.DataFrame({
        "河谷": valley_name,
        "valley": valley_key,
        "row": rows,
        "col": cols,
        "x": np.asarray(xs, dtype=float),
        "y": np.asarray(ys, dtype=float),
        "VAI": vai[valid],
        "DEM_m": dem[valid],
    })

    tree = cKDTree(river_samples[["x", "y"]].to_numpy())
    dist, idx = tree.query(grid[["x", "y"]].to_numpy(), k=1)
    nearest = river_samples.iloc[idx].reset_index(drop=True)

    grid["river_distance_m"] = dist
    grid["nearest_river_dem_m"] = nearest["river_dem_m"].to_numpy()
    grid["relative_height_m"] = grid["DEM_m"] - grid["nearest_river_dem_m"]
    grid["segment_id"] = nearest["segment_id"].to_numpy()
    grid["segment_feature_index"] = nearest["feature_index"].to_numpy()
    grid["segment_index"] = nearest["segment_index"].to_numpy()
    grid["abs_VAI"] = grid["VAI"].abs()
    grid["high_conf_elev"] = (
        (grid["DEM_m"] >= HIGH_CONF_LOW) &
        (grid["DEM_m"] <= HIGH_CONF_HIGH)
    )
    grid["near_river"] = grid["river_distance_m"] <= MAX_RIVER_DISTANCE_M
    return grid


def summarize_grid_intensity(grid_cells):
    """按河谷汇总 3 km 网格的 VAI 强度指标，输出 CSV"""
    rows = []
    for valley_name, grid in grid_cells.items():
        df = grid[grid["high_conf_elev"]].copy()
        near = df[df["near_river"]].copy()
        rows.append({
            "河谷": valley_name,
            "n_grid_high_conf": len(df),
            "n_grid_high_conf_near_river": len(near),
            "VAI_mean": df["VAI"].mean(),
            "VAI_median": df["VAI"].median(),
            "abs_VAI_median": df["abs_VAI"].median(),
            "abs_VAI_p90": df["abs_VAI"].quantile(0.90),
            "abs_VAI_ge10_pct": (df["abs_VAI"] >= 10).mean() * 100,
            "abs_VAI_ge20_pct": (df["abs_VAI"] >= 20).mean() * 100,
            "VAI_p95_minus_p05": df["VAI"].quantile(0.95) - df["VAI"].quantile(0.05),
            "near_river_abs_VAI_median": near["abs_VAI"].median(),
            "near_river_abs_VAI_p90": near["abs_VAI"].quantile(0.90),
            "near_river_abs_VAI_ge10_pct": (near["abs_VAI"] >= 10).mean() * 100,
            "near_river_median_relative_height_m": near["relative_height_m"].median(),
            "near_river_median_distance_km": near["river_distance_m"].median() / 1000,
        })
    out = pd.DataFrame(rows)
    out.to_csv(
        OUT_DIR / "zhao_grid_intensity_by_valley.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.2f",
    )
    return out


def summarize_segment_intensity(grid_cells):
    """按 30 km 河段汇总 VAI 强度，区分强弱河段并输出 CSV"""
    records = []
    for valley_name, grid in grid_cells.items():
        df = grid[grid["high_conf_elev"] & grid["near_river"]].copy()
        for segment_id, g in df.groupby("segment_id"):
            if len(g) < MIN_GRID_PER_SEGMENT:
                continue
            records.append({
                "河谷": valley_name,
                "segment_id": segment_id,
                "segment_feature_index": int(g["segment_feature_index"].mode().iloc[0]),
                "segment_index": int(g["segment_index"].mode().iloc[0]),
                "n_grid": len(g),
                "VAI_mean": g["VAI"].mean(),
                "VAI_median": g["VAI"].median(),
                "abs_VAI_median": g["abs_VAI"].median(),
                "abs_VAI_p90": g["abs_VAI"].quantile(0.90),
                "abs_VAI_ge10_pct": (g["abs_VAI"] >= 10).mean() * 100,
                "VAI_p95_minus_p05": g["VAI"].quantile(0.95) - g["VAI"].quantile(0.05),
                "pct_VAI_gt0": (g["VAI"] > 0).mean() * 100,
                "median_DEM_m": g["DEM_m"].median(),
                "median_relative_height_m": g["relative_height_m"].median(),
                "median_river_distance_km": g["river_distance_m"].median() / 1000,
                "x_center": g["x"].median(),
                "y_center": g["y"].median(),
                "x_min": g["x"].min(),
                "x_max": g["x"].max(),
                "y_min": g["y"].min(),
                "y_max": g["y"].max(),
            })

    segment = pd.DataFrame(records)
    segment.to_csv(
        OUT_DIR / "zhao_segment_intensity_30km.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.2f",
    )

    summary_rows = []
    for valley_name, g in segment.groupby("河谷"):
        summary_rows.append({
            "河谷": valley_name,
            "n_segments": len(g),
            "segment_abs_VAI_median": g["abs_VAI_median"].median(),
            "segment_abs_VAI_min": g["abs_VAI_median"].min(),
            "segment_abs_VAI_p10": g["abs_VAI_median"].quantile(0.10),
            "segment_abs_VAI_p90": g["abs_VAI_median"].quantile(0.90),
            "segment_abs_VAI_max": g["abs_VAI_median"].max(),
            "strong_segment_ge10_count": int((g["abs_VAI_median"] >= 10).sum()),
            "strong_segment_ge10_pct": (g["abs_VAI_median"] >= 10).mean() * 100,
            "weak_segment_le3_count": int((g["abs_VAI_median"] <= 3).sum()),
            "weak_segment_le3_pct": (g["abs_VAI_median"] <= 3).mean() * 100,
            "segment_amplitude_median": g["VAI_p95_minus_p05"].median(),
        })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(
        OUT_DIR / "zhao_segment_intensity_summary.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.2f",
    )
    return segment, summary


def plot_segment_intensity(segment):
    """Diagnostic plot for strong/weak 30 km river-neighborhood segments."""
    fig, axes = plt.subplots(4, 1, figsize=(9, 8.2), sharex=False)
    for i, (ax, valley_name) in enumerate(zip(axes, VALLEYS.keys())):
        g = segment[segment["河谷"] == valley_name].copy()
        g = g.sort_values(["segment_feature_index", "segment_index", "x_center", "y_center"])
        x_vals = np.arange(len(g))
        y_vals = g["abs_VAI_median"].to_numpy()

        ax.plot(x_vals, y_vals, color=COLORS[valley_name], lw=1.2, alpha=0.8)
        point_colors = np.where(
            y_vals >= 10,
            "#B2182B",
            np.where(y_vals <= 3, "#999999", COLORS[valley_name]),
        )
        ax.scatter(x_vals, y_vals, c=point_colors, s=28, zorder=3,
                   edgecolor="white", linewidth=0.4)
        ax.axhline(10, color="#B2182B", lw=0.8, ls="--", alpha=0.8)
        ax.axhline(3, color="#666666", lw=0.8, ls=":", alpha=0.8)
        ax.set_ylabel("|VAI|中位数(%)")
        ax.text(0.01, 0.88, f"{valley_name} 30 km 河段邻域",
                transform=ax.transAxes, fontsize=10.5, ha="left", va="top")
        ax.grid(axis="y", color="#D0D0D0", lw=0.5, alpha=0.7)
        ax.set_xlim(-0.6, max(len(g) - 0.4, 0.4))
        if i < len(axes) - 1:
            ax.set_xticklabels([])
        else:
            if len(g) <= 30:
                ax.set_xticks(x_vals)
            else:
                ax.set_xticks(np.linspace(0, len(g) - 1, 8, dtype=int))

    axes[-1].set_xlabel("河段序号(按中心线 feature 与段内序号排序)")
    fig.suptitle("迎风/背风差异强弱的河段尺度诊断", y=0.985, fontsize=13)
    fig.subplots_adjust(hspace=0.36, top=0.94, bottom=0.08, left=0.10, right=0.98)
    out_path = OUT_DIR / "Fig6_zhao_segment_intensity_30km.png"
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


# 4. Threshold height summary
def summarize_threshold_heights(river_baseline, grid_cells):
    """将 LOWESS 反转海拔换算为相对河道/谷底高差，生成阈值高度汇总表"""
    reversal = pd.read_csv(OUT_DIR / "reversal_bootstrap_results.csv")
    segmented = pd.read_csv(OUT_DIR / "methods_forest_data.csv")
    segmented = segmented[segmented["method"].str.contains("Segmented", na=False)].copy()

    rows = []
    for _, row in reversal.iterrows():
        valley_name = row["河谷"]
        rev = float(row["反转海拔_m"])
        grid = grid_cells[valley_name]
        base = river_baseline[river_baseline["河谷"] == valley_name].iloc[0]

        band = grid[
            grid["near_river"] &
            (np.abs(grid["DEM_m"] - rev) <= THRESHOLD_BAND_M)
        ].copy()
        high_conf_band = band[
            (band["DEM_m"] >= HIGH_CONF_LOW) &
            (band["DEM_m"] <= HIGH_CONF_HIGH)
        ].copy()

        seg_row = segmented[segmented["valley"] == valley_name]
        if len(seg_row):
            seg_est = float(seg_row["estimate"].iloc[0])
            seg_dist = float(seg_row["distance_to_lowess_m"].iloc[0])
        else:
            seg_est = np.nan
            seg_dist = np.nan

        rows.append({
            "河谷": valley_name,
            "LOWESS反转海拔_m": rev,
            "LOWESS_CI_low_m": row["CI_low_m"],
            "LOWESS_CI_high_m": row["CI_high_m"],
            "Segmented邻近断点_m": seg_est,
            "Segmented距LOWESS_m": seg_dist,
            "river_p05_m": base["river_dem_p05_m"],
            "river_p10_m": base["river_dem_p10_m"],
            "river_median_m": base["river_dem_median_m"],
            "反转海拔_minus_river_p05_m": rev - base["river_dem_p05_m"],
            "反转海拔_minus_river_p10_m": rev - base["river_dem_p10_m"],
            "反转海拔_minus_river_median_m": rev - base["river_dem_median_m"],
            "near_river_cells_within_100m": len(high_conf_band),
            "局地相对河道高差_median_m": high_conf_band["relative_height_m"].median(),
            "局地相对河道高差_p25_m": high_conf_band["relative_height_m"].quantile(0.25),
            "局地相对河道高差_p75_m": high_conf_band["relative_height_m"].quantile(0.75),
            "局地河距_median_km": high_conf_band["river_distance_m"].median() / 1000,
        })

    out = pd.DataFrame(rows)
    out.to_csv(
        OUT_DIR / "zhao_threshold_height_summary.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.1f",
    )

    valleys = out["河谷"].tolist()
    rev_alt = out["LOWESS反转海拔_m"].to_numpy()
    diff = np.abs(rev_alt[:, None] - rev_alt[None, :])
    diff_df = pd.DataFrame(diff, index=valleys, columns=valleys)
    diff_df.to_csv(
        OUT_DIR / "zhao_reversal_pairwise_height_diff.csv",
        encoding="utf-8-sig",
        float_format="%.0f",
    )
    return out, diff_df


# 5. Main
if __name__ == "__main__":
    print("=" * 70)
    print("Zhao task alignment: threshold height + intensity heterogeneity")
    print("=" * 70)

    centerline_samples = {}
    grid_cells = {}
    for valley_name, cfg in VALLEYS.items():
        print(f"\n[1/2] Loading river baseline: {valley_name}")
        river_samples = load_centerline_samples(valley_name, cfg)
        centerline_samples[valley_name] = river_samples
        print(f"  river samples: {len(river_samples)}")

        print(f"[2/2] Loading VAI grid and nearest river: {valley_name}")
        grid = load_grid_cells(valley_name, cfg, river_samples)
        grid_cells[valley_name] = grid
        print(f"  valid 3km grids: {len(grid)}")

    river_baseline = summarize_river_baseline(centerline_samples)
    grid_summary = summarize_grid_intensity(grid_cells)
    segment_table, segment_summary = summarize_segment_intensity(grid_cells)
    segment_plot = plot_segment_intensity(segment_table)
    threshold_summary, pairwise_diff = summarize_threshold_heights(
        river_baseline,
        grid_cells,
    )

    print("\n=== River baseline ===")
    print(river_baseline.to_string(index=False))

    print("\n=== Threshold height summary ===")
    print(threshold_summary.to_string(index=False))

    print("\n=== Grid intensity by valley ===")
    print(grid_summary.to_string(index=False))

    print("\n=== Segment intensity summary ===")
    print(segment_summary.to_string(index=False))

    print("\nOutputs:")
    for name in [
        "river_centerline_dem_summary.csv",
        "zhao_threshold_height_summary.csv",
        "zhao_reversal_pairwise_height_diff.csv",
        "zhao_grid_intensity_by_valley.csv",
        "zhao_segment_intensity_30km.csv",
        "zhao_segment_intensity_summary.csv",
    ]:
        print(f"  {OUT_DIR / name}")
    print(f"  {segment_plot}")
