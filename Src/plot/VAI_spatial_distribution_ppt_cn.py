# -*- coding: utf-8 -*-
# @Author  : ChaoQiezi
# @Time    : 2026/5/8
# @FileName: VAI_spatial_distribution_ppt_cn.py

"""
绘制组会 PPT 使用的 VAI 空间分布图。

输入:
  - E:/GeoProjects/dry_hot_valley/VAI/VAI_3km.tif
  - E:/GeoProjects/dry_hot_valley/valley_area/valley_chuanxi/valley_clip.shp

输出:
  - E:/GeoProjects/dry_hot_valley/Result/Chart/VAI_spatial_distribution_ppt_cn.png
  - E:/GeoProjects/dry_hot_valley/Result/Chart/VAI_spatial_distribution_ppt_cn.pdf
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mticker
import numpy as np
import rasterio as rio


# ============================================================
# 0. 路径与参数
# ============================================================
DATA_ROOT = Path(r"E:\GeoProjects\dry_hot_valley")
VAI_PATH = DATA_ROOT / "VAI" / "VAI_3km.tif"


OUT_DIR = DATA_ROOT / "Result" / "Chart"
OUT_PNG = OUT_DIR / "VAI_spatial_distribution_ppt_cn.png"
OUT_PDF = OUT_DIR / "VAI_spatial_distribution_ppt_cn.pdf"
OUT_MAP_ONLY_PNG = OUT_DIR / "VAI_spatial_distribution_map_only_cn.png"

# 色阶按 1%-99% 附近设置为对称范围，极端值用 extend 表示。
VAI_ABS_LIMIT = 60

VALLEY_COLORS = {
    "岷江": "#1B9E77",
    "大渡河": "#D95F02",
    "金沙江": "#7570B3",
    "雅砻江": "#E7298A",
}

LABEL_POS_KM = {
    "岷江": (940, 3545),
    "大渡河": (792, 3415),
    "金沙江": (650, 3090),
    "雅砻江": (760, 3285),
}


def set_chinese_font() -> str:
    """优先使用项目机器上已有的中文字体，避免中文乱码。"""
    preferred = ["Microsoft YaHei", "Source Han Sans CN", "SimHei", "SimSun"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font_name in preferred:
        if font_name in available:
            plt.rcParams["font.sans-serif"] = [font_name]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return font_name
    plt.rcParams["axes.unicode_minus"] = False
    return "default"


def km_formatter(x: float, pos: int | None = None) -> str:
    return f"{x / 1000:.0f}"


def add_scale_bar(ax, x0: float, y0: float, length_m: float = 100_000) -> None:
    ax.plot([x0, x0 + length_m], [y0, y0], color="#222222", lw=2.6, solid_capstyle="butt")
    tick = 7000
    ax.plot([x0, x0], [y0 - tick / 2, y0 + tick / 2], color="#222222", lw=2.0)
    ax.plot([x0 + length_m, x0 + length_m], [y0 - tick / 2, y0 + tick / 2], color="#222222", lw=2.0)
    ax.text(
        x0 + length_m / 2,
        y0 - 15_000,
        f"{int(length_m / 1000)} km",
        ha="center",
        va="top",
        fontsize=10,
        color="#222222",
    )


def add_north_arrow(ax, x: float, y: float, length_m: float = 45_000) -> None:
    ax.annotate(
        "",
        xy=(x, y + length_m),
        xytext=(x, y),
        arrowprops=dict(arrowstyle="-|>", lw=2.0, color="#222222", mutation_scale=18),
    )
    ax.text(x, y + length_m + 8000, "N", ha="center", va="bottom", fontsize=12, weight="bold")


def annotate_valley_labels(ax) -> None:
    for short_name, color in VALLEY_COLORS.items():
        if short_name in LABEL_POS_KM:
            x_km, y_km = LABEL_POS_KM[short_name]
            ax.text(
                x_km * 1000,
                y_km * 1000,
                short_name,
                color=color,
                fontsize=12,
                weight="bold",
                ha="center",
                va="center",
                zorder=7,
                path_effects=[pe.withStroke(linewidth=4, foreground="white")],
            )


def main() -> None:
    set_chinese_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "font.size": 9,
        "axes.linewidth": 0.8,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "savefig.dpi": 300,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })

    with rio.open(VAI_PATH) as src:
        vai = src.read(1).astype("float32")
        nodata = src.nodata
        crs = src.crs
        bounds = src.bounds
        extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    if nodata is not None and np.isfinite(nodata):
        vai[vai == nodata] = np.nan
    vai = np.where(np.isfinite(vai), vai, np.nan)
    vai_masked = np.ma.masked_invalid(vai)
    valid = vai[np.isfinite(vai)]
    if valid.size == 0:
        raise ValueError(f"VAI 栅格没有有效值: {VAI_PATH}")

    pct_pos = float((valid > 0).mean() * 100)
    pct_neg = float((valid < 0).mean() * 100)
    median_vai = float(np.median(valid))
    q01, q99 = np.percentile(valid, [1, 99])

    valid_rows, valid_cols = np.where(np.isfinite(vai))
    x_min = bounds.left + valid_cols.min() * 3000 - 15_000
    x_max = bounds.left + (valid_cols.max() + 1) * 3000 + 15_000
    y_max = bounds.top - valid_rows.min() * 3000 + 15_000
    y_min = bounds.top - (valid_rows.max() + 1) * 3000 - 15_000

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "vai_blue_green",
        ["#2166AC", "#92C5DE", "#F7F7F7", "#A6D96A", "#1A9850"],
        N=256,
    )
    cmap.set_bad((1, 1, 1, 0))
    norm = mcolors.TwoSlopeNorm(vmin=-VAI_ABS_LIMIT, vcenter=0, vmax=VAI_ABS_LIMIT)

    fig = plt.figure(figsize=(13.33, 7.5), dpi=300)

    # 手工控制版式，避免 PPT 宽屏图中标题、色标和统计框互相挤压。
    ax = fig.add_axes([0.055, 0.105, 0.405, 0.760])
    im = ax.imshow(
        vai_masked,
        extent=extent,
        origin="upper",
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
        zorder=1,
    )

    annotate_valley_labels(ax)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("UTM 47N 东向坐标 (km)", fontsize=10)
    ax.set_ylabel("UTM 47N 北向坐标 (km)", fontsize=10)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(km_formatter))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(km_formatter))
    ax.grid(color="#9E9E9E", linewidth=0.35, linestyle="--", alpha=0.35)
    ax.tick_params(top=True, right=True, labelsize=9)

    add_scale_bar(ax, x_min + 32_000, y_min + 42_000, 100_000)
    add_north_arrow(ax, x_max - 42_000, y_max - 82_000)

    cax = fig.add_axes([0.500, 0.315, 0.030, 0.465])
    cbar = fig.colorbar(im, cax=cax, orientation="vertical", extend="both")
    cbar.set_label("VAI (%)", fontsize=10)
    cbar.set_ticks(np.arange(-60, 61, 20))
    cbar.ax.tick_params(labelsize=9)
    cbar.outline.set_linewidth(0.8)
    cax.text(
        0.5,
        1.055,
        "迎风坡更绿",
        transform=cax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#1A9850",
        weight="bold",
    )
    cax.text(
        0.5,
        -0.055,
        "背风坡更绿",
        transform=cax.transAxes,
        ha="center",
        va="top",
        fontsize=10,
        color="#2166AC",
        weight="bold",
    )

    ax_info = fig.add_axes([0.585, 0.555, 0.360, 0.270])
    ax_info.axis("off")
    ax_info.text(
        0.0,
        0.98,
        "图例与统计",
        ha="left",
        va="top",
        fontsize=11,
        weight="bold",
        color="#222222",
    )
    legend_y = 0.82
    for i, (name, color) in enumerate(VALLEY_COLORS.items()):
        y = legend_y - i * 0.17
        ax_info.plot([0.02, 0.26], [y, y], color=color, lw=3.0, transform=ax_info.transAxes)
        ax_info.text(0.31, y, name, transform=ax_info.transAxes, va="center", fontsize=9)

    ax_stats = fig.add_axes([0.585, 0.415, 0.360, 0.105])
    ax_stats.axis("off")
    ax_stats.text(
        0.0,
        0.98,
        f"有效网格：{valid.size:,}\n"
        f"中位数：{median_vai:.2f}%\n"
        f"迎风坡更绿：{pct_pos:.1f}%\n"
        f"背风坡更绿：{pct_neg:.1f}%",
        transform=ax_stats.transAxes,
        ha="left",
        va="top",
        fontsize=9.0,
        linespacing=1.25,
        bbox=dict(boxstyle="round,pad=0.35", fc="#FAFAFA", ec="#D6D6D6", alpha=0.95),
    )

    ax_hist = fig.add_axes([0.585, 0.115, 0.360, 0.255])
    bins = np.linspace(-VAI_ABS_LIMIT, VAI_ABS_LIMIT, 49)
    clipped = valid[(valid >= -VAI_ABS_LIMIT) & (valid <= VAI_ABS_LIMIT)]
    counts, edges = np.histogram(clipped, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    widths = np.diff(edges)
    colors = [cmap(norm(c)) for c in centers]
    ax_hist.bar(centers, counts, width=widths * 0.92, color=colors, edgecolor="white", linewidth=0.25)
    ax_hist.axvline(0, color="#222222", lw=1.0, ls="--")
    ax_hist.axvline(median_vai, color="#B2182B", lw=1.2, ls=":")
    ax_hist.set_xlim(-VAI_ABS_LIMIT, VAI_ABS_LIMIT)
    ax_hist.set_xlabel("VAI (%)", fontsize=9.5)
    ax_hist.set_ylabel("网格数", fontsize=9.5)
    ax_hist.tick_params(labelsize=8, top=True, right=True)
    ax_hist.grid(axis="y", color="#C8C8C8", lw=0.35, alpha=0.55)

    fig.suptitle("川西干热河谷迎/背风坡植被不对称指数（VAI）空间分布", fontsize=15.5, weight="bold", y=0.955)
    fig.text(
        0.055,
        0.905,
        "基于 3 km 非重叠网格；VAI > 0 表示迎风坡 NDVI 更高，VAI < 0 表示背风坡 NDVI 更高；色阶按 ±60% 显示。",
        ha="left",
        va="center",
        fontsize=9,
        color="#444444",
    )
    fig.text(
        0.975,
        0.905,
        f"1%–99% 分位：{q01:.1f}% 至 {q99:.1f}%",
        ha="right",
        va="center",
        fontsize=8.5,
        color="#666666",
    )

    fig.savefig(OUT_PNG, dpi=300)
    # fig.savefig(OUT_PDF)
    plt.close(fig)

    # 另存一张纯地图版，方便在 PPT 中自行配标题和图例。
    fig_map = plt.figure(figsize=(8.0, 9.6), dpi=300)
    ax_map = fig_map.add_axes([0.105, 0.075, 0.79, 0.87])
    ax_map.imshow(
        vai_masked,
        extent=extent,
        origin="upper",
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
        zorder=1,
    )
    annotate_valley_labels(ax_map)
    ax_map.set_xlim(x_min, x_max)
    ax_map.set_ylim(y_min, y_max)
    ax_map.set_aspect("equal", adjustable="box")
    ax_map.set_xlabel("UTM 47N 东向坐标 (km)", fontsize=10)
    ax_map.set_ylabel("UTM 47N 北向坐标 (km)", fontsize=10)
    ax_map.xaxis.set_major_formatter(mticker.FuncFormatter(km_formatter))
    ax_map.yaxis.set_major_formatter(mticker.FuncFormatter(km_formatter))
    ax_map.grid(color="#9E9E9E", linewidth=0.35, linestyle="--", alpha=0.35)
    ax_map.tick_params(top=True, right=True, labelsize=8.5)
    add_scale_bar(ax_map, x_min + 32_000, y_min + 42_000, 100_000)
    add_north_arrow(ax_map, x_max - 42_000, y_max - 82_000)
    fig_map.savefig(OUT_MAP_ONLY_PNG, dpi=300)
    plt.close(fig_map)

    print(f"PNG saved: {OUT_PNG}")
    print(f"PDF saved: {OUT_PDF}")
    print(f"Map-only PNG saved: {OUT_MAP_ONLY_PNG}")
    print(f"Valid cells: {valid.size:,}")
    print(f"VAI median: {median_vai:.3f}%")
    print(f"VAI > 0: {pct_pos:.1f}%")
    print(f"VAI < 0: {pct_neg:.1f}%")


if __name__ == "__main__":
    main()
