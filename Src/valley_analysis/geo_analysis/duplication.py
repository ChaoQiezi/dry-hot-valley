# @Author  : ChaoQiezi
# @Time    : 2026/5/5 下午2:31
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: duplication.py

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