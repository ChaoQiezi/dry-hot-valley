import ee
from datetime import datetime

from utils import cal_ndvi, cloud_mask_by_probability
from qiezi.ee_utils import ee_export_image, image_float2int

# 准备
ee.Initialize(project='chaoqiezipython')
region_dir = 'projects/chaoqiezipython/assets/region/Chuanxi'
s2_dir = 'COPERNICUS/S2_SR_HARMONIZED'  # Sentinel-2 SR HARMONIZED
s2_cloud_dir = r'COPERNICUS/S2_CLOUD_PROBABILITY'  # Sentinel-2 Cloud Probability
# region = ee.Geometry.Rectangle([103.4, 31.2, 103.8, 31.6])  # 川西某一区域
# region = ee.Geometry.Rectangle([97.247493, 25.948207, 104.534109, 34.415239])  # 川西地区外接矩形范围
region = ee.FeatureCollection(region_dir)  # 川西地区
start_date_str = '2023-01-01'
end_date_str = '2023-12-31'
start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
max_cloud_probability = 65  # 云概率阈值(%)

# 时间和空间过滤
filter_criteria = ee.Filter.And(
    ee.Filter.bounds(region),
    ee.Filter.date(start_date_str, end_date_str),
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
s2_masked = s2_with_cloud.map(cloud_mask_by_probability)
# 计算NDVI
s2_ndvi = s2_masked.map(cal_ndvi)
# MVC最大值合成和裁剪
ndvi_composite = s2_ndvi.select('NDVI').max().clip(region)
# 缩放
ndvi_scaled = image_float2int(ndvi_composite, scale_factor=10000, int_type='int16')

# 导出下载
ee_export_image(ndvi_scaled, 'Chuanxi_NDVI', 'NDVI_{}'.format(start_date.year), scale=10, region=region,
                set_COG=False, no_data_value=-32767)
