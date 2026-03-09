# @Author  : ChaoQiezi
# @Time    : 2026/1/23 下午10:37
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: mcd12q1_process.py

"""
This script is used to 针对MCD12Q1(土地覆盖类型)产品数据集进行预处理

注意MCD12Q1是土地利用类型数据集预处理的一些注意事项:

1. 其数据类型为整型, 因此重采样方法设置为最近邻插值
2. 最后的类别不需要按照MODIS上的精细类别输出, 而是应该针对这些精细类别进行聚合, 大致按照如下文件所述进行聚合:
    "F:\PyProJect\GPP_ET_inconsistency\Assets\Doc\LC_type.xlsx"
    所谓聚合, 实际上就是重分类.
3. 最终只需要一张综合了多年的土地利用类型, 具体综合规则询问成师兄.
    主要就是基于某一像元的值连续多少年没有发生变化, 那么就认定为该像元的类别为该值对应的类别(具体待定)

严重警告: 如果后续将此代码用于其他任务, 应当注意到下方输入的Config.hv_ids仅有290个, 而全球的MCD12Q1的Tile有310个, 且
二者的tile集合是相交但是互不包含;
此处没有进行修改是因为该代码是用于全球山区, 因此只使用所有数据集tiles的交集即涉及的290个tiles
"""

import os
from glob import glob
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from osgeo import gdal
from tqdm import tqdm
import time

import Config
from utils import process_modis_land_cover_yearly, img_reproject, img_mask, img_reclass

# 准备
in_dir = r'I:\DataHub\MCD12Q1'
out_dir = r'I:\DataWorkspace\Landcover'
temp_dir = r'E:\MyTemp'
# mountain_path = r"G:\WorkSpace\DEM\global_mountain.tif"
start_date = datetime(2001, 1, 1)  # MCD12Q1数据集时间是从2001年开始的
end_date = datetime(2024, 12, 31)
gpp_name = 'LC_Type1'  # hdf文件中IGBP土地分类的变量名称
start_year = start_date.year
end_year = end_date.year
total_years = end_year - start_year + 1

if __name__ == '__main__':
    # 年尺度迭代
    pbar = tqdm(range(start_year, end_year + 1), desc='MCD12Q1-land_cover预处理', colour='blue', bar_format=Config.bar_format)
    for cur_year in pbar:
        pbar.refresh()

        # 检索
        wildcard = os.path.join(in_dir, 'MCD12Q1.A{}001.*.061.*.hdf'.format(cur_year))
        retrieval_paths = glob(wildcard, recursive=True)
        cur_out_path = os.path.join(out_dir, 'MODIS_land_cover_{}.tif'.format(cur_year))
        if os.path.exists(cur_out_path):
            pbar.write('\n跳过年份(已处理): {}'.format(cur_year))
            continue

        try:
            # hdf --> tif
            pbar.set_postfix_str('正在hdf-->tif中...')
            img_paths = []  # 存储当前年份所有tiles输出为geotiff文件的路径
            with ProcessPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(process_modis_land_cover_yearly, _path, temp_dir, gpp_name) for _path in retrieval_paths]
                for cur_future in as_completed(futures):
                    cur_path = cur_future.result()
                    img_paths.append(cur_path)

            # 镶嵌
            pbar.set_postfix_str('正在镶嵌中...')
            cur_vrt_path = os.path.join(temp_dir, 'modis_mosaic.vrt')
            vrt_options = gdal.BuildVRTOptions(
                resampleAlg=gdal.GRA_NearestNeighbour,  # 对于土地覆盖而言, 插值不能使用双线性或者三次内插
            )
            gdal.BuildVRT(cur_vrt_path, img_paths, options=vrt_options)
            # 重投影(sinu --> WGS84)
            pbar.set_postfix_str('正在重投影中...')
            # cur_glt_path = os.path.join(temp_dir, 'modis_glt.tif')
            cur_glt_path = cur_out_path
            img_reproject(cur_vrt_path, cur_glt_path, resample_alg=gdal.GRA_NearestNeighbour)
            # # 掩膜(全球山区)
            # pbar.set_postfix_str('正在掩膜中...')
            # cur_masked_path = os.path.join(temp_dir, 'modis_masked.tif')
            # img_mask(cur_glt_path, cur_masked_path, mask_path=mountain_path)
        except Exception as e:
            pbar.write('\n异常年份{}: {}'.format(cur_year, e))
            continue

        # # 重分类
        # try:
        #     pbar.set_postfix_str('正在重分类中...')
        #     img_reclass(cur_masked_path, cur_out_path, Config.reclass_rules)
        # except Exception as e:
        #     if os.path.exists(cur_out_path):
        #         os.remove(cur_out_path)
        #     pbar.write('\n异常年份{}: {}'.format(cur_year, e))
        #     continue

        # 删除中间文件
        try:
            pbar.set_postfix_str('正在删除中间文件中...')
            time.sleep(1)  # 休眠一秒, 避免删除文件时, 文件被占用
            _ = [os.remove(cur_path) for cur_path in img_paths + [cur_vrt_path,] if
                 os.path.exists(cur_path)]
        except Exception as e:
            pbar.write('\n异常年份{}: {}'.format(cur_year, e))
            continue

        pbar.write('\n完成年份: {}'.format(cur_year))

