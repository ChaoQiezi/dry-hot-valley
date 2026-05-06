# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/6
# @Email   : chaoqiezi.one@qq.com
# @FileName: VAI_corridor_enhancement_gradient.py

"""
Use near-far river-corridor differencing to isolate the extra VAI enhancement.

The previous river-corridor threshold script finds where VAI itself crosses 0.
That is a windward/leeward sign-reversal threshold, not necessarily the height
where the foehn-related enhancement disappears.

This script asks a narrower question:

    Delta VAI(z) = VAI_near_river(z) - VAI_far_river(z)

where near and far cells are compared within the same elevation bin. The main
scenario uses:

    near river: 0-10 km
    far river : 20-30 km

If Delta VAI decreases to 0, that height is a better candidate for the
"foehn enhancement cessation" threshold than VAI=0 itself.
"""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
BASE_DIR = Path(r"E:\GeoProjects\dry_hot_valley")

IN_CELLS = BASE_DIR / "Result" / "Table" / "altitude" / "VAI_river_corridor_cells.csv"

OUT_TABLE_DIR = BASE_DIR / "Result" / "Table" / "altitude"
OUT_CHART_DIR = BASE_DIR / "Result" / "Chart" / "altitude"
OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
OUT_CHART_DIR.mkdir(parents=True, exist_ok=True)

OUT_BINS = OUT_TABLE_DIR / "VAI_corridor_enhancement_bins.csv"
OUT_SUMMARY = OUT_TABLE_DIR / "VAI_corridor_enhancement_threshold_summary.csv"
OUT_SEGMENT_STRENGTH = OUT_TABLE_DIR / "VAI_corridor_segment_strength_20km.csv"
OUT_FIG = OUT_CHART_DIR / "VAI_corridor_enhancement_gradient.png"

ELEV_BIN_M = 100
REL_BIN_M = 100
MIN_GROUP_COUNT = 10
SEGMENT_MIN_COUNT = 10
SEGMENT_STRENGTH_MAX_DIST_M = 20_000
LOWESS_FRAC = 0.35
BOOTSTRAP_N = 500
RANDOM_SEED = 20260506

MAIN_SCENARIO = "near_0_10_vs_far_20_30"
SCENARIOS = [
    {
        "scenario": "near_0_10_vs_far_20_30",
        "label": "近河道0-10 km - 远河道20-30 km",
        "near_min_m": 0,
        "near_max_m": 10_000,
        "far_min_m": 20_000,
        "far_max_m": 30_000,
    },
    {
        "scenario": "near_0_20_vs_far_20_30",
        "label": "近河道0-20 km - 远河道20-30 km",
        "near_min_m": 0,
        "near_max_m": 20_000,
        "far_min_m": 20_000,
        "far_max_m": 30_000,
    },
]

VALLEY_LABELS = {
    "Daduhe": "大渡河",
    "Minjiang": "岷江",
    "Jinshajiang": "金沙江",
    "Yalongjiang": "雅砻江",
    "Combined": "川西四河谷合并",
}

VALLEY_COLORS = {
    "Daduhe": "#D95F02",
    "Minjiang": "#7570B3",
    "Jinshajiang": "#1B9E77",
    "Yalongjiang": "#E7298A",
    "Combined": "#333333",
}

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
# 1. Helpers
# ============================================================
def load_cells():
    df = pd.read_csv(IN_CELLS)
    required = {
        "VAI", "DEM_m", "relative_height_m",
        "river_distance_m", "valley",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df = df[
        np.isfinite(df["VAI"]) &
        np.isfinite(df["DEM_m"]) &
        np.isfinite(df["relative_height_m"]) &
        np.isfinite(df["river_distance_m"]) &
        (np.abs(df["VAI"]) <= 200) &
        (df["DEM_m"] > 0) &
        (df["relative_height_m"] >= 0) &
        (df["river_distance_m"] <= 30_000)
    ].reset_index(drop=True)
    return df


def add_combined_group(df):
    combined = df.copy()
    combined["valley"] = "Combined"
    return pd.concat([df, combined], ignore_index=True)


def subset_by_distance(df, min_m, max_m):
    return df[
        (df["river_distance_m"] >= min_m) &
        (df["river_distance_m"] < max_m)
    ].copy()


def make_edges(values, bin_m):
    lo = int(np.floor(np.nanmin(values) / bin_m) * bin_m)
    hi = int(np.ceil(np.nanmax(values) / bin_m) * bin_m)
    return np.arange(lo, hi + bin_m, bin_m)


def first_positive_to_nonpositive_crossing(x, y):
    if len(x) < 2:
        return np.nan
    for i in range(len(x) - 1):
        y0 = y[i]
        y1 = y[i + 1]
        if y0 > 0 and y1 <= 0:
            if y1 == y0:
                return x[i + 1]
            return x[i] + (0 - y0) * (x[i + 1] - x[i]) / (y1 - y0)
    return np.nan


def post_peak_positive_to_nonpositive_crossing(x, y):
    if len(x) < 2:
        return np.nan
    peak_idx = int(np.nanargmax(y))
    return first_positive_to_nonpositive_crossing(x[peak_idx:], y[peak_idx:])


def smooth_delta(bin_df):
    ok = (
        np.isfinite(bin_df["delta_vai_mean"]) &
        (bin_df["near_count"] >= MIN_GROUP_COUNT) &
        (bin_df["far_count"] >= MIN_GROUP_COUNT)
    )
    work = bin_df.loc[ok].sort_values("bin_center")
    if len(work) < 4:
        return np.array([]), np.array([])
    frac = min(1.0, max(LOWESS_FRAC, 4 / len(work)))
    smoothed = lowess(
        work["delta_vai_mean"].to_numpy(),
        work["bin_center"].to_numpy(),
        frac=frac,
        return_sorted=True,
    )
    return smoothed[:, 0], smoothed[:, 1]


def bootstrap_delta_ci(near_vals, far_vals, rng):
    if len(near_vals) < 2 or len(far_vals) < 2:
        return np.nan, np.nan

    near_vals = np.asarray(near_vals, dtype=float)
    far_vals = np.asarray(far_vals, dtype=float)
    deltas = np.empty(BOOTSTRAP_N, dtype=float)
    for i in range(BOOTSTRAP_N):
        near_sample = rng.choice(near_vals, size=len(near_vals), replace=True)
        far_sample = rng.choice(far_vals, size=len(far_vals), replace=True)
        deltas[i] = near_sample.mean() - far_sample.mean()
    return np.percentile(deltas, [2.5, 97.5])


def bin_delta_for_axis(df, scenario, valley, axis_name, value_col, bin_m, rng):
    valley_df = df[df["valley"] == valley]
    near = subset_by_distance(
        valley_df, scenario["near_min_m"], scenario["near_max_m"]
    )
    far = subset_by_distance(
        valley_df, scenario["far_min_m"], scenario["far_max_m"]
    )

    if near.empty or far.empty:
        return pd.DataFrame()

    edges = make_edges(
        pd.concat([near[value_col], far[value_col]], ignore_index=True),
        bin_m,
    )
    if len(edges) < 2:
        return pd.DataFrame()

    near_idx = np.clip(np.digitize(near[value_col], edges) - 1, 0, len(edges) - 2)
    far_idx = np.clip(np.digitize(far[value_col], edges) - 1, 0, len(edges) - 2)
    near = near.assign(bin_idx=near_idx)
    far = far.assign(bin_idx=far_idx)

    rows = []
    for i in range(len(edges) - 1):
        near_vals = near.loc[near["bin_idx"] == i, "VAI"].to_numpy()
        far_vals = far.loc[far["bin_idx"] == i, "VAI"].to_numpy()
        near_count = len(near_vals)
        far_count = len(far_vals)
        if near_count == 0 and far_count == 0:
            continue

        near_mean = np.nan if near_count == 0 else near_vals.mean()
        far_mean = np.nan if far_count == 0 else far_vals.mean()
        if near_count >= MIN_GROUP_COUNT and far_count >= MIN_GROUP_COUNT:
            delta_mean = near_mean - far_mean
            ci_low, ci_high = bootstrap_delta_ci(near_vals, far_vals, rng)
        else:
            delta_mean = np.nan
            ci_low, ci_high = np.nan, np.nan

        rows.append({
            "scenario": scenario["scenario"],
            "scenario_label": scenario["label"],
            "valley": valley,
            "valley_label": VALLEY_LABELS.get(valley, valley),
            "axis": axis_name,
            "axis_label": "绝对海拔" if axis_name == "absolute_elevation" else "相对河道高差",
            "bin_lo": edges[i],
            "bin_hi": edges[i + 1],
            "bin_center": (edges[i] + edges[i + 1]) / 2,
            "near_count": near_count,
            "far_count": far_count,
            "near_vai_mean": near_mean,
            "far_vai_mean": far_mean,
            "delta_vai_mean": delta_mean,
            "delta_ci_low": ci_low,
            "delta_ci_high": ci_high,
        })

    return pd.DataFrame(rows)


def summarize_threshold(bin_df):
    rows = []
    group_cols = ["scenario", "scenario_label", "valley", "valley_label", "axis", "axis_label"]

    for keys, group in bin_df.groupby(group_cols, dropna=False):
        group = group.sort_values("bin_center").copy()
        valid = group[
            np.isfinite(group["delta_vai_mean"]) &
            (group["near_count"] >= MIN_GROUP_COUNT) &
            (group["far_count"] >= MIN_GROUP_COUNT)
        ].copy()

        if len(valid):
            x_min = valid["bin_center"].min()
            x_max = valid["bin_center"].max()
            peak_idx = valid["delta_vai_mean"].idxmax()
            peak_x = valid.loc[peak_idx, "bin_center"]
            peak_delta = valid.loc[peak_idx, "delta_vai_mean"]
            significant = valid[valid["delta_ci_low"] > 0]
            last_sig_pos = significant["bin_center"].max() if len(significant) else np.nan
            after_peak = valid[valid["bin_center"] >= peak_x]
            not_sig_after_peak = after_peak[
                (after_peak["delta_ci_low"] <= 0) |
                (after_peak["delta_vai_mean"] <= 0)
            ]
            first_not_sig = (
                not_sig_after_peak["bin_center"].iloc[0]
                if len(not_sig_after_peak) else np.nan
            )
        else:
            x_min = x_max = peak_x = peak_delta = np.nan
            last_sig_pos = first_not_sig = np.nan

        xs, ys = smooth_delta(group)
        lowess_cross = first_positive_to_nonpositive_crossing(xs, ys)
        post_peak_lowess_cross = post_peak_positive_to_nonpositive_crossing(xs, ys)

        row = dict(zip(group_cols, keys))
        row.update({
            "valid_bins": len(valid),
            "x_min_valid": x_min,
            "x_max_valid": x_max,
            "peak_delta_m": peak_x,
            "peak_delta_vai": peak_delta,
            "last_significant_positive_m": last_sig_pos,
            "first_not_significant_after_peak_m": first_not_sig,
            "lowess_zero_crossing_m": lowess_cross,
            "post_peak_lowess_zero_crossing_m": post_peak_lowess_cross,
            "near_total_count": group["near_count"].sum(),
            "far_total_count": group["far_count"].sum(),
        })
        rows.append(row)

    return pd.DataFrame(rows)


def summarize_segment_strength(df):
    required = {
        "segment_id", "VAI", "DEM_m", "relative_height_m",
        "river_distance_m", "valley", "x", "y",
    }
    missing = required - set(df.columns)
    if missing:
        print(f"Skip segment strength summary, missing columns: {sorted(missing)}")
        return pd.DataFrame()

    work = df[
        np.isfinite(df["VAI"]) &
        np.isfinite(df["DEM_m"]) &
        np.isfinite(df["relative_height_m"]) &
        np.isfinite(df["river_distance_m"]) &
        (df["river_distance_m"] <= SEGMENT_STRENGTH_MAX_DIST_M) &
        (df["relative_height_m"] >= 0)
    ].copy()
    work["abs_VAI"] = work["VAI"].abs()

    rows = []
    for segment_id, group in work.groupby("segment_id"):
        if len(group) < SEGMENT_MIN_COUNT:
            continue

        row = {
            "segment_id": segment_id,
            "valley": group["valley"].mode().iloc[0],
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
        }
        for col in ["nearest_feature_index", "segment_index"]:
            if col in group.columns:
                row[col] = int(group[col].mode().iloc[0])
        rows.append(row)

    segment = pd.DataFrame(rows)
    if segment.empty:
        return segment

    q33 = segment["abs_VAI_median"].quantile(1 / 3)
    q67 = segment["abs_VAI_median"].quantile(2 / 3)
    segment["strength_class"] = np.where(
        segment["abs_VAI_median"] >= q67,
        "强",
        np.where(segment["abs_VAI_median"] <= q33, "弱", "中"),
    )
    segment["strength_q33"] = q33
    segment["strength_q67"] = q67

    sort_cols = [
        col for col in ["valley", "nearest_feature_index", "segment_index", "segment_id"]
        if col in segment.columns
    ]
    return segment.sort_values(sort_cols).reset_index(drop=True)


# ============================================================
# 2. Plot
# ============================================================
def plot_results(bin_df, summary_df):
    main = bin_df[bin_df["scenario"] == MAIN_SCENARIO].copy()
    main_summary = summary_df[summary_df["scenario"] == MAIN_SCENARIO].copy()

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.4))
    ax_abs, ax_rel, ax_cmp, ax_thr = axes.ravel()

    axis_cfg = [
        ("absolute_elevation", ax_abs, "A. 近远廊道ΔVAI随绝对海拔变化", "绝对海拔 (m)"),
        ("relative_height", ax_rel, "B. 近远廊道ΔVAI随相对河道高差变化", "相对河道高差 (m)"),
    ]

    for axis_name, ax, title, xlabel in axis_cfg:
        for valley in ["Daduhe", "Minjiang", "Jinshajiang", "Yalongjiang", "Combined"]:
            sub = main[(main["axis"] == axis_name) & (main["valley"] == valley)].copy()
            if sub.empty:
                continue
            valid = np.isfinite(sub["delta_vai_mean"])
            if valid.sum() == 0:
                continue

            color = VALLEY_COLORS[valley]
            lw = 2.4 if valley == "Combined" else 1.4
            alpha = 0.95 if valley == "Combined" else 0.75
            label = VALLEY_LABELS[valley]

            ax.scatter(
                sub.loc[valid, "bin_center"],
                sub.loc[valid, "delta_vai_mean"],
                s=np.clip((sub.loc[valid, "near_count"] + sub.loc[valid, "far_count"]) / 6, 12, 70),
                color=color,
                alpha=0.18,
                linewidth=0,
            )

            xs, ys = smooth_delta(sub)
            if len(xs):
                ax.plot(xs, ys, color=color, lw=lw, alpha=alpha, label=label)

            if valley == "Combined":
                ci_ok = valid & np.isfinite(sub["delta_ci_low"]) & np.isfinite(sub["delta_ci_high"])
                ax.fill_between(
                    sub.loc[ci_ok, "bin_center"].to_numpy(),
                    sub.loc[ci_ok, "delta_ci_low"].to_numpy(),
                    sub.loc[ci_ok, "delta_ci_high"].to_numpy(),
                    color=color,
                    alpha=0.10,
                    linewidth=0,
                )

        ax.axhline(0, color="#222222", lw=0.8, ls=":")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("ΔVAI = 近河道VAI - 远河道VAI (%)")
        ax.set_title(title)
        ax.grid(color="#D9D9D9", lw=0.5, alpha=0.75)
        ax.legend(frameon=False, fontsize=8, loc="best")

    # Combined near/far VAI lines under the main scenario.
    combined = main[
        (main["valley"] == "Combined") &
        (main["axis"] == "absolute_elevation")
    ].copy()
    ok_near = np.isfinite(combined["near_vai_mean"]) & (combined["near_count"] >= MIN_GROUP_COUNT)
    ok_far = np.isfinite(combined["far_vai_mean"]) & (combined["far_count"] >= MIN_GROUP_COUNT)
    ax_cmp.plot(
        combined.loc[ok_near, "bin_center"],
        combined.loc[ok_near, "near_vai_mean"],
        color="#D95F02",
        lw=1.8,
        label="近河道0-10 km",
    )
    ax_cmp.plot(
        combined.loc[ok_far, "bin_center"],
        combined.loc[ok_far, "far_vai_mean"],
        color="#1B9E77",
        lw=1.8,
        ls="--",
        label="远河道20-30 km",
    )
    ax_cmp.axhline(0, color="#222222", lw=0.8, ls=":")
    ax_cmp.set_xlabel("绝对海拔 (m)")
    ax_cmp.set_ylabel("平均VAI (%)")
    ax_cmp.set_title("C. 合并样本近远廊道VAI基线")
    ax_cmp.grid(color="#D9D9D9", lw=0.5, alpha=0.75)
    ax_cmp.legend(frameon=False, fontsize=8)

    # Threshold diagnostic.
    thr = main_summary[
        main_summary["axis"].isin(["absolute_elevation", "relative_height"])
    ].copy()
    thr = thr[thr["valley"].isin(["Daduhe", "Minjiang", "Jinshajiang", "Yalongjiang", "Combined"])]
    thr["plot_label"] = thr["valley_label"] + " - " + thr["axis_label"]
    thr = thr.sort_values(["axis", "valley"])
    ys = np.arange(len(thr))
    colors = thr["valley"].map(VALLEY_COLORS)
    ax_thr.scatter(
        thr["post_peak_lowess_zero_crossing_m"],
        ys,
        c=colors,
        s=42,
        marker="o",
        label="峰值后LOWESS过零",
        zorder=3,
    )
    ax_thr.scatter(
        thr["last_significant_positive_m"],
        ys,
        c=colors,
        s=38,
        marker="^",
        label="最后显著正增强",
        alpha=0.75,
        zorder=3,
    )
    ax_thr.set_yticks(ys)
    ax_thr.set_yticklabels(thr["plot_label"])
    ax_thr.set_xlabel("候选阈值高度 (m)")
    ax_thr.set_title("D. ΔVAI阈值候选")
    ax_thr.grid(axis="x", color="#D9D9D9", lw=0.5, alpha=0.75)
    ax_thr.tick_params(axis="y", labelsize=7)
    ax_thr.legend(frameon=False, fontsize=8, loc="best")

    fig.suptitle("近远河道廊道差分识别迎背风额外增强阈值", fontsize=13, y=0.985)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.08, top=0.93, wspace=0.48, hspace=0.38)
    fig.savefig(OUT_FIG)
    plt.close(fig)


# ============================================================
# 3. Main
# ============================================================
if __name__ == "__main__":
    print("=" * 72)
    print("VAI corridor enhancement gradient")
    print("=" * 72)

    rng = np.random.default_rng(RANDOM_SEED)
    base_cells = load_cells()
    segment_strength = summarize_segment_strength(base_cells)

    cells = add_combined_group(base_cells)
    print(f"Input cells after filters: {len(cells)}")

    tables = []
    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario['label']}")
        for valley in ["Daduhe", "Minjiang", "Jinshajiang", "Yalongjiang", "Combined"]:
            valley_df = cells[cells["valley"] == valley]
            near_n = len(subset_by_distance(
                valley_df, scenario["near_min_m"], scenario["near_max_m"]
            ))
            far_n = len(subset_by_distance(
                valley_df, scenario["far_min_m"], scenario["far_max_m"]
            ))
            print(f"  {VALLEY_LABELS[valley]}: near={near_n}, far={far_n}")

            tables.append(bin_delta_for_axis(
                cells, scenario, valley,
                "absolute_elevation", "DEM_m", ELEV_BIN_M, rng,
            ))
            tables.append(bin_delta_for_axis(
                cells, scenario, valley,
                "relative_height", "relative_height_m", REL_BIN_M, rng,
            ))

    bins = pd.concat([t for t in tables if len(t)], ignore_index=True)
    summary = summarize_threshold(bins)

    bins.to_csv(OUT_BINS, index=False, encoding="utf-8-sig", float_format="%.3f")
    summary.to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig", float_format="%.3f")
    segment_strength.to_csv(
        OUT_SEGMENT_STRENGTH, index=False, encoding="utf-8-sig", float_format="%.3f"
    )
    plot_results(bins, summary)

    print("\nMain scenario summary:")
    show = summary[summary["scenario"] == MAIN_SCENARIO].copy()
    show = show[[
        "valley_label", "axis_label", "valid_bins",
        "x_min_valid", "x_max_valid", "peak_delta_vai",
        "last_significant_positive_m",
        "first_not_significant_after_peak_m",
        "lowess_zero_crossing_m",
        "post_peak_lowess_zero_crossing_m",
    ]]
    print(show.to_string(index=False))

    if len(segment_strength):
        print("\nSegment strength class counts:")
        print(pd.crosstab(
            segment_strength["valley"],
            segment_strength["strength_class"],
        ).to_string())

    print("\nOutputs:")
    for path in [OUT_BINS, OUT_SUMMARY, OUT_SEGMENT_STRENGTH, OUT_FIG]:
        print(f"  {path}")
