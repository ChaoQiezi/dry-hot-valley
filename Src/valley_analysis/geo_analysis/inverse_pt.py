# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:32
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: inverse_pt.py

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
    '岷江':   r'E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\Result\Table\altitude\VAI_altitude_gradient.xlsx',
    '大渡河': r'E:\GeoProjects\dry_hot_valley\valley_analysis\Daduhe\Result\Table\VAI_altitude_gradient.xlsx',
    '金沙江': r'E:\GeoProjects\dry_hot_valley\valley_analysis\Jinshajiang\Result\Table\VAI_altitude_gradient.xlsx',
    '雅砻江': r'E:\GeoProjects\dry_hot_valley\valley_analysis\Yalongjiang\Result\Table\VAI_altitude_gradient.xlsx',
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
Fig 2: 四河反转点 Bootstrap CI + Forest Plot
- 对每条河做 1000 次 bootstrap,每次重采样海拔 bin
- LOWESS 平滑后查找零穿点
- 给出反转海拔 95% CI
- Forest plot 可视化
"""

from statsmodels.nonparametric.smoothers_lowess import lowess

OUT_PATH = os.path.join(OUT_DIR, 'Fig2_reversal_bootstrap_forest.png')
N_BOOTSTRAP = 1000

data = load_valley_data()


def bootstrap_reversal(elev, vai, n_boot=N_BOOTSTRAP, x_range=(HIGH_CONF_LOW, HIGH_CONF_HIGH),
                       frac=0.3, seed=42):
    """对 VAI~海拔曲线做 bootstrap, 返回反转海拔的 1000 次估计"""
    rng = np.random.default_rng(seed)
    mask = (elev >= x_range[0]) & (elev <= x_range[1])
    elev_sub, vai_sub = elev[mask], vai[mask]
    n = len(elev_sub)

    crossings_boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)  # 放回抽样
        x_b, y_b = elev_sub[idx], vai_sub[idx]
        # 排序(LOWESS 需要)
        order = np.argsort(x_b)
        x_b, y_b = x_b[order], y_b[order]
        try:
            sm = lowess(y_b, x_b, frac=frac, return_sorted=True)
            xs, ys = sm[:, 0], sm[:, 1]
            # 找第一个零穿点
            for i in range(len(ys) - 1):
                if ys[i] * ys[i + 1] < 0 and ys[i] > 0:  # 由正转负
                    x_zero = xs[i] - ys[i] * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
                    crossings_boot.append(x_zero)
                    break
        except:
            continue
    return np.array(crossings_boot)


# ============================================================
# 对每条河做 bootstrap
# ============================================================
results = {}
for name, df in data.items():
    elev = df['elev_center'].values
    vai = df['vai_mean'].values
    boot = bootstrap_reversal(elev, vai)
    if len(boot) == 0:
        print(f'{name}: bootstrap 失败,无反转点')
        continue
    results[name] = {
        'point': np.median(boot),
        'ci_low': np.percentile(boot, 2.5),
        'ci_high': np.percentile(boot, 97.5),
        'boot': boot,
        'n_valid': len(boot),
    }
    print(f'{name}: 反转海拔 = {results[name]["point"]:.0f} m '
          f'[{results[name]["ci_low"]:.0f}, {results[name]["ci_high"]:.0f}], '
          f'n_valid = {results[name]["n_valid"]}/{N_BOOTSTRAP}')

# ============================================================
# Forest plot
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5))

valley_order = list(results.keys())
y_pos = np.arange(len(valley_order))

# 误差棒
for i, name in enumerate(valley_order):
    r = results[name]
    ax.errorbar(r['point'], i, xerr=[[r['point'] - r['ci_low']],
                                     [r['ci_high'] - r['point']]],
                fmt='o', color=COLORS[name], markersize=12,
                markerfacecolor=COLORS[name], markeredgecolor='white',
                markeredgewidth=1.5, elinewidth=2.5, capsize=8, capthick=2,
                zorder=5)
    # 标数值
    ax.text(r['ci_high'] + 30, i,
            f'{r["point"]:.0f} m  [{r["ci_low"]:.0f}, {r["ci_high"]:.0f}]',
            va='center', fontsize=10, color=COLORS[name], fontweight='bold')

# 四河阈值汇总参考线
all_points = [r['point'] for r in results.values()]
overall_mean = np.mean(all_points)
overall_range = max(all_points) - min(all_points)
ax.axvline(x=overall_mean, color='gray', linewidth=1.2, linestyle='--', alpha=0.7,
           label=f'四河均值 = {overall_mean:.0f} m,极差 = {overall_range:.0f} m')

ax.set_yticks(y_pos)
ax.set_yticklabels(valley_order, fontsize=11)
ax.set_xlabel('反转海拔 (m) — VAI 由正转负的高度', fontsize=12)
ax.set_title(f'川西四河 VAI 反转海拔 Bootstrap 95% 置信区间(n_boot = {N_BOOTSTRAP})',
             fontsize=13, pad=10)
ax.tick_params(top=True, right=True, which='both')
ax.xaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4)
ax.set_axisbelow(True)
ax.invert_yaxis()
ax.legend(loc='lower right', fontsize=10, framealpha=0.9)

# 留出右侧标注空间
xlim = ax.get_xlim()
ax.set_xlim(xlim[0], xlim[1] + (xlim[1] - xlim[0]) * 0.25)

fig.savefig(OUT_PATH, dpi=600, bbox_inches='tight', pad_inches=0.1)
print(f'\n[Fig 2] Saved: {OUT_PATH}')
plt.show()

# 保存反转点结果到 CSV
result_df = pd.DataFrame([
    {'河谷': name, '反转海拔_m': r['point'],
     'CI_low_m': r['ci_low'], 'CI_high_m': r['ci_high'],
     'CI_width_m': r['ci_high'] - r['ci_low'], 'n_bootstrap_valid': r['n_valid']}
    for name, r in results.items()
])
result_df.to_csv(os.path.join(OUT_DIR, 'reversal_bootstrap_results.csv'),
                 index=False, encoding='utf-8-sig')
print(result_df.to_string())