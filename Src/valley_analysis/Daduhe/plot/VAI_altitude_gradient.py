# @Author  : ChaoQiezi
# @Time    : 2026/4/27 下午8:39
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_altitude_gradient.py

"""
This script is used to 绘制不同高程梯度下VAI的变化图

布局 (上中下三面板):
  上方主面板(a): VAI随高程变化曲线, 含±1σ阴影, VAI=0参考线
                 关键科学问题: 在哪个高程VAI发生反转?
  中间面板(b):  各高程带中 VAI>0 vs VAI<0 的比例 (堆叠柱状图)
                 直观展示迎风坡/背风坡优势的高程分布
  下方面板(c):  各高程带网格数量 (数据可靠性)

三个面板共享X轴(高程)

输入:
  - Excel表格 (由 vai_elevation_gradient_stats.py 生成)
输出:
  - 出版质量的高程梯度图 (中文标注)
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
in_path = r'E:\GeoProjects\dry_hot_valley\Daduhe\Result\Table\VAI_altitude_gradient.xlsx'
out_path = r'E:\GeoProjects\dry_hot_valley\Daduhe\Result\Chart\VAI_altitude_gradient.png'

# ============================================================
# 1. Read data
# ============================================================
df = pd.read_excel(in_path)

elev = df['elev_center'].values
vai_mean = df['vai_mean'].values
vai_std = df['vai_std'].values
vai_median = df['vai_median'].values
pct_gt0 = df['pct_gt0'].values    # % 迎风坡更绿
pct_lt0 = df['pct_lt0'].values    # % 背风坡更绿
count = df['count'].values

# 过滤: 仅保留有数据的高程带
valid = count > 0
elev = elev[valid]
vai_mean, vai_std, vai_median = vai_mean[valid], vai_std[valid], vai_median[valid]
pct_gt0, pct_lt0 = pct_gt0[valid], pct_lt0[valid]
count = count[valid]

elev_bin_width = np.diff(df['elev_lo'].values[:2])[0] if len(df) > 1 else 100

print(f'高程范围: {elev.min():.0f} – {elev.max():.0f} m')
print(f'有效高程带: {valid.sum()} / {len(valid)}')

# 寻找VAI=0交叉点 (从迎风更绿穿越到背风更绿的高程)
crossover_idx = np.where(np.diff(np.sign(vai_mean)))[0]
if len(crossover_idx) > 0:
    for ci in crossover_idx:
        e1, e2 = elev[ci], elev[ci + 1]
        g1, g2 = vai_mean[ci], vai_mean[ci + 1]
        if g2 != g1:
            crossover_elev = e1 + (0.0 - g1) / (g2 - g1) * (e2 - e1)
            print(f'VAI = 0 反转点位于 ~{crossover_elev:.0f} m')

# ============================================================
# 2. Plot
# ============================================================
# --- 中文字体支持 ---
plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei', 'STHeiti', 'WenQuanYi Micro Hei',
                        'Noto Sans CJK SC', 'sans-serif'],
    'font.family': 'sans-serif',
    'axes.unicode_minus': False,   # 解决负号显示为方块的问题
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
})

# --- 配色 ---
C_WW = '#4393C3'     # 蓝色 = VAI > 0 迎风坡更绿
C_LW = '#D6604D'     # 红色 = VAI < 0 背风坡更绿
C_MEAN = '#333333'   # 均值曲线

# --- 图幅布局 ---
fig = plt.figure(figsize=(14, 7.5))
gs = GridSpec(
    3, 1, height_ratios=[3.5, 1.5, 0.8],
    hspace=0.06,
    left=0.06, right=0.97, bottom=0.08, top=0.97,
)

# ====== 面板 (a): VAI 随高程变化 ======
ax_main = fig.add_subplot(gs[0])

# ±1σ 阴影
ax_main.fill_between(
    elev, vai_mean - vai_std, vai_mean + vai_std,
    color='#888888', alpha=0.12, edgecolor='none', zorder=1,
)

# VAI=0 参考线 (关键阈值)
ax_main.axhline(y=0.0, color='k', linewidth=0.6, linestyle='--', alpha=0.5, zorder=2)
ax_main.text(elev.max() - 50, 0.005, 'VAI = 0', fontsize=9, ha='right',
             va='bottom', color='k', alpha=0.6)

# 背景色: 上方(VAI>0)淡蓝, 下方(VAI<0)淡红
y_lo = min(0.0, np.nanmin(vai_mean - vai_std)) - 0.5
y_hi = max(0.0, np.nanmax(vai_mean + vai_std)) + 0.5
ax_main.fill_between(
    [elev.min(), elev.max()], 0.0, y_hi,
    color=C_WW, alpha=0.03, edgecolor='none', zorder=0,
)
ax_main.fill_between(
    [elev.min(), elev.max()], y_lo, 0.0,
    color=C_LW, alpha=0.03, edgecolor='none', zorder=0,
)

# 均值曲线
ax_main.plot(
    elev, vai_mean,
    color=C_MEAN, linewidth=1.8, zorder=4,
    label='VAI 均值',
)

# 中位数曲线 (虚线, 检验偏度)
ax_main.plot(
    elev, vai_median,
    color=C_MEAN, linewidth=1.0, linestyle=':', alpha=0.6, zorder=3,
    label='VAI 中位数',
)

# 稀疏标记点
n_show = max(1, len(elev) // 16)
idx = np.arange(len(elev))[::n_show]
ax_main.scatter(
    elev[idx], vai_mean[idx],
    s=22, zorder=5,
    facecolors='white', edgecolors=C_MEAN, linewidths=1.2,
    marker='o',
)

# # 交叉点标注
# for ci in crossover_idx:
#     e1, e2 = elev[ci], elev[ci + 1]
#     g1, g2 = vai_mean[ci], vai_mean[ci + 1]
#     if g2 != g1:
#         ce = e1 + (0.0 - g1) / (g2 - g1) * (e2 - e1)
#         ax_main.axvline(x=ce, color='#E07B39', linewidth=0.8,
#                         linestyle='-.', alpha=0.7, zorder=3)
#         ax_main.annotate(
#             f'~{ce:.0f} m',
#             xy=(ce, 0.0), xytext=(ce + 150, y_hi - 0.5),
#             fontsize=9, color='#E07B39',
#             arrowprops=dict(arrowstyle='->', color='#E07B39', lw=0.8),
#             ha='left', va='top',
#         )

# 坐标轴
ax_main.set_ylabel('VAI (%)', fontsize=12)
ax_main.set_ylim(y_lo, y_hi)
ax_main.set_xlim(elev.min(), elev.max())
ax_main.tick_params(labelbottom=False)
ax_main.tick_params(which='both', top=True, right=True)
ax_main.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax_main.set_axisbelow(True)

# 方向标注 (面板内)
ax_main.text(0.99, 0.96, '迎风坡更绿 ↑', transform=ax_main.transAxes,
             fontsize=8.5, ha='right', va='top', color=C_WW, fontstyle='italic')
ax_main.text(0.99, 0.04, '背风坡更绿 ↓', transform=ax_main.transAxes,
             fontsize=8.5, ha='right', va='bottom', color=C_LW, fontstyle='italic')

# 图例
legend_handles = [
    Line2D([0], [0], color=C_MEAN, linewidth=1.8,
           marker='o', markersize=4.5, markerfacecolor='white',
           markeredgewidth=1.2, markeredgecolor=C_MEAN,
           label='VAI 均值 (± 1σ)'),
    Line2D([0], [0], color=C_MEAN, linewidth=1.0, linestyle=':',
           alpha=0.6, label='VAI 中位数'),
]
ax_main.legend(
    handles=legend_handles,
    loc='lower left',
    fontsize=9, framealpha=0.88, edgecolor='#CCCCCC',
    handlelength=2.5,
)

ax_main.text(0.01, 0.97, '(a)', transform=ax_main.transAxes,
             fontsize=12, fontweight='bold', va='top')

# ====== 面板 (b): 百分比堆叠柱状图 ======
ax_pct = fig.add_subplot(gs[1], sharex=ax_main)

bar_w = elev_bin_width * 0.85

# 堆叠: 底部=VAI<0(红), 顶部=VAI>0(蓝), 总和=100%
ax_pct.bar(
    elev, pct_lt0,
    width=bar_w, color=C_LW, alpha=0.65, edgecolor='none',
    label='VAI < 0 (背风坡更绿)',
    zorder=2,
)
ax_pct.bar(
    elev, pct_gt0, bottom=pct_lt0,
    width=bar_w, color=C_WW, alpha=0.65, edgecolor='none',
    label='VAI ≥ 0 (迎风坡更绿)',
    zorder=2,
)

# 50% 参考线
ax_pct.axhline(y=50, color='k', linewidth=0.5, linestyle='--', alpha=0.4, zorder=1)

ax_pct.set_ylabel('比例 (%)', fontsize=11)
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

# ====== 面板 (c): 网格数量 ======
ax_count = fig.add_subplot(gs[2], sharex=ax_main)

ax_count.bar(
    elev, count,
    width=bar_w, color='#888888', alpha=0.45, edgecolor='none', zorder=2,
)

ax_count.set_xlabel('高程 (m)', fontsize=12)
ax_count.set_ylabel('网格数量', fontsize=11)
ax_count.tick_params(which='both', top=True, right=True)

ax_count.text(0.01, 0.88, '(c)', transform=ax_count.transAxes,
              fontsize=12, fontweight='bold', va='top')

# --- 保存 ---
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'图片已保存至: {out_path}')
plt.show()
