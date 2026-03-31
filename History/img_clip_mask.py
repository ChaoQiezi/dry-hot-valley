# @Author  : ChaoQiezi
# @Time    : 2026/3/25 上午8:56
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: img_clip_mask.py

"""
This script is used to 临时的裁剪掩膜
"""

import os
import numpy as np
import rasterio as rio
from rasterio.windows import Window
from rasterio.warp import transform_bounds
from osgeo import gdal


def extract_by_raster_mask(target_path, mask_path, out_path):
    """
    完美复刻 ArcGIS '按掩膜提取' 的核心算法：
    自动求交 -> 虚拟基准对齐(Snap) -> 裁剪输出边界 -> 分块矩阵掩膜

    :param target_path: 目标影像路径 (要被裁的 25GB 大图)
    :param mask_path: 掩膜影像路径 (大小不一、范围不一的 TIFF)
    :param out_path: 输出影像路径
    """
    print(f"开始执行掩膜提取: {os.path.basename(target_path)}")

    # ---------------------------------------------------------
    # 第一步：获取空间边界，计算严格的重叠区域 (Bounding Box Intersection)
    # ---------------------------------------------------------
    with rio.open(target_path) as tgt, rio.open(mask_path) as orig_msk:
        # 将掩膜的边界坐标转换到目标影像的坐标系下
        msk_bounds = transform_bounds(orig_msk.crs, tgt.crs, *orig_msk.bounds)

        # 计算两个框的交集
        intersect_left = max(tgt.bounds.left, msk_bounds[0])
        intersect_bottom = max(tgt.bounds.bottom, msk_bounds[1])
        intersect_right = min(tgt.bounds.right, msk_bounds[2])
        intersect_top = min(tgt.bounds.top, msk_bounds[3])

        if intersect_left >= intersect_right or intersect_bottom >= intersect_top:
            raise ValueError("错误：目标影像与掩膜影像在空间上完全没有重叠！")

        # 根据交集坐标，计算出在目标影像上的精确行列号窗口 (Window)
        # .round_lengths().round_offsets() 完美复刻了 ArcGIS 的 Snap Raster (捕捉栅格) 逻辑，确保像素边缘严丝合缝
        crop_window = tgt.window(intersect_left, intersect_bottom, intersect_right, intersect_top)
        crop_window = crop_window.round_lengths().round_offsets()

        # 提取目标影像的 Nodata 和 掩膜的 Nodata
        tgt_nodata = tgt.nodata if tgt.nodata is not None else -9999.0
        msk_nodata = orig_msk.nodata

        # 准备输出文件的属性 (只输出相交的最小边界，不浪费硬盘空间)
        out_meta = tgt.profile.copy()
        out_meta.update({
            'height': crop_window.height,
            'width': crop_window.width,
            'transform': tgt.window_transform(crop_window),  # 更新仿射变换系数为裁剪后的基准
            'nodata': tgt_nodata,
            'BIGTIFF': 'YES',
            'TILED': True,
            'COMPRESS': 'LZW'
        })

    # ---------------------------------------------------------
    # 第二步：魔法操作 - 创建完美对齐的虚拟掩膜 (VRT)
    # 不消耗任何硬盘空间，利用 GDAL C++ 底层将掩膜瞬间重采样、重投影到目标影像的网格上
    # ---------------------------------------------------------
    vrt_mask_path = out_path.replace('.tif', '_temp_aligned_mask.vrt')

    warp_opts = gdal.WarpOptions(
        format="VRT",
        outputBounds=(tgt.bounds.left, tgt.bounds.bottom, tgt.bounds.right, tgt.bounds.top),
        width=tgt.width,
        height=tgt.height,
        dstSRS=tgt.crs.to_wkt(),
        resampleAlg=gdal.GRA_NearestNeighbour  # 掩膜数据必须用最邻近，保持掩膜值的纯粹
    )
    # 生成对齐后的虚拟掩膜
    gdal.Warp(vrt_mask_path, mask_path, options=warp_opts)

    # ---------------------------------------------------------
    # 第三步：利用分块矩阵算法，进行安全的掩膜计算 (In-memory Math)
    # ---------------------------------------------------------
    with rio.open(target_path) as tgt, \
            rio.open(vrt_mask_path) as aligned_msk, \
            rio.open(out_path, 'w', **out_meta) as dst:

        # 遍历输出文件(相交区域)的每一个存储分块
        for ji, dest_window in dst.block_windows(1):

            # 反推这个输出小块，在原始大图(25GB)中的全局窗口位置
            src_window = Window(
                col_off=crop_window.col_off + dest_window.col_off,
                row_off=crop_window.row_off + dest_window.row_off,
                width=dest_window.width,
                height=dest_window.height
            )

            # 读取目标影像和对齐掩膜的对应矩阵块
            tgt_data = tgt.read(1, window=src_window)
            msk_data = aligned_msk.read(1, window=src_window)

            # 制定掩膜规则 (如果掩膜影像有 Nodata 则剔除，否则假设 >0 为有效区域)
            if msk_nodata is not None:
                is_valid = (msk_data != msk_nodata)
            else:
                is_valid = (msk_data > 0)

            # 执行矩阵替换：有效区保留原值，无效区赋 Nodata
            out_data = np.where(is_valid, tgt_data, tgt_nodata)

            # 写回硬盘
            dst.write(out_data, 1, window=dest_window)

    # 打扫战场：删除临时虚拟掩膜
    if os.path.exists(vrt_mask_path):
        os.remove(vrt_mask_path)

    print(f"掩膜提取完成！输出至: {out_path}")