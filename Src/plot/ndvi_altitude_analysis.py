# @Author  : ChaoQiezi
# @Time    : 2026/3/29
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_altitude_analysis.py

"""
This script is used to 绘制不同高程梯度下各分量NDVI变化图

2026/4/14-ps: 适配干热河谷内外侧 × 迎背风坡的多维度分析模式

分析模式 (ANALYSIS_MODE):
  - "wind_only":   迎风坡 vs 背风坡 (2条曲线)
  - "valley_only": 河谷内侧 vs 外侧 (2条曲线)
  - "combined":    4个分量: inner_windward, inner_leeward,
                   outer_windward, outer_leeward (4条曲线)

布局 (上中下三面板):
  上方主面板(a): NDVI随高程变化曲线
                2分量模式: 含±1σ阴影
                4分量模式: 不含阴影, 以色相区分迎/背风坡, 线型区分内/外侧
  中间面板(b): ΔNDVI 柱状图
                wind_only:   ΔNDVI = windward − leeward
                valley_only: ΔNDVI = inner − outer
                combined:    ΔNDVI_inner(W−L) vs ΔNDVI_outer(W−L) 并列柱状图
                             → 直接揭示焚风驱动的不对称性在河谷内外的差异
  下方面板(c): 各高程带像元数量 (归一化背靠背柱状图)

三个面板共享X轴(高程)

输入:
  - Excel表格 (由 ndvi_altitude_analysis.py 分析脚本生成)
输出:
  - 出版质量的高程梯度图
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
# 分析模式: "wind_only" | "valley_only" | "combined"
ANALYSIS_MODE = "combined"
# ANALYSIS_MODE = "valley_only"
# ANALYSIS_MODE = "wind_only"

in_dir = r'E:\GeoProjects\dry_hot_valley\Output\Table'
out_dir = r'E:\GeoProjects\dry_hot_valley\Result\Chart\ndvi_altitude_analysis'
os.makedirs(out_dir, exist_ok=True)

# 输入/输出路径根据模式自动生成
_suffix_map = {
    'wind_only': '_wind_only',
    'valley_only': '_valley_only',
    'combined': '_combined',
}
_suffix = _suffix_map[ANALYSIS_MODE]
in_path = os.path.join(in_dir, f'NDVI_elevation_gradient{_suffix}.xlsx')
out_path = os.path.join(out_dir, f'NDVI_elevation_gradient{_suffix}.png')

# ============================================================
# 分量配置
# ============================================================
# 颜色语义 (同 ndvi_yearly_mean.py 保持一致):
#   绿色系 = 迎风坡 (windward), 棕橙系 = 背风坡 (leeward)
#   深色/实线 = 河谷内侧 (inner), 浅色/虚线 = 河谷外侧 (outer)
#   对于valley_only: 暖棕色 = 内侧(干热), 冷绿色 = 外侧(相对湿润)

COMPONENT_CONFIG = {
    'wind_only': {
        'components': [
            {'key': 'windward',  'label': 'Windward',  'color': '#2E7D52', 'marker': 'o', 'ls': '-'},
            {'key': 'leeward',   'label': 'Leeward',   'color': '#C2652A', 'marker': 's', 'ls': '-'},
        ],
        # delta: A - B
        'delta_pairs': [
            {'a': 'windward', 'b': 'leeward', 'label': 'ΔNDVI (W−L)',
             'color_pos': '#2E7D52', 'color_neg': '#C2652A'},
        ],
        # count: 上方(正) vs 下方(负)
        'count_up': ['windward'],
        'count_down': ['leeward'],
        'count_up_label': 'Windward',
        'count_down_label': 'Leeward',
        'show_sigma': True,
    },
    'valley_only': {
        'components': [
            {'key': 'inner',  'label': 'Valley inner',  'color': '#C2652A', 'marker': 'o', 'ls': '-'},
            {'key': 'outer',  'label': 'Valley outer',  'color': '#2E7D52', 'marker': 's', 'ls': '-'},
        ],
        'delta_pairs': [
            {'a': 'inner', 'b': 'outer', 'label': 'ΔNDVI (Inner−Outer)',
             'color_pos': '#C2652A', 'color_neg': '#2E7D52'},
        ],
        'count_up': ['inner'],
        'count_down': ['outer'],
        'count_up_label': 'Inner',
        'count_down_label': 'Outer',
        'show_sigma': True,
    },
    'combined': {
        'components': [
            {'key': 'inner_windward',  'label': 'Inner windward',  'color': '#1B7340', 'marker': 'o', 'ls': '-'},
            {'key': 'inner_leeward',   'label': 'Inner leeward',   'color': '#B5442A', 'marker': 's', 'ls': '-'},
            {'key': 'outer_windward',  'label': 'Outer windward',  'color': '#6BBF8A', 'marker': '^', 'ls': '--'},
            {'key': 'outer_leeward',   'label': 'Outer leeward',   'color': '#E8945A', 'marker': 'D', 'ls': '--'},
        ],
        # combined delta: 对比河谷内外的焚风不对称性
        # ΔNDVI_inner = inner_windward − inner_leeward
        # ΔNDVI_outer = outer_windward − outer_leeward
        'delta_pairs': [
            {'a': 'inner_windward', 'b': 'inner_leeward',
             'label': 'ΔNDVI inner (W−L)', 'bar_color': '#3D5A80'},
            {'a': 'outer_windward', 'b': 'outer_leeward',
             'label': 'ΔNDVI outer (W−L)', 'bar_color': '#98C1D9'},
        ],
        # count: windward在上, leeward在下; 内外以深浅/alpha区分
        'count_up': ['inner_windward', 'outer_windward'],
        'count_down': ['inner_leeward', 'outer_leeward'],
        'count_up_label': 'Windward',
        'count_down_label': 'Leeward',
        'show_sigma': False,  # 4条线时不画阴影
    },
}

# ============================================================
# 1. Read data
# ============================================================
assert ANALYSIS_MODE in COMPONENT_CONFIG, \
    f"Invalid ANALYSIS_MODE: '{ANALYSIS_MODE}'. Must be one of {list(COMPONENT_CONFIG.keys())}."
print(f"Analysis mode: {ANALYSIS_MODE}")
print(f"Input:  {in_path}")
print(f"Output: {out_path}")

config = COMPONENT_CONFIG[ANALYSIS_MODE]
components = config['components']

df = pd.read_excel(in_path)

# 提取高程信息
elev_all = df['elev_center'].values
elev_bin_width = np.diff(df['elev_lo'].values[:2])[0] if len(df) > 1 else 50

# 提取各分量数据
comp_data = {}  # key -> {'mean': array, 'std': array, 'count': array}
for comp in components:
    key = comp['key']
    mean_col = f'{key}_mean'
    std_col = f'{key}_std'
    count_col = f'{key}_count'

    assert mean_col in df.columns, \
        f"Column '{mean_col}' not found in {in_path}. Available: {list(df.columns)}"

    comp_data[key] = {
        'mean': df[mean_col].values.copy(),
        'std': df[std_col].values.copy() if std_col in df.columns else np.full(len(df), np.nan),
        'count': df[count_col].values.copy() if count_col in df.columns else np.zeros(len(df), dtype=int),
    }

# 过滤: 仅保留至少一个分量有有效数据的高程带
any_valid = np.zeros(len(elev_all), dtype=bool)
for key in comp_data:
    any_valid |= (comp_data[key]['count'] > 0)

elev = elev_all[any_valid]
for key in comp_data:
    for field in ('mean', 'std', 'count'):
        comp_data[key][field] = comp_data[key][field][any_valid]

# 各分量有效掩膜
comp_valid = {key: comp_data[key]['count'] > 0 for key in comp_data}

# 计算delta
delta_pairs = config['delta_pairs']
delta_data = []  # list of {'delta': array, 'valid': array, ...}
for dp in delta_pairs:
    a_key, b_key = dp['a'], dp['b']
    both = comp_valid[a_key] & comp_valid[b_key]
    delta = np.full_like(elev, np.nan, dtype=float)
    delta[both] = comp_data[a_key]['mean'][both] - comp_data[b_key]['mean'][both]
    delta_data.append({
        'delta': delta,
        'valid': both & np.isfinite(delta),
        'label': dp['label'],
        'config': dp,
    })

print(f'Elevation range: {elev.min():.0f} – {elev.max():.0f} m')
print(f'Valid bins: {any_valid.sum()} / {len(any_valid)}')
for dd in delta_data:
    print(f"  {dd['label']}: {dd['valid'].sum()} bins with both sides")

# ============================================================
# 2. Plot
# ============================================================
# --- Academic style ---
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
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
    'mathtext.fontset': 'stix',
})

# --- Figure layout: 三面板上中下 ---
fig = plt.figure(figsize=(14, 7.5))
gs = GridSpec(
    3, 1, height_ratios=[3.5, 1.2, 1],
    hspace=0.06,
    left=0.06, right=0.97, bottom=0.08, top=0.97
)

# ====== Panel (a): NDVI vs Elevation ======
ax_main = fig.add_subplot(gs[0])

show_sigma = config['show_sigma']

# ±1σ 阴影 (仅2分量模式, 先画背景层)
if show_sigma:
    for comp in reversed(components):  # reversed使第一个分量在上层
        key = comp['key']
        vmask = comp_valid[key]
        mean_v = comp_data[key]['mean']
        std_v = comp_data[key]['std']
        ax_main.fill_between(
            elev[vmask],
            (mean_v - std_v)[vmask],
            (mean_v + std_v)[vmask],
            color=comp['color'], alpha=0.12, edgecolor='none', zorder=1,
        )

# 均值曲线
for i, comp in enumerate(components):
    key = comp['key']
    vmask = comp_valid[key]
    ax_main.plot(
        elev[vmask], comp_data[key]['mean'][vmask],
        color=comp['color'], linewidth=1.8, linestyle=comp['ls'], alpha=0.6,
        zorder=4,
    )

# 稀疏数据标记
n_show = max(1, len(elev) // 16)
for comp in components:
    key = comp['key']
    vmask = comp_valid[key]
    idx = np.where(vmask)[0][::n_show]
    ax_main.scatter(
        elev[idx], comp_data[key]['mean'][idx],
        s=22, zorder=5,
        facecolors='white', edgecolors=comp['color'], linewidths=1.2,
        marker=comp['marker'],
    )

# Y轴自适应
all_vals_list = []
for comp in components:
    key = comp['key']
    vmask = comp_valid[key]
    if show_sigma:
        all_vals_list.append((comp_data[key]['mean'] - comp_data[key]['std'])[vmask])
        all_vals_list.append((comp_data[key]['mean'] + comp_data[key]['std'])[vmask])
    else:
        all_vals_list.append(comp_data[key]['mean'][vmask])

all_vals = np.concatenate(all_vals_list)
if len(all_vals) > 0:
    y_lo = max(0, np.nanmin(all_vals) - 0.02)
    y_hi = min(1, np.nanmax(all_vals) + 0.02)
else:
    y_lo, y_hi = 0, 1
ax_main.set_ylim(y_lo, y_hi)
ax_main.set_xlim(elev.min(), elev.max())

ax_main.set_ylabel('NDVI', fontsize=12)
ax_main.tick_params(labelbottom=False)
ax_main.tick_params(which='both', top=True, right=True)
ax_main.yaxis.grid(True, linestyle='--', linewidth=0.3, alpha=0.4, color='grey')
ax_main.set_axisbelow(True)

# 图例
legend_handles = []
for comp in components:
    sigma_str = ' (mean ± 1σ)' if show_sigma else ''
    legend_handles.append(
        Line2D([0], [0], color=comp['color'], linewidth=1.8,
               linestyle=comp['ls'],
               marker=comp['marker'], markersize=4.5,
               markerfacecolor='white',
               markeredgewidth=1.2, markeredgecolor=comp['color'],
               label=f"{comp['label']}{sigma_str}")
    )

# 根据分量数调整图例列数
legend_ncol = 2 if len(components) <= 2 else 2
legend_fontsize = 9.5 if len(components) <= 2 else 8.5

ax_main.legend(
    handles=legend_handles,
    loc='lower right',
    fontsize=legend_fontsize,
    framealpha=0.88,
    edgecolor='#CCCCCC',
    handlelength=2.5,
    ncol=legend_ncol,
)

ax_main.text(
    0.01, 0.97, '(a)',
    transform=ax_main.transAxes,
    fontsize=12, fontweight='bold', va='top',
)

# ====== Panel (b): ΔNDVI bars ======
ax_delta = fig.add_subplot(gs[1], sharex=ax_main)

n_delta = len(delta_data)

if n_delta == 1:
    # ---- 单delta系列: 按正负分色 (原始行为) ----
    dd = delta_data[0]
    dp = dd['config']
    bar_w = elev_bin_width * 0.8
    dv = dd['valid']
    delta_v = dd['delta']

    # 按正负分色
    if 'color_pos' in dp and 'color_neg' in dp:
        bar_colors = np.where(delta_v >= 0, dp['color_pos'], dp['color_neg'])
    else:
        bar_colors = np.where(delta_v >= 0, '#2E7D52', '#C2652A')

    ax_delta.bar(
        elev[dv], delta_v[dv],
        width=bar_w, color=bar_colors[dv],
        alpha=0.65, edgecolor='none', zorder=2,
    )

    # 方向标注
    # 提取A和B的标签
    a_label = None
    b_label = None
    for comp in components:
        if comp['key'] == dp['a']:
            a_label = comp['label']
        if comp['key'] == dp['b']:
            b_label = comp['label']
    a_label = a_label or dp['a']
    b_label = b_label or dp['b']
    color_a = dp.get('color_pos', '#2E7D52')
    color_b = dp.get('color_neg', '#C2652A')

    ax_delta.text(
        0.99, 0.92, f'{a_label} greener ↑', transform=ax_delta.transAxes,
        fontsize=8, color=color_a, ha='right', va='top', fontstyle='italic',
    )
    ax_delta.text(
        0.99, 0.08, f'{b_label} greener ↓', transform=ax_delta.transAxes,
        fontsize=8, color=color_b, ha='right', va='bottom', fontstyle='italic',
    )

elif n_delta == 2:
    # ---- 双delta系列: 并列柱状图 (combined模式) ----
    # 用统一颜色区分 inner vs outer, 正负方向自然表达不对称性方向
    bar_w = elev_bin_width * 0.35  # 较窄以便并排
    offset = elev_bin_width * 0.20  # 偏移量

    for idx_d, dd in enumerate(delta_data):
        dp = dd['config']
        dv = dd['valid']
        delta_v = dd['delta']
        bar_color = dp.get('bar_color', '#3D5A80' if idx_d == 0 else '#98C1D9')
        x_offset = -offset if idx_d == 0 else +offset

        ax_delta.bar(
            elev[dv] + x_offset, delta_v[dv],
            width=bar_w, color=bar_color,
            alpha=0.75, edgecolor='none', zorder=2,
            label=dd['label'],
        )

    ax_delta.legend(
        loc='lower left', fontsize=8,
        framealpha=0.88, edgecolor='#CCCCCC',
        handlelength=1.5,
        ncol=1,
    )

    # 方向标注 (通用: windward greener ↑ / leeward greener ↓)
    ax_delta.text(
        0.99, 0.92, 'Windward greener ↑', transform=ax_delta.transAxes,
        fontsize=7.5, color='#3D5A80', ha='right', va='top', fontstyle='italic',
    )
    ax_delta.text(
        0.99, 0.08, 'Leeward greener ↓', transform=ax_delta.transAxes,
        fontsize=7.5, color='#3D5A80', ha='right', va='bottom', fontstyle='italic',
    )

# 零线
ax_delta.axhline(y=0, color='k', linewidth=0.5, zorder=1)

ax_delta.set_ylabel('ΔNDVI', fontsize=12)
ax_delta.tick_params(labelbottom=False)
ax_delta.tick_params(which='both', top=True, right=True)

# Y轴对称
all_delta_valid = np.concatenate([dd['delta'][dd['valid']] for dd in delta_data])
if len(all_delta_valid) > 0:
    delta_abs_max = np.nanmax(np.abs(all_delta_valid)) * 1.15
else:
    delta_abs_max = 0.1
ax_delta.set_ylim(-delta_abs_max, delta_abs_max)
ax_delta.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4, symmetric=True))

ax_delta.text(
    0.01, 0.95, '(b)',
    transform=ax_delta.transAxes,
    fontsize=12, fontweight='bold', va='top',
)

# ====== Panel (c): Pixel count ======
ax_count = fig.add_subplot(gs[2], sharex=ax_main)

bar_w_count = elev_bin_width * 0.8

# 收集所有分量的count用于归一化
all_counts = np.concatenate([comp_data[key]['count'] for key in comp_data])
max_count = all_counts.max() if all_counts.max() > 0 else 1

count_up_keys = config['count_up']
count_down_keys = config['count_down']

if len(count_up_keys) == 1 and len(count_down_keys) == 1:
    # ---- 2分量: 简单背靠背 (原始行为) ----
    up_key = count_up_keys[0]
    dn_key = count_down_keys[0]
    up_color = next(c['color'] for c in components if c['key'] == up_key)
    dn_color = next(c['color'] for c in components if c['key'] == dn_key)

    up_norm = comp_data[up_key]['count'] / max_count
    dn_norm = comp_data[dn_key]['count'] / max_count

    up_valid = comp_valid[up_key]
    dn_valid = comp_valid[dn_key]

    ax_count.bar(
        elev[up_valid], up_norm[up_valid],
        width=bar_w_count, color=up_color, alpha=0.5, edgecolor='none', zorder=2,
    )
    ax_count.bar(
        elev[dn_valid], -dn_norm[dn_valid],
        width=bar_w_count, color=dn_color, alpha=0.5, edgecolor='none', zorder=2,
    )

    ax_count.text(
        0.99, 0.88, config['count_up_label'], transform=ax_count.transAxes,
        fontsize=8, color=up_color, ha='right', va='top', fontweight='bold',
    )
    ax_count.text(
        0.99, 0.12, config['count_down_label'], transform=ax_count.transAxes,
        fontsize=8, color=dn_color, ha='right', va='bottom', fontweight='bold',
    )

else:
    # ---- 4分量: 分组背靠背 ----
    # 视觉编码: 位置(上/下) = windward/leeward, 颜色 = inner/outer
    # 使用独立于panel(a)迎/背风坡色系的inner/outer专用色,
    # 确保上下两组柱状图颜色一致, 图例不产生歧义
    C_COUNT_INNER = '#4A7C6F'   # 深青灰 — 河谷内侧
    C_COUNT_OUTER = '#A8CBB7'   # 浅鼠尾草 — 河谷外侧

    # 为每个key分配颜色: 按key名中是否含inner/outer
    count_color_map = {}
    for key in count_up_keys + count_down_keys:
        if 'inner' in key:
            count_color_map[key] = C_COUNT_INNER
        elif 'outer' in key:
            count_color_map[key] = C_COUNT_OUTER
        else:
            count_color_map[key] = '#888888'  # fallback

    n_up = len(count_up_keys)
    n_dn = len(count_down_keys)
    sub_bar_w = bar_w_count / max(n_up, n_dn)  # 每个子柱的宽度

    # 上方分量 (windward)
    for i, key in enumerate(count_up_keys):
        vmask = comp_valid[key]
        norm_v = comp_data[key]['count'] / max_count
        x_off = (i - (n_up - 1) / 2.0) * sub_bar_w
        ax_count.bar(
            elev[vmask] + x_off, norm_v[vmask],
            width=sub_bar_w * 0.9, color=count_color_map[key], alpha=0.55,
            edgecolor='none', zorder=2,
        )

    # 下方分量 (leeward)
    for i, key in enumerate(count_down_keys):
        vmask = comp_valid[key]
        norm_v = comp_data[key]['count'] / max_count
        x_off = (i - (n_dn - 1) / 2.0) * sub_bar_w
        ax_count.bar(
            elev[vmask] + x_off, -norm_v[vmask],
            width=sub_bar_w * 0.9, color=count_color_map[key], alpha=0.55,
            edgecolor='none', zorder=2,
        )

    # 标注: 上方=Windward, 下方=Leeward
    ax_count.text(
        0.99, 0.88, config['count_up_label'], transform=ax_count.transAxes,
        fontsize=8, color='#333333', ha='right', va='top', fontweight='bold',
    )
    ax_count.text(
        0.99, 0.12, config['count_down_label'], transform=ax_count.transAxes,
        fontsize=8, color='#333333', ha='right', va='bottom', fontweight='bold',
    )

    # 图例: inner/outer专用色 (上下一致)
    legend_patches = [
        Patch(facecolor=C_COUNT_INNER, alpha=0.55, label='Inner'),
        Patch(facecolor=C_COUNT_OUTER, alpha=0.55, label='Outer'),
    ]
    ax_count.legend(
        handles=legend_patches, loc='lower left',
        fontsize=7, framealpha=0.8, edgecolor='#CCCCCC',
        handlelength=1.0, handleheight=0.8,
        ncol=2,
    )

ax_count.axhline(y=0, color='k', linewidth=0.4, zorder=1)

ax_count.set_xlabel('Elevation (m)', fontsize=12)
ax_count.set_ylabel('Pixel count\n(normalized)', fontsize=10)
ax_count.tick_params(which='both', top=True, right=True)
ax_count.set_ylim(-1.15, 1.15)
ax_count.set_yticks([0])
ax_count.set_yticklabels(['0'])

ax_count.text(
    0.01, 0.92, '(c)',
    transform=ax_count.transAxes,
    fontsize=12, fontweight='bold', va='top',
)

# --- Save ---
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.savefig(out_path, dpi=600, bbox_inches='tight', pad_inches=0.08)
print(f'Figure saved to: {out_path}')
plt.show()