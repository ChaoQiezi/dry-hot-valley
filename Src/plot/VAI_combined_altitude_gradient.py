# @Author  : ChaoQiezi
# @Time    : 2026/5/5
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: VAI_combined_altitude_gradient.py

"""
四条河谷 VAI 高程梯度折线图叠加绘制。

输入:
  - 四个河谷的 VAI_altitude_gradient.xlsx
输出:
  - 出版质量的四河谷 VAI 对比图 (单面板, 仅均值折线, 无标准差阴影)
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
VALLEYS = {
    '岷江': r'E:\GeoProjects\dry_hot_valley\Minjiang\Result\Table\altitude\VAI_altitude_gradient.xlsx',
    '大渡河': r'E:\GeoProjects\dry_hot_valley\Daduhe\Result\Table\VAI_altitude_gradient.xlsx',
    '金沙江': r'E:\GeoProjects\dry_hot_valley\Jinshajiang\Result\Table\VAI_altitude_gradient.xlsx',
    '雅砻江': r'E:\GeoProjects\dry_hot_valley\Yalongjiang\Result\Table\VAI_altitude_gradient.xlsx',
}

COLORS = {
    '岷江': '#1B9E77',
    '大渡河': '#D95F02',
    '金沙江': '#7570B3',
    '雅砻江': '#E7298A',
}

# OUT_DIR = os.path.dirname(os.path.abspath(__file__))
# OUT_PATH = os.path.join(OUT_DIR, 'VAI_combined_altitude_gradient.png')
OUT_PATH = r'E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_combined_altitude_gradient.png'

# ============================================================
# 1. Load data
# ============================================================
data = {}
y_lo_all, y_hi_all = 0.0, 0.0

for name, path in VALLEYS.items():
    df = pd.read_excel(path)
    valid = df['count'].values > 0
    elev = df['elev_center'].values[valid]
    vai_mean = df['vai_mean'].values[valid]
    data[name] = {'elev': elev, 'vai_mean': vai_mean}
    y_lo_all = min(y_lo_all, np.nanmin(vai_mean))
    y_hi_all = max(y_hi_all, np.nanmax(vai_mean))
    print(f'{name}: {len(elev)} bins, VAI=[{np.nanmin(vai_mean):.2f}, {np.nanmax(vai_mean):.2f}]')

y_lo_all = y_lo_all - 0.5
y_hi_all = y_hi_all + 0.5

# ============================================================
# 2. Plot
# ============================================================
plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei', 'STHeiti', 'WenQuanYi Micro Hei',
                        'Noto Sans CJK SC', 'sans-serif'],
    'font.family': 'sans-serif',
    'axes.unicode_minus': False,
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
})

fig, ax = plt.subplots(figsize=(10, 6))

# VAI=0 参考线
ax.axhline(y=0.0, color='k', linewidth=0.6, linestyle='--', alpha=0.4, zorder=1)

# 背景分区色: VAI>0 淡蓝, VAI<0 淡红
ax.fill_between([0, 6000], 0.0, y_hi_all, color='#4393C3', alpha=0.03, edgecolor='none', zorder=0)
ax.fill_between([0, 6000], y_lo_all, 0.0, color='#D6604D', alpha=0.03, edgecolor='none', zorder=0)

# 四条河谷 VAI 均值折线
for name, d in data.items():
    ax.plot(
        d['elev'], d['vai_mean'],
        color=COLORS[name], linewidth=2.0, zorder=4,
        label=name,
    )
    # 稀疏标记点
    n_show = max(1, len(d['elev']) // 16)
    idx = np.arange(len(d['elev']))[::n_show]
    ax.scatter(
        d['elev'][idx], d['vai_mean'][idx],
        s=22, zorder=5,
        facecolors='white', edgecolors=COLORS[name], linewidths=1.2,
        marker='o',
    )

# 方向标注
ax.text(0.99, 0.96, '迎风坡更绿 ↑', transform=ax.transAxes,
        fontsize=9, ha='right', va='top', color='#4393C3', fontstyle='italic')
ax.text(0.99, 0.04, '背风坡更绿 ↓', transform=ax.transAxes,
        fontsize=9, ha='right', va='bottom', color='#D6604D', fontstyle='italic')

# 坐标轴
ax.set_ylabel('VAI (%)', fontsize=13)
ax.set_xlabel('高程 (m)', fontsize=13)
ax.set_ylim(y_lo_all, y_hi_all)
ax.tick_params(which='both', top=True, right=True)
ax.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax.set_axisbelow(True)

# 图例
ax.legend(
    fontsize=10, framealpha=0.88, edgecolor='#CCCCCC',
    handlelength=2.5, loc='lower left',
)

# 输出
fig.savefig(OUT_PATH, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'\nSaved: {OUT_PATH}')
plt.show()
