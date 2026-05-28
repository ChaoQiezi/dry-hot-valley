# @Author  : ChaoQiezi
# @Time    : 2026/3/29
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: plot_ndvi_elevation_gradient.py

"""
This script is used to 绘制不同高程梯度下迎风坡与背风坡NDVI变化图

布局 (上中下三面板):
  上方主面板(a): NDVI随高程变化曲线 (迎风坡 vs 背风坡), 含±1σ阴影
  中间面板(b): ΔNDVI = NDVI_windward - NDVI_leeward 柱状图
               正值(迎风坡更绿)向上, 负值(背风坡更绿)向下
  下方面板(c): 各高程带像元数量 (背靠背柱状图)

三个面板共享X轴(高程)
输入:
  - Excel表格 (由 ndvi_elevation_gradient_stats.py 生成)
输出:
  - 出版质量的高程梯度图
"""

import os
import warnings

from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

# 0. Configuration
in_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_elevation_gradient.xlsx'
out_path = r'G:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_elevation_gradient.png'
# 1. Read data
df = pd.read_excel(in_path)
elev = df['elev_center'].values
ww_mean = df['windward_mean'].values
ww_std = df['windward_std'].values
ww_count = df['windward_count'].values
lw_mean = df['leeward_mean'].values
lw_std = df['leeward_std'].values
lw_count = df['leeward_count'].values
# 过滤: 仅保留至少一侧有有效数据的高程带
valid = (ww_count > 0) | (lw_count > 0)
elev = elev[valid]
ww_mean, ww_std, ww_count = ww_mean[valid], ww_std[valid], ww_count[valid]
lw_mean, lw_std, lw_count = lw_mean[valid], lw_std[valid], lw_count[valid]
ww_valid = ww_count > 0
lw_valid = lw_count > 0
# ΔNDVI: 仅在两侧都有数据时计算, 否则为NaN
both_valid = ww_valid & lw_valid
delta_ndvi = np.full_like(elev, np.nan, dtype=float)
delta_ndvi[both_valid] = ww_mean[both_valid] - lw_mean[both_valid]
elev_bin_width = np.diff(df['elev_lo'].values[:2])[0] if len(df) > 1 else 50
print(f'Elevation range: {elev.min():.0f} – {elev.max():.0f} m')
print(f'Valid bins: {valid.sum()} / {len(valid)}')
print(f'Bins with both sides: {both_valid.sum()}')
# 2. Plot
# Academic style
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 12,
    'xtick.labelsize': 9.5,
    'ytick.labelsize': 9.5,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'mathtext.fontset': 'stix',
})
# Colors
C_WW = '#2E7D52'
C_LW = '#C2652A'
# Figure layout: 三面板上中下
fig = plt.figure(figsize=(14, 7.5))
gs = GridSpec(
    3, 1, height_ratios=[3.5, 1.2, 1],
    hspace=0.06,
    left=0.06, right=0.97, bottom=0.08, top=0.97
)
# Panel (a): NDVI vs Elevation
ax_main = fig.add_subplot(gs[0])
# ±1σ 阴影 (低alpha)
ax_main.fill_between(
    elev[lw_valid],
    (lw_mean - lw_std)[lw_valid],
    (lw_mean + lw_std)[lw_valid],
    color=C_LW, alpha=0.12, edgecolor='none', zorder=1,
)
ax_main.fill_between(
    elev[ww_valid],
    (ww_mean - ww_std)[ww_valid],
    (ww_mean + ww_std)[ww_valid],
    color=C_WW, alpha=0.12, edgecolor='none', zorder=2,
)
# 均值曲线
ax_main.plot(
    elev[ww_valid], ww_mean[ww_valid],
    color=C_WW, linewidth=1.8, zorder=4,
)
ax_main.plot(
    elev[lw_valid], lw_mean[lw_valid],
    color=C_LW, linewidth=1.8, zorder=4,
)
# 稀疏数据标记
n_show = max(1, len(elev) // 16)
for mask, vals, color, marker in [
    (ww_valid, ww_mean, C_WW, 'o'),
    (lw_valid, lw_mean, C_LW, 's'),
]:
    idx = np.where(mask)[0][::n_show]
    ax_main.scatter(
        elev[idx], vals[idx],
        s=22, zorder=5,
        facecolors='white', edgecolors=color, linewidths=1.2,
        marker=marker,
    )
# Y轴自适应
all_vals = np.concatenate([
    (ww_mean - ww_std)[ww_valid],
    (ww_mean + ww_std)[ww_valid],
    (lw_mean - lw_std)[lw_valid],
    (lw_mean + lw_std)[lw_valid],
])
y_lo = max(0, np.nanmin(all_vals) - 0.02)
y_hi = min(1, np.nanmax(all_vals) + 0.02)
ax_main.set_ylim(y_lo, y_hi)
ax_main.set_xlim(elev.min(), elev.max())
ax_main.set_ylabel('NDVI', fontsize=12)
ax_main.tick_params(labelbottom=False)
ax_main.tick_params(which='both', top=True, right=True)
ax_main.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax_main.set_axisbelow(True)
# 图例
legend_handles = [
    Line2D([0], [0], color=C_WW, linewidth=1.8,
           marker='o', markersize=4.5, markerfacecolor='white',
           markeredgewidth=1.2, markeredgecolor=C_WW,
           label='Windward (mean ± 1σ)'),
    Line2D([0], [0], color=C_LW, linewidth=1.8,
           marker='s', markersize=4.5, markerfacecolor='white',
           markeredgewidth=1.2, markeredgecolor=C_LW,
           label='Leeward (mean ± 1σ)'),
]
ax_main.legend(
    handles=legend_handles,
    loc='upper right',
    fontsize=9.5,
    framealpha=0.88,
    edgecolor='#CCCCCC',
    handlelength=2.5,
)
ax_main.text(
    0.01, 0.97, '(a)',
    transform=ax_main.transAxes,
    fontsize=12, fontweight='bold', va='top',
)
# Panel (b): ΔNDVI bars
ax_delta = fig.add_subplot(gs[1], sharex=ax_main)
bar_w = elev_bin_width * 0.8
# 按正负分色: 正值(迎风>背风)=绿, 负值(背风>迎风)=棕橙
delta_valid = both_valid & np.isfinite(delta_ndvi)
bar_colors = np.where(delta_ndvi >= 0, C_WW, C_LW)
ax_delta.bar(
    elev[delta_valid], delta_ndvi[delta_valid],
    width=bar_w, color=bar_colors[delta_valid],
    alpha=0.65, edgecolor='none', zorder=2,
)
# 零线
ax_delta.axhline(y=0, color='k', linewidth=0.5, zorder=1)
ax_delta.set_ylabel('ΔNDVI', fontsize=12)
ax_delta.tick_params(labelbottom=False)
ax_delta.tick_params(which='both', top=True, right=True)
# Y轴对称
delta_abs_max = np.nanmax(np.abs(delta_ndvi[delta_valid])) * 1.15
ax_delta.set_ylim(-delta_abs_max, delta_abs_max)
ax_delta.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4, symmetric=True))
# 方向标注
ax_delta.text(
    0.99, 0.92, 'Windward greener ↑', transform=ax_delta.transAxes,
    fontsize=8, color=C_WW, ha='right', va='top', fontstyle='italic',
)
ax_delta.text(
    0.99, 0.08, 'Leeward greener ↓', transform=ax_delta.transAxes,
    fontsize=8, color=C_LW, ha='right', va='bottom', fontstyle='italic',
)
ax_delta.text(
    0.01, 0.95, '(b)',
    transform=ax_delta.transAxes,
    fontsize=12, fontweight='bold', va='top',
)
# Panel (c): Pixel count
ax_count = fig.add_subplot(gs[2], sharex=ax_main)
max_count = max(ww_count.max(), lw_count.max())
ww_norm = ww_count / max_count
lw_norm = lw_count / max_count
ax_count.bar(
    elev[ww_valid], ww_norm[ww_valid],
    width=bar_w, color=C_WW, alpha=0.5, edgecolor='none', zorder=2,
)
ax_count.bar(
    elev[lw_valid], -lw_norm[lw_valid],
    width=bar_w, color=C_LW, alpha=0.5, edgecolor='none', zorder=2,
)
ax_count.axhline(y=0, color='k', linewidth=0.4, zorder=1)
ax_count.set_xlabel('Elevation (m)', fontsize=12)
ax_count.set_ylabel('Pixel count\n(normalized)', fontsize=10)
ax_count.tick_params(which='both', top=True, right=True)
ax_count.set_ylim(-1.15, 1.15)
ax_count.set_yticks([0])
ax_count.set_yticklabels(['0'])
ax_count.text(
    0.99, 0.88, 'Windward', transform=ax_count.transAxes,
    fontsize=8, color=C_WW, ha='right', va='top', fontweight='bold',
)
ax_count.text(
    0.99, 0.12, 'Leeward', transform=ax_count.transAxes,
    fontsize=8, color=C_LW, ha='right', va='bottom', fontweight='bold',
)
ax_count.text(
    0.01, 0.92, '(c)',
    transform=ax_count.transAxes,
    fontsize=12, fontweight='bold', va='top',
)
# Save
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'Figure saved to: {out_path}')
plt.show()