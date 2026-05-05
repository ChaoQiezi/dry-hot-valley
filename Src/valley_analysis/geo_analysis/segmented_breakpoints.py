# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:35
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: segmented_breakpoints.py

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


# @Author  : ChaoQiezi
# @Time    : 2026/5/5
# @FileName: Fig3_segmented_breakpoints.py

"""
Fig 3: 四河 Segmented 分段回归断点估计
- 用 piecewise-regression 包(Python 等价于 R 的 segmented)
- ModelSelection 选 BIC 最优断点数(限制最大 2 个,防过拟合)
- 输出每河断点位置 + 95% CI
- 与 Fig 2 LOWESS 反转点交叉验证
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import piecewise_regression as pw
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# Configuration
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
OUT_DIR = r'E:\GeoProjects\dry_hot_valley\Result\Chart\altitude'
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'Fig3_segmented_breakpoints.png')

MIN_COUNT_PER_BIN = 30
HIGH_CONF_LOW = 1500
HIGH_CONF_HIGH = 4500
MAX_BREAKPOINTS = 2  # 限制最大断点数,防止过拟合

plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei', 'STHeiti', 'WenQuanYi Micro Hei',
                        'Noto Sans CJK SC', 'sans-serif'],
    'font.family': 'sans-serif',
    'axes.unicode_minus': False,
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
})


# ============================================================
# 1. 加载数据
# ============================================================
def load_valley_data(min_count=MIN_COUNT_PER_BIN):
    data = {}
    for name, path in VALLEYS.items():
        df = pd.read_excel(path)
        df = df[df['count'] >= min_count].reset_index(drop=True)
        data[name] = df
        print(f'{name}: {len(df)} bins kept (count >= {min_count}), '
              f'elev range [{df["elev_center"].min():.0f}, {df["elev_center"].max():.0f}]')
    return data


data = load_valley_data()


# ============================================================
# 2. 对每河拟合 segmented 模型
# ============================================================
def fit_segmented(x, y, max_bp=MAX_BREAKPOINTS):
    """
    对一条河的 (x=elev, y=VAI) 序列做 segmented 拟合。
    返回:
        {
            'best_n': 最优断点数,
            'breakpoints': [bp1, bp2, ...] (排序后的断点位置),
            'ci_lows': [...],
            'ci_highs': [...],
            'ses': [...],
            'bic': BIC,
            'fit_obj': Fit 对象 (用于 predict),
            'davies_p': Davies test p-value (1+ 断点 vs 0 断点的显著性),
        }
    """
    # 用 ModelSelection 选最优断点数
    ms = pw.ModelSelection(x, y, max_breakpoints=max_bp, n_boot=50, verbose=False)

    best_n = None
    best_bic = np.inf
    for r in ms.model_summaries:
        if r is None or r.get('converged', False) is False:
            continue
        if r['bic'] < best_bic:
            best_bic = r['bic']
            best_n = r['n_breakpoints']

    if best_n is None or best_n == 0:
        # 不收敛或最优是 0 断点
        return None

    # 用最优 n 重新拟合(获得详细统计)
    fit = pw.Fit(x, y, n_breakpoints=best_n)
    results = fit.get_results()

    if not results['converged']:
        return None

    estimates = results['estimates']
    breakpoints = []
    ci_lows = []
    ci_highs = []
    ses = []

    for i in range(best_n):
        key = f'breakpoint{i + 1}'
        if key in estimates:
            bp = estimates[key]
            breakpoints.append(bp['estimate'])
            ci_lows.append(bp['confidence_interval'][0])
            ci_highs.append(bp['confidence_interval'][1])
            ses.append(bp['se'])

    # 按位置排序
    order = np.argsort(breakpoints)
    breakpoints = [breakpoints[i] for i in order]
    ci_lows = [ci_lows[i] for i in order]
    ci_highs = [ci_highs[i] for i in order]
    ses = [ses[i] for i in order]

    return {
        'best_n': best_n,
        'breakpoints': breakpoints,
        'ci_lows': ci_lows,
        'ci_highs': ci_highs,
        'ses': ses,
        'bic': best_bic,
        'fit_obj': fit,
        'davies_p': results.get('davies', None),
    }


seg_results = {}
print('\n' + '=' * 60)
print('对四条河分别拟合 segmented 模型')
print('=' * 60)

for name, df in data.items():
    print(f'\n--- {name} ---')
    mask = ((df['elev_center'] >= HIGH_CONF_LOW) &
            (df['elev_center'] <= HIGH_CONF_HIGH))
    x = df.loc[mask, 'elev_center'].values.astype(float)
    y = df.loc[mask, 'vai_mean'].values.astype(float)

    if len(x) < 5:
        print(f'  数据点太少 ({len(x)}),跳过')
        continue

    print(f'  数据点: {len(x)}, x 范围 [{x.min():.0f}, {x.max():.0f}]')

    try:
        r = fit_segmented(x, y)
        if r is None:
            print(f'  拟合失败或最优为 0 断点')
            continue

        r['x'] = x
        r['y'] = y
        seg_results[name] = r

        bp_str = ', '.join([f'{b:.0f}m [{l:.0f},{h:.0f}]'
                            for b, l, h in zip(r['breakpoints'],
                                               r['ci_lows'], r['ci_highs'])])
        print(f'  最优断点数: {r["best_n"]}, BIC: {r["bic"]:.2f}')
        print(f'  断点位置(含 95% CI): {bp_str}')
        if r['davies_p'] is not None:
            print(f'  Davies test p: {r["davies_p"]:.2e}')
    except Exception as e:
        print(f'  拟合异常: {type(e).__name__}: {e}')

# ============================================================
# 3. 绘图: 2x2 子图,每条河一个
# ============================================================
print('\n' + '=' * 60)
print('绘图')
print('=' * 60)

fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharey=True)
axes = axes.flatten()

valley_order = list(seg_results.keys())

for ax_idx, name in enumerate(valley_order):
    ax = axes[ax_idx]
    r = seg_results[name]
    x, y = r['x'], r['y']

    # 散点
    ax.scatter(x, y, s=28, color=COLORS[name], alpha=0.55,
               edgecolors='white', linewidths=0.6, zorder=3)

    # 拟合曲线
    try:
        x_pred = np.linspace(x.min(), x.max(), 300)
        y_pred = r['fit_obj'].predict(x_pred)
        ax.plot(x_pred, y_pred, color=COLORS[name], linewidth=2.4, zorder=4)
    except Exception as e:
        print(f'  {name} 预测失败: {e}')

    # 标注断点 + CI
    for bp, lo, hi in zip(r['breakpoints'], r['ci_lows'], r['ci_highs']):
        ax.axvline(x=bp, color='red', linewidth=1.4, linestyle='--',
                   alpha=0.75, zorder=5)
        ax.axvspan(lo, hi, color='red', alpha=0.12, zorder=2)
        # 标注海拔数字
        y_top = ax.get_ylim()[1] if ax.get_ylim()[1] != 1 else max(y) + 5
        ax.annotate(f'{bp:.0f} m\n[{lo:.0f}, {hi:.0f}]',
                    xy=(bp, max(y) * 0.85),
                    fontsize=9, color='red', fontweight='bold',
                    ha='left', va='top',
                    xytext=(bp + 50, max(y) * 0.85))

    # VAI=0 参考线
    ax.axhline(y=0, color='k', linewidth=0.6, linestyle=':', alpha=0.5, zorder=1)

    # 标题(含统计信息)
    title = f'{name}  (最优断点数 = {r["best_n"]}, BIC = {r["bic"]:.1f}'
    if r['davies_p'] is not None and r['davies_p'] < 1e-3:
        title += f', Davies p < 0.001)'
    elif r['davies_p'] is not None:
        title += f', Davies p = {r["davies_p"]:.3f})'
    else:
        title += ')'
    ax.set_title(title, fontsize=11, pad=8)

    ax.set_xlabel('高程 (m)', fontsize=11)
    ax.set_ylabel('VAI (%)', fontsize=11)
    ax.tick_params(top=True, right=True, which='both')
    ax.grid(True, linestyle='--', linewidth=0.3, alpha=0.4)

# 隐藏多余子图
for i in range(len(valley_order), len(axes)):
    axes[i].set_visible(False)

fig.suptitle('川西四河 VAI 沿海拔的 Segmented 分段回归断点',
             fontsize=14, y=1.00)
fig.tight_layout()
fig.savefig(OUT_PATH, dpi=600, bbox_inches='tight', pad_inches=0.1)
print(f'\n[Fig 3] Saved: {OUT_PATH}')
plt.show()

# ============================================================
# 4. 保存断点结果到 CSV
# ============================================================
seg_records = []
for name, r in seg_results.items():
    rec = {
        '河谷': name,
        '最优断点数': r['best_n'],
        'BIC': round(r['bic'], 2),
        'Davies_p': r['davies_p'],
    }
    for i in range(MAX_BREAKPOINTS):
        if i < len(r['breakpoints']):
            rec[f'断点{i + 1}_m'] = round(r['breakpoints'][i], 0)
            rec[f'断点{i + 1}_CI下界_m'] = round(r['ci_lows'][i], 0)
            rec[f'断点{i + 1}_CI上界_m'] = round(r['ci_highs'][i], 0)
            rec[f'断点{i + 1}_SE_m'] = round(r['ses'][i], 1)
        else:
            rec[f'断点{i + 1}_m'] = np.nan
            rec[f'断点{i + 1}_CI下界_m'] = np.nan
            rec[f'断点{i + 1}_CI上界_m'] = np.nan
            rec[f'断点{i + 1}_SE_m'] = np.nan
    seg_records.append(rec)

seg_df = pd.DataFrame(seg_records)
csv_path = os.path.join(OUT_DIR, 'segmented_breakpoints.csv')
seg_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f'\n[CSV] Saved: {csv_path}')
print('\n' + seg_df.to_string())