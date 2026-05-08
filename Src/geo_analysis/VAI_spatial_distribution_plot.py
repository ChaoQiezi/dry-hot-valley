# @Author  : ChaoQiezi
# @Time    : 2026/5/8
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_spatial_distribution_plot.py

"""
川西干旱河谷 VAI 空间分布图 —— 组会 PPT 用

基于 VAI_spatial_distribution.py 的计算结果 (VAI_3km.tif),
绘制带地形阴影的 VAI 空间分布图, 叠加河道中心线和河谷边界。
美学优化: 大字体投影可读、双侧信息面板、VAI直方图。
"""

import os
import math
import warnings

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import rasterio as rio
import shapefile
from matplotlib.colors import TwoSlopeNorm
from pyproj import CRS, Transformer

warnings.filterwarnings("ignore")

# ============================================================
# 0. Configuration
# ============================================================
VAI_PATH = r"E:\GeoProjects\dry_hot_valley\VAI\VAI_3km.tif"
DEM3_PATH = r"E:\GeoProjects\dry_hot_valley\VAI\DEM_3km.tif"
CENTERLINE_PATH = r"E:\GeoProjects\dry_hot_valley\valley_area\river_net\centerline_final.shp"
VALLEY_DIR = r"E:\GeoProjects\dry_hot_valley\valley_area\西南干旱河谷范围"

OUT_DIR = r"E:\GeoProjects\dry_hot_valley\Result\Chart"
OUT_PATH = os.path.join(OUT_DIR, "VAI_spatial_distribution.png")
os.makedirs(OUT_DIR, exist_ok=True)

VALLEY_NAMES = ["大渡河干旱河谷", "金沙江干旱河谷", "岷江干旱河谷", "雅砻江干旱河谷"]
VALLEY_LABELS = ["大渡河", "金沙江", "岷江", "雅砻江"]
VALLEY_LABEL_POSITIONS = [
    (610000, 3270000),
    (680000, 3100000),
    (700000, 3550000),
    (530000, 3400000),
]

VALLEY_COLORS = {
    "大渡河": "#D95F02",
    "金沙江": "#7570B3",
    "岷江":   "#1B9E77",
    "雅砻江": "#E7298A",
}

# ============================================================
# 1. Global matplotlib styling
# ============================================================
matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.linewidth": 0.6,
    "axes.labelsize": 14,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 300,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})


# ============================================================
# 2. Load rasters
# ============================================================
def compute_hillshade(dem_3km_path, azdeg=315, altdeg=45):
    with rio.open(dem_3km_path) as src:
        dem = src.read(1).astype(np.float64)
    dem[~np.isfinite(dem) | (dem <= 0)] = np.nan
    dy, dx = np.gradient(dem, 3000.0)
    slope = np.pi / 2.0 - np.arctan(np.sqrt(dx * dx + dy * dy))
    aspect = np.arctan2(-dx, dy)
    az_rad = np.deg2rad(360.0 - azdeg + 90.0)
    alt_rad = np.deg2rad(altdeg)
    shade = (np.sin(alt_rad) * np.sin(slope)
             + np.cos(alt_rad) * np.cos(slope)
             * np.cos(az_rad - aspect))
    return np.clip(shade, 0, 1)


def load_vai_raster():
    with rio.open(VAI_PATH) as src:
        vai = src.read(1).astype(np.float64)
        vai[~np.isfinite(vai)] = np.nan
        t = src.transform
        extent_km = [
            t.c / 1000, (t.c + t.a * src.width) / 1000,
            (t.f + t.e * src.height) / 1000, t.f / 1000,
        ]
    return vai, extent_km


# ============================================================
# 3. Load vector overlays
# ============================================================
def get_centerline_crs():
    prj_path = CENTERLINE_PATH.replace(".shp", ".prj")
    return CRS.from_wkt(open(prj_path, errors="ignore").read())


def load_centerlines():
    dst_crs = CRS.from_epsg(32647)
    src_crs = get_centerline_crs()
    same_crs = src_crs == dst_crs
    transformer = None if same_crs else Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    valley_parts = {}
    reader = shapefile.Reader(CENTERLINE_PATH)
    for sr in reader.iterShapeRecords():
        name = sr.record.as_dict().get("Name", "")
        if name not in VALLEY_NAMES:
            continue
        label = VALLEY_LABELS[VALLEY_NAMES.index(name)]
        parts = []
        part_indices = list(sr.shape.parts) + [len(sr.shape.points)]
        for pi in range(len(part_indices) - 1):
            pts = sr.shape.points[part_indices[pi]:part_indices[pi + 1]]
            if len(pts) >= 2:
                xs, ys = zip(*pts)
                if transformer:
                    xs, ys = transformer.transform(xs, ys)
                parts.append((np.array(xs) / 1000, np.array(ys) / 1000))
        valley_parts[label] = parts
    return valley_parts


def load_valley_boundaries():
    dst_crs = CRS.from_epsg(32647)
    boundaries = {}
    shp_names = {
        "大渡河": os.path.join(VALLEY_DIR, "Daduhe_valley.shp"),
        "金沙江": os.path.join(VALLEY_DIR, "Jinshajiang_valley.shp"),
        "岷江": os.path.join(VALLEY_DIR, "Minjiang_valley.shp"),
        "雅砻江": os.path.join(VALLEY_DIR, "Yalongjiang_valley.shp"),
    }
    for label, shp_path in shp_names.items():
        if not os.path.exists(shp_path):
            continue
        reader = shapefile.Reader(shp_path)
        prj_path = shp_path.replace(".shp", ".prj")
        src_crs = CRS.from_wkt(open(prj_path, errors="ignore").read()) if os.path.exists(prj_path) else dst_crs
        same_crs = src_crs == dst_crs
        transformer = None if same_crs else Transformer.from_crs(src_crs, dst_crs, always_xy=True)
        all_parts = []
        for shape in reader.shapes():
            for pi, si in enumerate(shape.parts):
                end = shape.parts[pi + 1] if pi + 1 < len(shape.parts) else len(shape.points)
                pts = shape.points[si:end]
                if len(pts) >= 3:
                    xs, ys = zip(*pts)
                    if transformer:
                        xs, ys = transformer.transform(xs, ys)
                    all_parts.append((np.array(xs) / 1000, np.array(ys) / 1000))
        boundaries[label] = all_parts
    return boundaries


# ============================================================
# 4. Plot
# ============================================================
def add_north_arrow(ax, x, y, size=10):
    """简洁指北针."""
    ax.annotate(
        "N", xy=(x, y + size * 0.55), fontsize=10, fontweight="bold",
        ha="center", va="bottom", color="#444444",
    )
    ax.annotate(
        "", xy=(x, y - size * 0.48), xytext=(x, y + size * 0.28),
        arrowprops=dict(arrowstyle="<-", color="#444444", lw=2.0),
    )


def add_scale_bar(ax, x, y, length_km=50):
    """简洁比例尺."""
    ax.plot([x, x + length_km], [y, y], color="#444444", lw=3.0, solid_capstyle="butt")
    ax.plot([x, x], [y - 3, y + 3], color="#444444", lw=2.0)
    ax.plot([x + length_km, x + length_km], [y - 3, y + 3], color="#444444", lw=2.0)
    ax.text(x + length_km / 2, y - 7, f"{length_km} km",
            ha="center", va="top", fontsize=10, color="#444444")


def plot_spatial_distribution():
    vai, extent = load_vai_raster()
    hillshade = compute_hillshade(DEM3_PATH)
    centerlines = load_centerlines()
    valley_bounds = load_valley_boundaries()

    vai_valid = vai[np.isfinite(vai)]
    p_pos = (vai_valid > 0).mean() * 100
    p_neg = (vai_valid < 0).mean() * 100
    vmax_abs = max(abs(np.nanpercentile(vai, 2)), abs(np.nanpercentile(vai, 98)))
    norm = TwoSlopeNorm(vcenter=0, vmin=-vmax_abs, vmax=vmax_abs)
    cmap = plt.cm.RdBu_r

    # ---- Figure layout ----
    fig = plt.figure(figsize=(16, 10))

    # map 区域: 左侧 68% 宽度
    ax_map = fig.add_axes([0.04, 0.06, 0.66, 0.90])
    # 右侧: 直方图
    ax_hist = fig.add_axes([0.725, 0.48, 0.24, 0.48])
    # 右侧下: 统计信息文本
    ax_info = fig.add_axes([0.725, 0.06, 0.24, 0.36])

    # ================================================================
    # Panel A: 主题地图
    # ================================================================
    # 地形阴影
    ax_map.imshow(
        hillshade, cmap="Greys_r", extent=extent, aspect="equal",
        interpolation="bilinear", vmin=0.25, vmax=1.0, alpha=0.45, zorder=1,
    )
    # VAI
    im = ax_map.imshow(
        vai, cmap=cmap, norm=norm, extent=extent, aspect="equal",
        interpolation="none", alpha=0.82, zorder=2,
    )
    # 河谷边界
    for label, parts in valley_bounds.items():
        for xs, ys in parts:
            ax_map.plot(xs, ys, color=VALLEY_COLORS.get(label, "#555555"),
                        lw=1.3, alpha=0.65, ls="--", zorder=3)
    # 河道中心线
    for label, parts in centerlines.items():
        for xs, ys in parts:
            ax_map.plot(xs, ys, color="#1a1a1a", lw=0.8, alpha=0.88, zorder=4)
    # 河谷名称标注
    for (x, y), label in zip(VALLEY_LABEL_POSITIONS, VALLEY_LABELS):
        ax_map.annotate(
            label, xy=(x / 1000, y / 1000), fontsize=13, fontweight="bold",
            color=VALLEY_COLORS.get(label, "#333333"), ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                      edgecolor=VALLEY_COLORS.get(label, "#333333"),
                      alpha=0.88, lw=1.5),
            zorder=5,
        )

    # 指北针 & 比例尺
    xlim, ylim = ax_map.get_xlim(), ax_map.get_ylim()
    dx, dy = xlim[1] - xlim[0], ylim[1] - ylim[0]
    add_north_arrow(ax_map, xlim[0] + dx * 0.93, ylim[0] + dy * 0.90)
    add_scale_bar(ax_map, xlim[0] + dx * 0.04, ylim[0] + dy * 0.05, length_km=50)

    # 地图坐标轴
    ax_map.set_xlabel("UTM 47N 东向 (km)", fontsize=14, labelpad=6)
    ax_map.set_ylabel("UTM 47N 北向 (km)", fontsize=14, labelpad=6)
    ax_map.tick_params(top=True, right=True, which="both", direction="in", labelsize=10)
    ax_map.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax_map.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax_map.set_title(
        "地形阴影 + 河道中心线 + 河谷边界",
        fontsize=12, color="#666666", pad=4, loc="left",
    )

    # 地图内 colorbar (inset)
    cbar_ax = fig.add_axes([0.62, 0.12, 0.018, 0.28])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label("VAI (%)", fontsize=12, labelpad=8)
    cbar.ax.tick_params(labelsize=9, direction="in")
    cbar.ax.yaxis.set_major_locator(mticker.MaxNLocator(7))

    # 图例标识: 迎风 vs 背风
    ax_map.text(
        0.98, 0.025, "迎风坡更绿 (VAI > 0)", transform=ax_map.transAxes,
        fontsize=10, color="#B2182B", ha="right", fontstyle="italic",
    )
    ax_map.text(
        0.98, 0.005, "背风坡更绿 (VAI < 0)", transform=ax_map.transAxes,
        fontsize=10, color="#2166AC", ha="right", fontstyle="italic",
    )

    # ================================================================
    # Panel B: VAI 直方图
    # ================================================================
    bins = np.linspace(-60, 40, 61)
    ax_hist.hist(
        np.clip(vai_valid, -60, 40), bins=bins,
        color="#888888", edgecolor="white", linewidth=0.3, alpha=0.8,
    )
    ax_hist.axvline(0, color="#222222", lw=1.2, ls="--")
    ax_hist.axvline(np.median(vai_valid), color="#B2182B", lw=1.0, ls=":")
    ax_hist.set_xlabel("VAI (%)", fontsize=12)
    ax_hist.set_ylabel("3 km 网格数", fontsize=12)
    ax_hist.set_title("VAI 频率分布", fontsize=13, fontweight="bold", pad=6)
    ax_hist.tick_params(direction="in", labelsize=9)
    # 标注中位数
    ax_hist.annotate(
        f"中位数 {np.median(vai_valid):.1f}%", xy=(np.median(vai_valid), 0),
        xytext=(np.median(vai_valid) + 12, ax_hist.get_ylim()[1] * 0.85),
        fontsize=9, color="#B2182B", ha="center",
        arrowprops=dict(arrowstyle="->", color="#B2182B", lw=1.2),
    )
    ax_hist.grid(axis="y", color="#EEEEEE", lw=0.5)

    # ================================================================
    # Panel C: 统计信息
    # ================================================================
    ax_info.axis("off")
    stats_text = (
        f"网格统计\n"
        f"━━━━━━━━━━━━\n"
        f"有效网格: {len(vai_valid):,}\n"
        f"VAI 范围: [{vai_valid.min():.1f}, {vai_valid.max():.1f}]%\n"
        f"均值 / 中位数: {vai_valid.mean():.2f} / {np.median(vai_valid):.2f}%\n"
        f"\n"
        f"不对称性\n"
        f"━━━━━━━━━━━━\n"
        f"迎风坡更绿: {p_pos:.1f}%\n"
        f"背风坡更绿: {p_neg:.1f}%\n"
        f"\n"
        f"网格规格\n"
        f"━━━━━━━━━━━━\n"
        f"分辨率: 3 × 3 km\n"
        f"投影: UTM 47N (EPSG:32647)\n"
        f"最小像素阈值: 15\n"
    )
    ax_info.text(
        0.05, 0.95, stats_text, transform=ax_info.transAxes,
        fontsize=10, va="top", fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#FAFAFA",
                  edgecolor="#CCCCCC", alpha=0.9, lw=0.8),
    )

    # ================================================================
    # 全局标题
    # ================================================================
    fig.suptitle(
        "川西干旱河谷迎背风植被不对称指数 (VAI) 空间分布",
        fontsize=22, fontweight="bold", y=0.985,
    )
    fig.text(
        0.5, 0.965,
        "基于 Sentinel-2 10 m NDVI 年际均值 (2019–2025)  |  迎风/背风划分: 30 m DEM 风向遮蔽角",
        fontsize=10, color="#888888", ha="center",
    )

    fig.savefig(OUT_PATH)
    plt.close(fig)
    print(f"Figure saved: {OUT_PATH}")


# ============================================================
# 5. Main
# ============================================================
if __name__ == "__main__":
    plot_spatial_distribution()
