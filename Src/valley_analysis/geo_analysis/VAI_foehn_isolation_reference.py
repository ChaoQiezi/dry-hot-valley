# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/6
# @Email   : chaoqiezi.one@qq.com
# @FileName: VAI_foehn_isolation_reference.py

"""
Isolate foehn enhancement by comparing valley-interior VAI with
reference-area VAI at the same absolute elevation.

Approach
--------
For each 3 km VAI grid cell over the full study area:
  1. Compute distance from cell centre to the nearest dry-hot-valley
     polygon (MSDC 包维楷 boundary).
  2. Classify:
       - "valley"   : cell centre INSIDE any valley polygon
       - "reference" : cell centre > REFERENCE_MIN_DIST km from ALL polygons
       - excluded    : transition zone in between
  3. Compare VAI ~ elevation curves for valley vs. reference.
  4. foehn_enhancement(z) = VAI_valley(z) − VAI_reference(z).
  5. The elevation where enhancement crosses zero → foehn cessation altitude.

Input
-----
  VAI_3km.tif          full study-area VAI  (3 km, EPSG:32647)
  DEM_3km.tif          full study-area DEM  (3 km, EPSG:32647)
  *_valley.shp ×4      dry-hot-valley polygon boundaries

Output
------
  CSV  VAI_foehn_isolation_reference.csv      binned statistics
  CSV  VAI_foehn_isolation_cells.csv          per-cell classification
  CSV  VAI_foehn_isolation_summary.csv        threshold summary
  PNG  VAI_foehn_isolation_reference.png      4-panel diagnostic figure
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio as rio
from rasterio.transform import xy
from shapely.ops import unary_union
from shapely.validation import make_valid
from statsmodels.nonparametric.smoothers_lowess import lowess as sm_lowess
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")

VAI_PATH = BASE_DIR / "VAI" / "VAI_3km.tif"
DEM_PATH = BASE_DIR / "VAI" / "DEM_3km.tif"
VALLEY_SHP_DIR = BASE_DIR / "valley_area" / "西南干旱河谷范围"

VALLEY_FILES = {
    "大渡河": "Daduhe_valley.shp",
    "岷江": "Minjiang_valley.shp",
    "金沙江": "Jinshajiang_valley.shp",
    "雅砻江": "Yalongjiang_valley.shp",
}

OUT_TABLE_DIR = BASE_DIR / "Result" / "Table" / "altitude"
OUT_CHART_DIR = BASE_DIR / "Result" / "Chart" / "altitude"
OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
OUT_CHART_DIR.mkdir(parents=True, exist_ok=True)

OUT_TABLE = OUT_TABLE_DIR / "VAI_foehn_isolation_reference.csv"
OUT_CELLS = OUT_TABLE_DIR / "VAI_foehn_isolation_cells.csv"
OUT_SUMMARY = OUT_TABLE_DIR / "VAI_foehn_isolation_summary.csv"
OUT_FIG = OUT_CHART_DIR / "VAI_foehn_isolation_reference.png"

TARGET_CRS = "EPSG:32647"
ELEV_BIN_M = 100
MIN_BIN_COUNT = 20
LOWESS_FRAC = 0.35
REFERENCE_MIN_DIST_M = 20_000   # >20 km → reference
EXCLUDE_BUFFER_M = 5_000        # 0-5 km → excluded (transition)

VALLEY_COLORS = {
    "大渡河": "#D95F02",
    "岷江": "#7570B3",
    "金沙江": "#1B9E77",
    "雅砻江": "#E7298A",
}

PER_VALLEY_BIN_M = 200          # coarser bins for per-valley curves
PER_VALLEY_MIN_COUNT = 10       # relaxed for per-valley

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "SimSun", "Arial"],
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
def load_grid():
    """Read full-extent VAI and DEM 3 km grids."""
    with rio.open(VAI_PATH) as src_vai, rio.open(DEM_PATH) as src_dem:
        vai = src_vai.read(1).astype(np.float64)
        dem = src_dem.read(1).astype(np.float64)
        valid = (
            np.isfinite(vai) & np.isfinite(dem)
            & (dem > 0) & (np.abs(vai) <= 200)
        )
        rows, cols = np.where(valid)
        xs, ys = xy(src_vai.transform, rows, cols, offset="center")

    return pd.DataFrame({
        "x": np.asarray(xs, dtype=np.float64),
        "y": np.asarray(ys, dtype=np.float64),
        "VAI": vai[valid],
        "DEM_m": dem[valid],
    })


def load_valley_polygons():
    """Read four valley shapefiles, reproject to UTM 47N, return merged GDF."""
    parts = []
    for name, fname in VALLEY_FILES.items():
        gdf = gpd.read_file(VALLEY_SHP_DIR / fname)
        if gdf.crs is None or gdf.crs.to_epsg() != 32647:
            gdf = gdf.to_crs(TARGET_CRS)
        gdf["valley_name"] = name
        parts.append(gdf)
    return pd.concat(parts, ignore_index=True)


# ============================================================
# 2. Classification
# ============================================================
def classify_cells(grid, valley_gdf):
    """Tag each cell as valley / reference / excluded."""
    valley_gdf = valley_gdf.copy()
    valley_gdf["geometry"] = valley_gdf["geometry"].apply(make_valid)
    merged_geom = unary_union(valley_gdf.geometry)
    pts = gpd.GeoSeries(
        gpd.points_from_xy(grid["x"], grid["y"]),
        crs=TARGET_CRS,
    )

    inside = pts.within(merged_geom)
    dist = pts.distance(merged_geom)
    dist[inside] = 0.0

    grid = grid.copy()
    grid["dist_to_valley_m"] = dist.values
    grid["inside_valley"] = inside.values

    grid["cell_class"] = "excluded"
    grid.loc[inside, "cell_class"] = "valley"
    grid.loc[
        (~inside) & (dist.values > REFERENCE_MIN_DIST_M), "cell_class"
    ] = "reference"

    # tag specific valley for cells inside polygons
    grid["valley_name"] = ""
    if inside.any():
        idx_inside = grid.index[inside]
        pts_inside = gpd.GeoDataFrame(
            grid.loc[idx_inside, ["x", "y"]],
            geometry=gpd.points_from_xy(
                grid.loc[idx_inside, "x"], grid.loc[idx_inside, "y"]
            ),
            crs=TARGET_CRS,
        )
        joined = gpd.sjoin(
            pts_inside, valley_gdf[["geometry", "valley_name"]],
            how="left", predicate="within",
        )
        # drop duplicate joins (shouldn't happen with non-overlapping polygons)
        joined = joined[~joined.index.duplicated(keep="first")]
        # column name depends on whether left also has 'valley_name'
        vn_col = ("valley_name_right" if "valley_name_right" in joined.columns
                  else "valley_name")
        grid.loc[idx_inside, "valley_name"] = joined[vn_col].values

    return grid


# ============================================================
# 3. Binning helpers
# ============================================================
def binned_stats(df, class_label):
    """VAI stats per elevation bin."""
    vals = df["DEM_m"].values
    lo = int(np.floor(vals.min() / ELEV_BIN_M) * ELEV_BIN_M)
    hi = int(np.ceil(vals.max() / ELEV_BIN_M) * ELEV_BIN_M)
    edges = np.arange(lo, hi + ELEV_BIN_M, ELEV_BIN_M)
    if len(edges) < 2:
        return pd.DataFrame()

    idx = np.clip(np.digitize(vals, edges) - 1, 0, len(edges) - 2)
    rows = []
    for i in range(len(edges) - 1):
        m = idx == i
        cnt = int(m.sum())
        vai = df.loc[m, "VAI"].values if cnt else np.array([])
        rows.append({
            "class": class_label,
            "bin_lo": edges[i],
            "bin_hi": edges[i + 1],
            "bin_center": (edges[i] + edges[i + 1]) / 2,
            "vai_mean": float(np.mean(vai)) if cnt else np.nan,
            "vai_median": float(np.median(vai)) if cnt else np.nan,
            "vai_std": float(np.std(vai)) if cnt else np.nan,
            "pct_gt0": float((vai > 0).mean() * 100) if cnt else np.nan,
            "count": cnt,
        })
    return pd.DataFrame(rows)


def binned_stats_flex(df, class_label, bin_m):
    """VAI stats per elevation bin with configurable bin size."""
    vals = df["DEM_m"].values
    lo = int(np.floor(vals.min() / bin_m) * bin_m)
    hi = int(np.ceil(vals.max() / bin_m) * bin_m)
    edges = np.arange(lo, hi + bin_m, bin_m)
    if len(edges) < 2:
        return pd.DataFrame()
    idx = np.clip(np.digitize(vals, edges) - 1, 0, len(edges) - 2)
    rows = []
    for i in range(len(edges) - 1):
        m = idx == i
        cnt = int(m.sum())
        vai = df.loc[m, "VAI"].values if cnt else np.array([])
        rows.append({
            "class": class_label,
            "bin_lo": edges[i], "bin_hi": edges[i + 1],
            "bin_center": (edges[i] + edges[i + 1]) / 2,
            "vai_mean": float(np.mean(vai)) if cnt else np.nan,
            "vai_median": float(np.median(vai)) if cnt else np.nan,
            "vai_std": float(np.std(vai)) if cnt else np.nan,
            "pct_gt0": float((vai > 0).mean() * 100) if cnt else np.nan,
            "count": cnt,
        })
    return pd.DataFrame(rows)


def lowess_smooth(df, min_count=MIN_BIN_COUNT, frac=LOWESS_FRAC):
    """Return (x, y) LOWESS of binned VAI means."""
    ok = np.isfinite(df["vai_mean"]) & (df["count"] >= min_count)
    w = df.loc[ok].sort_values("bin_center")
    if len(w) < 4:
        return np.array([]), np.array([])
    f = min(1.0, max(frac, 4 / len(w)))
    s = sm_lowess(w["vai_mean"].values, w["bin_center"].values,
                  frac=f, return_sorted=True)
    return s[:, 0], s[:, 1]


def first_pos_neg_crossing(x, y):
    """First positive → negative zero crossing via linear interpolation."""
    for i in range(len(x) - 1):
        if y[i] > 0 and y[i + 1] < 0:
            return x[i] + (0 - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i])
    return np.nan


# ============================================================
# 4. Plot
# ============================================================
def plot_results(valley_bins, ref_bins, enhancement_df,
                 threshold_combined, per_valley_thresholds, grid,
                 ref_cells):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    ax_vai, ax_enh, ax_pv, ax_cnt = axes.ravel()

    # ---- (a) VAI ~ elevation: valley vs reference ----
    cfg = [
        ("valley", valley_bins, "#D95F02", "河谷内部", "-"),
        ("reference", ref_bins, "#1B9E77", "参照区 (距河谷>20 km)", "--"),
    ]
    for _, bins_df, color, label, ls in cfg:
        ok = bins_df["count"] >= MIN_BIN_COUNT
        ax_vai.scatter(
            bins_df.loc[ok, "bin_center"], bins_df.loc[ok, "vai_mean"],
            s=np.clip(bins_df.loc[ok, "count"] / 5, 6, 50),
            color=color, alpha=0.2, linewidth=0,
        )
        xs, ys = lowess_smooth(bins_df)
        if len(xs):
            ax_vai.plot(xs, ys, color=color, lw=2.0, ls=ls, label=label)

    ax_vai.axhline(0, color="#333", lw=0.7, ls=":")
    ax_vai.set_ylabel("平均 VAI (%)")
    ax_vai.set_title("(a) VAI 随海拔变化：河谷 vs. 参照区")
    ax_vai.legend(frameon=False, fontsize=8)
    ax_vai.grid(color="#E0E0E0", lw=0.4)

    # ---- (b) combined enhancement ----
    if len(enhancement_df):
        xb = enhancement_df["bin_center"].values
        yb = enhancement_df["enhancement"].values
        if len(xb) >= 4:
            f = min(1.0, max(LOWESS_FRAC, 4 / len(xb)))
            s = sm_lowess(yb, xb, frac=f, return_sorted=True)
            xs, ys = s[:, 0], s[:, 1]
        else:
            xs, ys = xb, yb

        ax_enh.fill_between(xs, ys, 0, where=ys >= 0,
                            color="#D95F02", alpha=0.18, label="焚风增强")
        ax_enh.fill_between(xs, ys, 0, where=ys < 0,
                            color="#1B9E77", alpha=0.18, label="参照区偏高")
        ax_enh.plot(xs, ys, color="#333", lw=1.8)
        ax_enh.scatter(xb, yb, s=18, color="#666", alpha=0.45, zorder=5)

        if np.isfinite(threshold_combined):
            ax_enh.axvline(threshold_combined, color="#B2182B", lw=1.4, ls="--")
            ax_enh.text(
                threshold_combined + 60,
                max(ys) * 0.65,
                f"阈值 ≈ {threshold_combined:.0f} m",
                fontsize=9, color="#B2182B", fontweight="bold",
            )

    ax_enh.axhline(0, color="#333", lw=0.7, ls=":")
    ax_enh.set_ylabel("焚风增强量 (%)")
    ax_enh.set_title("(b) 焚风增强 = VAI(河谷) − VAI(参照)")
    ax_enh.grid(color="#E0E0E0", lw=0.4)

    # ---- (c) per-valley enhancement (coarser 200 m bins) ----
    # build coarse reference lookup
    ref_coarse = binned_stats_flex(ref_cells, "ref", PER_VALLEY_BIN_M)
    ref_lk_c = ref_coarse.set_index("bin_center")[["vai_mean", "count"]]

    for vname, color in VALLEY_COLORS.items():
        vc = grid[(grid["cell_class"] == "valley") & (grid["valley_name"] == vname)]
        if len(vc) < 20:
            continue
        vb = binned_stats_flex(vc, vname, PER_VALLEY_BIN_M)
        merged = vb[["bin_center", "vai_mean", "count"]].rename(
            columns={"vai_mean": "v_mean", "count": "v_cnt"}
        ).merge(
            ref_lk_c.rename(columns={"vai_mean": "r_mean", "count": "r_cnt"}),
            left_on="bin_center", right_index=True, how="inner",
        )
        ok = ((merged["v_cnt"] >= PER_VALLEY_MIN_COUNT)
              & (merged["r_cnt"] >= PER_VALLEY_MIN_COUNT))
        merged = merged.loc[ok].sort_values("bin_center")
        if len(merged) < 3:
            continue

        enh_vals = merged["v_mean"].values - merged["r_mean"].values
        xc = merged["bin_center"].values
        if len(xc) >= 4:
            f = min(1.0, max(0.45, 4 / len(xc)))
            s = sm_lowess(enh_vals, xc, frac=f, return_sorted=True)
            ax_pv.plot(s[:, 0], s[:, 1], color=color, lw=1.6, label=vname)
        else:
            ax_pv.plot(xc, enh_vals, color=color, lw=1.6, marker="o",
                       ms=4, label=vname)

        t = per_valley_thresholds.get(vname, np.nan)
        if np.isfinite(t):
            ax_pv.axvline(t, color=color, lw=0.9, ls=":", alpha=0.7)

    ax_pv.axhline(0, color="#333", lw=0.7, ls=":")
    ax_pv.set_xlabel("绝对海拔 (m)")
    ax_pv.set_ylabel("焚风增强量 (%)")
    ax_pv.set_title("(c) 分河谷焚风增强")
    ax_pv.legend(frameon=False, fontsize=8)
    ax_pv.grid(color="#E0E0E0", lw=0.4)

    # ---- (d) sample count ----
    ok_v = valley_bins["count"] >= MIN_BIN_COUNT
    ok_r = ref_bins["count"] >= MIN_BIN_COUNT
    w = ELEV_BIN_M * 0.4
    ax_cnt.bar(valley_bins.loc[ok_v, "bin_center"] - w / 2,
               valley_bins.loc[ok_v, "count"], width=w,
               color="#D95F02", alpha=0.55, label="河谷内部")
    ax_cnt.bar(ref_bins.loc[ok_r, "bin_center"] + w / 2,
               ref_bins.loc[ok_r, "count"], width=w,
               color="#1B9E77", alpha=0.55, label="参照区")
    ax_cnt.axhline(MIN_BIN_COUNT, color="#B2182B", lw=0.8, ls="--", alpha=0.6)
    ax_cnt.set_xlabel("绝对海拔 (m)")
    ax_cnt.set_ylabel("3 km 网格数")
    ax_cnt.set_title("(d) 各海拔段样本量")
    ax_cnt.legend(frameon=False, fontsize=8)
    ax_cnt.grid(color="#E0E0E0", lw=0.4)

    fig.tight_layout(w_pad=2.0, h_pad=2.0)
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 5. Main
# ============================================================
if __name__ == "__main__":
    print("=" * 64)
    print("Foehn isolation: valley vs. reference-area VAI comparison")
    print("=" * 64)

    # ---- load ----
    grid = load_grid()
    print(f"Valid 3 km cells: {len(grid)}")
    print(f"Elevation range : {grid['DEM_m'].min():.0f}–{grid['DEM_m'].max():.0f} m")

    valley_gdf = load_valley_polygons()
    print(f"Valley polygons : {len(valley_gdf)} features across "
          f"{valley_gdf['valley_name'].nunique()} valleys")

    # ---- classify ----
    grid = classify_cells(grid, valley_gdf)
    for cls in ["valley", "reference", "excluded"]:
        sub = grid[grid["cell_class"] == cls]
        n = len(sub)
        if n:
            print(f"  {cls:10s}: {n:>6,} cells,  "
                  f"elev {sub['DEM_m'].min():.0f}–{sub['DEM_m'].max():.0f} m")
        else:
            print(f"  {cls:10s}: {n:>6,} cells")

    for vn in VALLEY_COLORS:
        n = ((grid["cell_class"] == "valley") & (grid["valley_name"] == vn)).sum()
        print(f"    {vn}: {n} cells")

    grid.to_csv(OUT_CELLS, index=False, encoding="utf-8-sig", float_format="%.3f")

    # ---- binning ----
    valley_cells = grid[grid["cell_class"] == "valley"]
    ref_cells = grid[grid["cell_class"] == "reference"]

    valley_bins = binned_stats(valley_cells, "valley")
    ref_bins = binned_stats(ref_cells, "reference")
    all_bins = pd.concat([valley_bins, ref_bins], ignore_index=True)
    all_bins.to_csv(OUT_TABLE, index=False, encoding="utf-8-sig", float_format="%.3f")

    # ---- combined enhancement ----
    v_lk = valley_bins.set_index("bin_center")[["vai_mean", "count"]].rename(
        columns={"vai_mean": "vai_v", "count": "n_v"})
    r_lk = ref_bins.set_index("bin_center")[["vai_mean", "count"]].rename(
        columns={"vai_mean": "vai_r", "count": "n_r"})
    enh = v_lk.join(r_lk, how="inner")
    enh = enh[(enh["n_v"] >= MIN_BIN_COUNT) & (enh["n_r"] >= MIN_BIN_COUNT)].copy()
    enh["enhancement"] = enh["vai_v"] - enh["vai_r"]
    enh = enh.sort_index().reset_index()
    enh.rename(columns={"index": "bin_center"}, inplace=True)

    if len(enh) >= 4:
        f = min(1.0, max(LOWESS_FRAC, 4 / len(enh)))
        s = sm_lowess(enh["enhancement"].values, enh["bin_center"].values,
                      frac=f, return_sorted=True)
        threshold_combined = first_pos_neg_crossing(s[:, 0], s[:, 1])
    else:
        threshold_combined = np.nan

    # ---- per-valley thresholds (coarser 200 m bins) ----
    per_valley_thresholds = {}
    ref_coarse = binned_stats_flex(ref_cells, "ref", PER_VALLEY_BIN_M)
    ref_lk_c = ref_coarse.set_index("bin_center")[["vai_mean", "count"]]
    for vname in VALLEY_COLORS:
        vc = grid[(grid["cell_class"] == "valley") & (grid["valley_name"] == vname)]
        if len(vc) < 20:
            per_valley_thresholds[vname] = np.nan
            continue
        vb = binned_stats_flex(vc, vname, PER_VALLEY_BIN_M)
        mg = vb[["bin_center", "vai_mean", "count"]].rename(
            columns={"vai_mean": "v_mean", "count": "v_cnt"}
        ).merge(
            ref_lk_c.rename(columns={"vai_mean": "r_mean", "count": "r_cnt"}),
            left_on="bin_center", right_index=True, how="inner",
        )
        ok = ((mg["v_cnt"] >= PER_VALLEY_MIN_COUNT)
              & (mg["r_cnt"] >= PER_VALLEY_MIN_COUNT))
        mg = mg.loc[ok].sort_values("bin_center")
        if len(mg) < 3:
            per_valley_thresholds[vname] = np.nan
            continue
        e = mg["v_mean"].values - mg["r_mean"].values
        xc = mg["bin_center"].values
        if len(xc) >= 4:
            f2 = min(1.0, max(0.45, 4 / len(xc)))
            s2 = sm_lowess(e, xc, frac=f2, return_sorted=True)
            per_valley_thresholds[vname] = first_pos_neg_crossing(s2[:, 0], s2[:, 1])
        else:
            per_valley_thresholds[vname] = np.nan

    # ---- summary ----
    rows = [{
        "scope": "combined",
        "reference_min_dist_km": REFERENCE_MIN_DIST_M / 1000,
        "n_valley_cells": len(valley_cells),
        "n_reference_cells": len(ref_cells),
        "overlap_bins_count": len(enh),
        "foehn_threshold_m": threshold_combined,
    }]
    for vn, t in per_valley_thresholds.items():
        nv = ((grid["cell_class"] == "valley") & (grid["valley_name"] == vn)).sum()
        rows.append({
            "scope": vn,
            "reference_min_dist_km": REFERENCE_MIN_DIST_M / 1000,
            "n_valley_cells": nv,
            "n_reference_cells": len(ref_cells),
            "overlap_bins_count": np.nan,
            "foehn_threshold_m": t,
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig", float_format="%.1f")

    # ---- report ----
    print(f"\nCombined foehn threshold: {threshold_combined:.0f} m"
          if np.isfinite(threshold_combined) else "\nNo combined threshold found.")
    for vn, t in per_valley_thresholds.items():
        s = f"{t:.0f} m" if np.isfinite(t) else "N/A"
        print(f"  {vn}: {s}")

    # ---- plot ----
    plot_results(valley_bins, ref_bins, enh,
                 threshold_combined, per_valley_thresholds, grid,
                 ref_cells)

    print(f"\nOutputs:")
    for p in [OUT_TABLE, OUT_CELLS, OUT_SUMMARY, OUT_FIG]:
        print(f"  {p}")
