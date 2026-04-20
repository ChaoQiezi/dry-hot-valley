# @Author  : ChaoQiezi
# @Time    : 2026/4/1
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: plot_gai_spatial.py

"""
This script is used to 绘制GAI(绿度不对称指数)空间分布图

2026/4/14-ps: 适配干热河谷内外侧维度 (VALLEY_MODE)

布局:
  ┌──────────┬──────────┐
  │  (a) GAI │ (b) sig  │
  ├──────────┴──────────┤
  │  (c) histogram      │
  └─────────────────────┘

  (a) colorbar 置于左侧(垂直), 避免挤压地图高度

河谷模式 (VALLEY_MODE):
  - "inner": 仅河谷内侧像元参与GAI计算
  - "outer": 仅河谷外侧像元参与GAI计算
  - "all":   河谷内外侧所有像元
  输入/输出路径根据模式自动追加后缀

输入:
  - GAI GeoTIFF (3km分辨率, UTM 47N)
  - p-value GeoTIFF (3km分辨率, UTM 47N)
输出:
  - 出版质量的空间分布图
"""

import os
import numpy as np
import rioxarray as rxr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
# 河谷模式: "inner" | "outer" | "all"
# VALLEY_MODE = "inner"
# VALLEY_MODE = "outer"
VALLEY_MODE = "all"

# 输入/输出路径根据模式自动生成
gai_dir = r"E:\GeoProjects\dry_hot_valley\GAI"
out_dir = r"E:\GeoProjects\dry_hot_valley\Result\Chart\GAI_spatial_distribution"
os.makedirs(out_dir, exist_ok=True)

_suffix = f"_valley_{VALLEY_MODE}"
gai_path = os.path.join(gai_dir, f"GAI_3km{_suffix}.tif")
pval_path = os.path.join(gai_dir, f"GAI_pvalue_3km{_suffix}.tif")
out_path = os.path.join(out_dir, f"GAI_spatial{_suffix}.png")

# 研究区范围 (地理坐标, 川西干热河谷区域)
# 注: 当valley_mode限定后有效网格变少, 地图范围仍保持一致以便跨模式对比
lon_min, lon_max = 97.0, 105.0
lat_min, lat_max = 25.6, 34.6

# 模式中文标签 (用于图中标注)
VALLEY_MODE_LABEL = {
    'inner': 'Valley interior',
    'outer': 'Valley exterior',
    'all':   'All valley pixels',
}

# ============================================================
# 1. Read data + reproject to WGS84
# ============================================================
print(f"Valley mode: {VALLEY_MODE}")
print(f"GAI input:   {gai_path}")
print(f"pval input:  {pval_path}")

print("Reading GAI...")
gai_da = rxr.open_rasterio(gai_path, masked=True).squeeze().drop_vars('band')
print(f"  CRS: {gai_da.rio.crs}, shape: {gai_da.shape}")
gai_geo = gai_da.rio.reproject("EPSG:4326")

print("Reading p-value...")
pval_da = rxr.open_rasterio(pval_path, masked=True).squeeze().drop_vars('band')
pval_geo = pval_da.rio.reproject("EPSG:4326", nodata=np.nan)

# 提取数据
gai_vals = gai_geo.values
pval_vals = pval_geo.values
lons = gai_geo.x.values
lats = gai_geo.y.values

# 统计
gai_flat = gai_vals[np.isfinite(gai_vals)]
pval_flat = pval_vals[np.isfinite(pval_vals)]

if len(gai_flat) == 0:
    raise ValueError(
        f"No valid GAI cells found for valley_mode='{VALLEY_MODE}'. "
        f"Check the analysis output at {gai_path}."
    )

pct_gt1 = (gai_flat > 1).mean() * 100
pct_lt1 = (gai_flat < 1).mean() * 100
pct_sig001 = (pval_flat < 0.01).mean() * 100
pct_sig005 = ((pval_flat >= 0.01) & (pval_flat < 0.05)).mean() * 100
pct_ns = (pval_flat >= 0.05).mean() * 100

print(f"  Valid cells: {len(gai_flat)}")
print(f"  GAI > 1 (windward greener): {pct_gt1:.1f}%")
print(f"  GAI < 1 (leeward greener):  {pct_lt1:.1f}%")
print(f"  p < 0.01: {pct_sig001:.1f}%,  0.01 < p < 0.05: {pct_sig005:.1f}%,  p > 0.05: {pct_ns:.1f}%")

# ============================================================
# 2. Plot
# ============================================================
# --- Academic style ---
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'mathtext.fontset': 'stix',
})

proj = ccrs.PlateCarree()

# --- 地图要素的辅助函数 ---
def add_map_features(ax, show_ylabels=True):
    """为地图添加边界线、省界线和经纬网格"""
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor='gray')
    ax.add_feature(
        cfeature.NaturalEarthFeature('cultural', 'admin_1_states_provinces_lines',
                                     '10m', edgecolor='gray', facecolor='none'),
        linewidth=0.4,
    )
    ax.set_xticks(np.arange(lon_min, lon_max + 1, 2), crs=proj)
    ax.set_yticks(np.arange(lat_min, lat_max + 1, 2), crs=proj)
    ax.xaxis.set_major_formatter(LongitudeFormatter())
    if show_ylabels:
        ax.yaxis.set_major_formatter(LatitudeFormatter())
    else:
        ax.yaxis.set_major_formatter(mticker.NullFormatter())
    ax.tick_params(which='both', top=True, right=True)
    gl = ax.gridlines(draw_labels=False, linewidth=0.3,
                      linestyle='--', color='gray', alpha=0.4)
    gl.xlocator = mticker.FixedLocator(np.arange(lon_min, lon_max + 1, 2))
    gl.ylocator = mticker.FixedLocator(np.arange(lat_min, lat_max + 1, 2))


# --- Figure layout ---
fig = plt.figure(figsize=(14, 10))

# 外层: 上(地图行) / 下(直方图行)
gs_outer = GridSpec(
    2, 1, height_ratios=[3, 1.1],
    hspace=0.12,
    left=0.06, right=0.96, bottom=0.06, top=0.97,
)

# 上排: colorbar_a | map_a | map_b
# 给(a)的colorbar留出左侧窄列
gs_top = gs_outer[0].subgridspec(
    1, 3, width_ratios=[0.05, 1, 1],
    wspace=0.06,
)

# ====== Panel (a): GAI spatial map ======
ax_gai = fig.add_subplot(gs_top[0, 1], projection=proj)
ax_gai.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)

# 发散色标 (红 < 1 < 蓝)
gai_cmap = plt.cm.RdBu
gai_norm = mcolors.TwoSlopeNorm(vmin=0.5, vcenter=1.0, vmax=1.5)

im_gai = ax_gai.pcolormesh(
    lons, lats, gai_vals,
    cmap=gai_cmap, norm=gai_norm,
    transform=proj, shading='auto', rasterized=True,
)

add_map_features(ax_gai, show_ylabels=False)

# 面积比例标注 (含模式标签)
mode_label = VALLEY_MODE_LABEL[VALLEY_MODE]
ax_gai.text(
    0.03, 0.04,
    f'{mode_label}\n'
    f'GAI > 1: {pct_gt1:.1f}%\n'
    f'GAI < 1: {pct_lt1:.1f}%\n'
    f'n = {len(gai_flat)}',
    transform=ax_gai.transAxes,
    fontsize=9, va='bottom', ha='left',
    bbox=dict(facecolor='white', edgecolor='#BBBBBB',
              alpha=0.88, boxstyle='round,pad=0.3'),
)

ax_gai.text(0.02, 0.97, '(a)', transform=ax_gai.transAxes,
            fontsize=13, fontweight='bold', va='top',
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=2))

# Colorbar — 垂直, 置于(a)左侧的窄列, 刻度和标签在左侧
cbar_ax = fig.add_subplot(gs_top[0, 0])
cbar_ax.set_axes_locator(None)
cbar = fig.colorbar(im_gai, cax=cbar_ax, orientation='vertical', extend='both')
cbar.ax.yaxis.set_ticks_position('left')       # 刻度在左
cbar.ax.yaxis.set_label_position('left')        # 标签在左
cbar.set_label('GAI', fontsize=11)
cbar.ax.tick_params(labelsize=9)
cbar.outline.set_linewidth(0.6)

# ====== Panel (b): Significance map ======
ax_sig = fig.add_subplot(gs_top[0, 2], projection=proj)
ax_sig.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)

# 三级显著性
sig_class = np.full_like(pval_vals, np.nan)
sig_class[pval_vals < 0.01] = 1
sig_class[(pval_vals >= 0.01) & (pval_vals < 0.05)] = 2
sig_class[pval_vals >= 0.05] = 3

sig_cmap = mcolors.ListedColormap(['#2166AC', '#92C5DE', '#F4A582'])
sig_norm = mcolors.BoundaryNorm([0.5, 1.5, 2.5, 3.5], sig_cmap.N)

ax_sig.pcolormesh(
    lons, lats, sig_class,
    cmap=sig_cmap, norm=sig_norm,
    transform=proj, shading='auto', rasterized=True,
)

add_map_features(ax_sig, show_ylabels=True)

# 图例 (离散)
legend_patches = [
    Patch(facecolor='#2166AC', label=f'$p$ < 0.01 ({pct_sig001:.1f}%)'),
    Patch(facecolor='#92C5DE', label=f'0.01 ≤ $p$ < 0.05 ({pct_sig005:.1f}%)'),
    Patch(facecolor='#F4A582', label=f'$p$ ≥ 0.05 ({pct_ns:.1f}%)'),
]
ax_sig.legend(
    handles=legend_patches, loc='lower left',
    fontsize=8.5, framealpha=0.88, edgecolor='#CCCCCC',
    handlelength=1.5, handleheight=1.2,
)

ax_sig.text(0.02, 0.97, '(b)', transform=ax_sig.transAxes,
            fontsize=13, fontweight='bold', va='top',
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=2))

# ====== Panel (c): GAI histogram ======
ax_hist = fig.add_subplot(gs_outer[1])

bins = np.arange(0.4, 1.65, 0.025)

ax_hist.hist(
    gai_flat[gai_flat < 1], bins=bins,
    color='#D6604D', alpha=0.7, edgecolor='white', linewidth=0.3,
    label=f'GAI < 1 (leeward greener, {pct_lt1:.1f}%)',
    zorder=2,
)
ax_hist.hist(
    gai_flat[gai_flat >= 1], bins=bins,
    color='#4393C3', alpha=0.7, edgecolor='white', linewidth=0.3,
    label=f'GAI ≥ 1 (windward greener, {pct_gt1:.1f}%)',
    zorder=2,
)

# GAI = 1 参考线
ymax = ax_hist.get_ylim()[1]
ax_hist.axvline(x=1.0, color='k', linewidth=0.8, linestyle='--', zorder=3)
ax_hist.text(1.008, ymax * 0.95, 'GAI = 1', fontsize=9, va='top', ha='left', color='k')

# 中位数
gai_median = np.median(gai_flat)
ax_hist.axvline(x=gai_median, color='#666666', linewidth=0.8, linestyle=':', zorder=3)
ax_hist.text(gai_median - 0.008, ymax * 0.82,
             f'Median = {gai_median:.3f}', fontsize=8.5, va='top',
             ha='right', color='#666666')

ax_hist.set_xlabel('GAI', fontsize=12)
ax_hist.set_ylabel('Frequency', fontsize=12)
ax_hist.set_xlim(bins[0], bins[-1])
ax_hist.tick_params(which='both', top=True, right=True)
ax_hist.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax_hist.set_axisbelow(True)

ax_hist.legend(
    loc='upper right', fontsize=9,
    framealpha=0.88, edgecolor='#CCCCCC',
)

ax_hist.text(0.01, 0.95, '(c)', transform=ax_hist.transAxes,
             fontsize=13, fontweight='bold', va='top')

# --- Save ---
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'\nFigure saved to: {out_path}')
plt.show()