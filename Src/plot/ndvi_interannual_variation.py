# @Author  : ChaoQiezi
# @Time    : 2026/3/28 上午11:10
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: plot_ndvi_time_series.py

"""
This script is used to 绘制NDVI年尺度的时间序列变化

除NDVI年均值和标准差外, 还包括MK趋势和Sen率, 并绘制趋势线.
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.ticker as mticker
import pymannkendall as mk

from qiezi.stats import mk_trend_slope

# 准备
in_path = r'E:\GeoProjects\dry_hot_valley\Output\Table\NDVI_yearly_mean.xlsx'
out_path = r'E:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_interannual_variation.png'

# 读取
df = pd.read_excel(in_path, index_col='year')

# MK趋势分析
stats = mk_trend_slope(df['mean'].values)
print('--- Mann-Kendall Trend Test Results ---')
print(f"Trend direction : {stats['trend']}")
print(f"p-value         : {stats['p_value']:.4f}")
print(f"Kendall tau (τ) : {stats['tau']:.4f}")
print(f"Sen's Slope     : {stats['slope']:.6f}  "
      f"(95% CI: {stats['slope_ci_lo']:.6f} ~ {stats['slope_ci_hi']:.6f})")
print(f"Sen's Intercept : {stats['intercept']:.4f}")
print(f"Significant     : {'Yes ✓' if stats['significant'] else 'No ✗'}  (α = 0.05)")

# 绘制准备
years = df.index.values  # [2019, 2020, ..., 2025]
x_idx = np.arange(len(years))  # [0, 1, 2, ..., 6]
trend_line = stats['slope'] * x_idx + stats['intercept']
ci_upper = stats['slope_ci_hi'] * x_idx + stats['intercept']  # slope: 95% CI 上限(CI, confidence interval)
ci_lower = stats['slope_ci_lo'] * x_idx + stats['intercept']  # slope: 95% CI 下限(CI, confidence interval)
sig_marker = '*' if stats['significant'] else 'n.s.'
annotation = (
    f"Sen's slope = {stats['slope']*1000:.3f}×10⁻³ yr⁻¹  {sig_marker}\n"
    f"τ = {stats['tau']:.3f},  p = {stats['p_value']:.3f}"
)
# 绘制
fig, ax = plt.subplots(figsize=(9, 5))
## standard deviation area
ax.fill_between(
    years,
    df['mean'] - df['std'],
    df['mean'] + df['std'],
    color='#4CAF82',
    alpha=0.18,
    label='Mean ± Std (spatial variability)',
    zorder=2
)
## Sen's Slope 95% CI
ax.fill_between(
    years,
    ci_lower,
    ci_upper,
    color='#E07B39',
    alpha=0.15,
    label="Sen's Slope 95% CI",
    zorder=3
)
## Sen's slope line(Trend line)
ax.plot(
    years, trend_line,
    color='#E07B39',
    linewidth=1.8,
    linestyle='--',
    label="Sen's Slope trend",
    zorder=4
)
## NDVI time series
ax.plot(
    years, df['mean'],
    color='#2E7D52',
    linewidth=2.2,
    marker='o',
    markersize=6,
    markerfacecolor='white',
    markeredgewidth=2,
    markeredgecolor='#2E7D52',
    label='Yearly mean NDVI',
    zorder=5
)
## annotation
ax.text(
    0.03, 0.95, annotation,
    transform=ax.transAxes,          # position relative to axes (0–1 range)
    fontsize=9.5,
    verticalalignment='top',
    bbox=dict(
        boxstyle='round,pad=0.4',
        facecolor='white',
        edgecolor='#BBBBBB',
        alpha=0.85
    ),
    zorder=6
)
## axes formatting
### label
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('NDVI', fontsize=12)
ax.set_title('Interannual Variation of NDVI (2019–2025)', fontsize=13, fontweight='bold')
ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
ax.xaxis.set_minor_locator(mticker.MultipleLocator(1))
### Y, X axis limit
y_min = (df['mean'] - df['std']).min()
y_max = (df['mean'] + df['std']).max()
y_pad = (y_max - y_min) * 0.25   # 25% padding so annotation doesn't overlap data
ax.set_ylim(y_min - y_pad * 0.3, y_max + y_pad)
ax.set_xlim(years[0] - 0.3, years[-1] + 0.3)
### general
ax.yaxis.grid(True, linestyle='--', linewidth=0.5, alpha=0.5, color='grey')
ax.set_axisbelow(True)            # grid lines behind data
ax.spines[['top', 'right']].set_visible(False)
ax.legend(
    loc='lower right',
    fontsize=9,
    framealpha=0.85,
    edgecolor='#BBBBBB'
)
plt.tight_layout()
## output
plt.savefig(out_path, dpi=300, bbox_inches='tight')
print(f'\nFigure saved to: {out_path}')
plt.show()
