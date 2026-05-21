# 2026/03/05 任务说明

核心: 基于风向划分迎风坡、背风坡, 提取不同海拔梯度的植被差异

简要: 研究主要集中在川西地区, 分析在迎风坡和背风坡区域里不同海拔梯度下的
        植被差异, 植被差异通过NDVI值的差异来表示, NDVI基于Sentinel-2的高
        分辨率数据进行计算.

## 说明

研究区域: 川西地区
植被指标: NDVI(由于需要高分辨率, 因此使用Sentinel-2)
工具: GEE实现

## 注意事项和疑惑

1. 时间范围是多少？研究区域具体是哪里?
2. 迎风坡和背风坡根据什么来划分?是否因时间而变化?
3. 海拔梯度暂定为100m间隔;
4. NDVI计算依据Sentinel-2计算, 但是是否还需要进行额外处理?例如SG滤波等;
5. 最终植被差异以什么形式来呈现, 哪种图哪种表格呢?


# 2026/03/07 情况说明

1. 关于迎风坡和背风坡, 考虑使用saga-gis的Wind Effect根据来划分;
   或者这样考虑更好: 直接分8个坡向和平地, 而只在论文阐述上说明迎风坡和背风坡;
2. 川西地区的边界需要获取得到, 目前是取甘孜、阿坝、凉山三个州作为研究区域进行研究;
3. 还有DEM数据集, 之前有全球1km的数据集, 但是现在需要下载10m分辨率的数据集配合Sentinel-2;
4. 时间尺度是多少呢?是一个月?一个季节?还是分雨季和旱季呢?或者干脆一年?


# 2026/03/09 情况说明

1. 关于时间尺度, 目前按照年尺度先进行研究;
2. 对于已经下载的ALOS DEM数据集(大概率弃用), 虽然其标注了12.5m分辨率的数据集, 但是实际上对于中国及其其他大部分区域, 都是
基于SRTM数据集的30m分辨率上采样得来的, 具体见官方文档:
Assets/Ref/rtc_product_guide_v1.2.pdf; 因此实际上后续研究, 目前(2026/03/09)我们考虑的DEM数据集是使用GLO-30产品, 
从OpenTopography下载(搜索GLO-30即可): https://portal.opentopography.org/dataCatalog
3. 基于GLO-30 DEM产品进行裁剪、掩膜和重采样(10m)以及表面参数计算, 得到DEM、坡度、坡向


# 2026/03/10 情况说明

1. 目前处理年尺度的NDVI, GEE处一年数据需要约2h左右.
2. 关于sentinel-2的去云使用s2cloudless产品, 具体见: https://github.com/sentinel-hub/sentinel2-cloud-detector?tab=readme-ov-file
3. 关于迎风坡和背风坡, 还是着手考虑如何划分!
   目前打算使用saga-gis的Wind Effect工具进行, 见: https://saga-gis.sourceforge.io/saga_tool_doc/2.1.3/ta_morphometry_15.html
   另外需要注意这个wind effect是不是就是风坡夹角或者风效因子, 风坡夹角参考: https://www.cnblogs.com/ChaoQiezi/p/18980920
   关于wind effect, 需要输入风向和风速(例如era5),以及坡向数据;


# 2026/03/11 情况说明

1. GAI(greenness asymmetric index, 绿度不对称指数), 公式为: GAI = NDVI_PFS / NDVI_EFS
   [注: 2026-05-08 起 VAI 差值法取代 GAI 比值法; GAI 相关脚本已移至 History/]
2. GDI(greenness difference index, 绿度差异指数), 公式为: GDI = (NDVI_EFS − NDVI_PFS)/(NDVI_EFS + NDVI_PFS).
3. 目前可能还需要考虑一下是否针对川西地区所有地类进行? 还是只针对和植被相关的地类进行研究呢?


# 2026/03/12 情况说明

1. 迎风坡和背风坡的划分

    目前搜集了相关文献, 已经确定使用SAGA GIS的Wind Effect(Windward, Leeward)风效应指数工具进行迎风坡和背风坡的划分
    - 使用数据包括: DEM、ERA5的600hPa(pressure level)的u, v风场数据;
    - 时间维度上的处理, 取多年生长季(6-8月)的u、v均值(基于风速加权), 计算风向数据, 进而计算风效应指数;
      [注: 2026-05-16 起生长季已改为5-9月]
    - 空间尺度上的处理, 统一在10m分辨率、投影坐标系上计算风效应指数;
    - 迎风坡和背风坡划分, 根据SAGA GIS说明>1表示处在迎风区, <1表示背风区;
    > The 'Wind Effect' is a dimensionless index. Values below 1 indicate wind shadowed areas whereas values above 1 
    > indicate areas exposed to wind

    参考文献:
    > Gerlitz-2015, Bohner-2006, Bohner-2009, Karger-2017;


# 2026/03/17 情况说明

## 关于迎风坡和背风坡、NDVI的说明

> 由于川西地区不同时间段所盛行的风系是不一样的, 因此不应从全年所有时间段的
> 数据中计算出的迎风坡和背风坡, 而应基于川西地区盛行风系及其对应时间段进行考虑;
> 此外, 不同时间范围的NDVI也所表征的植被差异也不同, 例如生长季所代表的
> 植被比旱季所代表的植被要高;
> 目前来看, 既要考虑更好地表征年尺度的NDVI, 又要考虑盛行风系及其对应时间段,
> 所选择的时间段应该既可以较好地表征年尺度的NDVI, 又代表川西地区主要的盛行风系;


# 2026/03/18 情况说明

目前为止的疑问包括:

1. 如何划分迎风坡和背风坡?
2. 为什么使用生长季的NDVI来表征年尺度的植被变化?
3. 如何聚合生长季的风向?
4. 使用600hPa的u, v风场数据是否合适?

1. 使用SAGA-GIS的wind effect工具计算风效应指数, 据此进行二分类
2. 首先是全年盛行风系不一致, 在夏季盛行的风系与冬季不一致, 导致计算出来的迎/背
   风坡也不准确;其次, 使用生长季的NDVI可以排除一些其他的干扰, 更好说明该年尺度
   的植被变化;
3. 聚合方法考虑的是风速加权, 即根据风速对风向进行加权平均, 得到该生长季的风向;
   [注: 最终实现见 Src/preprocessing/wind_direction_cal.py]


2026/03/18 补充

1. 目前从gee上下载的NDVI, 存在2017-2018年的数据仅有少部分切片为有效值, 其余切片均为无效值;


# 2026/03/19 情况说明

1. 关于2017-2018年的Sentinel-2 Level-2A SR数据大量缺失的问题, 实际上是由于
   欧空局在2018年3月26开始系统性为欧洲提供Level-2A SR数据集, 而对于全球来说
   目前来看至少在川西地区是2019年实现完全覆盖.

解决措施:

   目前来看需要调整时间尺度的范围, 调整为2019年-2025年
   
2. 此外，基于目前的的迎/背风坡的划分, 发现迎风坡所处区域的NDVI大都较小,
   而背风坡所处区域的NDVI大都较大.
   
   - 可能是由于海拔跨度比较大, 高山(>5000m)虽然作为迎风坡但是海拔过高气温较低因此NDVI较低;
   - 可能是由于使用的风场数据是600hPa, 或许应该是使用u10和v10, 或者应该进一步进行文献调研了解wind effect工具传入的风场数据;


# 2026/03/23 情况说明(组会总结)

1. 完成情况:
   - 完成迎风坡和背风坡的划分(基于Wind Effect风效应指数)
   - 完成NDVI的下载(2017年-2025年)

2. 老师建议(仅参考)
   - 考虑引入雨季前后的对比;
   - 进行垂直梯度的对比分析时, 200m的海拔梯度跨度过大, 应设置更小例如50m;
   - 对于NDVI分析, 分析部分年份也可, 例如2019年-2025年, 前面的2017-2018年考虑丢弃;


# 2026/03/25 情况说明

1. 目前已经将从GEE-Drive下载的NDVI数据集进行预处理;
2. 今天要完成的是空间尺度上的分析: 
   - 年均值空间分布图(年聚合使用max);
   - 年际均值空间分布图(年际聚合使用mean);
   - 空间分布图轴边记录纬度上的NDVI变化;


# 2026/03/28 情况说明

1. 目前已经完成了NDVI年尺度的时间序列变化的绘制 (Mann-Kendall: no trend, p=1.0)
2. 目前已经完成了NDVI年尺度的空间分布图的绘制;
3. NDVI时间序列变化分析区分迎风坡和背风坡;


# 2026/03/29 情况说明

1. 目前正在处理不同海拔梯度下迎风坡和背风坡的NDVI统计值, 并绘制出图;


# 2026/03/31 情况说明

1. 目前已经完成不同海拔梯度下迎风坡和背风坡的NDVI.

2. 关于趋势分析, 发现2019-2025年期间的NDVI并不存在显著的趋势, 后续不往趋势方向进行分析;

3. 关键发现:
   - 在不同年份下, 背风坡NDVI均值 > 迎风坡NDVI均值(反常识)
   - <4100m: 迎风坡NDVI > 背风坡NDVI
   - 4100-5000m: 背风坡NDVI > 迎风坡NDVI
   - >5000m: 两侧NDVI均 < 0.3
   
   推测: 4000-5000m范围背风坡NDVI占主导, 拉高了整体均值.
   `ps`: 可能是高海拔裸地/冰雪像元被纳入了统计, 没有做好过滤

4. 进行土地利用类型(MCD12Q1)的预处理


# 2026/04/01 情况说明

1. ERA5 2m气温 + 总降水量下载完成
> 川西地区地理范围边界: 36°N, 96°E, 24°N, 106°E = 北, 西, 南, 东
> [注: 2026-05-18 起扩展为西南地区, 见 Xinan.shp]

2. GAI 统计值处理完成 [注: GAI 后续被 VAI 取代]
3. MCD12Q1 土地利用处理完成


# 2026/04/02 情况说明

1. 基于MCD12Q1的非植被像元掩膜过滤 (修改 ndvi_preprocess.py)
2. DEM重分类(gradient=1000m)和空间分布可视化完成


# 2026/04/08 组会总结

1. 当前的研究没有紧扣干热河谷这一主题, 过于发散
2. 下一步: 先提取具体河谷(大渡河、雅砻江等), 限定研究区在河谷两侧山体;
   河谷内部左右岸对比 + 风向因素


# 2026/04/09 情况说明

1. 查阅干旱河谷划分文献, 关注成都生物所包维楷老师
2. 聚焦干旱河谷, 引入河谷左右岸对比
3. 获取中国西南干热河谷边界shp (国家青藏高原科学数据中心)


# 2026/04/10 情况说明

1. 河谷中心线提取; 两岸对比代码框架
2. 方向矫正: 两岸对比应改为"左岸像元 vs 该山脉另一侧像元", 而非简单左右岸对应


# 2026/04/13 情况说明  [← 原 LOG 误标为 2026/3/13, 已修正]

初步河谷分析框架:

1. 河谷内侧/外侧划分: 通过河谷两侧山脊线提取边界
2. 基于河谷内外侧在 3km×3km 格网进行 GAI 分析
   [注: 后续切换到 VAI + buffer 4km, 网格思路保留]
3. 四类像元 NDVI-海拔曲线: 河谷内迎风/背风 + 河谷外迎风/背风

栅格编码: 十位=河谷(1大渡河/2岷江/3金沙江/4雅砻江), 个位=内外(1外侧/2内侧)


# 2026/04/14 情况说明

1. 细化到干热河谷范围的分析完成: GAI空间分布 / NDVI海拔梯度 / NDVI年际变化
2. 后续应全部聚焦干热河谷范围


# 2026/04/16 情况说明

1. 三类图绘制完成: GAI空间分布 / NDVI海拔梯度 / NDVI年际变化
2. 后续安排: 驱动因子分析 (空间自相关、GeoDetector、RF+SHAP等) + 文献调研


# 2026/04/19 组会总结

1. 明确科学问题, 讲好故事
2. 先拿岷江试验 (区域完整、面积小, 快速验证)


# 2026/04/21 情况说明

四个河谷子文件夹建立 (Daduhe, Jinshajiang, Minjiang, Yalongjiang).
各河谷 unify_dataset.py 完成数据集空间统一.
[注: 2026-05-16 起 unify_dataset.py 改为仅裁剪 windward_leeward, DEM/NDVI 已注释]


# 2026/05/05 情况说明

1. valley_analysis 下完成四河 VAI 分析 (_region 外接矩形版):
   vai_altitude_gradient.py, inverse_pt.py, segmented_breakpoints.py,
   intensity_comparison.py, methods_forest_plot.py
   [注: _region 版保留为 baseline, 后续 buffer 4km 版为主]
2. 缺少 slope>5° 过滤 (05-08 补上)


# 2026/05/07 情况说明

- 大渡河 buffer 4km: 543 cells, ABS 3530m, boot 99.8% → 确定为主线
- strict polygon (Daduhe): 226 cells, boot 58.6% → 样本不足, 废弃
  [注: strict/inner-outer/corridor trial 等已移至 History/]
- CRS 变换 bug 修复 (岷江 Albers→UTM 47N)
- TwoSlopeNorm vmin 兜底 (岷江 VAI 全部>0)
- Buffer 推广至四河; Panel D 渲染 bug 链修复


# 2026/05/08 情况说明

- 四河合并: 2049 cells, ABS 3735m, REL 1406m
- 文件重命名:
  VAI_buffer_valley_3km_all.py → VAI_spatial_distribution_buffer.py
  VAI_buffer_valley_threshold_all.py → VAI_altitude_gradient_buffer.py
- slope>5° 过滤加入 windward_leeward_divide.py
- slope>5° 版结果: ABS 3721m [3632, 3869], REL 1406m [1320, 1569]
- ERA5 生长季代码改为 5-9 月 (仅代码, 数据待重跑)
- 40+ 废弃文件移至 History/


# 2026/05/16 情况说明

windward_leeward_divide.py bug 修复:
  - predictor=3→2 (uint8 需整数 predictor)
  - block → 4096×4096 (16 倍数)

生长季 5-9 月风场链重跑 (run_growing_season_pipeline.py):
  Step 0→5: ERA5 nc → 0.25° u/v → 10m → DEM mask → wind_dir → 
             SAGA Wind Effect → windward_leeward.tif

4 × unify_dataset.py 改为仅裁剪 windward_leeward

run_vai_buffer_pipeline.py 创建 (Step 1→3, Step 4 注释可选)

管道运行结果:
  Step 1: ~1.5 min, 4 × windward_leeward_region.tif
  Step 2: ~0.5 min, Daduhe 583 / Jinsha 540 / Min 268 / Yalong 786 cells
  Step 3: ~2.6 min, 合并 2019 cells; ABS 3652m [3573, 3757]; REL 1356m [1273, 1515]


# 2026/05/17 组会 (赵伟导师)

汇报 05-16 结果. 赵老师核心反馈:

肯定: "做得挺好...可以直接重新定义整个干旱河谷的边界"

方法学批评:
  - "平均抵消效应": 3km 格网内谷底→山顶像元混合, VAI 被平滑
  → 建议分高度带 VAI (距河道 200/300/400/500/1000m)
  - 网格位置敏感性: 应测试 1km/2km/3km 多尺度
  - 沿河段阈值空间分布制图
  - 空间分布图去除人为边界

详见: Assets/Ref/group_meeting/2026-05-17_组会纪要.md


# 2026/05/18 情况说明

- 研究区扩展: 川西 → 西南地区 (Xinan.shp)
  矩形: 上35.6°N / 下22.4°N / 左92.1°E / 右106.6°E
- PROGRESS_2026-05-18.md 编写
- LOG 文件夹重建: 旧 LOG 移至 LOG/LOG_legacy_2026-05-18.md 等; 本文件为修复版


# 关键路径速查

| 类别 | 路径 |
|------|------|
| 风场管道 | Src/preprocessing/run_growing_season_pipeline.py |
| VAI管道 | Src/valley_analysis/run_vai_buffer_pipeline.py |
| buffer VAI | Src/valley_analysis/geo_analysis/VAI_spatial_distribution_buffer.py |
| 阈值+森林图 | Src/valley_analysis/geo_analysis/VAI_altitude_gradient_buffer.py |
| ERA5预处理 | Src/preprocessing/era5/era5_u_v_preprocess.py |
| 迎背风坡 | Src/preprocessing/windward_leeward_divide.py |
| 组会纪要 | Assets/Ref/group_meeting/2026-05-17_组会纪要.md |
| 进展文档 | Assets/Ref/claude/PROGRESS_2026-05-18.md |
| 废弃代码 | History/ |
| DEM解压 | Src/preprocessing/geo/unzip_dem.py |
| DEM拼接 | Src/preprocessing/geo/dem_mosaic_clip.py |
| DEM投影+重采样 | Src/preprocessing/geo/dem_reproject_resample.py |


# 2026/05/19 DEM 预处理代码编写

GLO-30 DEM 数据已于 I:\DataHub\GLO-30_DEM 就位 (6 Tile, ~30 GB).
现有 DEM 预处理全在 ArcGIS Pro 手动完成, 无代码留存, 故从头编写.

## 数据源结构

    I:\DataHub\GLO-30_DEM\
    
        ├── Tile1_92.1-94.6E_DEM.tar.gz    → output_hh.tif (Float32, ~1.6 GB)
        
        ├── Tile1_92.1-94.6E_Viz.tar.gz    → viz.hh_slope.tif + viz.hh_aspect.tif (~1.9 GB each)
        
        ├── ... (Tile2–Tile6, 覆盖 92.1°E–106.6°E)

## 处理链条

```
unzip_dem.py  →  dem_mosaic_clip.py  →  dem_reproject_resample.py
 (解压)           (VRT拼接+裁剪 WGS84)     (投影Albers+10m+坡度坡向)
```

## 1. unzip_dem.py

- 6 × Tile*_DEM.tar.gz → dem\Tile*_dem.tif
- 6 × Tile*_Viz.tar.gz → slope\Tile*_slope.tif + aspect\Tile*_aspect.tif
- 已存在跳过, 支持断点续传

## 2. dem_mosaic_clip.py

- VRT 拼接 (参考 mcd12q1_process.py) → gdal.Warp 裁剪
- 西南地区外接矩形 [92.1, 22.4, 106.6, 35.6] (WGS84)
- 仅矩形裁剪, 不掩膜 (region)
- 输出: G:\GeoProjects\...\{DEM,Slope,Aspect}\xinan\*_30m_geo_xinan_region.tif
- 同时处理 DEM / Slope / Aspect 三类数据

## 3. dem_reproject_resample.py

- 投影: 自定义 Albers 等面积圆锥投影
  +proj=aea +lat_1=24 +lat_2=34 +lat_0=29 +lon_0=99.35 +datum=WGS84
  (西南地区 92.1°E–106.6°E, 22.4°N–35.6°N 优化, 取代原川西 UTM 47N)
- 重采样: 30m → 10m (Bilinear)
- 坡度坡向: 直接从 10m 投影 DEM 用 gdaldem 计算 (避免 Viz 角度数据重采样畸变)
- 输出: G:\GeoProjects\...\{DEM,Slope,Aspect}\xinan\*_10m_proj_xinan_region.tif

## 关键决策

| 决策 | 理由 |
|------|------|
| Albers 等面积 vs UTM | 西南地区跨 4 个 UTM 带 (45N–48N); 等面积适配后续格网统计 |
| 自定义标准纬线 (24°/34°) | 比中国全国 Albers (25°/47°) 更贴合 22.4°N–35.6°N |
| xinan 子文件夹 | 不覆盖旧川西 GLO-30/ 文件 |
| 坡向坡度从 10m DEM 重算 | 避免 30m→10m 重采样对 0°/360° 角度数据引入插值畸变 |
| build_overviews 金字塔 | 与 era5/ wind/ 脚本一致, 用 qiezi.geo.build_overviews |

## Bug 修复记录

| 问题 | 原因 | 修复 |
|------|------|------|
| SyntaxError: unicodeescape | docstring 中 `\xinan` 的 `\x` 被解析为十六进制转义 | docstring 改 raw string + 反斜杠改正斜杠 |
| 边界无数据区填 0 | gdal.Warp 未设 dstNodata; 源文件本身无 NoData 元数据 | dstNodata=float('nan') |
| DEMProcessingOptions TypeError | 捏造了 processing= 参数 (实际是 DEMProcessing() 的位置参数) | 移除 processing= |
| NoData 传播断裂 | dem_reproject_resample.py Warp 未设 srcNodata/dstNodata | srcNodata=dstNodata=float('nan') |

## 代码位置

- Src/preprocessing/geo/unzip_dem.py
- Src/preprocessing/geo/dem_mosaic_clip.py
- Src/preprocessing/geo/dem_reproject_resample.py


# 2026/05/20 DEM 预处理代码修复

- NoData 链修复: 两脚本 gdal.Warp 均加 dstNodata=float('nan')
- DEMProcessingOptions 移除不存在的 processing= 形参
- 验证编译通过


# 2026/05/20 ERA5 代码适配西南地区 DEM

DEM 重复后（05-19），era5/ 和 wind/ 脚本中的硬编码路径失效，需更新。同时，西南地区
范围远超原川西，两个架构问题暴露。

## 1. DEM/Slope 路径更新 (5 文件)

DEM 路径于 2026/05/19 更改为 xinan/ 子文件夹。5 个文件引用旧路径，已更新：

| 文件 | 变量 | 旧路径 | 新路径 |
|------|------|--------|--------|
| era5_uv_preprocess.py | img_ref_path | ...\GLO-30\elevation_10m_projected.tif | ...\xinan\elevation_10m_proj_xinan_region.tif |
| era5_uv_reproject_to_10m.py | ref_path | 同上，docstring UTM 47N | 同上，docstring Albers |
| era5_uv_mask.py | ref_path | 同上 | 同上 |
| saga_wind_effect.py | dem_path | 同上 | 同上 |
| windward_leeward_divide.py | slope_path | E:\...\Slope\slope_10m_projected.tif | G:\...\Slope\xinan\slope_10m_proj_xinan_region.tif |

未修改: era5_t2m_tp_monthly/yearly（ERA5-Land，无 DEM 引用）、wind_direction_cal.py（仅 u/v）。

## 2. DEM 掩膜步骤废弃

`era5_uv_mask.py`（原名 era5_u_v_postgis_preprocess.py）将 DEM NoData 区域对 u/v 做掩膜。
西南地区 DEM 覆盖整个西南地区范围，无 NoData 空洞，掩膜不产生有价值结果。
SAGA Wind Effect 仅处理 DEM 有效区域，DEM 自身已是天然掩膜。

**变更:**
- `run_growing_season_pipeline.py`: Step 2（掩膜）移除，Step 2–5 前移为 Step 2–4
- `wind_direction_cal.py`: 输入从 masked/ 改回 unmasked/
- `era5_uv_mask.py`: 保留但不再由管道调用

管道现状（4 步）:
```
Step 0: era5_uv_preprocess.py       → 0.25° u/v/wind_dir
Step 1: era5_uv_reproject_to_10m.py → 10m u/v unmasked
Step 2: wind_direction_cal.py       → 10m wind_dir
Step 3: saga_wind_effect.py         → wind_effect.tif
Step 4: windward_leeward_divide.py  → 迎风/背风二分类
```

## 3. BigTIFF 问题 (wind_direction_cal.py)

西南地区 10m Float32 栅格 > 4GB（Classic TIFF 上限），600 hPa 时触发：
```
TIFFAppendToStrip: Maximum TIFF file size exceeded. Use BIGTIFF=YES creation option.
```

**根因:** Step 1 使用 gdal.Warp（creationOptions=['BIGTIFF=YES']）正确；Step 2 使用
rasterio（`out_profile = u_src.profile.copy()`）。`profile` 为数据元数据（dtype、尺寸、
CRS、压缩），BigTIFF 是文件格式级别标志，不出现在 profile 中。`copy()` 不继承 BigTIFF。

**修复:** `out_profile['bigtif'] = True`（添加于 wind_direction_cal.py）。

步骤 3–4 不涉此风险：SAGA 自行处理 TIFF 创建；windward_leeward_divide.py 输出 uint8，
远小于 4GB。
