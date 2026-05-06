# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/6
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_threshold_biclass_altitude_explore.py

"""
Exploratory test: classify 3 km grid cells by a VAI threshold, then inspect
their elevation distribution and VAI-elevation curves.

Important methodological note:
  - This does not define dry-hot-valley inner/outer zones.
  - The classes are response-defined classes: strong positive VAI vs the rest.
  - Therefore, the VAI difference between the two classes is diagnostic only
    and cannot be used as independent evidence for a VAI threshold.

Main useful output:
  - where strong positive windward advantage cells (VAI >= 10%) concentrate
    along elevation.
"""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
from statsmodels.nonparametric.smoothers_lowess import lowess

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")
OUT_DIR = BASE_DIR / "Result" / "Chart" / "altitude"
OUT_TABLE_DIR = BASE_DIR / "Result" / "Table" / "altitude"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)

VALLEYS = ["Minjiang", "Daduhe", "Jinshajiang", "Yalongjiang"]
VALLEY_LABELS = {
    "Minjiang": "Minjiang",
    "Daduhe": "Daduhe",
    "Jinshajiang": "Jinshajiang",
    "Yalongjiang": "Yalongjiang",
}
COLORS = {
    "Minjiang": "#1B9E77",
    "Daduhe": "#D95F02",
    "Jinshajiang": "#7570B3",
    "Yalongjiang": "#E7298A",
    "Combined": "#222222",
}

ELEV_STEP = 100
MIN_COUNT_PER_BIN = 30
HIGH_CONF_LOW = 1500
HIGH_CONF_HIGH = 4500
LOWESS_FRAC = 0.35
VAI_STRONG_THRESHOLD = 10.0
SENSITIVITY_THRESHOLDS = [5.0, 10.0, 15.0, 20.0]

OUT_FIG = OUT_DIR / "VAI_threshold_biclass_altitude_explore.png"
OUT_ALT_TABLE = OUT_TABLE_DIR / "VAI_threshold_biclass_altitude_explore.csv"
OUT_THRESHOLD_TABLE = OUT_TABLE_DIR / "VAI_threshold_biclass_threshold_summary.csv"
OUT_SENSITIVITY_TABLE = OUT_TABLE_DIR / "VAI_threshold_biclass_sensitivity.csv"
OUT_CELL_TABLE = OUT_TABLE_DIR / "VAI_threshold_biclass_cells.csv"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Microsoft YaHei", "SimHei"],
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
# 1. Data loading
# ============================================================
def valid_mask(values, nodata):
    mask = np.isfinite(values)
    if nodata is not None and np.isfinite(nodata):
        mask &= ~np.isclose(values, nodata)
    return mask


def load_valley_cells(valley):
    vai_path = BASE_DIR / valley / "VAI" / "VAI_3km_region.tif"
    dem_path = BASE_DIR / valley / "VAI" / "DEM_3km_region.tif"

    with rio.open(vai_path, "r") as src_vai, rio.open(dem_path, "r") as src_dem:
        vai = src_vai.read(1).astype(float)
        dem = src_dem.read(1).astype(float)
        valid = valid_mask(vai, src_vai.nodata) & valid_mask(dem, src_dem.nodata)
        valid &= dem > 0
        rows, cols = np.where(valid)

    df = pd.DataFrame({
        "valley": valley,
        "row": rows,
        "col": cols,
        "elevation_m": dem[valid],
        "VAI": vai[valid],
    })
    df["strong_positive"] = df["VAI"] >= VAI_STRONG_THRESHOLD
    df["class"] = np.where(
        df["strong_positive"],
        f"VAI >= {VAI_STRONG_THRESHOLD:g}%",
        f"VAI < {VAI_STRONG_THRESHOLD:g}%",
    )
    return df


def load_all_cells():
    frames = [load_valley_cells(valley) for valley in VALLEYS]
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(OUT_CELL_TABLE, index=False, encoding="utf-8-sig", float_format="%.4f")
    return out


# ============================================================
# 2. Statistics
# ============================================================
def summarize_elevation(df, group_name):
    elev_min = np.floor(df["elevation_m"].min() / ELEV_STEP) * ELEV_STEP
    elev_max = np.ceil(df["elevation_m"].max() / ELEV_STEP) * ELEV_STEP
    bins = np.arange(elev_min, elev_max + ELEV_STEP, ELEV_STEP)

    records = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        sub = df[(df["elevation_m"] >= lo) & (df["elevation_m"] < hi)]
        if len(sub) < MIN_COUNT_PER_BIN:
            continue

        strong = sub[sub["strong_positive"]]
        other = sub[~sub["strong_positive"]]
        row = {
            "group": group_name,
            "elev_lo": lo,
            "elev_hi": hi,
            "elev_center": (lo + hi) / 2,
            "count": len(sub),
            "VAI_mean": sub["VAI"].mean(),
            "VAI_median": sub["VAI"].median(),
            "VAI_std": sub["VAI"].std(ddof=1),
            "pct_strong_positive": len(strong) / len(sub) * 100,
            "pct_abs_VAI_ge10": (sub["VAI"].abs() >= 10).mean() * 100,
            "strong_count": len(strong),
            "other_count": len(other),
            "strong_VAI_mean": strong["VAI"].mean() if len(strong) else np.nan,
            "other_VAI_mean": other["VAI"].mean() if len(other) else np.nan,
            "strong_VAI_median": strong["VAI"].median() if len(strong) else np.nan,
            "other_VAI_median": other["VAI"].median() if len(other) else np.nan,
        }
        row["delta_mean_constructed"] = row["strong_VAI_mean"] - row["other_VAI_mean"]
        row["delta_median_constructed"] = row["strong_VAI_median"] - row["other_VAI_median"]
        records.append(row)

    return pd.DataFrame(records)


def smooth_series(summary, y_col, frac=LOWESS_FRAC):
    valid = np.isfinite(summary[y_col]) & (summary["count"] >= MIN_COUNT_PER_BIN)
    x = summary.loc[valid, "elev_center"].to_numpy()
    y = summary.loc[valid, y_col].to_numpy()
    if len(x) < 4:
        return np.empty((0, 2))
    return lowess(y, x, frac=frac, return_sorted=True)


def first_downward_crossing(x, y, level):
    for i in range(len(x) - 1):
        y0 = y[i] - level
        y1 = y[i + 1] - level
        if y0 >= 0 and y1 < 0:
            return x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0)
    return np.nan


def all_crossings(x, y, level):
    crossings = []
    for i in range(len(x) - 1):
        y0 = y[i] - level
        y1 = y[i + 1] - level
        if y0 == 0:
            crossings.append(x[i])
        elif y0 * y1 < 0:
            crossings.append(x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0))
    return crossings


def threshold_summary(summary, raw_cells, group_name):
    df = summary[
        (summary["elev_center"] >= HIGH_CONF_LOW) &
        (summary["elev_center"] <= HIGH_CONF_HIGH)
    ].copy()

    sm_pct = smooth_series(df, "pct_strong_positive")
    sm_vai = smooth_series(df, "VAI_median")
    cells = raw_cells.copy()
    strong = cells[cells["strong_positive"]]

    row = {
        "group": group_name,
        "n_cells": len(cells),
        "n_strong_positive": len(strong),
        "pct_strong_positive": len(strong) / len(cells) * 100 if len(cells) else np.nan,
        "VAI_median_all": cells["VAI"].median(),
        "strong_elev_p10_m": strong["elevation_m"].quantile(0.10) if len(strong) else np.nan,
        "strong_elev_median_m": strong["elevation_m"].median() if len(strong) else np.nan,
        "strong_elev_p90_m": strong["elevation_m"].quantile(0.90) if len(strong) else np.nan,
    }

    if len(sm_pct):
        x = sm_pct[:, 0]
        y = sm_pct[:, 1]
        row["pct10_first_downward_crossing_m"] = first_downward_crossing(x, y, 10)
        row["pct20_first_downward_crossing_m"] = first_downward_crossing(x, y, 20)
        row["pct5_first_downward_crossing_m"] = first_downward_crossing(x, y, 5)
        row["pct10_all_crossings_m"] = ";".join(f"{z:.1f}" for z in all_crossings(x, y, 10))
        row["pct_strong_lowess_min"] = np.nanmin(y)
        row["pct_strong_lowess_min_elev_m"] = x[np.nanargmin(y)]
        row["pct_strong_lowess_max"] = np.nanmax(y)
        row["pct_strong_lowess_max_elev_m"] = x[np.nanargmax(y)]
    else:
        row["pct10_first_downward_crossing_m"] = np.nan
        row["pct20_first_downward_crossing_m"] = np.nan
        row["pct5_first_downward_crossing_m"] = np.nan
        row["pct10_all_crossings_m"] = ""
        row["pct_strong_lowess_min"] = np.nan
        row["pct_strong_lowess_min_elev_m"] = np.nan
        row["pct_strong_lowess_max"] = np.nan
        row["pct_strong_lowess_max_elev_m"] = np.nan

    if len(sm_vai):
        x = sm_vai[:, 0]
        y = sm_vai[:, 1]
        row["VAI_median_zero_crossings_m"] = ";".join(f"{z:.1f}" for z in all_crossings(x, y, 0))
    else:
        row["VAI_median_zero_crossings_m"] = ""

    return row


def sensitivity_summary(df):
    records = []
    groups = [("Combined", df)] + [(valley, df[df["valley"] == valley]) for valley in VALLEYS]
    for group_name, group_df in groups:
        for threshold in SENSITIVITY_THRESHOLDS:
            strong = group_df[group_df["VAI"] >= threshold]
            records.append({
                "group": group_name,
                "threshold_pct": threshold,
                "n_cells": len(group_df),
                "n_strong_positive": len(strong),
                "pct_strong_positive": len(strong) / len(group_df) * 100 if len(group_df) else np.nan,
                "strong_elev_p10_m": strong["elevation_m"].quantile(0.10) if len(strong) else np.nan,
                "strong_elev_median_m": strong["elevation_m"].median() if len(strong) else np.nan,
                "strong_elev_p90_m": strong["elevation_m"].quantile(0.90) if len(strong) else np.nan,
            })
    return pd.DataFrame(records)


# ============================================================
# 3. Plot
# ============================================================
def plot_combined(combined_summary, threshold_row):
    high_conf = combined_summary[
        (combined_summary["elev_center"] >= HIGH_CONF_LOW) &
        (combined_summary["elev_center"] <= HIGH_CONF_HIGH)
    ].copy()

    sm_vai = smooth_series(high_conf, "VAI_median")
    sm_pct = smooth_series(high_conf, "pct_strong_positive")
    sm_delta = smooth_series(high_conf, "delta_mean_constructed")

    fig, axes = plt.subplots(
        4, 1, figsize=(8.4, 9.2), sharex=True,
        gridspec_kw={"height_ratios": [1.55, 1.55, 1.45, 1.0]},
    )

    ax = axes[0]
    ax.scatter(
        high_conf["elev_center"], high_conf["VAI_median"],
        s=np.clip(high_conf["count"] / 25, 8, 60),
        color="#4C78A8", alpha=0.45, edgecolor="none", label="100 m bins",
    )
    if len(sm_vai):
        ax.plot(sm_vai[:, 0], sm_vai[:, 1], color="#1F4E79", lw=2.1, label="LOWESS")
    ax.axhline(0, color="#666666", lw=0.8, ls="--")
    ax.set_ylabel("Median VAI (%)")
    ax.set_title("A. Overall VAI-elevation profile")
    ax.legend(frameon=False, loc="upper right")

    ax = axes[1]
    ax.scatter(
        high_conf["elev_center"], high_conf["pct_strong_positive"],
        s=np.clip(high_conf["count"] / 25, 8, 60),
        color="#F58518", alpha=0.45, edgecolor="none", label="100 m bins",
    )
    if len(sm_pct):
        ax.plot(sm_pct[:, 0], sm_pct[:, 1], color="#C95D00", lw=2.1, label="LOWESS")
    for level in [5, 10, 20]:
        ax.axhline(level, color="#999999", lw=0.7, ls=":")
    z10 = threshold_row.get("pct10_first_downward_crossing_m", np.nan)
    if np.isfinite(z10):
        ax.axvline(z10, color="#C95D00", lw=1.1, ls="--")
        ax.text(
            z10 + 35, 0.95 * ax.get_ylim()[1],
            f"10% crossing: {z10:.0f} m",
            color="#8A3F00", va="top", fontsize=8,
        )
    ax.set_ylabel(f"P(VAI >= {VAI_STRONG_THRESHOLD:g}%) (%)")
    ax.set_title("B. Elevation concentration of strong positive VAI cells")
    ax.legend(frameon=False, loc="upper right")

    ax = axes[2]
    valid_strong = high_conf["strong_count"] >= 3
    valid_other = high_conf["other_count"] >= 3
    ax.plot(
        high_conf.loc[valid_strong, "elev_center"],
        high_conf.loc[valid_strong, "strong_VAI_mean"],
        color="#D95F02", lw=1.7, marker="o", ms=3,
        label=f"VAI >= {VAI_STRONG_THRESHOLD:g}% class",
    )
    ax.plot(
        high_conf.loc[valid_other, "elev_center"],
        high_conf.loc[valid_other, "other_VAI_mean"],
        color="#7570B3", lw=1.7, marker="o", ms=3,
        label=f"VAI < {VAI_STRONG_THRESHOLD:g}% class",
    )
    ax.axhline(0, color="#666666", lw=0.8, ls="--")
    ax.set_ylabel("Mean VAI (%)")
    ax.set_title("C. VAI-threshold classes (separated by definition)")
    ax.legend(frameon=False, loc="upper right")

    ax = axes[3]
    valid_delta = np.isfinite(high_conf["delta_mean_constructed"])
    ax.bar(
        high_conf.loc[valid_delta, "elev_center"],
        high_conf.loc[valid_delta, "delta_mean_constructed"],
        width=80, color="#9E9E9E", alpha=0.65, edgecolor="none",
        label="Constructed delta",
    )
    if len(sm_delta):
        ax.plot(sm_delta[:, 0], sm_delta[:, 1], color="#333333", lw=1.6)
    ax.set_ylabel("Delta VAI (%)")
    ax.set_xlabel("Elevation (m)")
    ax.set_title("D. Delta between classes: diagnostic only")
    ax.legend(frameon=False, loc="upper right")

    for ax in axes:
        ax.grid(axis="y", color="#E0E0E0", lw=0.6)
        ax.set_xlim(HIGH_CONF_LOW, HIGH_CONF_HIGH)

    fig.tight_layout()
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 4. Main
# ============================================================
def main():
    cells = load_all_cells()

    altitude_frames = []
    threshold_rows = []
    for group_name, group_df in [("Combined", cells)] + [(v, cells[cells["valley"] == v]) for v in VALLEYS]:
        summary = summarize_elevation(group_df, group_name)
        altitude_frames.append(summary)
        threshold_rows.append(threshold_summary(summary, group_df, group_name))

    altitude_summary = pd.concat(altitude_frames, ignore_index=True)
    threshold_table = pd.DataFrame(threshold_rows)
    sensitivity_table = sensitivity_summary(cells)

    altitude_summary.to_csv(
        OUT_ALT_TABLE, index=False, encoding="utf-8-sig", float_format="%.3f"
    )
    threshold_table.to_csv(
        OUT_THRESHOLD_TABLE, index=False, encoding="utf-8-sig", float_format="%.3f"
    )
    sensitivity_table.to_csv(
        OUT_SENSITIVITY_TABLE, index=False, encoding="utf-8-sig", float_format="%.3f"
    )

    combined_summary = altitude_summary[altitude_summary["group"] == "Combined"].copy()
    combined_threshold = threshold_table[threshold_table["group"] == "Combined"].iloc[0]
    plot_combined(combined_summary, combined_threshold)

    print("Finished VAI-threshold biclass exploratory analysis.")
    print(f"Figure: {OUT_FIG}")
    print(f"Altitude table: {OUT_ALT_TABLE}")
    print(f"Threshold table: {OUT_THRESHOLD_TABLE}")
    print(f"Sensitivity table: {OUT_SENSITIVITY_TABLE}")
    print(f"Cell table: {OUT_CELL_TABLE}")


if __name__ == "__main__":
    main()
