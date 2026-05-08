# @Author  : ChaoQiezi
# @Time    : 2026/5/7
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_buffer_valley_threshold.py

"""
This script is used to 在4km河道buffer内的3km VAI上做迎背风海拔阈值分析

输入: VAI_3km_buffer.tif (由 VAI_buffer_valley_3km.py 生成)
输出: 与 VAI_strict_valley_threshold.py 同结构, 文件名后缀 _buffer
绘图: panel D 叠加金沙江中心线 (而非干热河谷polygon边界)
"""

import math
import os
import time
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
import shapefile
from matplotlib.colors import TwoSlopeNorm
from pyproj import CRS, Transformer
from rasterio.transform import xy
from scipy.spatial import cKDTree
from statsmodels.nonparametric.smoothers_lowess import lowess

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE = r"E:\GeoProjects\dry_hot_valley"

VAI_PATH = os.path.join(BASE, r"Jinshajiang\VAI\VAI_3km_buffer.tif")
DEM3_PATH = os.path.join(BASE, r"Jinshajiang\VAI\DEM_3km_buffer.tif")
FRAC_PATH = os.path.join(BASE, r"Jinshajiang\VAI\valley_fraction_3km_buffer.tif")
PVAL_PATH = os.path.join(BASE, r"Jinshajiang\VAI\VAI_pvalue_3km_buffer.tif")
DEM10_PATH = os.path.join(BASE, r"Jinshajiang\geo_factor\elevation_10m_projected_region.tif")
CENTERLINE_PATH = os.path.join(BASE, r"valley_area\river_net\centerline_final.shp")

OUT_TABLE_DIR = os.path.join(BASE, r"Jinshajiang\Result\Table\altitude")
OUT_CHART_DIR = os.path.join(BASE, r"Jinshajiang\Result\Chart\altitude")
os.makedirs(OUT_TABLE_DIR, exist_ok=True)
os.makedirs(OUT_CHART_DIR, exist_ok=True)

OUT_CELLS = os.path.join(OUT_TABLE_DIR, "VAI_buffer_cells.csv")
OUT_ABS_GRAD = os.path.join(OUT_TABLE_DIR, "VAI_buffer_abs_gradient.csv")
OUT_REL_GRAD = os.path.join(OUT_TABLE_DIR, "VAI_buffer_rel_gradient.csv")
OUT_THRESH = os.path.join(OUT_TABLE_DIR, "VAI_buffer_threshold_summary.csv")
OUT_FIG = os.path.join(OUT_CHART_DIR, "VAI_buffer_threshold.png")

JINSHAJIANG_NAME = "金沙江干旱河谷"
VALLEY_LABEL = "金沙江"
BUFFER_KM = 4.0  # 与 VAI_buffer_valley_3km.py 一致, 仅用于标题文案

# 网格筛选
VALLEY_FRACTION_MIN = 0.10

# 河道处理
CENTERLINE_SAMPLE_STEP_M = 100
SEGMENT_LENGTH_M = 30000

# 分箱
ABS_BIN_M = 100
REL_BIN_M = 100
MIN_BIN_COUNT = 10

LOWESS_FRAC = 0.35

N_BOOT = 500
RNG_SEED = 20260507

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
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
# 1. Geometry & loading
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
        dx, dy = x1 - x0, y1 - y0
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


def get_centerline_crs():
    prj_path = Path(CENTERLINE_PATH).with_suffix(".prj")
    return CRS.from_wkt(prj_path.read_text(errors="ignore"))


def load_centerline_in_raster_crs():
    """读取 Jinshajiang 中心线并投影到栅格 CRS, 加密 + 采样 10m DEM."""
    with rio.open(VAI_PATH) as src:
        dst_crs = CRS.from_user_input(src.crs)
    src_crs = get_centerline_crs()
    same_crs = src_crs == dst_crs
    if not same_crs:
        transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    records = []
    parts_for_plot = []
    reader = shapefile.Reader(str(CENTERLINE_PATH))
    feature_index = 0
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec.get("Name") != JINSHAJIANG_NAME:
            continue
        feature_index += 1
        target_fid = int(rec.get("TARGET_FID"))
        for pts in iter_parts(sr.shape):
            xs_raw, ys_raw = zip(*pts)
            if same_crs:
                xs, ys = list(xs_raw), list(ys_raw)
            else:
                xs, ys = transformer.transform(xs_raw, ys_raw)
                xs, ys = list(xs), list(ys)
            parts_for_plot.append((np.asarray(xs), np.asarray(ys)))
            for x, y, dist_along in densify_polyline(list(zip(xs, ys))):
                segment_index = int(dist_along // SEGMENT_LENGTH_M)
                records.append({
                    "feature_index": feature_index,
                    "target_fid": target_fid,
                    "x": x,
                    "y": y,
                    "dist_along_feature_m": dist_along,
                    "segment_index": segment_index,
                    "segment_id": f"Jinshajiang_f{feature_index:03d}_s{segment_index:03d}",
                })

    samples = pd.DataFrame(records)
    if samples.empty:
        raise RuntimeError("No Jinshajiang centerline samples found.")

    coords = list(zip(samples["x"], samples["y"]))
    river_dem = []
    with rio.open(DEM10_PATH, "r") as src:
        nodata = src.nodata
        for item in src.sample(coords, masked=False):
            z = float(item[0])
            if not math.isfinite(z) or (nodata is not None and np.isclose(z, nodata)) or z <= 0:
                river_dem.append(np.nan)
            else:
                river_dem.append(z)
    samples["river_dem_m"] = river_dem
    samples = samples.dropna(subset=["river_dem_m"]).reset_index(drop=True)
    return samples, parts_for_plot


def load_buffer_grid(centerline):
    """读取 buffer-valley VAI 3km 栅格, 绑定到最近河道点."""
    with rio.open(VAI_PATH) as src_vai, \
            rio.open(DEM3_PATH) as src_dem, \
            rio.open(FRAC_PATH) as src_frac, \
            rio.open(PVAL_PATH) as src_pval:
        vai = src_vai.read(1).astype(np.float64)
        dem = src_dem.read(1).astype(np.float64)
        frac = src_frac.read(1).astype(np.float64)
        pval = src_pval.read(1).astype(np.float64)
        transform = src_vai.transform

        valid = np.isfinite(vai) & np.isfinite(dem) & (frac >= VALLEY_FRACTION_MIN)
        rows, cols = np.where(valid)
        xs, ys = xy(transform, rows, cols, offset="center")

    grid = pd.DataFrame({
        "row": rows,
        "col": cols,
        "x": np.asarray(xs, dtype=np.float64),
        "y": np.asarray(ys, dtype=np.float64),
        "VAI": vai[valid],
        "DEM_m": dem[valid],
        "buffer_fraction": frac[valid],
        "p_value": pval[valid],
    })

    tree = cKDTree(centerline[["x", "y"]].to_numpy())
    river_dist, idx = tree.query(grid[["x", "y"]].to_numpy(), k=1)
    nearest = centerline.iloc[idx].reset_index(drop=True)

    grid["river_distance_m"] = river_dist
    grid["nearest_river_dem_m"] = nearest["river_dem_m"].to_numpy()
    grid["relative_height_m"] = grid["DEM_m"] - grid["nearest_river_dem_m"]
    grid["segment_id"] = nearest["segment_id"].to_numpy()
    return grid


# ============================================================
# 2. Binning, LOWESS, threshold
# ============================================================
def bin_stats(df, axis_col, bin_step):
    values = df[axis_col].to_numpy()
    if len(values) == 0:
        return pd.DataFrame()
    lo = int(np.floor(np.nanmin(values) / bin_step) * bin_step)
    hi = int(np.ceil(np.nanmax(values) / bin_step) * bin_step)
    edges = np.arange(lo, hi + bin_step, bin_step)
    if len(edges) < 2:
        return pd.DataFrame()
    bin_idx = np.clip(np.digitize(values, edges) - 1, 0, len(edges) - 2)

    rows = []
    tmp = df.copy()
    tmp["bin_idx"] = bin_idx
    for idx, group in tmp.groupby("bin_idx", sort=True):
        rows.append({
            "bin_lo": edges[idx],
            "bin_hi": edges[idx + 1],
            "bin_center": (edges[idx] + edges[idx + 1]) / 2,
            "vai_mean": group["VAI"].mean(),
            "vai_median": group["VAI"].median(),
            "vai_std": group["VAI"].std(ddof=1) if len(group) > 1 else np.nan,
            "vai_p25": group["VAI"].quantile(0.25),
            "vai_p75": group["VAI"].quantile(0.75),
            "pct_gt0": (group["VAI"] > 0).mean() * 100,
            "count": len(group),
        })
    return pd.DataFrame(rows)


def lowess_cells(df, x_col, x_min=None, x_max=None, frac=LOWESS_FRAC):
    valid = np.isfinite(df[x_col]) & np.isfinite(df["VAI"])
    if x_min is not None:
        valid &= df[x_col] >= x_min
    if x_max is not None:
        valid &= df[x_col] <= x_max
    work = df.loc[valid]
    if len(work) < 4:
        return np.array([]), np.array([])
    eff_frac = min(1.0, max(frac, 4.0 / len(work)))
    smoothed = lowess(
        work["VAI"].to_numpy(),
        work[x_col].to_numpy(),
        frac=eff_frac,
        return_sorted=True,
    )
    return smoothed[:, 0], smoothed[:, 1]


def first_pos2neg_crossing(x, y):
    if len(x) < 2:
        return np.nan
    for i in range(len(x) - 1):
        y0, y1 = y[i], y[i + 1]
        if y0 == 0 and i > 0 and y[i - 1] > 0:
            return x[i]
        if y0 > 0 and y1 < 0:
            return x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0)
    return np.nan


def bootstrap_threshold(df, axis_col, x_min=None, x_max=None,
                        n_boot=N_BOOT, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    n = len(df)
    if n < 50:
        return np.nan, np.nan, np.nan, 0
    crossings = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample = df.iloc[idx]
        xs, ys = lowess_cells(sample, axis_col, x_min=x_min, x_max=x_max)
        z = first_pos2neg_crossing(xs, ys)
        if np.isfinite(z):
            crossings.append(z)
    if len(crossings) == 0:
        return np.nan, np.nan, np.nan, 0
    arr = np.asarray(crossings)
    return (
        float(np.median(arr)),
        float(np.percentile(arr, 2.5)),
        float(np.percentile(arr, 97.5)),
        len(crossings),
    )


# ============================================================
# 3. Plot
# ============================================================
def plot_threshold(grid, abs_bin, rel_bin, summary, centerline_parts):
    fig = plt.figure(figsize=(11.5, 8.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1],
                           wspace=0.26, hspace=0.32)
    ax_abs = fig.add_subplot(gs[0, 0])
    ax_rel = fig.add_subplot(gs[0, 1])
    ax_count = fig.add_subplot(gs[1, 0])
    ax_map = fig.add_subplot(gs[1, 1])

    # --- (a) VAI vs absolute elevation
    ax_abs.scatter(
        grid["DEM_m"], grid["VAI"],
        s=10, c="#BBBBBB", alpha=0.45, edgecolor="none",
        label=f"网格 (n={len(grid)})",
    )
    ax_abs.scatter(
        abs_bin["bin_center"], abs_bin["vai_mean"],
        s=np.clip(abs_bin["count"] * 2, 14, 100),
        c="#444444", alpha=0.7, edgecolor="white", linewidth=0.5,
        label="100m 分箱均值",
    )
    xs, ys = lowess_cells(grid, "DEM_m")
    if len(xs):
        ax_abs.plot(xs, ys, color="#B2182B", lw=2.0, label="cell-level LOWESS")
    abs_z = summary["abs_crossing_median"].iloc[0]
    abs_lo = summary["abs_crossing_lo95"].iloc[0]
    abs_hi = summary["abs_crossing_hi95"].iloc[0]
    if np.isfinite(abs_z):
        ax_abs.axvspan(abs_lo, abs_hi, color="#B2182B", alpha=0.14, label="95% CI")
        ax_abs.axvline(abs_z, color="#B2182B", lw=1.2, ls="--",
                       label=f"反转 {abs_z:.0f} m")
    ax_abs.axhline(0, color="#222222", lw=0.8, ls=":")
    ax_abs.set_xlabel("绝对海拔 (m)")
    ax_abs.set_ylabel("VAI (%)")
    ax_abs.set_title(f"A. {VALLEY_LABEL} {BUFFER_KM:.0f}km 河道 buffer VAI–海拔反转")
    ax_abs.legend(frameon=False, loc="best", fontsize=8)
    ax_abs.grid(color="#DDDDDD", lw=0.5, alpha=0.7)

    # --- (b) VAI vs relative river height
    rel_grid = grid[grid["relative_height_m"] >= 0]
    ax_rel.scatter(
        rel_grid["relative_height_m"], rel_grid["VAI"],
        s=10, c="#BBBBBB", alpha=0.45, edgecolor="none",
        label=f"网格 (n={len(rel_grid)})",
    )
    ax_rel.scatter(
        rel_bin["bin_center"], rel_bin["vai_mean"],
        s=np.clip(rel_bin["count"] * 2, 14, 100),
        c="#444444", alpha=0.7, edgecolor="white", linewidth=0.5,
        label="100m 分箱均值",
    )
    xs, ys = lowess_cells(rel_grid, "relative_height_m", x_min=0)
    if len(xs):
        ax_rel.plot(xs, ys, color="#1B7837", lw=2.0, label="cell-level LOWESS")
    rel_z = summary["rel_crossing_median"].iloc[0]
    rel_lo = summary["rel_crossing_lo95"].iloc[0]
    rel_hi = summary["rel_crossing_hi95"].iloc[0]
    if np.isfinite(rel_z):
        ax_rel.axvspan(rel_lo, rel_hi, color="#1B7837", alpha=0.14, label="95% CI")
        ax_rel.axvline(rel_z, color="#1B7837", lw=1.2, ls="--",
                       label=f"反转 {rel_z:.0f} m")
    ax_rel.axhline(0, color="#222222", lw=0.8, ls=":")
    ax_rel.set_xlabel("相对河道高差 (m)")
    ax_rel.set_ylabel("VAI (%)")
    ax_rel.set_title(f"B. {VALLEY_LABEL} {BUFFER_KM:.0f}km buffer VAI–相对河道高差反转")
    ax_rel.legend(frameon=False, loc="best", fontsize=8)
    ax_rel.grid(color="#DDDDDD", lw=0.5, alpha=0.7)

    # --- (c) sample count by bin
    ax_count.bar(
        abs_bin["bin_center"], abs_bin["count"], width=ABS_BIN_M * 0.9,
        color="#B2182B", alpha=0.4, label="按绝对海拔",
    )
    ax_count.bar(
        rel_bin["bin_center"], -rel_bin["count"], width=REL_BIN_M * 0.9,
        color="#1B7837", alpha=0.4, label="按相对高差",
    )
    ax_count.axhline(MIN_BIN_COUNT, color="#999999", lw=0.8, ls=":")
    ax_count.axhline(-MIN_BIN_COUNT, color="#999999", lw=0.8, ls=":")
    ax_count.axhline(0, color="#222222", lw=0.7)
    ax_count.set_xlabel("海拔 / 高差 (m)")
    ax_count.set_ylabel("3 km 网格数 (绝对↑ / 相对↓)")
    ax_count.set_title("C. 样本量支撑")
    ax_count.legend(frameon=False, loc="best", fontsize=8)
    ax_count.grid(axis="y", color="#DDDDDD", lw=0.5, alpha=0.7)

    # --- (d) spatial map: imshow raster for filled grid-cell squares
    with rio.open(VAI_PATH) as src:
        vai_raster = src.read(1).astype(np.float64)
        vai_raster[~np.isfinite(vai_raster)] = np.nan
        t = src.transform
        extent_km = [
            t.c / 1000,
            (t.c + t.a * src.width) / 1000,
            (t.f + t.e * src.height) / 1000,
            t.f / 1000,
        ]
    _vlo = float(np.nanpercentile(vai_raster, 2))
    _vhi = float(np.nanpercentile(vai_raster, 98))
    pad_x = (extent_km[1] - extent_km[0]) * 0.02
    pad_y = (extent_km[3] - extent_km[2]) * 0.02
    x_lim = (grid["x"].min() / 1000 - pad_x, grid["x"].max() / 1000 + pad_x)
    y_lim = (grid["y"].min() / 1000 - pad_y, grid["y"].max() / 1000 + pad_y)
    if _vlo >= 0:
        _vlo = -abs(_vhi) * 0.05
    if _vhi <= 0:
        _vhi = abs(_vlo) * 0.05
    norm = TwoSlopeNorm(vcenter=0, vmin=_vlo, vmax=_vhi)
    im = ax_map.imshow(
        vai_raster, cmap="RdBu_r", norm=norm,
        extent=extent_km, aspect="equal", interpolation="none",
    )
    ax_map.set_xlim(*x_lim)
    ax_map.set_ylim(*y_lim)
    ax_map.set_adjustable("datalim")
    for xs_part, ys_part in centerline_parts:
        ax_map.plot(xs_part / 1000, ys_part / 1000,
                    color="#222222", lw=0.7, alpha=0.85)
    ax_map.set_xlabel("UTM 47N X (km)")
    ax_map.set_ylabel("UTM 47N Y (km)")
    ax_map.set_title(f"D. {VALLEY_LABEL} {BUFFER_KM:.0f}km buffer 3 km VAI 空间分布")
    ax_map.grid(color="#EEEEEE", lw=0.4, alpha=0.7)
    cbar = plt.colorbar(im, ax=ax_map, fraction=0.046, pad=0.03)
    cbar.set_label("VAI (%)")

    fig.suptitle(
        f"{VALLEY_LABEL} 河道 {BUFFER_KM:.0f}km buffer 内 3 km VAI 反转阈值",
        fontsize=13, y=0.99,
    )
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 4. Main
# ============================================================
if __name__ == "__main__":
    t_start = time.time()
    print("=" * 72)
    print(f"{VALLEY_LABEL} {BUFFER_KM:.0f}km buffer VAI threshold analysis")
    print("=" * 72)

    centerline, centerline_parts = load_centerline_in_raster_crs()
    print(f"Centerline samples: {len(centerline)}")
    print(
        f"River DEM range: {centerline['river_dem_m'].min():.1f}–"
        f"{centerline['river_dem_m'].max():.1f} m"
    )

    grid = load_buffer_grid(centerline)
    print(f"Buffer-valley 3 km cells (frac>={VALLEY_FRACTION_MIN}): {len(grid)}")
    print(
        f"VAI: median={grid['VAI'].median():.2f}, "
        f"p10={grid['VAI'].quantile(0.10):.2f}, "
        f"p90={grid['VAI'].quantile(0.90):.2f}"
    )
    print(
        f"DEM: {grid['DEM_m'].min():.0f}–{grid['DEM_m'].max():.0f} m, "
        f"relative_height: {grid['relative_height_m'].min():.0f}–"
        f"{grid['relative_height_m'].max():.0f} m"
    )

    grid.to_csv(OUT_CELLS, index=False, encoding="utf-8-sig", float_format="%.4f")

    abs_bin = bin_stats(grid, "DEM_m", ABS_BIN_M)
    rel_bin = bin_stats(grid[grid["relative_height_m"] >= 0],
                        "relative_height_m", REL_BIN_M)

    abs_bin.to_csv(OUT_ABS_GRAD, index=False, encoding="utf-8-sig",
                   float_format="%.3f")
    rel_bin.to_csv(OUT_REL_GRAD, index=False, encoding="utf-8-sig",
                   float_format="%.3f")
    print(f"\nABS bins (count>={MIN_BIN_COUNT}): "
          f"{int((abs_bin['count'] >= MIN_BIN_COUNT).sum())}")
    print(f"REL bins (count>={MIN_BIN_COUNT}): "
          f"{int((rel_bin['count'] >= MIN_BIN_COUNT).sum())}")

    print("\nBootstrapping ABS-axis crossing (cell-level) ...")
    abs_med, abs_lo, abs_hi, abs_n = bootstrap_threshold(grid, "DEM_m")
    print("Bootstrapping REL-axis crossing (cell-level) ...")
    rel_med, rel_lo, rel_hi, rel_n = bootstrap_threshold(
        grid[grid["relative_height_m"] >= 0], "relative_height_m", x_min=0,
    )

    summary = pd.DataFrame([{
        "valley": VALLEY_LABEL,
        "buffer_km": BUFFER_KM,
        "n_cells": len(grid),
        "abs_elev_min_m": float(grid["DEM_m"].min()),
        "abs_elev_max_m": float(grid["DEM_m"].max()),
        "rel_height_min_m": float(grid["relative_height_m"].min()),
        "rel_height_max_m": float(grid["relative_height_m"].max()),
        "abs_crossing_median": abs_med,
        "abs_crossing_lo95": abs_lo,
        "abs_crossing_hi95": abs_hi,
        "abs_n_boot_with_crossing": abs_n,
        "rel_crossing_median": rel_med,
        "rel_crossing_lo95": rel_lo,
        "rel_crossing_hi95": rel_hi,
        "rel_n_boot_with_crossing": rel_n,
        "n_boot": N_BOOT,
        "lowess_frac": LOWESS_FRAC,
        "buffer_fraction_min": VALLEY_FRACTION_MIN,
    }])
    summary.to_csv(OUT_THRESH, index=False, encoding="utf-8-sig",
                   float_format="%.3f")

    plot_threshold(grid, abs_bin, rel_bin, summary, centerline_parts)

    elapsed = time.time() - t_start
    print(f"\nElapsed: {elapsed / 60:.1f} min")
    print("\n=== Threshold summary ===")
    print(
        f"ABS crossing: {abs_med:.0f} m  "
        f"[{abs_lo:.0f}, {abs_hi:.0f}]  "
        f"({abs_n}/{N_BOOT} boots had crossing)"
    )
    print(
        f"REL crossing: {rel_med:.0f} m  "
        f"[{rel_lo:.0f}, {rel_hi:.0f}]  "
        f"({rel_n}/{N_BOOT} boots had crossing)"
    )
    print(f"\nOutputs:\n  {OUT_CELLS}\n  {OUT_ABS_GRAD}\n  {OUT_REL_GRAD}")
    print(f"  {OUT_THRESH}\n  {OUT_FIG}")
