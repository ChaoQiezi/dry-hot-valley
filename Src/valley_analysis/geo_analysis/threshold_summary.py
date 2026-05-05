# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:40
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: threshold_summary.py

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
Table 1: 四河阈值汇总 + 高度差矩阵
"""

OUT_PATH = os.path.join(OUT_DIR, 'Table1_threshold_summary.csv')
OUT_PATH_DIFF = os.path.join(OUT_DIR, 'Table1b_pairwise_diff.csv')

df_lowess = pd.read_csv(os.path.join(OUT_DIR, 'reversal_bootstrap_results.csv'))
df_seg = pd.read_csv(os.path.join(OUT_DIR, 'segmented_breakpoints.csv'))
df_intensity = pd.read_csv(os.path.join(OUT_DIR, 'intensity_metrics.csv'))

# 合并主表
summary = df_lowess.merge(df_seg, on='河谷').merge(df_intensity, on='河谷')

# 添加高度差列(相对于谷底海拔——这里用各河的最低有效海拔近似)
data = load_valley_data()
for valley in summary['河谷']:
    df_v = data[valley]
    valley_floor = df_v['elev_center'].min()
    rev = summary.loc[summary['河谷'] == valley, '反转海拔_m'].values[0]
    summary.loc[summary['河谷'] == valley, '谷底海拔_m'] = valley_floor
    summary.loc[summary['河谷'] == valley, '反转高差_m'] = rev - valley_floor
    summary.loc[summary['河谷'] == valley, '极值高差_m'] = (
        summary.loc[summary['河谷'] == valley, 'elev_min_vai'].values[0] - valley_floor
    )

# 关键列重排
key_cols = ['河谷', '反转海拔_m', 'CI_low_m', 'CI_high_m', '断点1_m', '断点2_m',
            'abs_vai_median', 'amplitude', 'elev_min_vai', '谷底海拔_m',
            '反转高差_m', '极值高差_m']
summary_out = summary[key_cols].copy()
summary_out.columns = ['河谷', '反转海拔(m)', 'CI下界(m)', 'CI上界(m)',
                       '分段断点1(m)', '分段断点2(m)',
                       '|VAI|中位数(%)', 'VAI振幅(%)', '极值海拔(m)',
                       '谷底海拔(m)', '反转相对高差(m)', '极值相对高差(m)']
summary_out.to_csv(OUT_PATH, index=False, encoding='utf-8-sig', float_format='%.1f')
print('\n=== 主汇总表 ===\n', summary_out.to_string())

# 反转海拔两两差
valleys = summary['河谷'].tolist()
rev_alt = summary['反转海拔_m'].values
diff_matrix = np.abs(rev_alt[:, None] - rev_alt[None, :])
diff_df = pd.DataFrame(diff_matrix, index=valleys, columns=valleys)
diff_df.to_csv(OUT_PATH_DIFF, encoding='utf-8-sig', float_format='%.0f')
print('\n=== 反转海拔两两差矩阵(m) ===\n', diff_df.to_string())