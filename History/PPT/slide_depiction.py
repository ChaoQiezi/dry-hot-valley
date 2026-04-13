# @Author  : ChaoQiezi
# @Time    : 2026/4/2 上午10:07
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: slide_depiction.py

"""
This script is used to 
"""

"""
script_extract_spatial_stats.py
从 NDVI_interannual_mean.tif 提取空间统计量，用于幻灯片文字描述
运行环境：本地 Python，需要 rasterio, numpy
"""

import numpy as np
import rasterio
from rasterio.enums import Resampling

TIF_PATH = r"G:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif"

print("=" * 55)
print("  NDVI Spatial Statistics — NDVI_interannual_mean.tif")
print("=" * 55)

with rasterio.open(TIF_PATH) as src:
    # 用overview降采样读取，避免内存溢出（overview_level=2即1/4分辨率）
    overview_level = 2
    scale = 1 / (2 ** overview_level)
    out_shape = (
        src.count,
        int(src.height * scale),
        int(src.width  * scale),
    )
    data = src.read(
        out_shape=out_shape,
        resampling=Resampling.average
    )
    nodata = src.nodata
    print(f"  CRS      : {src.crs}")
    print(f"  Res (m)  : {src.res}")
    print(f"  Bands    : {src.count}")
    print(f"  NoData   : {nodata}")

arr = data[0].astype(np.float32)

# 掩掉nodata
if nodata is not None:
    mask = (arr == nodata)
else:
    mask = ~np.isfinite(arr)

arr_valid = arr[~mask]

total_pixels   = arr.size
valid_pixels   = arr_valid.size
nodata_pixels  = total_pixels - valid_pixels
valid_pct      = valid_pixels / total_pixels * 100

ndvi_mean = arr_valid.mean()
ndvi_std  = arr_valid.std()
ndvi_med  = np.median(arr_valid)
ndvi_min  = arr_valid.min()
ndvi_max  = arr_valid.max()
ndvi_p5   = np.percentile(arr_valid, 5)
ndvi_p95  = np.percentile(arr_valid, 95)

# 低值区（干热河谷代理）：NDVI < 0.4
low_pct  = (arr_valid < 0.4).sum()  / valid_pixels * 100
# 高覆盖区：NDVI > 0.8
high_pct = (arr_valid > 0.8).sum()  / valid_pixels * 100
# 中等覆盖：0.4–0.8
mid_pct  = 100 - low_pct - high_pct

print(f"\n  Valid pixels  : {valid_pixels:,}  ({valid_pct:.1f}%)")
print(f"  Mean NDVI     : {ndvi_mean:.4f}")
print(f"  Std  NDVI     : {ndvi_std:.4f}")
print(f"  Median NDVI   : {ndvi_med:.4f}")
print(f"  Min  NDVI     : {ndvi_min:.4f}")
print(f"  Max  NDVI     : {ndvi_max:.4f}")
print(f"  5th  pct      : {ndvi_p5:.4f}")
print(f"  95th pct      : {ndvi_p95:.4f}")
print(f"\n  NDVI < 0.4    : {low_pct:.1f}%  (sparse/bare — dry-hot valley proxy)")
print(f"  NDVI 0.4–0.8  : {mid_pct:.1f}%  (moderate vegetation)")
print(f"  NDVI > 0.8    : {high_pct:.1f}%  (dense vegetation)")

# 纬度方向统计（沿行聚合，粗估北南梯度）
# 仅在overview级别做，精度足够幻灯片叙述
row_means = np.nanmean(np.where(~mask, arr, np.nan), axis=1)
# 找最低和最高纬度行对应的均值（行0=北）
north_mean = np.nanmean(row_means[:len(row_means)//5])      # 最北20%行
south_mean = np.nanmean(row_means[4*len(row_means)//5:])    # 最南20%行
print(f"\n  North-zone mean NDVI (~33–34°N) : {north_mean:.4f}")
print(f"  South-zone mean NDVI (~26–27°N) : {south_mean:.4f}")
print("=" * 55)