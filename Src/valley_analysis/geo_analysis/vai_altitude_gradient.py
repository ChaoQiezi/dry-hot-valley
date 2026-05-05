# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:29
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: vai_altitude_gradient.py

"""
This script is used to 
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

VALLEYS = {
    '岷江':   r'E:\GeoProjects\dry_hot_valley\Minjiang\Result\Table\altitude\VAI_altitude_gradient.xlsx',
    '大渡河': r'E:\GeoProjects\dry_hot_valley\Daduhe\Result\Table\VAI_altitude_gradient.xlsx',
    '金沙江': r'E:\GeoProjects\dry_hot_valley\Jinshajiang\Result\Table\VAI_altitude_gradient.xlsx',
    '雅砻江': r'E:\GeoProjects\dry_hot_valley\Yalongjiang\Result\Table\VAI_altitude_gradient.xlsx',
}
COLORS = {
    '岷江':   '#1B9E77',
    '大渡河': '#D95F02',
    '金沙江': '#7570B3',
    '雅砻江': '#E7298A',
}
OUT_DIR = r'E:\GeoProjects\dry_hot_valley\Result\Chart\altitude'
os.makedirs(OUT_DIR, exist_ok=True)

# 关键阈值参数
MIN_COUNT_PER_BIN = 10        # 每个海拔 bin 至少要有的网格数(剔除低样本噪声)
HIGH_CONF_LOW = 1500          # 高置信海拔区间下界
HIGH_CONF_HIGH = 4500         # 高置信海拔区间上界(再高积雪不对称污染信号)

plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei', 'STHeiti', 'WenQuanYi Micro Hei',
                        'Noto Sans CJK SC', 'sans-serif'],
    'font.family': 'sans-serif',
    'axes.unicode_minus': False,
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
})


def load_valley_data(min_count=MIN_COUNT_PER_BIN):
    """加载四河数据,过滤低样本 bin。
    返回: dict, 每个河谷一个 DataFrame, 列: elev_center, vai_mean, vai_q25, vai_q75, count
    """
    data = {}
    for name, path in VALLEYS.items():
        df = pd.read_excel(path)
        df = df[df['count'] >= min_count].reset_index(drop=True)
        data[name] = df
        print(f'{name}: {len(df)} bins kept (count >= {min_count}), '
              f'elev range [{df["elev_center"].min():.0f}, {df["elev_center"].max():.0f}]')
    return data


"""
Fig 1: 四河 VAI 沿海拔剖面对比(改进版)
- count >= 30 过滤
- 25/75 分位数阴影
- LOWESS 平滑
- 反转点自动检测并标注
- 底部子图显示样本量
"""

from statsmodels.nonparametric.smoothers_lowess import lowess
from scipy.interpolate import interp1d

OUT_PATH = os.path.join(OUT_DIR, 'Fig1_VAI_altitude_profile.png')

data = load_valley_data()


# ============================================================
# 计算反转点(LOWESS 平滑后曲线穿过 0 的位置)
# ============================================================
def find_zero_crossings(x, y, x_range=(HIGH_CONF_LOW, HIGH_CONF_HIGH)):
    """在指定海拔范围内查找 LOWESS 平滑曲线的零穿点"""
    mask = (x >= x_range[0]) & (x <= x_range[1])
    if mask.sum() < 5:
        return []
    x_sub, y_sub = x[mask], y[mask]
    # LOWESS 平滑
    smoothed = lowess(y_sub, x_sub, frac=0.3, return_sorted=True)
    xs, ys = smoothed[:, 0], smoothed[:, 1]
    # 查找符号变化
    crossings = []
    for i in range(len(ys) - 1):
        if ys[i] * ys[i + 1] < 0:
            # 线性插值得到零点
            x_zero = xs[i] - ys[i] * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
            crossings.append(x_zero)
    return crossings


reversal_points = {}
for name, df in data.items():
    elev = df['elev_center'].values
    vai = df['vai_mean'].values
    crossings = find_zero_crossings(elev, vai)
    reversal_points[name] = crossings
    print(f'{name} 反转点(高置信段内): {[f"{c:.0f}m" for c in crossings]}')

# ============================================================
# 绘图
# ============================================================
fig = plt.figure(figsize=(12, 8))
gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax1)

# 上图: VAI 剖面 + IQR 阴影
y_all = []
for name, df in data.items():
    elev = df['elev_center'].values
    vai_mean = df['vai_mean'].values
    y_all.extend(vai_mean.tolist())

    # IQR 阴影(若有 q25/q75 列)
    if 'vai_q25' in df.columns and 'vai_q75' in df.columns:
        ax1.fill_between(elev, df['vai_q25'].values, df['vai_q75'].values,
                         color=COLORS[name], alpha=0.12, zorder=2)

    # 折线
    ax1.plot(elev, vai_mean, color=COLORS[name], linewidth=2.0,
             label=name, zorder=4)

# VAI=0 参考线
ax1.axhline(y=0, color='k', linewidth=0.6, linestyle='--', alpha=0.5, zorder=1)

# 高置信区间标注
ax1.axvspan(HIGH_CONF_LOW, HIGH_CONF_HIGH, color='gray', alpha=0.04, zorder=0)
ax1.text(HIGH_CONF_LOW + 50, ax1.get_ylim()[1] * 0.92,
         f'高置信区间 ({HIGH_CONF_LOW}–{HIGH_CONF_HIGH} m)',
         fontsize=9, color='gray', fontstyle='italic')

# 反转点标注
y_min, y_max = min(y_all) - 5, max(y_all) + 5
for name, points in reversal_points.items():
    for p in points:
        ax1.axvline(x=p, color=COLORS[name], linewidth=1.0,
                    linestyle=':', alpha=0.6, zorder=3)
        ax1.annotate(f'{p:.0f}m', xy=(p, 0), xytext=(p + 30, -8),
                     fontsize=8, color=COLORS[name],
                     fontweight='bold', zorder=5)

# 方向标注
ax1.text(0.99, 0.96, '迎风坡更绿 ↑', transform=ax1.transAxes,
         fontsize=10, ha='right', va='top', color='#4393C3',
         fontstyle='italic', fontweight='bold')
ax1.text(0.99, 0.04, '背风坡更绿 ↓', transform=ax1.transAxes,
         fontsize=10, ha='right', va='bottom', color='#D6604D',
         fontstyle='italic', fontweight='bold')

ax1.set_ylabel('VAI (%)', fontsize=12)
ax1.set_ylim(y_min, y_max)
ax1.legend(loc='lower left', framealpha=0.9, fontsize=10, edgecolor='#CCCCCC')
ax1.tick_params(top=True, right=True, which='both')
ax1.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4)
ax1.set_axisbelow(True)
plt.setp(ax1.get_xticklabels(), visible=False)

# 下图: 样本量
for name, df in data.items():
    ax2.plot(df['elev_center'].values, df['count'].values,
             color=COLORS[name], linewidth=1.2, alpha=0.7)
ax2.axhline(y=MIN_COUNT_PER_BIN, color='red', linewidth=0.8,
            linestyle='--', alpha=0.6, label=f'最小阈值 (n={MIN_COUNT_PER_BIN})')
ax2.set_xlabel('高程 (m)', fontsize=12)
ax2.set_ylabel('网格数', fontsize=11)
ax2.set_yscale('log')
ax2.tick_params(top=True, right=True, which='both')
ax2.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4)
ax2.set_axisbelow(True)
ax2.legend(loc='upper right', fontsize=9)

ax1.set_title('川西四条河谷 VAI 沿海拔变化(LOWESS 平滑 + IQR 阴影)',
              fontsize=13, pad=10)

fig.savefig(OUT_PATH, dpi=600, bbox_inches='tight', pad_inches=0.1)
print(f'\n[Fig 1] Saved: {OUT_PATH}')
plt.show()