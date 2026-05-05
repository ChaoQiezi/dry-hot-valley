# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:37
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: methods_forest_plot.py

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
MIN_COUNT_PER_BIN = 30        # 每个海拔 bin 至少要有的网格数(剔除低样本噪声)
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
Fig 5: 综合 Forest Plot - 多方法 × 四河阈值收敛性
关键问题: 不同方法对同一河给出的阈值是否一致?
         同一方法对不同河给出的阈值是否一致?
         如果都收敛 → 阈值客观存在,跨四河一致
"""

OUT_PATH = os.path.join(OUT_DIR, 'Fig5_methods_forest_plot.png')

# 读取前面两步保存的结果
df_lowess = pd.read_csv(os.path.join(OUT_DIR, 'reversal_bootstrap_results.csv'))
df_seg = pd.read_csv(os.path.join(OUT_DIR, 'segmented_breakpoints.csv'))

# ============================================================
# 整理数据
# ============================================================
methods_data = []
for _, row in df_lowess.iterrows():
    methods_data.append({
        'valley': row['河谷'],
        'method': 'LOWESS 反转点',
        'estimate': row['反转海拔_m'],
        'ci_low': row['CI_low_m'],
        'ci_high': row['CI_high_m'],
    })
for _, row in df_seg.iterrows():
    lowess_match = df_lowess[df_lowess['河谷'] == row['河谷']]
    if lowess_match.empty:
        continue
    lowess_reversal = lowess_match['反转海拔_m'].iloc[0]

    candidates = []
    for i in range(1, 3):
        bp = row.get(f'断点{i}_m', np.nan)
        if np.isnan(bp):
            continue
        candidates.append({
            'bp': bp,
            'ci_low': row[f'断点{i}_CI下界_m'],
            'ci_high': row[f'断点{i}_CI上界_m'],
            'distance': abs(bp - lowess_reversal),
            'index': i,
        })

    if candidates:
        # 多断点时只取最接近 LOWESS 反转点的断点,避免把低海拔 slope break 当成反转阈值。
        nearest = min(candidates, key=lambda item: item['distance'])
        methods_data.append({
            'valley': row['河谷'],
            'method': 'Segmented 最近断点',
            'estimate': nearest['bp'],
            'ci_low': nearest['ci_low'],
            'ci_high': nearest['ci_high'],
            'segmented_bp_index': nearest['index'],
            'distance_to_lowess_m': nearest['distance'],
        })

forest_df = pd.DataFrame(methods_data)
forest_df.to_csv(os.path.join(OUT_DIR, 'methods_forest_data.csv'),
                 index=False, encoding='utf-8-sig', float_format='%.1f')

# ============================================================
# 绘图
# ============================================================
fig, ax = plt.subplots(figsize=(11, 7))

valley_order = ['岷江', '大渡河', '金沙江', '雅砻江']
methods = ['LOWESS 反转点', 'Segmented 最近断点']
method_markers = {'LOWESS 反转点': 'o', 'Segmented 最近断点': 's'}
method_offset = {'LOWESS 反转点': -0.15, 'Segmented 最近断点': 0.15}

y_labels = []
y_pos_count = 0
y_positions = {}

for v in valley_order:
    y_labels.append(v)
    for m in methods:
        y_positions[(v, m)] = y_pos_count + method_offset[m]
    y_pos_count += 1

# 绘制每个点
for _, row in forest_df.iterrows():
    v, m = row['valley'], row['method']
    if (v, m) not in y_positions:
        continue
    y = y_positions[(v, m)]
    ax.errorbar(row['estimate'], y,
                xerr=[[row['estimate'] - row['ci_low']],
                      [row['ci_high'] - row['estimate']]],
                fmt=method_markers[m], color=COLORS[v], markersize=11,
                markerfacecolor=COLORS[v], markeredgecolor='white',
                markeredgewidth=1.2, elinewidth=2, capsize=6, capthick=1.5,
                zorder=5)

# 河谷分隔线
for i in range(1, len(valley_order)):
    ax.axhline(y=i - 0.5, color='gray', linewidth=0.4, linestyle=':', alpha=0.5)

# 整体均值参考线
all_estimates = forest_df['estimate'].values
overall_mean = np.mean(all_estimates)
overall_range = np.max(all_estimates) - np.min(all_estimates)
ax.axvline(x=overall_mean, color='black', linewidth=1.2, linestyle='--', alpha=0.6,
           label=f'整体均值 = {overall_mean:.0f} m\n所有估计极差 = {overall_range:.0f} m')

ax.set_yticks(np.arange(len(valley_order)))
ax.set_yticklabels(valley_order, fontsize=12)
ax.set_xlabel('阈值海拔 (m)', fontsize=12)
ax.invert_yaxis()
ax.tick_params(top=True, right=True, which='both')
ax.xaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4)
ax.set_axisbelow(True)

# 自定义图例
from matplotlib.lines import Line2D
legend_elems = [
    Line2D([0], [0], marker='o', color='gray', markersize=10,
           markerfacecolor='gray', markeredgecolor='white',
           linestyle='', label='LOWESS 反转点 (95% CI)'),
    Line2D([0], [0], marker='s', color='gray', markersize=10,
           markerfacecolor='gray', markeredgecolor='white',
           linestyle='', label='Segmented 最近断点 (95% CI)'),
    Line2D([0], [0], color='black', linewidth=1.2, linestyle='--',
           label=f'整体均值 = {overall_mean:.0f} m'),
]
ax.legend(handles=legend_elems, loc='upper right', fontsize=10, framealpha=0.9)

ax.set_title('川西四河 VAI 阈值的多方法 × 多河谷收敛性\n'
             f'(LOWESS 反转点与相邻 segmented 断点集中在 {np.min(all_estimates):.0f}–{np.max(all_estimates):.0f} m)',
             fontsize=13, pad=10)

fig.savefig(OUT_PATH, dpi=600, bbox_inches='tight', pad_inches=0.1)
print(f'\n[Fig 5] Saved: {OUT_PATH}')
plt.show()
