import ee
from datetime import datetime
from calendar import monthrange

from utils import cal_ndvi, cloud_mask_by_probability
from qiezi.ee_utils import ee_export_image, image_float2int

# 准备
ee.Initialize(project='chaoqiezipython')
s2_dir = 'COPERNICUS/S2_SR_HARMONIZED'  # Sentinel-2 SR HARMONIZED
s2_cloud_dir = r'COPERNICUS/S2_CLOUD_PROBABILITY'  # Sentinel-2 Cloud Probability
# 西南地区外接矩形 (基于 Xinan.shp). Rectangle 而非 FeatureCollection 以防止掩膜裁剪
region = ee.Geometry.Rectangle([92.1, 22.4, 106.6, 35.6])  # [西, 南, 东, 北]
start_date_str = '2024-01-01'
end_date_str = '2025-12-31'
sos_month_start = 5  # growing season 开始月份
sos_month_end = 9  # growing season 截止月份
start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
max_cloud_probability = 65  # 云概率阈值(%)

for year in range(start_date.year, end_date.year + 1):
    # 当前年份时间范围
    cur_start_date = '{}-{:02d}-01'.format(year, sos_month_start)
    cur_end_date = '{}-{:02d}-{}'.format(year, sos_month_end, monthrange(year, sos_month_end)[1])

    # 时间和空间过滤
    filter_criteria = ee.Filter.And(
        ee.Filter.bounds(region),
        ee.Filter.date(cur_start_date, cur_end_date),
    )
    s2 = (ee.ImageCollection(s2_dir)
          .filter(filter_criteria)
          .select(['B4', 'B8']))
    s2_cloud = ee.ImageCollection(s2_cloud_dir).filter(filter_criteria)
    # 整合s2和s2cloudless
    match_criteria = ee.Filter.equals(leftField='system:index', rightField='system:index')
    s2_with_cloud = ee.Join.saveFirst('cloud_mask').apply(primary=s2, secondary=s2_cloud, condition=match_criteria)
    s2_with_cloud = ee.ImageCollection(s2_with_cloud)
    # 像素级云掩膜
    s2_masked = s2_with_cloud.map(lambda img: cloud_mask_by_probability(img, max_cloud_probability))
    # 计算NDVI
    s2_ndvi = s2_masked.map(cal_ndvi)
    # MVC最大值合成和裁剪
    ndvi_composite = s2_ndvi.select('NDVI').max().clip(region)
    # 缩放
    ndvi_scaled = image_float2int(ndvi_composite, scale_factor=10000, int_type='int16')

    # 导出下载
    ee_export_image(ndvi_scaled, 'Chuanxi_NDVI', 'NDVI_{}_m{:02d}_m{:02d}'.format(year, sos_month_start, sos_month_end), scale=10, region=region,
                    set_COG=False, no_data_value=-32767)
