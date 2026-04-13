"""
This script is used to 绘制不同高程梯度下迎风坡与背风坡NDVI变化图

布局 (上中下三面板):
  上方主面板(a): NDVI随高程变化曲线 (迎风坡 vs 背风坡), 含±1σ阴影
  中间面板(b): ΔNDVI = NDVI_windward - NDVI_leeward 柱状图
               正值(迎风坡更绿)向上, 负值(背风坡更绿)向下
  下方面板(c): 各高程带像元数量 (背靠背柱状图)

三个面板共享X轴(高程)

输入:
  - Excel表格 (由 ndvi_elevation_gradient_stats.py 生成)
输出:
  - 出版质量的高程梯度图
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
in_path = r'G:\GeoProjects\dry_hot_valley\Output\Table\NDVI_elevation_gradient.xlsx'
out_path = r'G:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_elevation_gradient_gemini.png'

# Ensure the output directory exists
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# ============================================================
# 1. Data Loading & Preprocessing
# ============================================================
# 尝试读取 Excel，如果报错则尝试读取同名的 CSV 格式
try:
    df = pd.read_excel(in_path)
except Exception:
    csv_path = in_path.replace('.xlsx', '.csv')
    df = pd.read_csv(csv_path)

# 确保数据列为数值型，处理可能存在的空值
numeric_cols = [
    'elev_center', 'windward_mean', 'windward_std', 'windward_count',
    'leeward_mean', 'leeward_std', 'leeward_count'
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 过滤掉高程为空的行
df = df.dropna(subset=['elev_center'])

# 提取变量
elev = df['elev_center']
w_mean, w_std = df['windward_mean'], df['windward_std']
l_mean, l_std = df['leeward_mean'], df['leeward_std']

# 计算差异 (ΔNDVI)
delta_ndvi = w_mean - l_mean

# 像元数量，缺失值填充为0
w_count = df['windward_count'].fillna(0)
l_count = df['leeward_count'].fillna(0)

# 柱状图宽度设定 (基于高程组距，默认50的话取40以留出间隙)
bin_width = np.nanmedian(df['elev_hi'] - df['elev_lo'])
bar_width = bin_width * 0.8 if not np.isnan(bin_width) else 40

# ============================================================
# 2. Styling Parameters (Publication Quality)
# ============================================================
# Colorblind-friendly colors (Nature/Science style)
color_wind = '#0072B2'   # 优雅的深蓝色
color_lee = '#D55E00'    # 优雅的朱红色
alpha_shade = 0.2
font_dict = {'fontweight': 'bold', 'fontsize': 12}

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']

# ============================================================
# 3. Plotting
# ============================================================
fig = plt.figure(figsize=(8.5, 10), dpi=300)
# 设定网格比例：主图(a)占比最大，辅助图(b)(c)较小
gs = GridSpec(3, 1, height_ratios=[2.5, 1, 1.2], hspace=0.1)

ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax1)
ax3 = fig.add_subplot(gs[2], sharex=ax1)

# ------------------------------------------------------------
# Panel (a): NDVI vs Elevation Curve with ±1σ Shading
# ------------------------------------------------------------
# 迎风坡
ax1.plot(elev, w_mean, color=color_wind, lw=2, label='Windward Slope', zorder=4)
ax1.fill_between(elev, w_mean - w_std, w_mean + w_std, color=color_wind, alpha=alpha_shade, lw=0, zorder=3)

# 背风坡
ax1.plot(elev, l_mean, color=color_lee, lw=2, label='Leeward Slope', zorder=4)
ax1.fill_between(elev, l_mean - l_std, l_mean + l_std, color=color_lee, alpha=alpha_shade, lw=0, zorder=3)

ax1.set_ylabel('NDVI', **font_dict)
ax1.legend(loc='upper right', frameon=False, fontsize=11)
ax1.text(0.015, 0.96, '(a)', transform=ax1.transAxes, fontsize=14, fontweight='bold', va='top')
ax1.tick_params(axis='x', labelbottom=False)

# ------------------------------------------------------------
# Panel (b): ΔNDVI Bar Chart
# ------------------------------------------------------------
# 正值使用迎风坡颜色，负值使用背风坡颜色
color_delta = np.where(delta_ndvi >= 0, color_wind, color_lee)
ax2.bar(elev, delta_ndvi, width=bar_width, color=color_delta, alpha=0.9, zorder=3)

ax2.axhline(0, color='black', lw=1, ls='--', zorder=2)
ax2.set_ylabel(r'$\Delta$NDVI' + '\n(Wind. - Lee.)', fontweight='bold', fontsize=11)
ax2.text(0.015, 0.94, '(b)', transform=ax2.transAxes, fontsize=14, fontweight='bold', va='top')
ax2.tick_params(axis='x', labelbottom=False)

# ------------------------------------------------------------
# Panel (c): Back-to-Back Bar Chart for Pixel Count
# ------------------------------------------------------------
ax3.bar(elev, w_count, width=bar_width, color=color_wind, alpha=0.9, label='Windward', zorder=3)
ax3.bar(elev, -l_count, width=bar_width, color=color_lee, alpha=0.9, label='Leeward', zorder=3)

ax3.axhline(0, color='black', lw=1, zorder=2)
ax3.set_ylabel('Pixel Count', **font_dict)
ax3.set_xlabel('Elevation (m)', **font_dict)
ax3.text(0.015, 0.95, '(c)', transform=ax3.transAxes, fontsize=14, fontweight='bold', va='top')

# 自定义 Y 轴格式，隐藏负号并加上 'k' 表示千
def abs_k_formatter(x, pos):
    val = abs(x)
    if val >= 1000:
        return f'{val/1000:.0f}k'
    return f'{val:.0f}'

ax3.yaxis.set_major_formatter(mticker.FuncFormatter(abs_k_formatter))

# ============================================================
# 4. Global Adjustments & Saving
# ============================================================
# 统一设置刻度线朝内并去除右侧和上方边框
for ax in [ax1, ax2, ax3]:
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='both', which='major', labelsize=11, direction='in', length=5)

# 自动调整X轴范围，留出一点边界余量
x_min, x_max = elev.min(), elev.max()
margin = bin_width if not np.isnan(bin_width) else 50
ax1.set_xlim(x_min - margin, x_max + margin)

plt.tight_layout()
plt.savefig(out_path, bbox_inches='tight', dpi=300, facecolor='white')
print(f"Chart successfully generated and saved to: {out_path}")
plt.close()