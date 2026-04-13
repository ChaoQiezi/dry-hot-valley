# @Author  : ChaoQiezi
# @Time    : 2026/4/3
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: plot_gai_elevation_gradient.py

"""
This script is used to 绘制不同高程梯度下GAI的变化图

布局 (上中下三面板):
  上方主面板(a): GAI随高程变化曲线, 含±1σ阴影, GAI=1参考线
                 关键科学问题: 在哪个高程GAI发生反转?
  中间面板(b):  各高程带中 GAI>1 vs GAI<1 的比例 (堆叠柱状图)
                 直观展示迎风坡/背风坡优势的高程分布
  下方面板(c):  各高程带网格数量 (数据可靠性)

三个面板共享X轴(高程)

输入:
  - Excel表格 (由 gai_elevation_gradient_stats.py 生成)
输出:
  - 出版质量的高程梯度图
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
in_path = r'E:\GeoProjects\dry_hot_valley\Output\Table\GAI_elevation_gradient.xlsx'
out_path = r'E:\GeoProjects\dry_hot_valley\Result\Chart\GAI_elevation_gradient.png'

# ============================================================
# 1. Read data
# ============================================================
df = pd.read_excel(in_path)

elev = df['elev_center'].values
gai_mean = df['gai_mean'].values
gai_std = df['gai_std'].values
gai_median = df['gai_median'].values
pct_gt1 = df['pct_gt1'].values    # % windward greener
pct_lt1 = df['pct_lt1'].values    # % leeward greener
count = df['count'].values

# 过滤: 仅保留有数据的高程带
valid = count > 0
elev = elev[valid]
gai_mean, gai_std, gai_median = gai_mean[valid], gai_std[valid], gai_median[valid]
pct_gt1, pct_lt1 = pct_gt1[valid], pct_lt1[valid]
count = count[valid]

elev_bin_width = np.diff(df['elev_lo'].values[:2])[0] if len(df) > 1 else 100

print(f'Elevation range: {elev.min():.0f} – {elev.max():.0f} m')
print(f'Valid bins: {valid.sum()} / {len(valid)}')

# 寻找GAI=1交叉点 (从上方穿越到下方的高程)
crossover_idx = np.where(np.diff(np.sign(gai_mean - 1)))[0]
if len(crossover_idx) > 0:
    # 线性插值精确交叉点
    for ci in crossover_idx:
        e1, e2 = elev[ci], elev[ci + 1]
        g1, g2 = gai_mean[ci], gai_mean[ci + 1]
        if g2 != g1:
            crossover_elev = e1 + (1.0 - g1) / (g2 - g1) * (e2 - e1)
            print(f'GAI = 1 crossover at ~{crossover_elev:.0f} m')

# ============================================================
# 2. Plot
# ============================================================
# --- Academic style ---
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

# --- Colors ---
C_WW = '#4393C3'     # 蓝色 = GAI > 1 迎风坡更绿 (与GAI空间图一致)
C_LW = '#D6604D'     # 红色 = GAI < 1 背风坡更绿
C_MEAN = '#333333'   # 均值曲线

# --- Figure layout ---
fig = plt.figure(figsize=(14, 7.5))
gs = GridSpec(
    3, 1, height_ratios=[3.5, 1.5, 0.8],
    hspace=0.06,
    left=0.06, right=0.97, bottom=0.08, top=0.97,
)

# ====== Panel (a): GAI vs Elevation ======
ax_main = fig.add_subplot(gs[0])

# ±1σ 阴影
ax_main.fill_between(
    elev, gai_mean - gai_std, gai_mean + gai_std,
    color='#888888', alpha=0.12, edgecolor='none', zorder=1,
)

# GAI=1 参考线 (关键阈值)
ax_main.axhline(y=1.0, color='k', linewidth=0.6, linestyle='--', alpha=0.5, zorder=2)
ax_main.text(elev.max() - 50, 1.005, 'GAI = 1', fontsize=9, ha='right',
             va='bottom', color='k', alpha=0.6)

# 背景色: 上方(GAI>1)淡蓝, 下方(GAI<1)淡红
y_lo = max(0.4, np.nanmin(gai_mean - gai_std) - 0.05)
y_hi = np.nanmax(gai_mean + gai_std) + 0.05
ax_main.fill_between(
    [elev.min(), elev.max()], 1.0, y_hi,
    color=C_WW, alpha=0.03, edgecolor='none', zorder=0,
)
ax_main.fill_between(
    [elev.min(), elev.max()], y_lo, 1.0,
    color=C_LW, alpha=0.03, edgecolor='none', zorder=0,
)

# 均值曲线
ax_main.plot(
    elev, gai_mean,
    color=C_MEAN, linewidth=1.8, zorder=4,
    label='GAI mean',
)

# 中位数曲线 (虚线, 检验偏度)
ax_main.plot(
    elev, gai_median,
    color=C_MEAN, linewidth=1.0, linestyle=':', alpha=0.6, zorder=3,
    label='GAI median',
)

# 稀疏标记点
n_show = max(1, len(elev) // 16)
idx = np.arange(len(elev))[::n_show]
ax_main.scatter(
    elev[idx], gai_mean[idx],
    s=22, zorder=5,
    facecolors='white', edgecolors=C_MEAN, linewidths=1.2,
    marker='o',
)

# 交叉点标注
for ci in crossover_idx:
    e1, e2 = elev[ci], elev[ci + 1]
    g1, g2 = gai_mean[ci], gai_mean[ci + 1]
    if g2 != g1:
        ce = e1 + (1.0 - g1) / (g2 - g1) * (e2 - e1)
        ax_main.axvline(x=ce, color='#E07B39', linewidth=0.8,
                        linestyle='-.', alpha=0.7, zorder=3)
        ax_main.annotate(
            f'~{ce:.0f} m',
            xy=(ce, 1.0), xytext=(ce + 150, y_hi - 0.05),
            fontsize=9, color='#E07B39',
            arrowprops=dict(arrowstyle='->', color='#E07B39', lw=0.8),
            ha='left', va='top',
        )

# 坐标轴
ax_main.set_ylabel('GAI', fontsize=12)
ax_main.set_ylim(y_lo, y_hi)
ax_main.set_xlim(elev.min(), elev.max())
ax_main.tick_params(labelbottom=False)
ax_main.tick_params(which='both', top=True, right=True)
ax_main.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax_main.set_axisbelow(True)

# 方向标注 (面板内)
ax_main.text(0.99, 0.96, 'Windward greener ↑', transform=ax_main.transAxes,
             fontsize=8.5, ha='right', va='top', color=C_WW, fontstyle='italic')
ax_main.text(0.99, 0.04, 'Leeward greener ↓', transform=ax_main.transAxes,
             fontsize=8.5, ha='right', va='bottom', color=C_LW, fontstyle='italic')

# 图例
legend_handles = [
    Line2D([0], [0], color=C_MEAN, linewidth=1.8,
           marker='o', markersize=4.5, markerfacecolor='white',
           markeredgewidth=1.2, markeredgecolor=C_MEAN,
           label='GAI mean (± 1σ)'),
    Line2D([0], [0], color=C_MEAN, linewidth=1.0, linestyle=':',
           alpha=0.6, label='GAI median'),
]
ax_main.legend(
    handles=legend_handles,
    loc='upper left',
    fontsize=9, framealpha=0.88, edgecolor='#CCCCCC',
    handlelength=2.5,
)

ax_main.text(0.01, 0.97, '(a)', transform=ax_main.transAxes,
             fontsize=12, fontweight='bold', va='top')

# ====== Panel (b): Percentage stacked bars ======
ax_pct = fig.add_subplot(gs[1], sharex=ax_main)

bar_w = elev_bin_width * 0.85

# 堆叠: 底部=GAI<1(红), 顶部=GAI>1(蓝), 总和=100%
ax_pct.bar(
    elev, pct_lt1,
    width=bar_w, color=C_LW, alpha=0.65, edgecolor='none',
    label='GAI < 1 (leeward greener)',
    zorder=2,
)
ax_pct.bar(
    elev, pct_gt1, bottom=pct_lt1,
    width=bar_w, color=C_WW, alpha=0.65, edgecolor='none',
    label='GAI ≥ 1 (windward greener)',
    zorder=2,
)

# 50% 参考线
ax_pct.axhline(y=50, color='k', linewidth=0.5, linestyle='--', alpha=0.4, zorder=1)

ax_pct.set_ylabel('Proportion (%)', fontsize=11)
ax_pct.set_ylim(0, 100)
ax_pct.set_yticks([0, 25, 50, 75, 100])
ax_pct.tick_params(labelbottom=False)
ax_pct.tick_params(which='both', top=True, right=True)

ax_pct.legend(
    loc='upper right', fontsize=8.5,
    framealpha=0.88, edgecolor='#CCCCCC',
    ncol=2, columnspacing=1.0,
)

ax_pct.text(0.01, 0.93, '(b)', transform=ax_pct.transAxes,
            fontsize=12, fontweight='bold', va='top')

# ====== Panel (c): Grid cell count ======
ax_count = fig.add_subplot(gs[2], sharex=ax_main)

ax_count.bar(
    elev, count,
    width=bar_w, color='#888888', alpha=0.45, edgecolor='none', zorder=2,
)

ax_count.set_xlabel('Elevation (m)', fontsize=12)
ax_count.set_ylabel('Grid cells', fontsize=11)
ax_count.tick_params(which='both', top=True, right=True)

ax_count.text(0.01, 0.88, '(c)', transform=ax_count.transAxes,
              fontsize=12, fontweight='bold', va='top')

# --- Save ---
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'Figure saved to: {out_path}')
plt.show()