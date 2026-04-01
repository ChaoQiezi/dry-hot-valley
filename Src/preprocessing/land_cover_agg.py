# @Author  : ChaoQiezi
# @Time    : 2026/1/25 下午2:33
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: land_cover_agg.py

"""
This script is used to 对多年的土地利用类型数据集进行聚合得到单张栅格文件.

输入图像为land_cover_process.py处理得到的每年土地利用栅格文件.

聚合要求:
对于任一像元, 24年间存在15年以上(不必连续)的像元均保持同一个类别,那么就将该像元设置为该类别.

若不满足上述要求, 那么该像元被认定为不稳定区域, 那么将该像元设置为某一特定数值例如100, 以便
后续分类别计算sMAPE识别到不稳定区域不纳入计算.

ps： 但注意上述不稳定区域的像元不设置为无效值和常规无效值混为一谈, 后续进行空间分布绘制时
可能需要标注不稳定区域的分布(故不应设置为nan)

ps: 该文件由GPP_ET_inconsistency项目修改而来:

Keep: 1–10 (forests, shrublands, savannas, grasslands), 12, 14 (croplands)
Remove: 11 (wetlands), 13 (urban), 15 (snow/ice), 16 (barren), 17 (water)

ps: MCD12Q1 LC_Prop1分类

:Evergreen_Needleleaf_Forests = 1B; // byte
:Evergreen_Broadleaf_Forests = 2B; // byte
:Deciduous_Needleleaf_Forests = 3B; // byte
:Deciduous_Broadleaf_Forests = 4B; // byte
:Mixed_Forests = 5B; // byte
:Closed_Shrublands = 6B; // byte
:Open_Shrublands = 7B; // byte
:Woody_Savannas = 8B; // byte
:Savannas = 9B; // byte
:Grasslands = 10B; // byte
:Permanent_Wetlands = 11B; // byte
:Croplands = 12B; // byte
:Urban_and_Built-up_Lands = 13B; // byte
:Cropland_Natural_Vegetation_Mosaics = 14B; // byte
:Permanent_Snow_and_Ice = 15B; // byte
:Barren = 16B; // byte
:Water_Bodies = 17B; // byte
:Unclassified = -1B; // byte
:valid_range = 1B, 17B; // byte
:_FillValue = -1B; // byte
"""

import os
import re
import numpy as np
import rasterio as rio
from rasterio.windows import Window, from_bounds
import math
import rioxarray as rxr
import xarray as xr
from dask.distributed import Client, LocalCluster
from dask.diagnostics import ProgressBar
from glob import glob
from scipy import stats
import warnings
import shutil

from qiezi import img_reclass, extract_nodata_value, build_overviews


# 准备
land_cover_dir = r'E:\MyTEMP\Landcover'
out_dir = r'E:\MyTEMP\Landcover\output'
out_global_agg_path = os.path.join(out_dir, 'MODIS_land_cover_global_mode.tif')
out_mask_path = os.path.join(out_dir, 'vegetation_mask_10m_utm47n.tif')
ref_path = r'G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif'
nodata_value = 255
class_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14]
reclass_rule = {
    1: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14],
    nodata_value: [11, 13, 15, 16, 17],  # 设置为无效值
}
chunk_size = {'x': 1024, 'y': 1024}
start_year = 2019
end_year = 2025


def compute_mode_block(block, nodata):
    # block参数
    n_years, bh, bw = block.shape
    n_pixels = bh * bw
    # 重组为 (n_pixels, n_years)
    flat = block.reshape(n_years, n_pixels)
    flat_clean = flat.copy()

    # 无效值处理(映射为0)
    invalid_idx = (flat_clean == nodata) | (flat_clean < 1) | (flat_clean > 17)
    flat_clean[invalid_idx] = 0

    # 计算众数
    n_bins = 18  # 0-17
    counts = np.zeros((n_pixels, n_bins), dtype=np.uint8)
    pixel_idx = np.arange(n_pixels)
    for idx in range(n_years):
        np.add.at(counts, (pixel_idx, flat_clean[idx]), 1)
    counts[:, 0] = 0  # 忽略无效值的计数
    mode = np.argmax(counts, axis=1)

    # 忽略全为无效值(即0)的像元 ==> 重新映射为nodata
    max_count = np.max(counts, axis=1).astype(np.uint8)
    mode[max_count == 0] = nodata

    # 重组为 (bh, bw)
    mode = mode.reshape(bh, bw)

    return mode


def mode_agg(in_paths, out_path, block_rows=2048):
    """全球尺度windowed众数聚合, 不用Dask."""

    # 读取和基本参数
    n_years = len(in_paths)
    srcs = [rio.open(p) for p in in_paths]  # 获取所有栅格句柄
    src_ref = srcs[0]
    h, w = src_ref.height, src_ref.width
    nodata_value = src_ref.nodata
    if nodata_value is None:
        nodata_value = extract_nodata_value(src_ref.dtypes[0])  # MCD12Q1默认_FillValue
    nodata_value = int(nodata_value)
    print(f'全球栅格: {h} x {w}, nodata={nodata_value}, {n_years}年')
    print(f'预估内存峰值: {n_years * block_rows * w * 2 / 1024 ** 3:.1f} GB (int16)')
    n_blocks = math.ceil(h / block_rows)
    print(f'分 {n_blocks} 个块处理 (每块 {block_rows} 行)\n')

    # 输出设置
    out_profile = src_ref.profile.copy()
    out_profile.update(
        dtype='uint8',
        nodata=nodata_value,
        compress='lzw',
        tiled=True,
        blockxsize=512,
        blockysize=512,
    )

    # 分块进行众数聚合
    with rio.open(out_path, 'w', **out_profile) as dst:
        for cur_block_idx in range(n_blocks):
            # 读取当前分块栅格
            cur_row_off = cur_block_idx * block_rows
            cur_height = block_rows
            if cur_block_idx == (n_blocks - 1):
                cur_height = h - cur_row_off
            win = Window(col_off=0, row_off=cur_row_off, width=w, height=cur_height)
            block_stack = np.empty((n_years, cur_height, w), dtype=np.uint8)
            for idx, src in enumerate(srcs):
                block_stack[idx] = src.read(1, window=win)
            # 计算众数
            cur_mode_block = compute_mode_block(block_stack, nodata_value)

            # 输出当前分块
            dst.write(cur_mode_block[None, :, :], window=win)

            print(f'已处理块 {cur_block_idx+1}/{n_blocks}')

    # 释放资源
    for src in srcs:
        src.close()

    print(f'\n全球聚合完成: {out_path}')
    # 文件大小
    fsize = os.path.getsize(out_path) / 1024 ** 2
    print(f'文件大小: {fsize:.1f} MB')


if __name__ == '__main__':
    # 检索
    wildcard = os.path.join(land_cover_dir, 'MODIS_land_cover_[0-9][0-9][0-9][0-9].tif')  # 检索结尾为年份的所有tif文件
    lc_paths = glob(wildcard)
    re_pattern = re.compile(r'MODIS_land_cover_(\d{4}).tif')
    lc_paths = [_p for _p in lc_paths if start_year <= int(re_pattern.search(_p)[1]) <= end_year]

    # 计算众数和输出
    mode_agg(lc_paths, out_global_agg_path)
    # 复制一份, 留作备用
    out_agg_dir = os.path.join(land_cover_dir, 'agg')
    os.makedirs(out_agg_dir, exist_ok=True)
    out_agg_path2 = os.path.join(out_agg_dir, os.path.basename(out_global_agg_path))
    shutil.copy(out_global_agg_path, out_agg_path2)

    # 重分类(just need vegetation)
    out_reclass_path = os.path.join(out_dir, 'MODIS_land_cover_global_mode_reclass.tif')
    img_reclass(out_global_agg_path, out_reclass_path, reclass_rule)

    # 重投影+重采样(对齐栅格)
    ds_lc = rxr.open_rasterio(out_reclass_path)
    ds_ref = rxr.open_rasterio(ref_path)
    ds_lc_warped = ds_lc.rio.reproject_match(ds_ref)
    # 掩膜(UTM - 47, 10m)
    ds_lc_warped = ds_lc_warped.where(~np.isclose(ds_ref, ds_ref.rio.nodata), ds_lc.rio.nodata)
    ds_lc_warped.rio.to_raster(out_mask_path)
    # 创建金字塔
    build_overviews(out_mask_path)


