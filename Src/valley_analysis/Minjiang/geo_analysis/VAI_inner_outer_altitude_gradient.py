# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/5
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_inner_outer_altitude_gradient.py

"""
This script is used to test whether the VAI-elevation pattern inside the
dry-hot valley polygon differs from the surrounding valley-neighborhood region.

Working hypothesis:
  - VAI_inner is the windward/leeward vegetation asymmetry inside the dry-hot
    valley polygon.
  - VAI_outer is the background windward/leeward vegetation asymmetry in the
    same rectangular valley-neighborhood window.
  - Delta_VAI = VAI_inner - VAI_outer measures the dry-hot-valley enhancement.
  - The elevation where Delta_VAI approaches or crosses 0 can be treated as a
    candidate elevation threshold for the valley-specific windward/leeward effect.

Only Minjiang is processed here. After the logic is checked, the same script can
be generalized to the other three valleys.
"""

import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
from rasterio.features import rasterize
import shapefile
from pyproj import CRS, Transformer
from statsmodels.nonparametric.smoothers_lowess import lowess

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")
VALLEY = "Minjiang"
VALLEY_CN = "岷江"

VAI_PATH = BASE_DIR / VALLEY / "VAI" / "VAI_3km_region.tif"
DEM3_PATH = BASE_DIR / VALLEY / "VAI" / "DEM_3km_region.tif"
DEM10_PATH = BASE_DIR / VALLEY / "geo_factor" / "elevation_10m_projected_region.tif"
VALLEY_SHP = BASE_DIR / "valley_area" / "西南干旱河谷范围" / "Minjiang_valley.shp"

OUT_DIR = BASE_DIR / VALLEY / "Result" / "Chart" / "altitude"
OUT_TABLE_DIR = BASE_DIR / VALLEY / "Result" / "Table" / "altitude"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(OUT_TABLE_DIR, exist_ok=True)

OUT_FIG = OUT_DIR / "VAI_inner_outer_altitude_gradient.png"
OUT_TABLE = OUT_TABLE_DIR / "VAI_inner_outer_altitude_gradient.csv"
OUT_CELL_TABLE = OUT_TABLE_DIR / "VAI_inner_outer_3km_cells.csv"

GRID_PIXELS = 300
ELEV_STEP = 100
INNER_FRACTION_MIN = 0.25
OUTER_FRACTION_MAX = 0.0
MIN_COUNT_PER_GROUP = 3
LOWESS_FRAC = 0.35

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


# ============================================================
# 1. Polygon rasterization
# ============================================================
def read_projected_polygon(shp_path, dst_crs):
    """Read a polygon shapefile with pyshp and transform it to dst_crs."""
    prj_path = shp_path.with_suffix(".prj")
    src_crs = CRS.from_wkt(prj_path.read_text(errors="ignore"))
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    reader = shapefile.Reader(str(shp_path))
    geoms = []
    for shape in reader.shapes():
        parts = list(shape.parts) + [len(shape.points)]
        rings = []
        for i in range(len(parts) - 1):
            points = shape.points[parts[i]:parts[i + 1]]
            xs, ys = zip(*points)
            x_proj, y_proj = transformer.transform(xs, ys)
            rings.append(list(zip(x_proj, y_proj)))
        geoms.append({"type": "Polygon", "coordinates": rings})
    return geoms


def build_inner_fraction_3km():
    """Rasterize dry-hot valley polygon to 10 m grid and aggregate to 3 km."""
    with rio.open(DEM10_PATH, "r") as dem10, rio.open(VAI_PATH, "r") as vai3:
        geoms = read_projected_polygon(VALLEY_SHP, dem10.crs)
        mask10 = rasterize(
            [(geom, 1) for geom in geoms],
            out_shape=(dem10.height, dem10.width),
            transform=dem10.transform,
            fill=0,
            dtype="uint8",
        )

        n_grid_rows = vai3.height
        n_grid_cols = vai3.width
        mask10 = mask10[:n_grid_rows * GRID_PIXELS, :n_grid_cols * GRID_PIXELS]
        inner_fraction = mask10.reshape(
            n_grid_rows,
            GRID_PIXELS,
            n_grid_cols,
            GRID_PIXELS,
        ).mean(axis=(1, 3))

    return inner_fraction


# ============================================================
# 2. Statistics
# ============================================================
def classify_cells():
    inner_fraction = build_inner_fraction_3km()

    with rio.open(VAI_PATH, "r") as src_vai, rio.open(DEM3_PATH, "r") as src_dem:
        vai = src_vai.read(1).astype(float)
        dem = src_dem.read(1).astype(float)

    valid = np.isfinite(vai) & np.isfinite(dem)
    rows, cols = np.where(valid)
    df = pd.DataFrame({
        "row": rows,
        "col": cols,
        "elevation_m": dem[valid],
        "VAI": vai[valid],
        "inner_fraction": inner_fraction[valid],
    })

    df["zone"] = "mixed"
    df.loc[df["inner_fraction"] >= INNER_FRACTION_MIN, "zone"] = "inner"
    df.loc[df["inner_fraction"] <= OUTER_FRACTION_MAX, "zone"] = "outer"
    df.to_csv(OUT_CELL_TABLE, index=False, encoding="utf-8-sig", float_format="%.4f")
    return df


def summarize_by_elevation(df):
    elev_min = np.floor(df["elevation_m"].min() / ELEV_STEP) * ELEV_STEP
    elev_max = np.ceil(df["elevation_m"].max() / ELEV_STEP) * ELEV_STEP
    bins = np.arange(elev_min, elev_max + ELEV_STEP, ELEV_STEP)

    records = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        row = {
            "elev_lo": lo,
            "elev_hi": hi,
            "elev_center": (lo + hi) / 2,
        }
        for zone in ["inner", "outer"]:
            vals = df[
                (df["zone"] == zone) &
                (df["elevation_m"] >= lo) &
                (df["elevation_m"] < hi)
            ]["VAI"].to_numpy()
            row[f"{zone}_count"] = len(vals)
            row[f"{zone}_mean"] = np.nan if len(vals) == 0 else np.mean(vals)
            row[f"{zone}_median"] = np.nan if len(vals) == 0 else np.median(vals)
            row[f"{zone}_std"] = np.nan if len(vals) <= 1 else np.std(vals, ddof=1)
        row["delta_mean"] = row["inner_mean"] - row["outer_mean"]
        row["delta_median"] = row["inner_median"] - row["outer_median"]
        records.append(row)

    out = pd.DataFrame(records)
    out.to_csv(OUT_TABLE, index=False, encoding="utf-8-sig", float_format="%.3f")
    return out


def smooth_xy(df, y_col):
    valid = (
        np.isfinite(df[y_col]) &
        (df["inner_count"] >= MIN_COUNT_PER_GROUP) &
        (df["outer_count"] >= MIN_COUNT_PER_GROUP)
    )
    x = df.loc[valid, "elev_center"].to_numpy()
    y = df.loc[valid, y_col].to_numpy()
    if len(x) < 4:
        return x, y
    smoothed = lowess(y, x, frac=LOWESS_FRAC, return_sorted=True)
    return smoothed[:, 0], smoothed[:, 1]


def find_zero_crossing(x, y):
    if len(x) < 2:
        return np.nan
    for i in range(len(x) - 1):
        y0, y1 = y[i], y[i + 1]
        if y0 == 0:
            return x[i]
        if y0 * y1 < 0:
            return x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0)
    return np.nan


# ============================================================
# 3. Plot
# ============================================================
def plot_result(summary):
    x_inner, y_inner = smooth_xy(
        summary.rename(columns={"inner_mean": "target"}), "target"
    )
    x_outer, y_outer = smooth_xy(
        summary.rename(columns={"outer_mean": "target"}), "target"
    )
    x_delta, y_delta = smooth_xy(summary, "delta_mean")
    zero_cross = find_zero_crossing(x_delta, y_delta)

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(8.5, 8.0),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.6, 1.0]},
    )

    ax = axes[0]
    valid_inner = summary["inner_count"] >= MIN_COUNT_PER_GROUP
    valid_outer = summary["outer_count"] >= MIN_COUNT_PER_GROUP
    ax.scatter(
        summary.loc[valid_inner, "elev_center"],
        summary.loc[valid_inner, "inner_mean"],
        s=25,
        color="#D95F02",
        alpha=0.55,
        label="河谷内 VAI 均值",
    )
    ax.scatter(
        summary.loc[valid_outer, "elev_center"],
        summary.loc[valid_outer, "outer_mean"],
        s=25,
        color="#1B9E77",
        alpha=0.55,
        label="河谷外 VAI 均值",
    )
    ax.plot(x_inner, y_inner, color="#D95F02", lw=2.0)
    ax.plot(x_outer, y_outer, color="#1B9E77", lw=2.0)
    ax.axhline(0, color="#666666", lw=0.8, ls="--")
    ax.set_ylabel("VAI (%)")
    ax.set_title(f"{VALLEY_CN}: 河谷内/外 VAI 海拔梯度", loc="left", fontsize=12)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.grid(axis="y", color="#D0D0D0", lw=0.5, alpha=0.7)

    ax = axes[1]
    valid_delta = (
        (summary["inner_count"] >= MIN_COUNT_PER_GROUP) &
        (summary["outer_count"] >= MIN_COUNT_PER_GROUP) &
        np.isfinite(summary["delta_mean"])
    )
    ax.bar(
        summary.loc[valid_delta, "elev_center"],
        summary.loc[valid_delta, "delta_mean"],
        width=80,
        color=np.where(summary.loc[valid_delta, "delta_mean"] >= 0, "#7570B3", "#BDBDBD"),
        alpha=0.75,
        label="VAI_inner - VAI_outer",
    )
    ax.plot(x_delta, y_delta, color="#333333", lw=1.8)
    ax.axhline(0, color="#666666", lw=0.8, ls="--")
    if np.isfinite(zero_cross):
        ax.axvline(zero_cross, color="#B2182B", lw=1.0, ls="--")
        ax.text(
            zero_cross,
            ax.get_ylim()[1] * 0.85,
            f"候选阈值 {zero_cross:.0f} m",
            color="#B2182B",
            rotation=90,
            ha="right",
            va="top",
        )
    ax.set_ylabel("ΔVAI (%)")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", color="#D0D0D0", lw=0.5, alpha=0.7)

    ax = axes[2]
    ax.bar(
        summary["elev_center"] - 18,
        summary["inner_count"],
        width=36,
        color="#D95F02",
        alpha=0.65,
        label="河谷内",
    )
    ax.bar(
        summary["elev_center"] + 18,
        summary["outer_count"],
        width=36,
        color="#1B9E77",
        alpha=0.65,
        label="河谷外",
    )
    ax.axhline(MIN_COUNT_PER_GROUP, color="#666666", lw=0.8, ls=":")
    ax.set_ylabel("网格数")
    ax.set_xlabel("高程 (m)")
    ax.legend(frameon=False, ncol=2, loc="upper right")
    ax.grid(axis="y", color="#D0D0D0", lw=0.5, alpha=0.7)

    fig.tight_layout()
    fig.savefig(OUT_FIG)
    plt.close(fig)

    return zero_cross


# ============================================================
# 4. Main
# ============================================================
if __name__ == "__main__":
    cells = classify_cells()
    summary_table = summarize_by_elevation(cells)
    threshold = plot_result(summary_table)

    print("=" * 70)
    print(f"{VALLEY_CN}: inner/outer VAI altitude gradient")
    print("=" * 70)
    print("3 km cell classification:")
    print(cells["zone"].value_counts().to_string())
    print(f"inner fraction threshold: >= {INNER_FRACTION_MIN}")
    print(f"outer fraction threshold: <= {OUTER_FRACTION_MAX}")
    if np.isfinite(threshold):
        print(f"Candidate Delta_VAI zero-crossing threshold: {threshold:.1f} m")
    else:
        print("Candidate Delta_VAI zero-crossing threshold: NA")
    print(f"Table: {OUT_TABLE}")
    print(f"Cell table: {OUT_CELL_TABLE}")
    print(f"Figure: {OUT_FIG}")
