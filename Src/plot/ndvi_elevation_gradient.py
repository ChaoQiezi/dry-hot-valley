# @Author  : ChaoQiezi
# @Time    : 2026/3/29 上午11:05
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_elevation_gradient.py

"""
This script is used to 绘制不同高程梯度下迎风坡与背风坡NDVI变化图

布局:
  左侧主面板: NDVI随高程变化曲线 (迎风坡 vs 背风坡), 含±1σ阴影
  右侧窄面板: 各高程带像元数量分布 (水平柱状图), 反映数据可靠性

输入:
  - Excel表格 (由 ndvi_elevation_gradient_stats.py 生成)
输出:
  - 出版质量的高程梯度图
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
in_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_elevation_gradient.xlsx'
out_path = r'G:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_elevation_gradient.png'

# ============================================================
# 1. Read data
# ============================================================
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

# 各侧有效掩膜 (用于绘图时避免NaN断线)
ww_valid = ww_count > 0
lw_valid = lw_count > 0

print(f'Elevation range: {elev.min():.0f} – {elev.max():.0f} m')
print(f'Valid bins: {valid.sum()} / {len(valid)}')

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

# --- Colors (与时间序列图一致: 绿=迎风湿润, 棕橙=背风干热) ---
C_WW = '#2E7D52'
C_WW_FILL = '#A8D5BA'
C_LW = '#C2652A'
C_LW_FILL = '#EABB8D'
C_COUNT_WW = '#2E7D52'
C_COUNT_LW = '#C2652A'

# --- Figure layout ---
fig = plt.figure(figsize=(10, 6))
gs = GridSpec(
    1, 2, width_ratios=[4, 1],
    wspace=0.05,
    left=0.09, right=0.95, bottom=0.11, top=0.95
)

# ====== Panel (a): NDVI vs Elevation ======
ax_main = fig.add_subplot(gs[0, 0])

# ±1σ 阴影
ax_main.fill_betweenx(
    elev[ww_valid],
    (ww_mean - ww_std)[ww_valid],
    (ww_mean + ww_std)[ww_valid],
    color=C_WW_FILL, alpha=0.35, edgecolor='none', zorder=1,
)
ax_main.fill_betweenx(
    elev[lw_valid],
    (lw_mean - lw_std)[lw_valid],
    (lw_mean + lw_std)[lw_valid],
    color=C_LW_FILL, alpha=0.35, edgecolor='none', zorder=1,
)

# 均值曲线
ax_main.plot(
    ww_mean[ww_valid], elev[ww_valid],
    color=C_WW, linewidth=1.8, zorder=4,
    label='Windward',
)
ax_main.plot(
    lw_mean[lw_valid], elev[lw_valid],
    color=C_LW, linewidth=1.8, zorder=4,
    label='Leeward',
)

# 数据点标记 (稀疏显示, 避免密集; 每隔N个bin标一个点)
n_show = max(1, len(elev) // 15)  # 约15个标记点
for mask, color, marker in [(ww_valid, C_WW, 'o'), (lw_valid, C_LW, 's')]:
    idx = np.where(mask)[0][::n_show]
    ax_main.scatter(
        ww_mean[idx] if marker == 'o' else lw_mean[idx],
        elev[idx],
        s=22, zorder=5,
        facecolors='white', edgecolors=color, linewidths=1.2,
        marker=marker,
    )

# 坐标轴
ax_main.set_xlabel('NDVI', fontsize=12)
ax_main.set_ylabel('Elevation (m)', fontsize=12)
ax_main.set_ylim(elev.min(), elev.max())
# X轴: 自适应
all_vals = np.concatenate([
    (ww_mean - ww_std)[ww_valid],
    (ww_mean + ww_std)[ww_valid],
    (lw_mean - lw_std)[lw_valid],
    (lw_mean + lw_std)[lw_valid],
])
x_lo = max(0, np.nanmin(all_vals) - 0.03)
x_hi = min(1, np.nanmax(all_vals) + 0.03)
ax_main.set_xlim(x_lo, x_hi)

ax_main.tick_params(which='both', top=True, right=True)
ax_main.xaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax_main.set_axisbelow(True)

# 图例
ax_main.legend(
    loc='lower left',
    fontsize=9.5,
    framealpha=0.88,
    edgecolor='#CCCCCC',
    handlelength=2.0,
)

# Panel label
ax_main.text(
    0.02, 0.98, '(a)',
    transform=ax_main.transAxes,
    fontsize=12, fontweight='bold', va='top',
)

# ====== Panel (b): Pixel count distribution ======
ax_count = fig.add_subplot(gs[0, 1], sharey=ax_main)

# 水平柱状图 (背靠背: 迎风坡向右, 背风坡向左)
bar_h = np.diff(df['elev_lo'].values[:2])[0] * 0.8 if len(df) > 1 else 80  # 柱宽略小于bin宽

# 归一化像元数 (便于显示, 避免数值过大)
max_count = max(ww_count.max(), lw_count.max())
ww_norm = ww_count / max_count
lw_norm = lw_count / max_count

ax_count.barh(
    elev[ww_valid], ww_norm[ww_valid],
    height=bar_h, color=C_COUNT_WW, alpha=0.5, edgecolor='none',
    label='Windward', zorder=2,
)
ax_count.barh(
    elev[lw_valid], -lw_norm[lw_valid],
    height=bar_h, color=C_COUNT_LW, alpha=0.5, edgecolor='none',
    label='Leeward', zorder=2,
)

# 零线
ax_count.axvline(x=0, color='k', linewidth=0.4, zorder=1)

# 坐标轴
ax_count.set_xlabel('Pixel count\n(normalized)', fontsize=10)
ax_count.tick_params(labelleft=False)  # Y轴标签由Panel (a) 提供
ax_count.tick_params(which='both', top=True, right=True)
ax_count.set_xlim(-1.15, 1.15)

# X轴刻度简化 (只标0)
ax_count.set_xticks([0])
ax_count.set_xticklabels(['0'])
# 在两端标注方向
ax_count.text(
    0.85, 0.02, 'WW', transform=ax_count.transAxes,
    fontsize=8, color=C_WW, ha='center', va='bottom', fontweight='bold',
)
ax_count.text(
    0.15, 0.02, 'LW', transform=ax_count.transAxes,
    fontsize=8, color=C_LW, ha='center', va='bottom', fontweight='bold',
)

# Panel label
ax_count.text(
    0.08, 0.98, '(b)',
    transform=ax_count.transAxes,
    fontsize=12, fontweight='bold', va='top',
)

# --- Save ---
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'Figure saved to: {out_path}')
plt.show()