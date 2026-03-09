import ee
import geemap

from utils import calculate_ndvi, cloud_mask_s2
from qiezi.ee_utils import ee_export_image

# 准备
ee.Initialize(project='chaoqiezipython')
region_dir = 'projects/chaoqiezipython/assets/region/Chuanxi'
# region = ee.Geometry.Rectangle([103.4, 31.2, 103.8, 31.6])  # 川西某一区域
# region = ee.Geometry.Rectangle([97.247493, 25.948207, 104.534109, 34.415239])  # 川西某一区域
region = ee.FeatureCollection(region_dir)  # 川西地区
start_date = '2023-06-01'
end_date = '2023-09-30'
sentinel_2_dir = 'COPERNICUS/S2_SR_HARMONIZED'
cloud_threshold = 20  # 场景级云量阈值(%)

# 场景级云过滤(剔除高云量影像)
sentinel_2 = (ee.ImageCollection(sentinel_2_dir)
              .filterDate(start_date, end_date)
              .filterBounds(region)
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold)))
print(f'过滤后影像数量: {sentinel_2.size().getInfo()}')

# 像素级云掩膜
sentinel_2_masked = sentinel_2.map(cloud_mask_s2)

# 计算NDVI
sentinel_2_ndvi = sentinel_2_masked.map(calculate_ndvi)

# MVC合成和裁剪
# ndvi_composite = sentinel_2_ndvi.select('NDVI').median().clip(region)
ndvi_composite = sentinel_2_ndvi.select('NDVI').max().clip(region)

# 可视化
ndvi_vis = {
    'min': -0.2,
    'max': 0.9,
    'palette': [
        '#d73027',  # 极低NDVI (裸地/水体)
        '#fc8d59',  # 低NDVI
        '#fee08b',  # 中低NDVI
        '#d9ef8b',  # 中NDVI
        '#91cf60',  # 中高NDVI
        '#1a9850',  # 高NDVI (密集植被)
    ]
}
# 可视化
Map = geemap.Map()
Map.centerObject(region, zoom=10)
Map.addLayer(ndvi_composite, ndvi_vis, 'NDVI (中值合成)')
Map.addLayer(region, {'color': 'red'}, '研究区域', opacity=0.3)
Map.addLayerControl()
Map

# 统计
stats = ndvi_composite.reduceRegion(
    reducer=ee.Reducer.mean()
    .combine(ee.Reducer.minMax(), sharedInputs=True)  # sharedInputs=True
    .combine(ee.Reducer.stdDev(), sharedInputs=True),
    geometry=region,
    scale=10,  # Sentinel-2 B4/B8分辨率为10m
    maxPixels=1e9
)
print(f'均值:   {stats.get("NDVI_mean").getInfo():.4f}')
print(f'最小值: {stats.get("NDVI_min").getInfo():.4f}')
print(f'最大值: {stats.get("NDVI_max").getInfo():.4f}')
print(f'标准差: {stats.get("NDVI_stdDev").getInfo():.4f}')

# 导出下载
ee_export_image(ndvi_composite, 'Chuanxi_NDVI', 'NDVI', scale=10, region=region)
