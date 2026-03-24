# @Author  : ChaoQiezi
# @Time    : 2026/3/7 下午2:01
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: utils.py

"""
This script is used to 定义一些通用的函数.
"""

import os
import re

import ee
import numpy as np
from osgeo import gdal, osr
import rasterio as rio

import Config
from qiezi import read_sinu_info, read_h4_var, write_tiff


def cloud_mask_by_scl(image: ee.Image):
    """
    基于SCL(Scene Classification Layer)波段进行像素级云掩膜.
    SCL分类值说明:
        1 - 饱和/缺失       6 - 水体
        2 - 暗区域(含阴影)   7 - 未分类
        3 - 云影             8 - 中概率云
        4 - 植被             9 - 高概率云
        5 - 裸土            10 - 薄卷云
        11 - 冰雪
    保留4(植被)、5(裸土)、6(水体)、11(冰雪)等有效像素.
    """

    scl = image.select('SCL')
    # 保留有效像素: 植被(4), 裸土(5), 水体(6), 冰雪(11)
    valid_mask = (scl.eq(4)
                  .Or(scl.eq(5))
                  .Or(scl.eq(6))
                  .Or(scl.eq(11)))

    return image.updateMask(valid_mask)


def cloud_mask_by_probability(image: ee.Image, max_cloud_probability=65.0):
    """基于Sentinel-2: Cloud Probability进行像素级云掩膜"""

    cloud_mask = ee.Image(image.get('cloud_mask')).select(['probability'])
    not_cloud = cloud_mask.lt(max_cloud_probability)

    return image.updateMask(not_cloud)


def cal_ndvi(image):
    """
    基于Sentinel-2的B8(NIR, 842nm)和B4(Red, 665nm)计算NDVI.
    NDVI = (B8 - B4) / (B8 + B4)
    """

    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)


def process_modis_land_cover_yearly(hdf_path, out_dir, var_name='LC_Type1'):
    # 获取当前文件所在年份和tile号
    result = re.search(r'\.A(\d{4})001\.h(\d{2})v(\d{2})', os.path.basename(hdf_path))
    year, hv_id = result.group(1), 'h{}v{}'.format(result.group(2), result.group(3))

    # 输出设置
    out_path = os.path.join(out_dir, 'MODIS_land_cover_{}_{}.tif'.format(hv_id, year))
    # 判断是否已经预处理过:
    if os.path.exists(out_path):
        out_ds = gdal.Open(out_path)
        if out_ds is not None:
            out_ds = None
            return out_path
        else:
            os.remove(out_path)

    # 获取当前tile的地理+投影信息
    cur_sinu_info = read_sinu_info(hdf_path)
    geo_transform = cur_sinu_info['transform']
    sinu_proj4 = cur_sinu_info['sinu_proj4']

    # 读取变量
    arr_var = read_h4_var(hdf_path, var_name=var_name, scale_op=None)
    # 单位换算: MCD12Q1土地覆盖类型不需要进行单位换算
    # arr_var *= 1000

    # 输出为tif文件(sinu坐标系)
    try:
        write_tiff(out_path, arr_var, geo_transform, proj4_str=sinu_proj4)
    except (Exception, KeyboardInterrupt) as e:
        if os.path.exists(out_path):
            os.remove(out_path)  # 输出tif文件异常, 需要将创建的tif文件删除

    return out_path


def img_reproject(in_path, out_path, resample_alg=gdal.GRA_Bilinear, dst_nodata=None, dst_srs=None):
    """
    重投影和重采样.
    :param in_path: 输入数据集路径.
    :param out_path: 输出数据集路径.
    :param resample_alg: 重采样算法.
    :param dst_nodata: 目标数据集的Nodata值.
    :param dst_srs: 目标数据集的投影信息.
    :return:
    """

    if dst_srs is None:
        dst_srs = osr.SpatialReference()  # 输出坐标系
        dst_srs.ImportFromEPSG(4326)

    from qiezi import extract_nodata_value
    if dst_nodata:
        extract_nodata_value()
    # 重投影
    warp_options = gdal.WarpOptions(
        format='GTiff',
        outputBounds=Config.out_bounds,
        xRes=Config.out_res,
        yRes=Config.out_res,
        dstSRS=dst_srs,
        dstNodata=dst_nodata,
        resampleAlg=resample_alg,
        warpOptions=['WRAP_DATELINE=YES'],  # 国际日期变更线(横跨-180-180需要)
        creationOptions=['BIGTIFF=YES', 'TILED=YES', 'COMPRESS=DEFLATE'],  # 支持大文件
        multithread=True,
    )
    out_ds = gdal.Warp(out_path, in_path, options=warp_options)
    out_ds = None


def img_mask(in_path, out_path, mask_path=Config.global_mountain_path):
    with rio.open(mask_path, 'r') as src:
        img_mountain_mask = src.read(1)
    with rio.open(in_path) as src:
        # 获取波段数量
        img_arr = src.read(masked=True, fill_value=np.nan)
        img_profile = src.profile
    img_arr.mask = img_arr.mask | (img_mountain_mask == 0)  # 1表示山区, 0表示非山区(需要被掩膜掉), 若为多波段则会自动广播
    with rio.open(out_path, 'w', **img_profile) as dst:
        dst.write(img_arr)


def img_reclass(in_path, out_path, reclass_rule):
    """重分类"""

    # 读取原数据集
    with rio.open(in_path, 'r') as src:
        img_arr = src.read(1, masked=True)
        img_profile = src.profile

    # 重分类
    img_out = np.full(img_arr.shape, img_profile['nodata'], dtype=img_profile['dtype'])
    for new_val, old_val in reclass_rule.items():
        img_out[np.isin(img_arr, old_val)] = new_val

    # 输出
    with rio.open(out_path, 'w', **img_profile)as dst:
        dst.write(img_out, 1)