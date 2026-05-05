# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:37
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: intensity_comparison.py

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
Fig 4: 四河差异强度量化对比
- |VAI| 中位数 (整体强度)
- VAI 振幅 (沿海拔变化幅度)
- 反转海拔
- 极值海拔(VAI 最低位置)
"""

OUT_PATH = os.path.join(OUT_DIR, 'Fig4_intensity_comparison.png')

data = load_valley_data()

# ============================================================
# 计算各项指标(限制在高置信区间)
# ============================================================
metrics = {}
for name, df in data.items():
    mask = ((df['elev_center'] >= HIGH_CONF_LOW) &
            (df['elev_center'] <= HIGH_CONF_HIGH))
    sub = df.loc[mask]

    abs_vai_median = np.nanmedian(np.abs(sub['vai_mean'].values))
    vai_max = np.nanmax(sub['vai_mean'].values)
    vai_min = np.nanmin(sub['vai_mean'].values)
    amplitude = vai_max - vai_min

    # 极值海拔(VAI 最小值位置, 即背风坡最绿处)
    idx_min = np.nanargmin(sub['vai_mean'].values)
    elev_min = sub['elev_center'].values[idx_min]

    metrics[name] = {
        'abs_vai_median': abs_vai_median,
        'amplitude': amplitude,
        'vai_max': vai_max,
        'vai_min': vai_min,
        'elev_min_vai': elev_min,
    }
    print(f'{name}: |VAI|中位数={abs_vai_median:.1f}%, 振幅={amplitude:.1f}%, '
          f'极值海拔={elev_min:.0f}m')

# ============================================================
# 绘图: 2x2 柱状图
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(12, 8))

valley_order = list(metrics.keys())
positions = np.arange(len(valley_order))
colors_list = [COLORS[v] for v in valley_order]

# (a) |VAI| 中位数
ax = axes[0, 0]
vals = [metrics[v]['abs_vai_median'] for v in valley_order]
bars = ax.bar(positions, vals, color=colors_list, edgecolor='black',
              linewidth=0.8, alpha=0.85)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.3,
            f'{v:.1f}%', ha='center', fontsize=10, fontweight='bold')
ax.set_xticks(positions)
ax.set_xticklabels(valley_order, fontsize=10)
ax.set_ylabel('|VAI| 中位数 (%)', fontsize=11)
ax.set_title('(a) 整体不对称强度', fontsize=11, pad=8)
ax.tick_params(top=True, right=True)
ax.grid(axis='y', linestyle='--', linewidth=0.3, alpha=0.4)

# (b) VAI 振幅
ax = axes[0, 1]
vals = [metrics[v]['amplitude'] for v in valley_order]
bars = ax.bar(positions, vals, color=colors_list, edgecolor='black',
              linewidth=0.8, alpha=0.85)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
            f'{v:.1f}%', ha='center', fontsize=10, fontweight='bold')
ax.set_xticks(positions)
ax.set_xticklabels(valley_order, fontsize=10)
ax.set_ylabel('VAI 振幅 (max−min) (%)', fontsize=11)
ax.set_title('(b) 沿海拔变化的剧烈程度', fontsize=11, pad=8)
ax.tick_params(top=True, right=True)
ax.grid(axis='y', linestyle='--', linewidth=0.3, alpha=0.4)

# (c) VAI 最值
ax = axes[1, 0]
width = 0.35
vmax = [metrics[v]['vai_max'] for v in valley_order]
vmin = [metrics[v]['vai_min'] for v in valley_order]
ax.bar(positions - width / 2, vmax, width, label='VAI 最大值',
       color='#4393C3', edgecolor='black', linewidth=0.8, alpha=0.85)
ax.bar(positions + width / 2, vmin, width, label='VAI 最小值',
       color='#D6604D', edgecolor='black', linewidth=0.8, alpha=0.85)
for i, (mx, mn) in enumerate(zip(vmax, vmin)):
    ax.text(i - width / 2, mx + 0.5, f'{mx:.0f}', ha='center', fontsize=9)
    ax.text(i + width / 2, mn - 1.5, f'{mn:.0f}', ha='center', fontsize=9)
ax.axhline(y=0, color='k', linewidth=0.6, linestyle='--', alpha=0.5)
ax.set_xticks(positions)
ax.set_xticklabels(valley_order, fontsize=10)
ax.set_ylabel('VAI (%)', fontsize=11)
ax.set_title('(c) 迎/背风极值', fontsize=11, pad=8)
ax.legend(fontsize=9, loc='best')
ax.tick_params(top=True, right=True)
ax.grid(axis='y', linestyle='--', linewidth=0.3, alpha=0.4)

# (d) 极值海拔
ax = axes[1, 1]
vals = [metrics[v]['elev_min_vai'] for v in valley_order]
bars = ax.bar(positions, vals, color=colors_list, edgecolor='black',
              linewidth=0.8, alpha=0.85)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 30,
            f'{v:.0f}m', ha='center', fontsize=10, fontweight='bold')
ax.set_xticks(positions)
ax.set_xticklabels(valley_order, fontsize=10)
ax.set_ylabel('极值海拔 (m)', fontsize=11)
ax.set_title('(d) 背风坡最绿位置', fontsize=11, pad=8)
ax.tick_params(top=True, right=True)
ax.grid(axis='y', linestyle='--', linewidth=0.3, alpha=0.4)

fig.suptitle(f'川西四河 VAI 差异强度对比 (高置信区间 {HIGH_CONF_LOW}–{HIGH_CONF_HIGH} m)',
             fontsize=13, y=1.00)
fig.tight_layout()
fig.savefig(OUT_PATH, dpi=600, bbox_inches='tight', pad_inches=0.1)
print(f'\n[Fig 4] Saved: {OUT_PATH}')
plt.show()

# 保存指标表
metrics_df = pd.DataFrame(metrics).T
metrics_df.index.name = '河谷'
metrics_df.to_csv(os.path.join(OUT_DIR, 'intensity_metrics.csv'), encoding='utf-8-sig')
print('\n', metrics_df)