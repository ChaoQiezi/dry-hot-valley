# @Author  : ChaoQiezi
# @Time    : 2026/3/13 下午2:31
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: dead_code.py

"""
This script is used to 
"""

from dask.distributed import LocalCluster, Client
import rasterio as rio
from rasterio.warp import reproject
import rioxarray as rxr
import os

out_dir = r'E:\MyTEMP\Landcover\output'
in_path = os.path.join(out_dir, 'MODIS_land_cover_global_mode.tif')
ref_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif'
out_mask_path = os.path.join(out_dir, 'vegetation_mask_10m_utm47n.tif')

ds_lc = rxr.open_rasterio(in_path)
ds_ref = rxr.open_rasterio(ref_path)

ds_lc_warped = ds_lc.rio.reproject_match(ds_ref)

