# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/6
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_buffer_inner_outer_altitude_gradient.py

"""
All-valley combined VAI elevation gradient using the earlier valley inner/outer raster.

This script continues the old NDVI altitude-analysis workflow:
  - valley_chuanxi_clip.tif encodes valley outer/inner classes.
  - tens digit: 1=Daduhe, 2=Minjiang, 3=Jinshajiang, 4=Yalongjiang.
  - ones digit: 1=outer, 2=inner.

All four dry-hot valleys are pooled together:
  - outer = {11, 21, 31, 41}
  - inner = {12, 22, 32, 42}

For each elevation bin, the script first computes the four NDVI means:
  inner_windward, inner_leeward, outer_windward, outer_leeward

Then it converts them to bin-level VAI:
  VAI = (NDVI_windward - NDVI_leeward) /
        ((NDVI_windward + NDVI_leeward) / 2) * 100

This is not the later rectangular-region 3 km VAI workflow. It is a direct
extension of the old buffer-based inner/outer NDVI altitude analysis.
"""

from pathlib import Path
from rasterio.windows import Window
from statsmodels.nonparametric.smoothers_lowess import lowess
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")

NDVI_PATH = BASE_DIR / "NDVI" / "Interannual" / "NDVI_interannual_mean.tif"
DEM_PATH = BASE_DIR / "GeoFactor" / "DEM" / "elevation_10m_projected_valley_clip.tif"
DIRECTION_PATH = BASE_DIR / "GeoFactor" / "windward_leeward" / "windward_leeward.tif"
VALLEY_PATH = BASE_DIR / "valley_area" / "valley_chuanxi" / "valley_chuanxi_clip.tif"

OUT_TABLE_DIR = BASE_DIR / "Result" / "Table" / "altitude"
OUT_CHART_DIR = BASE_DIR / "Result" / "Chart" / "altitude"
OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
OUT_CHART_DIR.mkdir(parents=True, exist_ok=True)

OUT_XLSX = OUT_TABLE_DIR / "VAI_buffer_inner_outer_altitude_gradient.xlsx"
OUT_CSV = OUT_TABLE_DIR / "VAI_buffer_inner_outer_altitude_gradient.csv"
OUT_SUMMARY = OUT_TABLE_DIR / "VAI_buffer_inner_outer_altitude_summary.csv"
OUT_FIG = OUT_CHART_DIR / "VAI_buffer_inner_outer_altitude_gradient.png"

ELEV_STEP = 50
READ_BLOCK_SIZE = 2048
NDVI_MIN = 0.1
MIN_SIDE_PIXELS = 100
SUMMARY_MIN_SIDE_PIXELS = 500
SUMMARY_ELEV_LOW = 800
SUMMARY_ELEV_HIGH = 4000
LOWESS_FRAC = 0.35

WINDWARD_VAL = 1
LEEWARD_VAL = 2
ALL_OUTER_VALS = {11, 21, 31, 41}
ALL_INNER_VALS = {12, 22, 32, 42}

COMPONENTS = {
    "inner_windward": (ALL_INNER_VALS, WINDWARD_VAL),
    "inner_leeward": (ALL_INNER_VALS, LEEWARD_VAL),
    "outer_windward": (ALL_OUTER_VALS, WINDWARD_VAL),
    "outer_leeward": (ALL_OUTER_VALS, LEEWARD_VAL),
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "Arial", "DejaVu Sans"],
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
# 1. Helpers
# ============================================================
def grow(arr, min_len):
    if min_len <= len(arr):
        return arr
    new_len = max(min_len, int(len(arr) * 1.5) + 16)
    out = np.zeros(new_len, dtype=arr.dtype)
    out[:len(arr)] = arr
    return out


def valid_float(values, nodata):
    mask = np.isfinite(values)
    if nodata is not None and np.isfinite(float(nodata)):
        mask &= ~np.isclose(values, float(nodata))
    return mask


def add_values(acc, component, bin_idx, ndvi_vals):
    if len(bin_idx) == 0:
        return

    max_idx = int(bin_idx.max()) + 1
    for field in ["sum", "sumsq", "count"]:
        acc[component][field] = grow(acc[component][field], max_idx)

    counts = np.bincount(bin_idx, minlength=max_idx)
    sums = np.bincount(bin_idx, weights=ndvi_vals, minlength=max_idx)
    sumsqs = np.bincount(bin_idx, weights=ndvi_vals * ndvi_vals, minlength=max_idx)

    acc[component]["count"][:max_idx] += counts.astype(np.int64)
    acc[component]["sum"][:max_idx] += sums
    acc[component]["sumsq"][:max_idx] += sumsqs


def mean_from_acc(acc, component, idx):
    count = acc[component]["count"][idx] if idx < len(acc[component]["count"]) else 0
    if count == 0:
        return np.nan
    return acc[component]["sum"][idx] / count


def std_from_acc(acc, component, idx):
    count = acc[component]["count"][idx] if idx < len(acc[component]["count"]) else 0
    if count == 0:
        return np.nan
    mean_val = acc[component]["sum"][idx] / count
    var = acc[component]["sumsq"][idx] / count - mean_val * mean_val
    return np.sqrt(max(var, 0.0))


def count_from_acc(acc, component, idx):
    if idx >= len(acc[component]["count"]):
        return 0
    return int(acc[component]["count"][idx])


def calc_vai(windward_mean, leeward_mean, windward_count, leeward_count):
    if windward_count < MIN_SIDE_PIXELS or leeward_count < MIN_SIDE_PIXELS:
        return np.nan
    if not np.isfinite(windward_mean) or not np.isfinite(leeward_mean):
        return np.nan
    denominator = (windward_mean + leeward_mean) / 2
    if denominator <= 0:
        return np.nan
    return (windward_mean - leeward_mean) / denominator * 100


def smooth_xy(df, x_col, y_col):
    valid = np.isfinite(df[y_col])
    x = df.loc[valid, x_col].to_numpy()
    y = df.loc[valid, y_col].to_numpy()
    if len(x) < 4:
        return x, y
    smoothed = lowess(y, x, frac=LOWESS_FRAC, return_sorted=True)
    return smoothed[:, 0], smoothed[:, 1]


def first_positive_to_negative_crossing(x, y):
    if len(x) < 2:
        return np.nan
    for i in range(len(x) - 1):
        y0, y1 = y[i], y[i + 1]
        if y0 == 0 and i > 0 and y[i - 1] > 0:
            return x[i]
        if y0 > 0 and y1 < 0:
            return x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0)
    return np.nan


# ============================================================
# 2. Accumulate binned NDVI statistics
# ============================================================
def accumulate_statistics():
    acc = {
        comp: {
            "sum": np.zeros(256, dtype=np.float64),
            "sumsq": np.zeros(256, dtype=np.float64),
            "count": np.zeros(256, dtype=np.int64),
        }
        for comp in COMPONENTS
    }

    all_valley_vals = ALL_OUTER_VALS | ALL_INNER_VALS

    with (
        rio.open(NDVI_PATH, "r") as src_ndvi,
        rio.open(DEM_PATH, "r") as src_dem,
        rio.open(DIRECTION_PATH, "r") as src_dir,
        rio.open(VALLEY_PATH, "r") as src_valley,
    ):
        shapes = {
            "NDVI": (src_ndvi.height, src_ndvi.width),
            "DEM": (src_dem.height, src_dem.width),
            "Direction": (src_dir.height, src_dir.width),
            "Valley": (src_valley.height, src_valley.width),
        }
        if len(set(shapes.values())) != 1:
            raise RuntimeError(f"Input raster shape mismatch: {shapes}")

        height, width = src_valley.height, src_valley.width
        ndvi_nodata = src_ndvi.nodata
        dem_nodata = src_dem.nodata
        direction_nodata = src_dir.nodata
        valley_nodata = src_valley.nodata

        total_windows = 0
        used_windows = 0
        valley_pixels = 0

        for row_off in range(0, height, READ_BLOCK_SIZE):
            win_h = min(READ_BLOCK_SIZE, height - row_off)
            for col_off in range(0, width, READ_BLOCK_SIZE):
                win_w = min(READ_BLOCK_SIZE, width - col_off)
                window = Window(col_off, row_off, win_w, win_h)
                total_windows += 1

                valley = src_valley.read(1, window=window)
                valley_mask = np.isin(valley, list(all_valley_vals))
                if valley_nodata is not None:
                    valley_mask &= valley != valley_nodata
                if not valley_mask.any():
                    continue

                used_windows += 1
                valley_pixels += int(valley_mask.sum())

                ndvi = src_ndvi.read(1, window=window).astype(np.float64)
                dem = src_dem.read(1, window=window).astype(np.float64)
                direction = src_dir.read(1, window=window)

                base_valid = valley_mask
                base_valid &= valid_float(ndvi, ndvi_nodata)
                base_valid &= valid_float(dem, dem_nodata)
                base_valid &= ndvi > NDVI_MIN
                base_valid &= dem > 0
                base_valid &= (direction == WINDWARD_VAL) | (direction == LEEWARD_VAL)
                if direction_nodata is not None:
                    base_valid &= direction != direction_nodata
                if not base_valid.any():
                    continue

                for comp, (valley_values, direction_value) in COMPONENTS.items():
                    mask = base_valid & np.isin(valley, list(valley_values)) & (direction == direction_value)
                    if not mask.any():
                        continue
                    elev_vals = dem[mask]
                    ndvi_vals = ndvi[mask]
                    bin_idx = np.floor(elev_vals / ELEV_STEP).astype(np.int32)
                    add_values(acc, comp, bin_idx, ndvi_vals)

            print(
                f"Processed row {min(row_off + READ_BLOCK_SIZE, height)}/{height}; "
                f"used windows={used_windows}, valley pixels={valley_pixels:,}"
            )

        print(f"Total windows: {total_windows}, windows with valleys: {used_windows}")

    return acc


# ============================================================
# 3. Build output tables
# ============================================================
def build_table(acc):
    max_len = max(len(acc[comp]["count"]) for comp in COMPONENTS)
    records = []

    for idx in range(max_len):
        counts = {comp: count_from_acc(acc, comp, idx) for comp in COMPONENTS}
        if sum(counts.values()) == 0:
            continue

        row = {
            "elev_lo": idx * ELEV_STEP,
            "elev_hi": (idx + 1) * ELEV_STEP,
            "elev_center": (idx + 0.5) * ELEV_STEP,
        }

        for comp in COMPONENTS:
            row[f"{comp}_mean"] = mean_from_acc(acc, comp, idx)
            row[f"{comp}_std"] = std_from_acc(acc, comp, idx)
            row[f"{comp}_count"] = counts[comp]

        row["inner_pair_count"] = min(counts["inner_windward"], counts["inner_leeward"])
        row["outer_pair_count"] = min(counts["outer_windward"], counts["outer_leeward"])
        row["inner_vai"] = calc_vai(
            row["inner_windward_mean"],
            row["inner_leeward_mean"],
            counts["inner_windward"],
            counts["inner_leeward"],
        )
        row["outer_vai"] = calc_vai(
            row["outer_windward_mean"],
            row["outer_leeward_mean"],
            counts["outer_windward"],
            counts["outer_leeward"],
        )
        row["delta_vai_inner_minus_outer"] = row["inner_vai"] - row["outer_vai"]
        row["inner_vai_valid"] = np.isfinite(row["inner_vai"])
        row["outer_vai_valid"] = np.isfinite(row["outer_vai"])
        row["both_vai_valid"] = row["inner_vai_valid"] and row["outer_vai_valid"]

        records.append(row)

    df = pd.DataFrame(records)
    return df.sort_values("elev_center").reset_index(drop=True)


def summarize(df):
    rows = []
    for zone, y_col, count_col in [
        ("inner", "inner_vai", "inner_pair_count"),
        ("outer", "outer_vai", "outer_pair_count"),
    ]:
        valid = df[
            np.isfinite(df[y_col]) &
            (df[count_col] >= SUMMARY_MIN_SIDE_PIXELS) &
            (df["elev_center"] >= SUMMARY_ELEV_LOW) &
            (df["elev_center"] <= SUMMARY_ELEV_HIGH)
        ].copy()
        x_sm, y_sm = smooth_xy(valid, "elev_center", y_col)
        rows.append({
            "zone": zone,
            "summary_min_side_pixels": SUMMARY_MIN_SIDE_PIXELS,
            "summary_elev_low_m": SUMMARY_ELEV_LOW,
            "summary_elev_high_m": SUMMARY_ELEV_HIGH,
            "valid_bins": len(valid),
            "elev_min_m": valid["elev_center"].min() if len(valid) else np.nan,
            "elev_max_m": valid["elev_center"].max() if len(valid) else np.nan,
            "mean_vai": valid[y_col].mean() if len(valid) else np.nan,
            "median_vai": valid[y_col].median() if len(valid) else np.nan,
            "zero_crossing_lowess_m": first_positive_to_negative_crossing(x_sm, y_sm),
            "max_abs_vai": valid[y_col].abs().max() if len(valid) else np.nan,
            "max_abs_vai_elev_m": valid.loc[valid[y_col].abs().idxmax(), "elev_center"] if len(valid) else np.nan,
        })

    common = df[
        df["both_vai_valid"] &
        (df["inner_pair_count"] >= SUMMARY_MIN_SIDE_PIXELS) &
        (df["outer_pair_count"] >= SUMMARY_MIN_SIDE_PIXELS) &
        (df["elev_center"] >= SUMMARY_ELEV_LOW) &
        (df["elev_center"] <= SUMMARY_ELEV_HIGH)
    ].copy()
    rows.append({
        "zone": "inner_minus_outer",
        "summary_min_side_pixels": SUMMARY_MIN_SIDE_PIXELS,
        "summary_elev_low_m": SUMMARY_ELEV_LOW,
        "summary_elev_high_m": SUMMARY_ELEV_HIGH,
        "valid_bins": len(common),
        "elev_min_m": common["elev_center"].min() if len(common) else np.nan,
        "elev_max_m": common["elev_center"].max() if len(common) else np.nan,
        "mean_vai": common["delta_vai_inner_minus_outer"].mean() if len(common) else np.nan,
        "median_vai": common["delta_vai_inner_minus_outer"].median() if len(common) else np.nan,
        "zero_crossing_lowess_m": np.nan,
        "max_abs_vai": common["delta_vai_inner_minus_outer"].abs().max() if len(common) else np.nan,
        "max_abs_vai_elev_m": common.loc[
            common["delta_vai_inner_minus_outer"].abs().idxmax(), "elev_center"
        ] if len(common) else np.nan,
    })
    return pd.DataFrame(rows)


# ============================================================
# 4. Plot
# ============================================================
def plot_result(df, summary):
    plot_df = df[
        (df["elev_center"] >= SUMMARY_ELEV_LOW) &
        (df["elev_center"] <= SUMMARY_ELEV_HIGH)
    ].copy()

    inner_valid = np.isfinite(plot_df["inner_vai"])
    outer_valid = np.isfinite(plot_df["outer_vai"])
    both_valid = plot_df["both_vai_valid"].astype(bool)

    x_inner, y_inner = smooth_xy(
        plot_df[inner_valid & (plot_df["inner_pair_count"] >= SUMMARY_MIN_SIDE_PIXELS)],
        "elev_center", "inner_vai"
    )
    x_outer, y_outer = smooth_xy(
        plot_df[outer_valid & (plot_df["outer_pair_count"] >= SUMMARY_MIN_SIDE_PIXELS)],
        "elev_center", "outer_vai"
    )
    x_delta, y_delta = smooth_xy(
        plot_df[
            both_valid &
            (plot_df["inner_pair_count"] >= SUMMARY_MIN_SIDE_PIXELS) &
            (plot_df["outer_pair_count"] >= SUMMARY_MIN_SIDE_PIXELS)
        ],
        "elev_center", "delta_vai_inner_minus_outer"
    )

    fig, axes = plt.subplots(
        3, 1, figsize=(9.2, 8.2), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.35, 1.0]},
    )

    ax = axes[0]
    ax.scatter(
        plot_df.loc[inner_valid, "elev_center"],
        plot_df.loc[inner_valid, "inner_vai"],
        s=np.clip(plot_df.loc[inner_valid, "inner_pair_count"] / 600, 10, 60),
        color="#D95F02", alpha=0.45, edgecolor="none", label="内部",
    )
    ax.scatter(
        plot_df.loc[outer_valid, "elev_center"],
        plot_df.loc[outer_valid, "outer_vai"],
        s=np.clip(plot_df.loc[outer_valid, "outer_pair_count"] / 600, 10, 60),
        color="#1B9E77", alpha=0.45, edgecolor="none", label="外部",
    )
    if len(x_inner):
        ax.plot(x_inner, y_inner, color="#D95F02", lw=2.0, label="内部 LOWESS")
    if len(x_outer):
        ax.plot(x_outer, y_outer, color="#1B9E77", lw=2.0, label="外部 LOWESS")
    ax.axhline(0, color="#555555", lw=0.8, ls="--")

    for _, row in summary[summary["zone"].isin(["inner", "outer"])].iterrows():
        z = row["zero_crossing_lowess_m"]
        if np.isfinite(z):
            color = "#D95F02" if row["zone"] == "inner" else "#1B9E77"
            ax.axvline(z, color=color, lw=1.0, ls=":")
            zlabel = "内部" if row["zone"] == "inner" else "外部"
            ax.text(z + 20, ax.get_ylim()[1] * 0.85, f"{zlabel} z0={z:.0f} m",
                    color=color, fontsize=8, rotation=90, va="top")

    ax.set_ylabel("VAI (%)")
    ax.set_title("川西四河谷 buffer 内部/外部 VAI 海拔梯度")
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)

    ax = axes[1]
    pos_color = "#C36A2D"
    neg_color = "#4A7C6F"
    colors = np.where(plot_df.loc[both_valid, "delta_vai_inner_minus_outer"] >= 0, pos_color, neg_color)
    ax.bar(
        plot_df.loc[both_valid, "elev_center"],
        plot_df.loc[both_valid, "delta_vai_inner_minus_outer"],
        width=ELEV_STEP * 0.82, color=colors, alpha=0.68, edgecolor="none",
    )
    if len(x_delta):
        ax.plot(x_delta, y_delta, color="#333333", lw=1.4)
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set_ylabel("内部 − 外部\nVAI (%)")
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)

    ax = axes[2]
    max_count = np.nanmax([
        plot_df["inner_pair_count"].max(),
        plot_df["outer_pair_count"].max(),
    ])
    if max_count <= 0:
        max_count = 1
    ax.bar(
        plot_df["elev_center"], plot_df["inner_pair_count"] / max_count,
        width=ELEV_STEP * 0.82, color="#D95F02", alpha=0.45, edgecolor="none", label="内部配对数",
    )
    ax.bar(
        plot_df["elev_center"], -plot_df["outer_pair_count"] / max_count,
        width=ELEV_STEP * 0.82, color="#1B9E77", alpha=0.45, edgecolor="none", label="外部配对数",
    )
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set_ylabel("配对数\n（归一化）")
    ax.set_xlabel("海拔 (m)")
    ax.legend(frameon=False, loc="upper right")

    xmin = plot_df.loc[inner_valid | outer_valid, "elev_center"].min()
    xmax = plot_df.loc[inner_valid | outer_valid, "elev_center"].max()
    for ax in axes:
        ax.set_xlim(xmin - ELEV_STEP, xmax + ELEV_STEP)

    fig.tight_layout()
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 5. Main
# ============================================================
def main():
    print("Starting all-valley buffer-based inner/outer VAI altitude analysis.")
    print(f"Inputs:\n  {NDVI_PATH}\n  {DEM_PATH}\n  {DIRECTION_PATH}\n  {VALLEY_PATH}")
    print(f"Outer codes: {ALL_OUTER_VALS}, Inner codes: {ALL_INNER_VALS}")

    acc = accumulate_statistics()
    df = build_table(acc)
    summary = summarize(df)

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig", float_format="%.6f")
    df.to_excel(OUT_XLSX, index=False)
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig", float_format="%.3f")
    plot_result(df, summary)

    print("\nFinished.")
    print(f"Table CSV: {OUT_CSV}")
    print(f"Table XLSX: {OUT_XLSX}")
    print(f"Summary: {OUT_SUMMARY}")
    print(f"Figure: {OUT_FIG}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
