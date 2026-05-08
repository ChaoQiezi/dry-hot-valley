# @Author  : ChaoQiezi
# @Time    : 2026/5/8
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_buffer_valley_threshold_all.py

"""
四条干热河谷 4km 河道 buffer 内 3km VAI 的整体反转海拔阈值分析

将大渡河、金沙江、岷江、雅砻江的 buffer VAI 网格数据合并, 统一分析:
  - 整体 LOWESS 平滑 + bootstrap 阈值检测
  - 分河谷 LOWESS 曲线对比
  - 森林图汇总各河谷及整体反转海拔 (panel D)

输入: 各河谷 VAI_buffer_valley_3km.py 生成的 VAI_3km_buffer.tif 等
输出:
  - Result/Table/altitude/VAI_buffer_cells_all.csv
  - Result/Table/altitude/VAI_buffer_abs_gradient_all.csv
  - Result/Table/altitude/VAI_buffer_rel_gradient_all.csv
  - Result/Table/altitude/VAI_buffer_threshold_summary_all.csv
  - Result/Chart/altitude/VAI_buffer_threshold_all.png
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
CENTERLINE_PATH = os.path.join(BASE, r"valley_area\river_net\centerline_final.shp")

OUT_TABLE_DIR = os.path.join(BASE, r"Result\Table\altitude")
OUT_CHART_DIR = os.path.join(BASE, r"Result\Chart\altitude")
os.makedirs(OUT_TABLE_DIR, exist_ok=True)
os.makedirs(OUT_CHART_DIR, exist_ok=True)

OUT_CELLS = os.path.join(OUT_TABLE_DIR, "VAI_buffer_cells_all.csv")
OUT_ABS_GRAD = os.path.join(OUT_TABLE_DIR, "VAI_buffer_abs_gradient_all.csv")
OUT_REL_GRAD = os.path.join(OUT_TABLE_DIR, "VAI_buffer_rel_gradient_all.csv")
OUT_THRESH = os.path.join(OUT_TABLE_DIR, "VAI_buffer_threshold_summary_all.csv")
OUT_FIG = os.path.join(OUT_CHART_DIR, "VAI_buffer_threshold_all.png")

VALLEY_CONFIGS = [
    {
        "label": "大渡河",
        "name_filter": "大渡河干旱河谷",
        "vai_path": os.path.join(BASE, r"Daduhe\VAI\VAI_3km_buffer.tif"),
        "dem3_path": os.path.join(BASE, r"Daduhe\VAI\DEM_3km_buffer.tif"),
        "frac_path": os.path.join(BASE, r"Daduhe\VAI\valley_fraction_3km_buffer.tif"),
        "pval_path": os.path.join(BASE, r"Daduhe\VAI\VAI_pvalue_3km_buffer.tif"),
        "dem10_path": os.path.join(BASE, r"Daduhe\geo_factor\elevation_10m_projected_region.tif"),
    },
    {
        "label": "金沙江",
        "name_filter": "金沙江干旱河谷",
        "vai_path": os.path.join(BASE, r"Jinshajiang\VAI\VAI_3km_buffer.tif"),
        "dem3_path": os.path.join(BASE, r"Jinshajiang\VAI\DEM_3km_buffer.tif"),
        "frac_path": os.path.join(BASE, r"Jinshajiang\VAI\valley_fraction_3km_buffer.tif"),
        "pval_path": os.path.join(BASE, r"Jinshajiang\VAI\VAI_pvalue_3km_buffer.tif"),
        "dem10_path": os.path.join(BASE, r"Jinshajiang\geo_factor\elevation_10m_projected_region.tif"),
    },
    {
        "label": "岷江",
        "name_filter": "岷江干旱河谷",
        "vai_path": os.path.join(BASE, r"Minjiang\VAI\VAI_3km_buffer.tif"),
        "dem3_path": os.path.join(BASE, r"Minjiang\VAI\DEM_3km_buffer.tif"),
        "frac_path": os.path.join(BASE, r"Minjiang\VAI\valley_fraction_3km_buffer.tif"),
        "pval_path": os.path.join(BASE, r"Minjiang\VAI\VAI_pvalue_3km_buffer.tif"),
        "dem10_path": os.path.join(BASE, r"Minjiang\geo_factor\elevation_10m_projected_region.tif"),
    },
    {
        "label": "雅砻江",
        "name_filter": "雅砻江干旱河谷",
        "vai_path": os.path.join(BASE, r"Yalongjiang\VAI\VAI_3km_buffer.tif"),
        "dem3_path": os.path.join(BASE, r"Yalongjiang\VAI\DEM_3km_buffer.tif"),
        "frac_path": os.path.join(BASE, r"Yalongjiang\VAI\valley_fraction_3km_buffer.tif"),
        "pval_path": os.path.join(BASE, r"Yalongjiang\VAI\VAI_pvalue_3km_buffer.tif"),
        "dem10_path": os.path.join(BASE, r"Yalongjiang\geo_factor\elevation_10m_projected_region.tif"),
    },
]

COLORS = {
    "大渡河": "#D95F02",
    "金沙江": "#7570B3",
    "岷江": "#1B9E77",
    "雅砻江": "#E7298A",
}
VALLEY_ORDER = ["大渡河", "金沙江", "岷江", "雅砻江"]

BUFFER_KM = 4.0

VALLEY_FRACTION_MIN = 0.10
CENTERLINE_SAMPLE_STEP_M = 100
SEGMENT_LENGTH_M = 30000

ABS_BIN_M = 100
REL_BIN_M = 100
MIN_BIN_COUNT = 10

LOWESS_FRAC = 0.35
N_BOOT = 500
RNG_SEED = 20260508

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
# 1. Geometry & loading (parameterized)
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


def get_centerline_crs(centerline_path):
    prj_path = Path(centerline_path).with_suffix(".prj")
    return CRS.from_wkt(prj_path.read_text(errors="ignore"))


def load_centerline(name_filter, vai_path, dem10_path, centerline_path, valley_label):
    """读取指定河谷中心线, 投影到 VAI 栅格 CRS, 加密 + 采样 10m DEM."""
    with rio.open(vai_path) as src:
        dst_crs = CRS.from_user_input(src.crs)
    src_crs = get_centerline_crs(centerline_path)
    same_crs = src_crs == dst_crs
    if not same_crs:
        transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    records = []
    parts_for_plot = []
    reader = shapefile.Reader(str(centerline_path))
    feature_index = 0
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec.get("Name") != name_filter:
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
                abbr = valley_label[:4]
                records.append({
                    "feature_index": feature_index,
                    "target_fid": target_fid,
                    "x": x,
                    "y": y,
                    "dist_along_feature_m": dist_along,
                    "segment_index": segment_index,
                    "segment_id": f"{abbr}_f{feature_index:03d}_s{segment_index:03d}",
                })

    samples = pd.DataFrame(records)
    if samples.empty:
        raise RuntimeError(f"No centerline samples found for {valley_label}.")

    coords = list(zip(samples["x"], samples["y"]))
    river_dem = []
    with rio.open(dem10_path, "r") as src:
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


def load_buffer_grid(vai_path, dem3_path, frac_path, pval_path, centerline):
    """读取 buffer-valley VAI 3km 栅格, 绑定到最近河道点."""
    with rio.open(vai_path) as src_vai, \
            rio.open(dem3_path) as src_dem, \
            rio.open(frac_path) as src_frac, \
            rio.open(pval_path) as src_pval:
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


def load_all_valleys(configs):
    """加载所有河谷的 grid cells 和 centerline parts."""
    all_grids = []
    centerline_parts_all = {}
    for cfg in configs:
        label = cfg["label"]
        print(f"  Loading {label} ...")
        centerline, parts = load_centerline(
            cfg["name_filter"], cfg["vai_path"], cfg["dem10_path"],
            CENTERLINE_PATH, label,
        )
        grid = load_buffer_grid(
            cfg["vai_path"], cfg["dem3_path"], cfg["frac_path"], cfg["pval_path"],
            centerline,
        )
        grid["valley"] = label
        all_grids.append(grid)
        centerline_parts_all[label] = parts
        print(f"    Centerline samples: {len(centerline)}, "
              f"grid cells: {len(grid)}, "
              f"VAI median: {grid['VAI'].median():.2f}")
    combined = pd.concat(all_grids, ignore_index=True)
    return combined, centerline_parts_all


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
def plot_all_valleys(grid, abs_bin, rel_bin, combined_abs, combined_rel,
                     per_valley_results, centerline_parts_all):
    fig = plt.figure(figsize=(13, 9))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1],
                           wspace=0.28, hspace=0.34)
    ax_abs = fig.add_subplot(gs[0, 0])
    ax_rel = fig.add_subplot(gs[0, 1])
    ax_count = fig.add_subplot(gs[1, 0])
    ax_forest = fig.add_subplot(gs[1, 1])

    # --- (a) VAI vs absolute elevation — combined + per-valley LOWESS
    ax_abs.scatter(
        grid["DEM_m"], grid["VAI"],
        s=4, c="#DDDDDD", alpha=0.35, edgecolor="none",
        label=f"网格 (n={len(grid)})",
    )
    for valley in VALLEY_ORDER:
        sub = grid[grid["valley"] == valley]
        if len(sub) < 4:
            continue
        xs, ys = lowess_cells(sub, "DEM_m")
        if len(xs):
            ax_abs.plot(xs, ys, color=COLORS[valley], lw=1.0, alpha=0.55,
                        label=f"{valley} LOWESS")
    xs_c, ys_c = lowess_cells(grid, "DEM_m")
    if len(xs_c):
        ax_abs.plot(xs_c, ys_c, color="#222222", lw=2.2, label="整体 LOWESS")
    abs_med, abs_lo, abs_hi, abs_n = combined_abs
    if np.isfinite(abs_med):
        ax_abs.axvspan(abs_lo, abs_hi, color="#444444", alpha=0.12, label="95% CI (整体)")
        ax_abs.axvline(abs_med, color="#222222", lw=1.4, ls="--",
                       label=f"整体反转 {abs_med:.0f} m")
    ax_abs.axhline(0, color="#222222", lw=0.8, ls=":")
    ax_abs.set_xlabel("绝对海拔 (m)")
    ax_abs.set_ylabel("VAI (%)")
    ax_abs.set_title(f"A. 四河合计 VAI–海拔反转 ({BUFFER_KM:.0f}km buffer)")
    ax_abs.legend(frameon=False, loc="best", fontsize=7)
    ax_abs.grid(color="#DDDDDD", lw=0.5, alpha=0.7)

    # --- (b) VAI vs relative river height — combined + per-valley LOWESS
    rel_grid = grid[grid["relative_height_m"] >= 0]
    ax_rel.scatter(
        rel_grid["relative_height_m"], rel_grid["VAI"],
        s=4, c="#DDDDDD", alpha=0.35, edgecolor="none",
        label=f"网格 (n={len(rel_grid)})",
    )
    for valley in VALLEY_ORDER:
        sub = rel_grid[rel_grid["valley"] == valley]
        if len(sub) < 4:
            continue
        xs, ys = lowess_cells(sub, "relative_height_m", x_min=0)
        if len(xs):
            ax_rel.plot(xs, ys, color=COLORS[valley], lw=1.0, alpha=0.55,
                        label=f"{valley} LOWESS")
    xs_c, ys_c = lowess_cells(rel_grid, "relative_height_m", x_min=0)
    if len(xs_c):
        ax_rel.plot(xs_c, ys_c, color="#222222", lw=2.2, label="整体 LOWESS")
    rel_med, rel_lo, rel_hi, rel_n = combined_rel
    if np.isfinite(rel_med):
        ax_rel.axvspan(rel_lo, rel_hi, color="#444444", alpha=0.12, label="95% CI (整体)")
        ax_rel.axvline(rel_med, color="#222222", lw=1.4, ls="--",
                       label=f"整体反转 {rel_med:.0f} m")
    ax_rel.axhline(0, color="#222222", lw=0.8, ls=":")
    ax_rel.set_xlabel("相对河道高差 (m)")
    ax_rel.set_ylabel("VAI (%)")
    ax_rel.set_title(f"B. 四河合计 VAI–相对高差反转 ({BUFFER_KM:.0f}km buffer)")
    ax_rel.legend(frameon=False, loc="best", fontsize=7)
    ax_rel.grid(color="#DDDDDD", lw=0.5, alpha=0.7)

    # --- (c) sample count by bin (combined)
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
    ax_count.set_title("C. 样本量支撑 (四河合计)")
    ax_count.legend(frameon=False, loc="best", fontsize=8)
    ax_count.grid(axis="y", color="#DDDDDD", lw=0.5, alpha=0.7)

    # --- (d) forest plot: ABS crossing thresholds per valley + combined
    forest_valleys = VALLEY_ORDER + ["整体"]
    y_positions = list(range(len(forest_valleys)))
    for i, valley in enumerate(forest_valleys):
        if valley == "整体":
            med, lo, hi, n_cross = combined_abs
            color = "#222222"
            ms = 9
            lw = 2.0
        else:
            r = per_valley_results[valley]["abs"]
            med, lo, hi, n_cross = r["median"], r["lo95"], r["hi95"], r["n_cross"]
            color = COLORS[valley]
            ms = 7
            lw = 1.2
        if np.isfinite(med):
            ax_forest.errorbar(
                med, i, xerr=[[med - lo], [hi - med]],
                fmt="o", color=color, capsize=3, markersize=ms,
                linewidth=lw, markeredgecolor="white", markeredgewidth=0.5,
            )
            ax_forest.text(
                med, i + 0.28,
                f"{med:.0f} m  ({n_cross}/{N_BOOT})",
                fontsize=7, ha="center", va="bottom", color=color,
            )
        else:
            ax_forest.text(
                0.5, i, f"no crossing ({n_cross}/{N_BOOT})",
                fontsize=7, ha="center", va="center", color="#999999",
            )
    ax_forest.set_yticks(y_positions)
    ax_forest.set_yticklabels(forest_valleys, fontsize=9)
    ax_forest.axvline(x=abs_med, color="#999999", ls=":", lw=0.8, alpha=0.6)
    ax_forest.set_xlabel("反转海拔 (m)")
    ax_forest.set_title("D. 各河谷及整体 bootstrap 反转阈值 (95% CI)")
    ax_forest.grid(axis="x", color="#DDDDDD", lw=0.5, alpha=0.7)

    fig.suptitle(
        f"川西四条干熱河谷 {BUFFER_KM:.0f}km 河道 buffer 内 3 km VAI 反转阈值——整体分析",
        fontsize=14, y=0.995,
    )
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 4. Main
# ============================================================
if __name__ == "__main__":
    t_start = time.time()
    print("=" * 72)
    print(f"Four-valley combined {BUFFER_KM:.0f}km buffer VAI threshold analysis")
    print("=" * 72)

    grid, centerline_parts_all = load_all_valleys(VALLEY_CONFIGS)
    print(f"\nCombined grid cells: {len(grid)}")
    print(f"  VAI: median={grid['VAI'].median():.2f}, "
          f"p10={grid['VAI'].quantile(0.10):.2f}, "
          f"p90={grid['VAI'].quantile(0.90):.2f}")
    print(f"  DEM: {grid['DEM_m'].min():.0f}–{grid['DEM_m'].max():.0f} m")
    print(f"  Relative height: {grid['relative_height_m'].min():.0f}–"
          f"{grid['relative_height_m'].max():.0f} m")

    grid.to_csv(OUT_CELLS, index=False, encoding="utf-8-sig", float_format="%.4f")

    # Combined bin stats
    abs_bin = bin_stats(grid, "DEM_m", ABS_BIN_M)
    rel_bin = bin_stats(grid[grid["relative_height_m"] >= 0],
                        "relative_height_m", REL_BIN_M)
    abs_bin.to_csv(OUT_ABS_GRAD, index=False, encoding="utf-8-sig", float_format="%.3f")
    rel_bin.to_csv(OUT_REL_GRAD, index=False, encoding="utf-8-sig", float_format="%.3f")
    print(f"\nABS bins (count>={MIN_BIN_COUNT}): "
          f"{int((abs_bin['count'] >= MIN_BIN_COUNT).sum())}")
    print(f"REL bins (count>={MIN_BIN_COUNT}): "
          f"{int((rel_bin['count'] >= MIN_BIN_COUNT).sum())}")

    # Combined bootstrap
    print("\nBootstrapping combined ABS-axis crossing (cell-level) ...")
    abs_med, abs_lo, abs_hi, abs_n = bootstrap_threshold(grid, "DEM_m")
    print("Bootstrapping combined REL-axis crossing (cell-level) ...")
    rel_med, rel_lo, rel_hi, rel_n = bootstrap_threshold(
        grid[grid["relative_height_m"] >= 0], "relative_height_m", x_min=0,
    )
    combined_abs = (abs_med, abs_lo, abs_hi, abs_n)
    combined_rel = (rel_med, rel_lo, rel_hi, rel_n)

    # Per-valley bootstrap
    per_valley_results = {}
    for valley in VALLEY_ORDER:
        sub = grid[grid["valley"] == valley]
        print(f"\nPer-valley bootstrap: {valley} (n={len(sub)}) ...")
        abs_m, abs_l, abs_h, abs_nv = bootstrap_threshold(sub, "DEM_m")
        rel_m, rel_l, rel_h, rel_nv = bootstrap_threshold(
            sub[sub["relative_height_m"] >= 0], "relative_height_m", x_min=0,
        )
        per_valley_results[valley] = {
            "abs": {"median": abs_m, "lo95": abs_l, "hi95": abs_h, "n_cross": abs_nv},
            "rel": {"median": rel_m, "lo95": rel_l, "hi95": rel_h, "n_cross": rel_nv},
        }
        print(f"  ABS: {abs_m:.0f} [{abs_l:.0f}, {abs_h:.0f}] ({abs_nv}/{N_BOOT})")
        print(f"  REL: {rel_m:.0f} [{rel_l:.0f}, {rel_h:.0f}] ({rel_nv}/{N_BOOT})")

    # Summary table
    summary_rows = []
    for valley in VALLEY_ORDER:
        sub = grid[grid["valley"] == valley]
        r = per_valley_results[valley]
        summary_rows.append({
            "valley": valley,
            "n_cells": len(sub),
            "abs_elev_min_m": float(sub["DEM_m"].min()),
            "abs_elev_max_m": float(sub["DEM_m"].max()),
            "rel_height_min_m": float(sub["relative_height_m"].min()),
            "rel_height_max_m": float(sub["relative_height_m"].max()),
            "abs_crossing_median": r["abs"]["median"],
            "abs_crossing_lo95": r["abs"]["lo95"],
            "abs_crossing_hi95": r["abs"]["hi95"],
            "abs_n_boot_with_crossing": r["abs"]["n_cross"],
            "rel_crossing_median": r["rel"]["median"],
            "rel_crossing_lo95": r["rel"]["lo95"],
            "rel_crossing_hi95": r["rel"]["hi95"],
            "rel_n_boot_with_crossing": r["rel"]["n_cross"],
        })
    summary_rows.append({
        "valley": "整体",
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
    })
    summary = pd.DataFrame(summary_rows)
    summary["n_boot"] = N_BOOT
    summary["lowess_frac"] = LOWESS_FRAC
    summary["buffer_fraction_min"] = VALLEY_FRACTION_MIN
    summary.to_csv(OUT_THRESH, index=False, encoding="utf-8-sig", float_format="%.3f")

    # Plot
    plot_all_valleys(grid, abs_bin, rel_bin, combined_abs, combined_rel,
                     per_valley_results, centerline_parts_all)

    elapsed = time.time() - t_start
    print(f"\nElapsed: {elapsed / 60:.1f} min")
    print("\n=== Combined threshold summary ===")
    print(f"ABS crossing: {abs_med:.0f} m  [{abs_lo:.0f}, {abs_hi:.0f}]  "
          f"({abs_n}/{N_BOOT} boots had crossing)")
    print(f"REL crossing: {rel_med:.0f} m  [{rel_lo:.0f}, {rel_hi:.0f}]  "
          f"({rel_n}/{N_BOOT} boots had crossing)")
    print(f"\nOutputs:\n  {OUT_CELLS}\n  {OUT_ABS_GRAD}\n  {OUT_REL_GRAD}")
    print(f"  {OUT_THRESH}\n  {OUT_FIG}")
