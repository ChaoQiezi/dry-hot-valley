# @Author  : ChaoQiezi
# @Time    : 2026/3/28 上午11:10
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_time_series.py

"""
This script is used to 绘制NDVI时间序列变化图

变更说明:
    - 2026/4/14-ps: 适配干热河谷内外侧 × 迎背风坡的多维度分析模式

分析模式 (ANALYSIS_MODE):
  - "wind_only":   迎风坡 vs 背风坡 (2条折线)
  - "valley_only": 河谷内侧 vs 外侧 (2条折线)
  - "combined":    4个分量: inner_windward, inner_leeward,
                   outer_windward, outer_leeward (4条折线)
所有模式均不绘制±1σ阴影, 以避免多条线相互遮盖.
除NDVI年均值外, 还包括MK趋势和Sen's Slope, 并绘制趋势线.
图例、轴范围、标注均根据模式和实际数据自适应.
输入:
  - Excel表格 (由 ndvi_yearly_mean_by_windward_leeward.py 生成)
输出:
  - 出版质量的时间序列折线图
"""

import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from qiezi.stats import mk_trend_slope
ANALYSIS_MODE = "wind_only"
in_dir = r'E:\GeoProjects\dry_hot_valley\Output\Table'
out_dir = r'E:\GeoProjects\dry_hot_valley\Result\Chart\ndvi_yearly_mean_by_aspect_valley'
os.makedirs(out_dir, exist_ok=True)
# 输入/输出路径根据模式自动生成
_suffix_map = {
    'wind_only': '_wind_only',
    'valley_only': '_valley_only',
    'combined': '_combined',
}
_suffix = _suffix_map[ANALYSIS_MODE]
in_path = os.path.join(in_dir, f'NDVI_yearly_stats{_suffix}.xlsx')
out_path = os.path.join(out_dir, f'NDVI_time_series{_suffix}.png')
# 分量配置: 颜色、标记、线型
# 颜色语义:
#   绿色系 = 迎风坡 (windward), 棕橙系 = 背风坡 (leeward)
#   深色/实线 = 河谷内侧 (inner), 浅色/虚线 = 河谷外侧 (outer)
#   对于valley_only: 暖棕色 = 内侧(干热), 冷绿色 = 外侧(相对湿润)
COMPONENT_CONFIG = {
    'wind_only': [
        {'key': 'windward',  'label': 'Windward',  'color': '#2E7D52', 'marker': 'o', 'ls': '-'},
        {'key': 'leeward',   'label': 'Leeward',   'color': '#C2652A', 'marker': 's', 'ls': '-'},
    ],
    'valley_only': [
        {'key': 'inner',  'label': 'Valley inner',  'color': '#C2652A', 'marker': 'o', 'ls': '-'},
        {'key': 'outer',  'label': 'Valley outer',  'color': '#2E7D52', 'marker': 's', 'ls': '-'},
    ],
    'combined': [
        {'key': 'inner_windward',  'label': 'Inner windward',  'color': '#1B7340', 'marker': 'o', 'ls': '-'},
        {'key': 'inner_leeward',   'label': 'Inner leeward',   'color': '#B5442A', 'marker': 's', 'ls': '-'},
        {'key': 'outer_windward',  'label': 'Outer windward',  'color': '#6BBF8A', 'marker': '^', 'ls': '--'},
        {'key': 'outer_leeward',   'label': 'Outer leeward',   'color': '#E8945A', 'marker': 'D', 'ls': '--'},
    ],
}
# 1. Read data
assert ANALYSIS_MODE in COMPONENT_CONFIG, \
    f"Invalid ANALYSIS_MODE: '{ANALYSIS_MODE}'. Must be one of {list(COMPONENT_CONFIG.keys())}."
print(f"Analysis mode: {ANALYSIS_MODE}")
print(f"Input:  {in_path}")
print(f"Output: {out_path}")
df = pd.read_excel(in_path)
years = df['year'].values
n = len(years)
x_idx = np.arange(n)
components = COMPONENT_CONFIG[ANALYSIS_MODE]
# 提取各分量数据并进行MK趋势检验
comp_data = {}  # key -> {'mean': array, 'std': array, 'cv': array, 'mk': dict, 'trend': array}
for comp in components:
    key = comp['key']
    mean_col = f'{key}_mean'
    std_col = f'{key}_std'
    cv_col = f'{key}_cv'
    # 检查列是否存在
    assert mean_col in df.columns, \
        f"Column '{mean_col}' not found in {in_path}. Available: {list(df.columns)}"
    mean_vals = df[mean_col].values
    std_vals = df[std_col].values if std_col in df.columns else np.full(n, np.nan)
    cv_vals = df[cv_col].values if cv_col in df.columns else np.full(n, np.nan)
    # MK趋势检验
    mk_stats = mk_trend_slope(mean_vals)
    # Sen's slope 趋势线 (基于x_idx)
    trend_line = mk_stats['slope'] * x_idx + mk_stats['intercept']
    comp_data[key] = {
        'mean': mean_vals,
        'std': std_vals,
        'cv': cv_vals,
        'mk': mk_stats,
        'trend': trend_line,
    }
# 打印MK结果
for comp in components:
    key = comp['key']
    s = comp_data[key]['mk']
    print(f"\n--- {comp['label']} Mann-Kendall Trend Test ---")
    print(f"  Trend       : {s['trend']}")
    print(f"  p-value     : {s['p_value']:.4f}")
    print(f"  τ           : {s['tau']:.4f}")
    print(f"  Sen's slope : {s['slope']:.6f}  "
          f"(95% CI: {s['slope_ci_lo']:.6f} ~ {s['slope_ci_hi']:.6f})")
    print(f"  Intercept   : {s['intercept']:.4f}")
    print(f"  Significant : {'Yes' if s['significant'] else 'No'}  (α = 0.05)")
# 2. Plot
# Academic style
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 10,
    'axes.linewidth': 0.8,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'figure.dpi': 300,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'mathtext.fontset': 'stix',
})
# Single clean panel
fig, ax = plt.subplots(figsize=(9, 5))
# 绘制各分量
for comp in components:
    key = comp['key']
    d = comp_data[key]
    # Sen's slope 趋势线 (虚细线, 颜色同主线但透明度低)
    ax.plot(
        years, d['trend'],
        color=comp['color'], linewidth=1.0, linestyle=':', alpha=0.6, zorder=3,
    )
    # NDVI 均值折线 + 数据点
    ax.plot(
        years, d['mean'],
        color=comp['color'], linewidth=2.0, linestyle=comp['ls'], zorder=5,
        marker=comp['marker'], markersize=6.5,
        markerfacecolor='white', markeredgewidth=1.8, markeredgecolor=comp['color'],
        label=f"{comp['label']} mean NDVI",
    )
# Annotation box: MK趋势统计
def fmt_annotation(label, s):
    """格式化单行MK趋势标注"""
    sig = '*' if s['significant'] else 'n.s.'
    return (f"{label}: slope = {s['slope'] * 1000:+.3f}"
            f"×10⁻³ yr⁻¹  {sig}  "
            f"(τ = {s['tau']:.3f}, p = {s['p_value']:.3f})")
annotation_lines = []
for comp in components:
    annotation_lines.append(fmt_annotation(comp['label'], comp_data[comp['key']]['mk']))
annotation = '\n'.join(annotation_lines)
# 根据分量数调整标注字号
ann_fontsize = 8.5 if len(components) <= 2 else 7.5
ax.text(
    0.03, 0.96, annotation,
    transform=ax.transAxes,
    fontsize=ann_fontsize,
    verticalalignment='top',
    linespacing=1.5,
    bbox=dict(
        boxstyle='round,pad=0.4',
        facecolor='white',
        edgecolor='#BBBBBB',
        alpha=0.88
    ),
    zorder=6
)
# Axes formatting
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('NDVI', fontsize=12)
ax.xaxis.set_major_locator(mticker.FixedLocator(years))
ax.xaxis.set_minor_locator(mticker.MultipleLocator(1))
# Y轴范围: 基于所有分量均值自适应 (无阴影, 仅考虑均值)
all_means = np.concatenate([comp_data[c['key']]['mean'] for c in components])
y_lo = np.nanmin(all_means)
y_hi = np.nanmax(all_means)
y_range = y_hi - y_lo
# 留出上方空间给annotation, 下方留小量padding
n_ann_lines = len(components)
ann_height_frac = 0.06 * n_ann_lines + 0.10  # 随行数自适应
ax.set_ylim(y_lo - y_range * 0.08, y_hi + y_range * (ann_height_frac + 0.05))
ax.set_xlim(years[0] - 0.4, years[-1] + 0.4)
# 网格 + spine
ax.yaxis.grid(True, linestyle='--', linewidth=0.4, alpha=0.5, color='grey')
ax.set_axisbelow(True)
ax.spines[['top', 'right']].set_visible(False)
# 图例: 根据分量数调整布局
n_comps = len(components)
if n_comps <= 2:
    legend_ncol = 2
    legend_fontsize = 8.5
else:
    legend_ncol = 2
    legend_fontsize = 8.0
ax.legend(
    loc='upper right',
    fontsize=legend_fontsize,
    framealpha=0.88,
    edgecolor='#CCCCCC',
    ncol=legend_ncol,
    columnspacing=1.2,
    handlelength=2.2,
)
# Save
plt.tight_layout()
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.05)
print(f'\nFigure saved to: {out_path}')
plt.show()