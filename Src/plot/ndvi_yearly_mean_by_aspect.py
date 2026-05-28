# @Author  : ChaoQiezi
# @Time    : 2026/3/28 下午3:10
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_ward_time_series.py

"""
This script is used to 绘制迎风坡与背风坡NDVI时间序列变化图

输入:
  - Excel表格 (由 ndvi_windward_leeward_stats.py 生成)
输出:
  - 出版质量的时间序列折线图 (含±1σ, 趋势线, 差值子图)
"""

import warnings

from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats
warnings.filterwarnings('ignore')

# 0. Configuration
in_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_windward_leeward_yearly.xlsx'
out_path = r'G:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_ward_time_series.png'
# 1. Read data
df = pd.read_excel(in_path)
years = df['year'].values
ww_mean = df['windward_mean'].values
ww_std = df['windward_std'].values
lw_mean = df['leeward_mean'].values
lw_std = df['leeward_std'].values
# 2. Trend analysis (OLS linear regression)
def linear_trend(x, y):
    """返回斜率, 截距, R², p值"""
    slope, intercept, r, p, se = stats.linregress(x, y)
    return slope, intercept, r ** 2, p
ww_slope, ww_inter, ww_r2, ww_p = linear_trend(years, ww_mean)
lw_slope, lw_inter, lw_r2, lw_p = linear_trend(years, lw_mean)
# 趋势线拟合值
years_fit = np.linspace(years.min() - 0.3, years.max() + 0.3, 100)
ww_fit = ww_slope * years_fit + ww_inter
lw_fit = lw_slope * years_fit + lw_inter
# 3. Plot
# Academic style
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
    'xtick.top': True,
    'ytick.right': True,
    'legend.fontsize': 9,
    'legend.framealpha': 0.9,
    'legend.edgecolor': '#CCCCCC',
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'mathtext.fontset': 'stix',
})
# Colors
C_WW = '#D94E4E'   # 暖红色 — 迎风坡
C_LW = '#3A7CA5'   # 冷蓝色 — 背风坡
C_WW_FILL = '#F2C4C4'
C_LW_FILL = '#B8D4E3'
# Figure layout: 主图 + 差值子图
fig = plt.figure(figsize=(8, 5.5))
gs = GridSpec(
    2, 1, height_ratios=[3, 1],
    hspace=0.08,
    left=0.10, right=0.95, bottom=0.10, top=0.95
)
# Panel (a): NDVI time series
ax_main = fig.add_subplot(gs[0])
# ±1σ 阴影
ax_main.fill_between(
    years, ww_mean - ww_std, ww_mean + ww_std,
    color=C_WW_FILL, alpha=0.8, edgecolor='none', zorder=1
)
ax_main.fill_between(
    years, lw_mean - lw_std, lw_mean + lw_std,
    color=C_LW_FILL, alpha=0.8, edgecolor='none', zorder=1
)
# 均值折线 + 数据点
ax_main.plot(years, ww_mean, color=C_WW, linewidth=1.5, zorder=3,
             marker='o', markersize=5, markeredgecolor='white',
             markeredgewidth=0.8, label='Windward')
ax_main.plot(years, lw_mean, color=C_LW, linewidth=1.5, zorder=3,
             marker='s', markersize=5, markeredgecolor='white',
             markeredgewidth=0.8, label='Leeward')
# 趋势线
def p_to_stars(p):
    """将p值转换为显著性星号标记"""
    if p < 0.001:
        return '***'
    elif p < 0.01:
        return '**'
    elif p < 0.05:
        return '*'
    return ''
ax_main.plot(years_fit, ww_fit, color=C_WW, linewidth=1.0,
             linestyle='--', alpha=0.7, zorder=2)
ax_main.plot(years_fit, lw_fit, color=C_LW, linewidth=1.0,
             linestyle='--', alpha=0.7, zorder=2)
# 趋势线标注 (slope/decade, R², 显著性)
ww_trend_text = (f'Windward: {ww_slope * 10:+.4f}/decade '
                 f'($R^2$={ww_r2:.2f}{p_to_stars(ww_p)})')
lw_trend_text = (f'Leeward: {lw_slope * 10:+.4f}/decade '
                 f'($R^2$={lw_r2:.2f}{p_to_stars(lw_p)})')
ax_main.text(0.02, 0.06, ww_trend_text, transform=ax_main.transAxes,
             fontsize=8.5, color=C_WW, va='bottom',
             bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1))
ax_main.text(0.02, 0.015, lw_trend_text, transform=ax_main.transAxes,
             fontsize=8.5, color=C_LW, va='bottom',
             bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1))
# 坐标轴
ax_main.set_ylabel('NDVI', fontsize=12)
ax_main.set_xlim(years.min() - 0.5, years.max() + 0.5)
ax_main.xaxis.set_major_locator(mticker.FixedLocator(years))
ax_main.set_xticklabels([])  # x标签在下方子图显示
ax_main.legend(loc='upper right', frameon=True)
ax_main.grid(axis='y', linewidth=0.3, linestyle=':', alpha=0.5)
# Panel label
ax_main.text(0.02, 0.97, '(a)', transform=ax_main.transAxes,
             fontsize=12, fontweight='bold', va='top')
# Panel (b): NDVI difference (windward - leeward)
ax_diff = fig.add_subplot(gs[1], sharex=ax_main)
diff = ww_mean - lw_mean
# 柱状图: 正值(迎风>背风)用暖色, 负值用冷色
bar_colors = [C_WW if d >= 0 else C_LW for d in diff]
ax_diff.bar(years, diff, width=0.6, color=bar_colors, edgecolor='white',
            linewidth=0.5, alpha=0.8, zorder=2)
# 零线
ax_diff.axhline(y=0, color='k', linewidth=0.5, linestyle='-', zorder=1)
# 坐标轴
ax_diff.set_xlabel('Year', fontsize=12)
ax_diff.set_ylabel('$\Delta$NDVI', fontsize=12)
ax_diff.xaxis.set_major_locator(mticker.FixedLocator(years))
ax_diff.set_xticklabels([str(y) for y in years])
ax_diff.grid(axis='y', linewidth=0.3, linestyle=':', alpha=0.5)
# 对称Y轴
max_abs = max(abs(diff.min()), abs(diff.max())) * 1.3
ax_diff.set_ylim(-max_abs, max_abs)
# Panel label
ax_diff.text(0.02, 0.92, '(b)', transform=ax_diff.transAxes,
             fontsize=12, fontweight='bold', va='top')
# Save
import os
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.1)
print(f'Figure saved to: {out_path}')
plt.show()