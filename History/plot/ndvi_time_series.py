# @Author  : ChaoQiezi
# @Time    : 2026/3/28 上午11:10
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_time_series.py

"""
This script is used to 绘制迎风坡与背风坡NDVI时间序列变化图

除NDVI年均值和标准差外, 还包括MK趋势和Sen's Slope, 并绘制趋势线.

输入:
  - Excel表格 (由 ndvi_windward_leeward_stats.py 生成)
输出:
  - 出版质量的时间序列折线图
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from qiezi.stats import mk_trend_slope

# ============================================================
# 0. Configuration
# ============================================================
in_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_windward_leeward_yearly.xlsx'
out_path = r'G:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_direction_time_series.png'

# ============================================================
# 1. Read data
# ============================================================
df = pd.read_excel(in_path)
years = df['year'].values
n = len(years)
x_idx = np.arange(n)

ww_mean = df['windward_mean'].values
ww_std = df['windward_std'].values
lw_mean = df['leeward_mean'].values
lw_std = df['leeward_std'].values

# ============================================================
# 2. MK Trend + Sen's Slope
# ============================================================
ww_stats = mk_trend_slope(ww_mean)
lw_stats = mk_trend_slope(lw_mean)

for label, s in [('Windward', ww_stats), ('Leeward', lw_stats)]:
    print(f'\n--- {label} Mann-Kendall Trend Test ---')
    print(f"  Trend       : {s['trend']}")
    print(f"  p-value     : {s['p_value']:.4f}")
    print(f"  τ           : {s['tau']:.4f}")
    print(f"  Sen's slope : {s['slope']:.6f}  "
          f"(95% CI: {s['slope_ci_lo']:.6f} ~ {s['slope_ci_hi']:.6f})")
    print(f"  Intercept   : {s['intercept']:.4f}")
    print(f"  Significant : {'Yes' if s['significant'] else 'No'}  (α = 0.05)")

# 趋势线 (基于x_idx, 绘图时映射回years)
ww_trend = ww_stats['slope'] * x_idx + ww_stats['intercept']
lw_trend = lw_stats['slope'] * x_idx + lw_stats['intercept']

# ============================================================
# 3. Plot
# ============================================================
# --- Academic style ---
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'mathtext.fontset': 'stix',
})

# --- Colors ---
# 迎风坡: 深绿 (植被茂盛侧); 背风坡: 棕橙 (干热河谷侧)
C_WW = '#2E7D52'
C_WW_FILL = '#A8D5BA'
C_LW = '#C2652A'
C_LW_FILL = '#EABB8D'

# --- Single clean panel ---
fig, ax = plt.subplots(figsize=(9, 5))

# ±1σ 阴影 (空间变异性)
ax.fill_between(
    years, ww_mean - ww_std, ww_mean + ww_std,
    color=C_WW_FILL, alpha=0.35, edgecolor='none', zorder=1,
    label='Windward ± 1σ'
)
ax.fill_between(
    years, lw_mean - lw_std, lw_mean + lw_std,
    color=C_LW_FILL, alpha=0.35, edgecolor='none', zorder=1,
    label='Leeward ± 1σ'
)

# Sen's slope 趋势线
ax.plot(
    years, ww_trend,
    color=C_WW, linewidth=1.2, linestyle='--', alpha=0.7, zorder=3,
)
ax.plot(
    years, lw_trend,
    color=C_LW, linewidth=1.2, linestyle='--', alpha=0.7, zorder=3,
)

# NDVI 均值折线 + 数据点
ax.plot(
    years, ww_mean,
    color=C_WW, linewidth=2.0, zorder=5,
    marker='o', markersize=6.5,
    markerfacecolor='white', markeredgewidth=1.8, markeredgecolor=C_WW,
    label='Windward mean NDVI'
)
ax.plot(
    years, lw_mean,
    color=C_LW, linewidth=2.0, zorder=5,
    marker='s', markersize=6.5,
    markerfacecolor='white', markeredgewidth=1.8, markeredgecolor=C_LW,
    label='Leeward mean NDVI'
)

# --- Annotation box ---
def fmt_annotation(label, s):
    sig = '*' if s['significant'] else 'n.s.'
    return (f"{label}: Sen's slope = {s['slope'] * 1000:+.3f}"
            f"×10⁻³ yr⁻¹  {sig}  "
            f"(τ = {s['tau']:.3f}, p = {s['p_value']:.3f})")

annotation = fmt_annotation('Windward', ww_stats) + '\n' + fmt_annotation('Leeward', lw_stats)

ax.text(
    0.03, 0.96, annotation,
    transform=ax.transAxes,
    fontsize=8.5,
    verticalalignment='top',
    linespacing=1.5,
    bbox=dict(
        boxstyle='round,pad=0.4',
        facecolor='white',
        edgecolor='#BBBBBB',
        alpha=0.88
    ),
    zorder=6
)

# --- Axes formatting ---
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('NDVI', fontsize=12)
ax.xaxis.set_major_locator(mticker.FixedLocator(years))
ax.xaxis.set_minor_locator(mticker.MultipleLocator(1))

# Y轴留出上方空间给annotation
all_upper = np.concatenate([ww_mean + ww_std, lw_mean + lw_std])
all_lower = np.concatenate([ww_mean - ww_std, lw_mean - lw_std])
y_lo, y_hi = all_lower.min(), all_upper.max()
y_pad = (y_hi - y_lo)
ax.set_ylim(y_lo - y_pad * 0.08, y_hi + y_pad * 0.35)
ax.set_xlim(years[0] - 0.4, years[-1] + 0.4)

# 网格 + spine
ax.yaxis.grid(True, linestyle='--', linewidth=0.4, alpha=0.5, color='grey')
ax.set_axisbelow(True)
ax.spines[['top', 'right']].set_visible(False)

# 图例
ax.legend(
    loc='lower right',
    fontsize=8.5,
    framealpha=0.88,
    edgecolor='#CCCCCC',
    ncol=2,
    columnspacing=1.2,
    handlelength=2.2,
)

# --- Save ---
plt.tight_layout()
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.05)
print(f'\nFigure saved to: {out_path}')
plt.show()