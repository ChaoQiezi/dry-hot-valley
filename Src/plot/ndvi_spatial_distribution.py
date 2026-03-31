# @Author  : ChaoQiezi
# @Time    : 2026/3/28 下午12:38
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: ndvi_spatial_distribution.py

"""
This script is used to plot the interannual NDVI spatial distribution
with a latitudinal zonal-mean profile (publication-quality figure).

Reference style: two-panel figure
  (a) Spatial map of mean NDVI over Chuanxi area
  (b) Latitudinal zonal-mean NDVI curve with ±1 std shading

Notes:
  - The input GeoTIFF is ~20GB at 10m resolution with overviews (.ovr).
  - The CRS is PROJECTED, not geographic.
  - We open at a coarse overview level for plotting, then reproject to
    EPSG:4326 so that cartopy PlateCarree works correctly.
"""

import os
import numpy as np
import xarray as xr
import rioxarray as rxr
import rasterio as rio
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
import warnings

warnings.filterwarnings('ignore')

# ============================================================
# 0. Configuration
# ============================================================
in_path = r'G:\GeoProjects\dry_hot_valley\NDVI\Interannual\NDVI_interannual_mean.tif'
out_fig = r'G:\GeoProjects\dry_hot_valley\Result\Chart\NDVI_interannual_mean_spatial.png'
# 研究区大致范围 (川西地区, 地理坐标°)
lon_min, lon_max = 97.0, 105.0
lat_min, lat_max = 26.0, 34.5

# overview_level: 直接打开对应的overview金字塔层级
# rasterio.open(path, overview_level=N) 中 N 从0开始
# level 0 = 第一层overview (通常2x降采样), level 4 ≈ 16x~32x降采样
# 可通过 gdalinfo 查看有多少层 overview, 根据需要调整
overview_level = 4

# NDVI 色标范围
vmin, vmax = 0.0, 1.0
# 纬度剖面中标注的关键纬度线(°N)
key_lats = [27, 29, 31, 33]


# ============================================================
# 1. Read data — directly open overview + reproject to WGS84
# ============================================================
def read_ndvi(path, overview_level=4):
    """
    Read a large GeoTIFF using rioxarray, directly at an overview level.

    Why overview_level parameter?
    -----------------------------
    rioxarray.open_rasterio(path, overview_level=N) opens the Nth
    overview layer DIRECTLY from the .ovr pyramid. The returned dataset
    already has the correct transform, shape, and CRS — no manual
    resampling or transform calculation needed.

    Contrast with the WRONG approach:
        src.read(1, out_shape=(...))  # manually resamples, ignores .ovr
        transform = src.transform * src.transform.scale(...)  # hacky, error-prone

    Why reproject?
    --------------
    The source file uses a projected CRS (coordinates in meters).
    Cartopy PlateCarree expects lon/lat in degrees. We reproject
    the (small, overview-level) array to EPSG:4326 so that the
    x/y coords become true longitude/latitude.
    """
    # ------ 直接打开overview层级 ------
    da = rxr.open_rasterio(
        path,
        overview_level=overview_level,  # 获取.overviews(1)(1为第一个波段)索引为overview_level的金字塔层级
        masked=True,  # nodata → NaN
    ).squeeze().drop_vars('band')  # 单波段, 去掉band维度

    print(f"原始CRS: {da.rio.crs}")
    print(f"Overview shape: {da.shape}")
    print(f"X range (proj): [{float(da.x.min()):.1f}, {float(da.x.max()):.1f}]")
    print(f"Y range (proj): [{float(da.y.min()):.1f}, {float(da.y.max()):.1f}]")

    # ------ 重投影到 EPSG:4326 (WGS84 地理坐标) ------
    da_geo = da.rio.reproject("EPSG:4326")

    print(f"重投影后CRS: {da_geo.rio.crs}")
    print(f"Lon range: [{float(da_geo.x.min()):.4f}, {float(da_geo.x.max()):.4f}]")
    print(f"Lat range: [{float(da_geo.y.min()):.4f}, {float(da_geo.y.max()):.4f}]")

    return da_geo


# ============================================================
# 2. Compute latitudinal zonal statistics
# ============================================================
def compute_lat_profile(da, n_bins=300):
    """
    Compute latitudinal zonal-mean and ±1 std for the NDVI field.
    Bins the latitude range into n_bins strips and computes statistics.

    Parameters
    ----------
    da : xr.DataArray
        NDVI data with 'y' as latitude (already in EPSG:4326).
    n_bins : int
        Number of latitude bins.

    Returns
    -------
    lat_centers : 1D array, south → north
    means, stds : 1D arrays of zonal statistics
    """
    lat_vals = da.y.values
    data = da.values

    # 确定纬度方向 (统一南→北)
    lat_south = min(lat_vals[0], lat_vals[-1])
    lat_north = max(lat_vals[0], lat_vals[-1])
    lat_edges = np.linspace(lat_south, lat_north, n_bins + 1)
    lat_centers = 0.5 * (lat_edges[:-1] + lat_edges[1:])

    means = np.full(n_bins, np.nan)
    stds = np.full(n_bins, np.nan)

    for i in range(n_bins):
        mask = (lat_vals >= lat_edges[i]) & (lat_vals < lat_edges[i + 1])
        if mask.sum() == 0:
            continue
        strip = data[mask, :]
        valid = strip[np.isfinite(strip)]
        if valid.size > 0:
            means[i] = np.nanmean(valid)
            stds[i] = np.nanstd(valid)

    return lat_centers, means, stds


# ============================================================
# 3. Build the figure
# ============================================================
def plot_ndvi_spatial_latitude(da, out_fig, key_lats, vmin=0, vmax=1,
                               lon_range=(97, 105), lat_range=(26, 34)):
    """
    Create a two-panel publication figure:
      (a) Spatial map of interannual mean NDVI
      (b) Latitudinal zonal-mean profile with ±1σ shading
    """
    # --- Academic style settings ---
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman'],
        'font.size': 10,
        'axes.linewidth': 0.8,
        'axes.labelsize': 11,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 0.6,
        'ytick.major.width': 0.6,
        'xtick.minor.width': 0.4,
        'ytick.minor.width': 0.4,
        'legend.fontsize': 9,
        'figure.dpi': 300,
        'savefig.dpi': 600,
        'savefig.bbox': 'tight',
        'mathtext.fontset': 'stix',
    })

    # --- Custom NDVI colormap (brown → yellow-green → dark green) ---
    ndvi_colors = [
        '#8B4513',  # brown (bare soil / low NDVI)
        '#D2B48C',  # tan
        '#F5DEB3',  # wheat
        '#FFFACD',  # lemon chiffon
        '#F0FFF0',  # honeydew
        '#C7EDBB',  # light green
        '#90D68C',  # medium light green
        '#55B848',  # green
        '#2E8B2E',  # medium green
        '#1A6C1A',  # dark green
        '#0A4F0A',  # very dark green
    ]
    ndvi_cmap = mcolors.LinearSegmentedColormap.from_list('ndvi', ndvi_colors, N=256)

    # --- Compute latitudinal profile ---
    lat_centers, lat_means, lat_stds = compute_lat_profile(da, n_bins=300)

    # --- Create figure layout ---
    fig = plt.figure(figsize=(10, 7.5))
    gs = GridSpec(
        1, 2, width_ratios=[3.5, 1],
        wspace=0.02,
        left=0.08, right=0.92, bottom=0.10, top=0.95
    )

    # ====== Panel (a): Spatial Map ======
    proj = ccrs.PlateCarree()
    ax_map = fig.add_subplot(gs[0, 0], projection=proj)
    ax_map.set_extent([*lon_range, *lat_range], crs=proj)

    # 绘制NDVI (da已经是EPSG:4326, x=经度, y=纬度)
    im = ax_map.pcolormesh(
        da.x.values, da.y.values, da.values,
        cmap=ndvi_cmap, vmin=vmin, vmax=vmax,
        transform=proj, shading='auto',
        rasterized=True
    )

    # 地图要素
    ax_map.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor='gray')
    ax_map.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor='gray')
    ax_map.add_feature(
        cfeature.NaturalEarthFeature('cultural', 'admin_1_states_provinces_lines',
                                     '10m', edgecolor='gray', facecolor='none'),
        linewidth=0.6
    )
    # ax_map.add_feature(
    #     cfeature.NaturalEarthFeature('physical', 'rivers_lake_centerlines', '10m',
    #                                  edgecolor='#4A90D9', facecolor='none'),
    #     linewidth=0.3, alpha=0.5
    # )

    # 经纬度刻度
    ax_map.set_xticks(np.arange(lon_range[0], lon_range[1] + 1, 2), crs=proj)
    ax_map.set_yticks(np.arange(lat_range[0], lat_range[1] + 1, 2), crs=proj)
    ax_map.xaxis.set_major_formatter(LongitudeFormatter())
    ax_map.yaxis.set_major_formatter(LatitudeFormatter())
    ax_map.tick_params(which='both', top=True, right=True)

    # 经纬网格线
    gl = ax_map.gridlines(draw_labels=False, linewidth=0.3,
                          linestyle='--', color='gray', alpha=0.5)
    gl.xlocator = mticker.FixedLocator(np.arange(lon_range[0], lon_range[1] + 1, 2))
    gl.ylocator = mticker.FixedLocator(np.arange(lat_range[0], lat_range[1] + 1, 2))

    # 关键纬度参考线
    for lat in key_lats:
        if lat_range[0] <= lat <= lat_range[1]:
            ax_map.axhline(y=lat, color='k', linewidth=0.4, linestyle='--', alpha=0.4)

    # Colorbar
    cbar_ax = fig.add_axes([0.08, 0.04, 0.55, 0.02])
    cbar = fig.colorbar(im, cax=cbar_ax, orientation='horizontal', extend='both')
    cbar.set_label('NDVI', fontsize=11)
    cbar.ax.tick_params(labelsize=9, width=0.5)
    cbar.outline.set_linewidth(0.6)

    # Panel label
    ax_map.text(0.02, 0.97, '(a)', transform=ax_map.transAxes,
                fontsize=12, fontweight='bold', va='top', ha='left',
                bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=2))

    # ====== Panel (b): Latitudinal Profile ======
    ax_lat = fig.add_subplot(gs[0, 1])

    valid = ~np.isnan(lat_means)
    lc = lat_centers[valid]
    lm = lat_means[valid]
    ls = lat_stds[valid]

    # ±1σ 阴影
    ax_lat.fill_betweenx(
        lc, lm - ls, lm + ls,
        color='#B0B0B0', alpha=0.4, edgecolor='none', label='±1σ'
    )
    ax_lat.plot(lm, lc, color='k', linewidth=0.9, label='Zonal mean')

    ax_lat.set_ylim(lat_range)
    ax_lat.set_xlabel('NDVI', fontsize=11)
    ax_lat.set_ylabel('Latitude', fontsize=11)
    ax_lat.yaxis.set_label_position('right')
    ax_lat.yaxis.tick_right()

    lat_ticks = np.arange(lat_range[0], lat_range[1] + 1, 2)
    ax_lat.set_yticks(lat_ticks)
    ax_lat.set_yticklabels([f'{t}°N' for t in lat_ticks])
    ax_lat.tick_params(which='both', direction='in', left=True, right=True)

    # 关键纬度标注
    for lat in key_lats:
        if lat_range[0] <= lat <= lat_range[1]:
            ax_lat.axhline(y=lat, color='k', linewidth=0.4, linestyle='--', alpha=0.4)
            ax_lat.text(ax_lat.get_xlim()[0] + 0.002, lat + 0.15,
                        f'{lat}°N', fontsize=7.5, color='k', va='bottom', ha='left')

    # X轴自适应
    x_margin = 0.05
    x_lo = max(0, np.nanmin(lm - ls) - x_margin)
    x_hi = min(1, np.nanmax(lm + ls) + x_margin)
    ax_lat.set_xlim(x_lo, x_hi)
    ax_lat.xaxis.set_major_locator(mticker.MaxNLocator(nbins=4, prune='both'))

    ax_lat.grid(axis='x', linewidth=0.3, linestyle=':', alpha=0.5)

    ax_lat.text(0.05, 0.97, '(b)', transform=ax_lat.transAxes,
                fontsize=12, fontweight='bold', va='top', ha='left',
                bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=2))

    # ------ Save ------
    fig.savefig(out_fig, dpi=600, bbox_inches='tight', pad_inches=0.1)
    print(f'Figure saved to: {out_fig}')
    plt.show()


# ============================================================
# 4. Main
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("Reading NDVI (overview level → reproject to WGS84)...")
    print("=" * 60)
    da = read_ndvi(in_path, overview_level=overview_level)
    print(f"\nValue range: [{float(da.min()):.4f}, {float(da.max()):.4f}]")

    # 绘图
    plot_ndvi_spatial_latitude(
        da, out_fig,
        key_lats=key_lats,
        vmin=vmin, vmax=vmax,
        lon_range=(lon_min, lon_max),
        lat_range=(lat_min, lat_max),
    )
    print("Done.")


