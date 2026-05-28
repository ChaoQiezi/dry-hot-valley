# @Author  : ChaoQiezi
# @Time    : 2026/4/2
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dem_reclass.py
"""
Visualise the reclassified DEM (1 000 m elevation bands) for western Sichuan.
Style is consistent with the NDVI spatial-distribution figure already published.
"""

import os
import warnings

from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from rasterio.enums import Resampling
from rasterio.plot import show
import rioxarray as rxr
warnings.filterwarnings('ignore')

# 0. Configuration
reclass_dem_path = r"E:\GeoProjects\dry_hot_valley\GeoFactor\DEM\elevation_reclass_1000m.tif"
out_plot_path = r"E:\GeoProjects\dry_hot_valley\Result\Chart\DEM_reclass_spatial.png"
lon_min, lon_max = 97.0, 105.0
lat_min, lat_max = 25.6, 34.6
# 1. Read data & Reproject
print("Reading and reprojecting reclassified DEM …")
dem_da = rxr.open_rasterio(reclass_dem_path, masked=True, overview_level=3).squeeze().drop_vars('band')
# Discrete raster → nearest-neighbour resampling (never bilinear!)
dem_geo = dem_da.rio.reproject("EPSG:4326", resampling=Resampling.nearest, nodata=dem_da.rio.nodata)
dem_vals = dem_geo.values
lons = dem_geo.x.values
lats = dem_geo.y.values
valid = np.isfinite(dem_vals) & (dem_vals > 0)
if not valid.any():
    raise ValueError("No valid classified pixels found after reprojection.")
min_class = int(np.nanmin(dem_vals[valid]))
max_class = int(np.nanmax(dem_vals[valid]))
n_classes = max_class - min_class + 1
print(f"  Elevation classes: {min_class} → {max_class}  ({n_classes} classes)")
# 2. Colour palette — hand-picked topographic progression
#    low (warm greens) → mid (golden/tan) → high (cool greys/white)
# Palette designed for 7 classes (0–7000 m). If your data has a
# different number, it will interpolate gracefully.
_anchor_colors = [
    '#2D6A4F',  # class 1:  0–1 000 m   deep forest green  (low-valley vegetation)
    '#52B788',  # class 2:  1–2 000 m   medium green        (montane forest belt)
    '#B7E4C7',  # class 3:  2–3 000 m   light green         (subalpine transition)
    '#F2CC8F',  # class 4:  3–4 000 m   warm sand/gold      (alpine meadow / shrub)
    '#E07A5F',  # class 5:  4–5 000 m   terracotta          (alpine sparse veg)
    '#BC6C8A',  # class 6:  5–6 000 m   muted mauve         (periglacial / rock)
    '#8E9AAF',  # class 7:  6–7 000 m   cool grey-blue      (nival / ice zone)
]
# Trim or extend palette to actual number of classes
if n_classes <= len(_anchor_colors):
    palette = _anchor_colors[:n_classes]
else:
    # Linearly interpolate in RGB space for more classes
    from matplotlib.colors import LinearSegmentedColormap
    _base_cmap = LinearSegmentedColormap.from_list('topo_ext', _anchor_colors, N=256)
    palette = [mcolors.to_hex(_base_cmap(i / (n_classes - 1))) for i in range(n_classes)]
cmap = mcolors.ListedColormap(palette)
bounds = np.arange(min_class - 0.5, max_class + 1.5, 1)
norm = mcolors.BoundaryNorm(bounds, cmap.N)
# 3. Plot
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'mathtext.fontset': 'stix',
    'font.size': 11,
    'axes.linewidth': 0.8,
    'figure.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.08,
})
fig = plt.figure(figsize=(8.5, 8))
proj = ccrs.PlateCarree()
ax = fig.add_subplot(1, 1, 1, projection=proj)
ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)
# Raster layer
im = ax.pcolormesh(
    lons, lats, dem_vals,
    cmap=cmap, norm=norm,
    transform=proj, shading='auto', rasterized=True,
)
# Mapfeatures
ax.add_feature(cfeature.BORDERS, linewidth=0.6, edgecolor='#555555')
ax.add_feature(
    cfeature.NaturalEarthFeature(
        'cultural', 'admin_1_states_provinces_lines', '10m',
        edgecolor='#888888', facecolor='none'),
    linewidth=0.4, linestyle=':'
)
# ── Ticks & gridlines (four-side inward ticks, matching NDVI figure) ─
ax.set_xticks(np.arange(97, 106, 2), crs=proj)
ax.set_yticks(np.arange(26, 35, 2), crs=proj)
ax.xaxis.set_major_formatter(LongitudeFormatter())
ax.yaxis.set_major_formatter(LatitudeFormatter())
ax.tick_params(which='both', direction='in', top=True, right=True,
               length=4, width=0.6, labelsize=10)
gl = ax.gridlines(draw_labels=False, linewidth=0.35, linestyle='--',
                  color='gray', alpha=0.5)
gl.xlocator = mticker.FixedLocator(np.arange(97, 106, 2))
gl.ylocator = mticker.FixedLocator(np.arange(26, 35, 2))
# ── Legend (patch-based, cleaner than colorbar for discrete classes) ─
legend_handles = []
for i, cls in enumerate(range(min_class, max_class + 1)):
    lo = (cls - 1) * 1000
    hi = cls * 1000
    label = f'{lo}\u2013{hi} m'
    legend_handles.append(
        mpatches.Patch(facecolor=palette[i], edgecolor='#444444',
                       linewidth=0.4, label=label)
    )
leg = ax.legend(
    handles=legend_handles,
    title='Elevation',
    loc='lower left',
    fontsize=9,
    title_fontsize=10,
    frameon=True,
    framealpha=0.92,
    edgecolor='#AAAAAA',
    fancybox=False,
    borderpad=0.6,
    labelspacing=0.45,
    handlelength=1.3,
    handleheight=1.0,
)
leg.get_frame().set_linewidth(0.5)
plt.tight_layout()
# Save
os.makedirs(os.path.dirname(out_plot_path), exist_ok=True)
fig.savefig(out_plot_path, dpi=600)
print(f"Figure saved → {out_plot_path}")
plt.show()
