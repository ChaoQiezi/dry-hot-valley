# @Author  : ChaoQiezi
# @Time    : 2026/3/16 上午11:36
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: era5_u_v_postgis_preprocess.py

"""
This script is used to 将gis软件重投影和重采样后的的u、v数据集进行批量掩膜
"""
import os.path
from glob import glob
import rioxarray as rxr
from dask.distributed import Client, LocalCluster, Lock
import rasterio as rio
from rasterio.enums import Resampling
from qiezi.geo import build_overviews

if __name__ == '__main__':
    # 准备
    cluster = LocalCluster(threads_per_worker=4, n_workers=4, memory_limit='8GB')
    client = Client(cluster)
    print('client dashboard:', client.dashboard_link)
    in_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\unmasked'
    out_dir = r'G:\GeoProjects\dry_hot_valley\u_v\10m\new'
    ref_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif'
    chunks = 4096 * 2

    # 检索
    wildcard = 'u_*hPa_10m.tif'
    wildcard = os.path.join(in_dir, wildcard)
    img_paths = glob(wildcard)
    # 读取掩膜文件
    ref_img = rxr.open_rasterio(ref_path, masked=True, chunks=chunks)
    # 迭代掩膜
    for cur_path in img_paths:
        # 输出参数
        cur_out_name = os.path.basename(cur_path)
        cur_out_path = os.path.join(out_dir, cur_out_name)
        if os.path.exists(cur_out_path):
            build_overviews(cur_out_path)
            continue
        with rio.open(cur_path, 'r') as src:
            out_profile = src.profile.copy()
        out_profile['tiled'] = True
        out_profile['blockxsize'] = chunks
        out_profile['blockysize'] = chunks
        out_profile['compress'] = out_profile.get('compress', 'lzw')

        # 掩膜
        cur_img = rxr.open_rasterio(cur_path, masked=True, chunks=chunks)
        cur_img_masked = cur_img.where(ref_img.notnull())  # where对值为True的部分进行保留, 其他部分设为缺失值

        # 输出
        cur_img_masked.rio.to_raster(
            cur_out_path,
            windowed=True,
            lock=Lock('multi-mask'),
            **out_profile
        )
        build_overviews(cur_out_path)

        print(f'{cur_out_name} done.')
