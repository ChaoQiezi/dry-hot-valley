# 川西干热河谷项目代码级调研记录

调研时间: 2026-05-05  
调研者: Codex  
调研原则: 以代码、真实数据文件和当前输出为主; `LOG.MD`、Claude 文档仅作线索,不作为执行事实。

## 0. 赵导原始问题的代码级拆解

赵导原话包含三层任务:

1. `迎风背风坡效应的海拔阈值效应是否存在`
   - 需要从 VAI 或 NDVI_windward - NDVI_leeward 沿海拔变化中识别阈值。
   - 当前代码主要用 `VAI=0` 反转点和 segmented 断点回答。

2. `是多少高度差`
   - 可能至少有三种含义:
     - 阈值的绝对海拔差: 四河反转海拔两两差。
     - 阈值相对谷底的高度差: 反转点 - 谷底海拔。
     - 同一山体/河谷段两侧迎背风差异随高程变化的高度带宽。
   - 当前 `threshold_summary.py` 已输出两两差矩阵,但“相对谷底高差”只是用 count>=30 后的最低有效 VAI bin 近似,不是实际谷底。

3. `有些山迎风背风坡差异很大,有些则不大`
   - 需要山体、坡面单元、河段或至少 3 km 网格尺度的空间异质性量化。
   - 当前 Fig 4 只做“四河谷整体强度对比”,还没有做到“山间差异”。

## 1. 当前项目真实主线

代码中存在两条历史线:

1. 早期全川西分析线:
   - 目录: `Src/geo_analysis/`, `Src/plot/`
   - 数据: `E:\GeoProjects\dry_hot_valley\NDVI`, `VAI`, `GAI`, `Result`
   - 内容: 全川西 NDVI、GAI、VAI、年际变化、海拔梯度。
   - 对赵导当前问题只能作为背景,不应作为主证据。

2. 当前四河谷分析线:
   - 目录: `Src/valley_analysis/{Minjiang,Daduhe,Jinshajiang,Yalongjiang}/`
   - 跨河综合脚本: `Src/valley_analysis/geo_analysis/`
   - 数据: `E:\GeoProjects\dry_hot_valley\{ValleyName}\`
   - 内容: 四条河谷独立 VAI/NDVI 栅格、VAI 海拔梯度、跨河阈值比较。
   - 这是当前回答赵导问题的主线。

## 2. 数据处理链路

### 2.1 NDVI

代码线索:

- `Src/Download/ndvi_download.py`
  - GEE 数据源: `COPERNICUS/S2_SR_HARMONIZED`
  - 云概率: `COPERNICUS/S2_CLOUD_PROBABILITY`, `max_cloud_probability=65`
  - NDVI: `(B8 - B4) / (B8 + B4)`
  - 代码中 `sos_month_start=5`, `sos_month_end=9`, `start_date_str='2019-01-01'`, `end_date_str='2021-12-31'`
  - 但真实数据目录中有 2019-2025 年逐年 NDVI,说明下载脚本不是当前数据全流程的完整记录。

- `Src/preprocessing/ndvi_preprocess.py`
  - 将 GEE 下载结果镶嵌、重投影/重采样、裁剪到 DEM 参考。
  - 输出分辨率: 10 m。
  - `remove_invalid_values()` 中实际过滤 `NDVI > 0.1`。
  - 真实数据目录: `E:\GeoProjects\dry_hot_valley\NDVI\Yearly\NDVI_2019.tif` 至 `NDVI_2025.tif`,以及 `NDVI\Interannual\NDVI_interannual_mean.tif`。

### 2.2 风场与迎背风分类

代码线索:

- `Src/preprocessing/era5/era5_u_v_preprocess.py`
  - ERA5 pressure level u/v。
  - 年份: 2017-2025。
  - 生长季: 6-8 月。
  - 对 u/v 用风速加权:
    - `u_weighted = sum(u_i * V_i) / sum(V_i)`
    - `v_weighted = sum(v_i * V_i) / sum(V_i)`
  - 输出各 pressure level 的 u、v、wind direction。

- `Src/preprocessing/windward_leeward_divide.py`
  - 输入: SAGA GIS Wind Effect。
  - 二分类:
    - `wind_effect > 1` -> 1,迎风坡
    - 其他有效值 -> 2,背风坡
  - nodata -> 255。

当前代码未看到:

- 坡度 `>5°` 过滤。
- 迎风/背风像元比例平衡约束。

`LOG.MD` 最后也写了“迎风坡和背风坡没有进行 >5° 的限制”。

### 2.3 四河谷裁剪

代码线索:

- `Src/valley_analysis/*/preprocessing/unify_dataset.py`
  - 输入 DEM、NDVI、迎背风坡二分类栅格。
  - 用 `E:\GeoProjects\dry_hot_valley\valley_area\西南干旱河谷范围\*_valley.shp` 作为模板。
  - 关键参数: `clipping_geometry = False`。

重要事实:

- ArcGIS `Clip` 在 `clipping_geometry=False` 时按矢量外接矩形裁剪,不是按 polygon 精确掩膜。
- 因此当前四河 `_region.tif` 更准确地说是“各河谷边界外接矩形区域”,不是“干热河谷 polygon 内部区域”。
- 这可能保留了河谷两侧山体,但不能在论文中说成“严格限制在干热河谷边界内”。

边界数据事实:

- `valley_origin.shp` 有 8 条西南干旱河谷记录。
- 当前只取四条:
  - 岷江干旱河谷
  - 大渡河干旱河谷
  - 金沙江干旱河谷
  - 雅砻江干旱河谷
- 这些边界来自外部数据源,不是本项目自行识别。
- 如果导师反对“用别人的干热河谷 shp 当研究区边界”,当前四河裁剪链路存在方法风险。

四河矢量基本信息:

| 河谷 | shp features | bounds WGS84 | 近似面积 km2 |
|---|---:|---|---:|
| Minjiang | 1 | 103.1716,31.2847,103.8962,32.4086 | 727.8 |
| Daduhe | 2 | 101.6568,29.2038,103.0301,31.9046 | 1102.7 |
| Jinshajiang | 5 | 98.4139,26.0482,103.8752,31.8619 | 3461.4 |
| Yalongjiang | 3 | 100.9869,27.0154,102.3909,30.2086 | 2700.7 |

## 3. VAI 生成链路

四河脚本:

- `Src/valley_analysis/{Valley}/geo_analysis/VAI_spatial_distribution.py`

共同逻辑:

- 输入:
  - `NDVI_interannual_mean_region.tif`
  - `windward_leeward_region.tif`
  - `elevation_10m_projected_region.tif`
- 网格:
  - `GRID_SIZE_M = 3000`
  - `PIXEL_SIZE_M = 10`
  - `GRID_PIXELS = 300`
- VAI:
  - `VAI = (NDVI_windward - NDVI_leeward) / ((NDVI_windward + NDVI_leeward)/2) * 100`
- 输出:
  - `VAI_3km_region.tif`
  - `VAI_pvalue_3km_region.tif`
  - `NDVI_windward_3km_region.tif`
  - `NDVI_leeward_3km_region.tif`
  - `DEM_3km_region.tif`

重要风险:

- 注释写“若任一侧有效像素 <50,该网格 nodata”,但代码实际没有执行该过滤。
- `MIN_PIXEL_THRESHOLD = 15` 被定义,但没有被使用。
- 代码没有输出 `windward_count` / `leeward_count` 栅格。
- 因此目前无法从现有 VAI 栅格反查每个 3 km 网格的迎背风像元数平衡是否合格。
- 用户 prompt 中写的“每侧最少 30 像素 + 像素数比 <=2 + 每侧 >=25%”没有在当前 VAI 生成脚本中落地。

四河 VAI 栅格统计:

| 河谷 | VAI 栅格 shape | 有效 3km 网格数 | VAI min | VAI max | VAI mean |
|---|---:|---:|---:|---:|---:|
| Minjiang | 41x22 | 853 | -62.266 | 73.683 | 0.379 |
| Daduhe | 99x46 | 3206 | -112.867 | 114.875 | -10.980 |
| Jinshajiang | 213x177 | 21478 | -117.012 | 119.197 | -4.777 |
| Yalongjiang | 117x48 | 5007 | -89.722 | 95.180 | -2.478 |

注意:

- VAI 实际已经出现超过 ±100% 的网格值;不能再说“实际数据 [-100%,+100%]”。
- 理论范围仍是 [-200%,+200%]。

## 4. VAI 海拔梯度表

脚本:

- `Src/valley_analysis/{Valley}/geo_analysis/VAI_altitude_gradient.py`

共同逻辑:

- 读取 `VAI_3km_region.tif` 与 `DEM_3km_region.tif`。
- 按 DEM_3km 平均高程分箱。
- 实际 `elev_step = 100`,不是 50 m。
- 输出列:
  - `elev_lo`
  - `elev_hi`
  - `elev_center`
  - `vai_mean`
  - `vai_std`
  - `vai_median`
  - `pct_gt0`
  - `pct_lt0`
  - `count`

四河 VAI 海拔表统计:

| 河谷 | 表路径 | rows | count>0 | count>=10 | count>=30 | count>=30 海拔范围 |
|---|---|---:|---:|---:|---:|---|
| Minjiang | `Minjiang\Result\Table\altitude\VAI_altitude_gradient.xlsx` | 31 | 31 | 24 | 13 | 2550-3850 |
| Daduhe | `Daduhe\Result\Table\VAI_altitude_gradient.xlsx` | 54 | 51 | 32 | 25 | 2350-4750 |
| Jinshajiang | `Jinshajiang\Result\Table\VAI_altitude_gradient.xlsx` | 60 | 57 | 47 | 43 | 750-5050 |
| Yalongjiang | `Yalongjiang\Result\Table\VAI_altitude_gradient.xlsx` | 51 | 50 | 37 | 34 | 1450-4750 |

问题:

- ~~Fig 1 和 Fig 4 脚本中 `MIN_COUNT_PER_BIN=10`,但注释写 count>=30。~~ **已修正: 所有脚本统一为 `MIN_COUNT_PER_BIN=30`。**
- Fig 2、Fig 3、Fig 5、Table 1 脚本中 `MIN_COUNT_PER_BIN=30`。
- ~~这会导致不同图使用的低样本过滤不一致。~~ **已消除。**

## 5. 跨河阈值分析脚本与结果

位置:

- `Src/valley_analysis/geo_analysis/`

### 5.1 Fig 1: `vai_altitude_gradient.py`

功能:

- 四河 VAI-海拔曲线叠加。
- LOWESS 平滑后标注 VAI=0 反转点。
- 底部显示各高程 bin 的网格数。

参数:

- `MIN_COUNT_PER_BIN=30`(已从 10 统一修正)
- 注释写 IQR 阴影,但当前 VAI 表没有 `vai_q25` / `vai_q75`,所以实际不会画 IQR 阴影。

### 5.2 Fig 2: `inverse_pt.py`

功能:

- 对四河 VAI 海拔 bin 均值做 LOWESS。
- Bootstrap 1000 次估计 VAI 由正转负的反转海拔。
- 输出 `reversal_bootstrap_results.csv`。

参数:

- `MIN_COUNT_PER_BIN=30`
- `HIGH_CONF_LOW=1500`
- `HIGH_CONF_HIGH=4500`
- `frac=0.3`
- Bootstrap 基于海拔 bin 重采样,不是基于 3 km 网格重采样。

结果:

| 河谷 | LOWESS 反转海拔 m | 95% CI m | CI 宽度 m |
|---|---:|---|---:|
| 岷江 | 3164.5 | 3110.0-3212.9 | 102.9 |
| 大渡河 | 3394.0 | 3230.6-3547.2 | 316.6 |
| 金沙江 | 3684.2 | 3594.6-3720.9 | 126.3 |
| 雅砻江 | 3605.6 | 3402.2-3736.7 | 334.4 |

解释:

- 这可以回答“绝对海拔阈值是否存在”。
- 目前结果显示四河反转点集中在 3164-3684 m,极差约 520 m。

限制:

- 岷江 count>=30 后只有 13 个海拔 bin,bootstrap 样本少。
- 置信区间反映的是 bin 曲线重采样,不是空间样本不确定性。

### 5.3 Fig 3: `segmented_breakpoints.py`

功能:

- 用 `piecewise_regression` 做分段回归。
- BIC 选择最优断点数,最大断点数限制为 2。
- 输出 `segmented_breakpoints.csv`。

已修正:

- 原脚本调用不存在的 `Fit.predict()`,已改为用 `fit.best_muggeo.best_fit.raw_params` 和 `next_breakpoints` 手工预测拟合线。

结果:

| 河谷 | BIC 最优断点数 | 断点1 m | 断点2 m | Davies p |
|---|---:|---:|---:|---:|
| 岷江 | 0 | NA | NA | NA |
| 大渡河 | 1 | 3919 | NA | 2.71e-89 |
| 金沙江 | 2 | 1792 | 3817 | 9.46e-49 |
| 雅砻江 | 2 | 1792 | 3911 | 7.05e-38 |

解释:

- 大渡河、金沙江、雅砻江在 3.8-3.9 km 附近有分段断点。
- 金沙江、雅砻江的 1792 m 是低海拔 slope break,不应当直接当作 VAI 反转阈值。
- 岷江 segmented 在 BIC 下最优为 0 断点,不能强行说四河 segmented 都支持同一阈值。

### 5.4 Fig 4: `intensity_comparison.py`

功能:

- 四河整体差异强度比较。
- 指标基于高置信区间 `1500-4500 m` 内的海拔 bin 均值。

参数:

- `MIN_COUNT_PER_BIN=30`(已从 10 统一修正)

结果:

| 河谷 | \|VAI\|中位数 % | VAI 振幅 % | VAI max % | VAI min % | VAI 最小值海拔 m |
|---|---:|---:|---:|---:|---:|
| 岷江 | 5.25 | 34.96 | 17.20 | -17.76 | 4250 |
| 大渡河 | 7.49 | 43.48 | 11.78 | -31.70 | 4450 |
| 金沙江 | 3.01 | 24.41 | 8.63 | -15.78 | 4450 |
| 雅砻江 | 3.05 | 36.80 | 18.98 | -17.82 | 4450 |

解释:

- 当前四河整体强度排序更接近: 大渡河最强,岷江次之,金沙江/雅砻江较弱。
- 这和 Claude 文档中“岷江最强、金沙江最弱”的理论先验不完全一致。

限制:

- 这是“四河谷之间”的差异,不是“有些山之间”的差异。
- 指标基于海拔 bin 均值,不是 3 km 网格或山体单元分布。

### 5.5 Fig 5: `methods_forest_plot.py`

功能:

- LOWESS 反转点与 segmented 邻近断点的综合 forest plot。

已修正:

- 原脚本把 `断点1` 直接当反转阈值,这会把金沙江/雅砻江的 1792 m 低海拔断点误用。
- 现改为选择“最接近 LOWESS 反转点的 segmented 断点”。
- 使用真实 segmented 95% CI,不再用假设的 `±100 m`。

结果:

| 河谷 | LOWESS 反转 m | segmented 邻近断点 m | 二者差 m |
|---|---:|---:|---:|
| 岷江 | 3164.5 | NA | NA |
| 大渡河 | 3394.0 | 3919.0 | 525.0 |
| 金沙江 | 3684.2 | 3817.0 | 132.8 |
| 雅砻江 | 3605.6 | 3911.0 | 305.4 |

解释:

- LOWESS 与 segmented 并非完全一致,特别是大渡河差距 525 m。
- 不宜汇报为“多方法高度一致”,更稳妥说法是“LOWESS 反转集中在 3.2-3.7 km; segmented 在 3.8-3.9 km 给出结构性断点,两者共同指向 3.2-3.9 km 的过渡带”。

### 5.6 Table 1: `threshold_summary.py`

功能:

- 合并 LOWESS、segmented、强度指标。
- 输出阈值汇总和两两差矩阵。

已修正:

- 原脚本内连接会丢掉岷江,因为岷江没有 segmented 断点。
- 现以 LOWESS 主表左连接,保留四河。

当前输出:

| 河谷 | 反转海拔 m | CI | 邻近 segmented m | \|VAI\|中位数 % | VAI 振幅 % | “谷底” m | “反转相对高差” m |
|---|---:|---|---:|---:|---:|---:|---:|
| 岷江 | 3164.5 | 3110.0-3212.9 | NA | 5.3 | 35.0 | 2550 | 614.5 |
| 大渡河 | 3394.0 | 3230.6-3547.2 | 3919 | 7.5 | 43.5 | 2350 | 1044.0 |
| 金沙江 | 3684.2 | 3594.6-3720.9 | 3817 | 3.0 | 24.4 | 750 | 2934.2 |
| 雅砻江 | 3605.6 | 3402.2-3736.7 | 3911 | 3.1 | 36.8 | 1450 | 2155.6 |

两两反转海拔差:

| pair | diff m |
|---|---:|
| 岷江-大渡河 | 230 |
| 岷江-金沙江 | 520 |
| 岷江-雅砻江 | 441 |
| 大渡河-金沙江 | 290 |
| 大渡河-雅砻江 | 212 |
| 金沙江-雅砻江 | 79 |

限制:

- `谷底海拔_m` 是 `count>=30` 过滤后的最低有效 bin,不是真实谷底。
- 因此 `反转相对高差_m` 当前不适合直接向导师汇报。

## 6. 现有结果对赵导问题的回答程度

### Q1: 海拔阈值效应是否存在?

确定知识:

- 以 LOWESS VAI=0 反转点定义,四河均存在由正转负的反转点。
- 反转点集中在 3164.5-3684.2 m。
- 两两最大差约 520 m,最小差约 79 m。

推断:

- 当前结果支持“绝对海拔阈值存在”,但更稳妥应表述为“约 3.2-3.7 km 的反转阈值带”。
- segmented 结果支持 3.8-3.9 km 附近存在曲线结构性断点,但不是四河全都有。

不能直接说:

- 不能说“所有方法完全收敛到同一阈值”。
- 不能说“阈值相对谷底高差已经确定”,因为谷底定义目前不可靠。
- 不能说“严格在干热河谷 polygon 内发现阈值”,因为裁剪是外接矩形。

### Q2: 多少高度差?

当前可报:

- 四河 LOWESS 反转绝对海拔差最大 520 m,最小 79 m。
- 如果用 LOWESS 与 segmented 的方法差,大渡河 525 m,金沙江 133 m,雅砻江 305 m。

当前不建议报:

- Table 1 中 `反转相对高差_m`,因为“谷底”只是 count>=30 后最低有效 bin。

需要后续补:

- 用真实河流中心线或 DEM valley floor 计算每个河段/网格的相对高差。
- 或至少用每条河谷 polygon/centerline 内 DEM 最低值、5% 分位数作为谷底基准。

### Q3: 有些山差异大、有些不大?

当前可报:

- 若把“四河”当比较对象,现有 Fig 4 支持差异强度不同:
  - 大渡河强度最高。
  - 岷江次之。
  - 金沙江和雅砻江较弱。

当前不能报:

- 不能说“有些山”已经被量化,因为没有山体单元、河段单元、坡面单元。
- 当前只到“河谷级”。

现有 3 km 网格可补充的 valley-level 强度:

| 河谷 | 范围 | n_grid | VAI mean | \|VAI\| median | \|VAI\| p90 | \|VAI\|>10% |
|---|---|---:|---:|---:|---:|---:|
| Minjiang | 1500-4500m | 852 | 0.36 | 3.14 | 20.73 | 26.76% |
| Daduhe | 1500-4500m | 2873 | -8.99 | 6.67 | 36.16 | 39.71% |
| Jinshajiang | 1500-4500m | 17821 | -2.05 | 3.87 | 17.46 | 21.15% |
| Yalongjiang | 1500-4500m | 4576 | -0.48 | 3.61 | 16.31 | 19.49% |

这个网格级统计同样显示大渡河最强,但仍不是山体单元。

## 7. 与 Claude 文档的主要偏差

Claude 文档路径:

- `Assets\Ref\claude\川西四河谷阈值分析的方法学定稿与七日工作计划.md`

主要问题:

1. 它提出了很多方法,但没有核查项目实际实现。
   - 当前实现: LOWESS bootstrap、segmented、强度比较、综合 forest plot。
   - 未实现: logistic 占比阈值、PELT/bcp、滑动 t/Wilcoxon、山间回归。

2. 它默认四方法 forest plot 已可作为核心,但项目只有两类阈值证据。

3. 它提出“山间差异归因”变量,但当前项目没有山体单元和自变量表。

4. 它给出“岷江最强 > 雅砻江 > 大渡河 > 金沙江”的理论排序,但当前项目数据更支持“大渡河最强”。

5. 它没有发现 `clipping_geometry=False` 导致当前四河区域是外接矩形裁剪。

6. 它没有发现 VAI 栅格生成未执行迎/背风样本平衡约束。

结论:

- Claude 文档适合作为“方法备选清单”和“文献写法草稿”,不适合作为当前项目状态依据。

## 8. 高优先级风险清单

1. 研究区边界风险
   - 当前四河使用外部干旱河谷 shp 的外接矩形裁剪。
   - 如果导师反对外部边界,当前研究区定义需要重新表述或重做。

2. 样本平衡风险
   - 现有 VAI 栅格没有执行迎/背风像元数平衡约束。
   - 没有保存每个网格迎/背风 count,无法事后筛查。

3. `高度差` 定义风险
   - 当前相对高差不是实际谷底高差。
   - 只能可靠汇报绝对阈值海拔和四河间差值。

4. `有些山` 未落地
   - 当前仅有四河谷级别强度。
   - 还没有山体/河段/坡面单元级别强度。

5. ~~图表参数不一致~~ **已修正: 所有脚本统一 `MIN_COUNT_PER_BIN=30`。**

6. VAI 空间脚本注释与代码不一致
   - 注释称 `<50 masked`,代码未执行。
   - `MIN_PIXEL_THRESHOLD=15` 未使用。

7. 高海拔信号风险
   - `HIGH_CONF_HIGH=4500` 是人为设置。
   - 4500 m 以上可能有积雪/裸地信号,但目前未用 snow/landcover 做显式剔除。

## 9. 当前最稳妥的汇报口径

可以说:

> 目前在四条川西河谷外接矩形区域内,基于 3 km 网格 VAI 沿海拔统计,LOWESS bootstrap 显示四河均存在 VAI 由正转负的海拔反转,反转海拔集中在约 3.16-3.68 km,四河最大差约 520 m。segmented 分段回归在大渡河、金沙江、雅砻江给出 3.8-3.9 km 附近的结构性断点,与 LOWESS 共同指向 3.2-3.9 km 的过渡带。强度上,大渡河当前最强,金沙江和雅砻江较弱,但这仍是河谷级差异,还没有完成山体/河段级量化。

不能说:

> 已经严格按干热河谷边界完成分析。

> 已经按每侧 30 像素、比例 <=2、每侧 >=25% 完成样本平衡。

> 已经回答了“有些山差异大、有些不大”。

> 相对谷底高度差已经确定。

## 10. 下一步锚点

如果继续做,不应先加新文献或新方法,而应先把赵导三句话和当前代码缺口对齐:

1. 明确研究区:
   - 当前外接矩形方案是否可表述为“河谷段邻域/河谷两侧山地分析窗口”。
   - 如果不行,需要重做四河裁剪/掩膜。

2. 重算 VAI 空间分布:
   - 输出 `windward_count_3km_region.tif` 与 `leeward_count_3km_region.tif`。
   - 执行每侧最少像元数、比例、覆盖率约束。

3. ~~重新生成 VAI altitude tables:~~ 已通过代码统一 `MIN_COUNT_PER_BIN=30` 完成。
   - 保持 `elev_step=100` 或统一改 50 m,但全项目一致。

4. 重新定义高度差:
   - 首选: 相对河流中心线/谷底 DEM 的高差。
   - 备选: 每条河谷 DEM 有效低海拔 5% 分位数作为谷底基准。

5. 落地“有些山”:
   - 不建议继续只做四河平均。
   - 最小可行方案: 沿河流中心线按固定距离分段,每段统计 VAI 强度和反转阈值。
   - 更强方案: 用坡面单元/山体单元统计每个单元的 `median(|VAI|)`、`VAI amplitude`、`反转是否存在`。

## 11. 2026-05-05 用户澄清后的更新

补充记录见:

- `F:\PyProJect\dry_hot_valley\Assets\Ref\codex\ZHAO_TASK_ALIGNMENT_2026-05-05.md`

关键修正:

- `_region` 是有意保留的河谷邻域窗口,不是误裁剪; 论文中需按“河谷邻域窗口/两侧山地分析窗口”表述,不能说成严格 polygon 内部。
- 迎/背风样本平衡是因严格约束会导致有效格网过于零散而暂时放宽; 正式结果前建议输出 count 栅格并做敏感性检查。
- “高度差”已新增两个工作定义: 四河反转阈值间绝对海拔差,以及反转阈值附近 3 km 网格相对最近河道 DEM 的局地高差。
- 已新增 `Src\valley_analysis\geo_analysis\zhao_threshold_intensity.py`,输出河道 DEM 基准、阈值相对高差、3 km 局地窗口强弱和 30 km 河段强弱。
