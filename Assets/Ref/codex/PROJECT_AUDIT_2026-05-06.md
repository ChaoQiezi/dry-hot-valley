# 川西干热河谷项目代码级调研更新

调研时间: 2026-05-06  
调研者: Codex  
更新对象: `F:\PyProJect\dry_hot_valley\Assets\Ref\codex\PROJECT_AUDIT_2026-05-05.md`  
调研原则: 仍以代码、真实输出表和当前运行结果为准; `LOG.MD`、Claude 文档和口头设想只作为线索。

## 0. BLUF

当前最诚实的判断:

1. **赵导问题还没有被完全解决。**
   - 现有结果能回答“VAI 随海拔存在由正转负的反转阈值”。
   - 现有结果还不能严格回答“焚风效应本身在哪个高度差后停止”。

2. **5 月 5 日 Fig 1-5 的核心问题仍在。**
   - 它们主要基于四河 `_region` 外接矩形邻域窗口。
   - 这些图可以描述“河谷邻域迎/背风 VAI 的海拔反转”,但不能直接说成“严格干热河谷内部焚风阈值”。

3. **5 月 6 日新增的内外、参照区、河道廊道、近远差分试验没有形成一个更强的核心结论。**
   - 内外缓冲区结果能说明河谷内 VAI 整体更强,但这接近常识,不是赵导问题的关键。
   - 远离河谷参照区方法因海拔范围不匹配,没有给出可靠阈值。
   - 河道廊道 `VAI=0` 反转能给出更贴近河道的高度差,但仍只是 VAI 符号反转,不是焚风停止。
   - 近河-远河 `ΔVAI` 差分有探索价值,但目前结论“近河额外增强随相对高差衰减”不够特别,不能作为主成果包装。

4. **目前最可保留的两类成果是:**
   - Q1 候选回答: 四河 VAI 绝对海拔反转,LOWESS 约 `3164.5-3684.2 m`,四河最大差约 `520 m`。
   - Q2 候选回答: 沿河段的迎背风差异强弱分级,以 20 km 河道邻域内 `|VAI|` 中位数划分强/中/弱。

5. **下一步不应继续堆新图。**
   - 必须先把“赵导说的海拔阈值”定义为可计算量。
   - 如果定义为 `VAI=0` 反转,现有工作可以继续整理。
   - 如果定义为“焚风额外增强停止高度”,现有证据不足,需要更强的对照设计或重新定义效应强度。

## 1. 赵导三句话与当前可回答程度

### 1.1 “迎风背风坡效应的海拔阈值效应是否存在”

确定知识:

- 四河 `_region` VAI-海拔曲线存在 LOWESS 正负反转。
- 5 月 5 日结果:

| 河谷 | LOWESS 反转海拔 m | 95% CI m |
|---|---:|---|
| 岷江 | 3164.5 | 3110.0-3212.9 |
| 大渡河 | 3394.0 | 3230.6-3547.2 |
| 金沙江 | 3684.2 | 3594.6-3720.9 |
| 雅砻江 | 3605.6 | 3402.2-3736.7 |

推断:

- 如果把“迎背风坡效应的海拔阈值”定义为 `VAI` 由正转负的海拔反转,则可以回答“存在”,阈值带约 `3.16-3.68 km`。
- 这个定义是现有数据最容易支撑的定义。

不确定:

- `VAI=0` 不等于焚风效应停止。它只表示迎风坡 NDVI 与背风坡 NDVI 的相对大小发生换符号。
- 因此如果赵导要的是“焚风造成的额外增强在哪个海拔消失”,现有 Fig 1-5 不能直接回答。

### 1.2 “是多少高度差”

当前有三种候选解释:

| 高度差定义 | 当前状态 | 是否建议主报 |
|---|---|---|
| 四河反转阈值之间的绝对海拔差 | 已有,最大约 520 m,最小约 79 m | 可报 |
| 反转阈值相对真实河道/谷底 DEM 的高差 | 已探索,但仍需更稳健定义 | 谨慎 |
| 近河额外增强 `ΔVAI` 消失的相对河道高差 | 5 月 6 日试验给出合并样本约 2.4 km,但单河不稳 | 暂不主报 |

确定知识:

| 河谷对 | LOWESS 反转海拔差 m |
|---|---:|
| 岷江-大渡河 | 230 |
| 岷江-金沙江 | 520 |
| 岷江-雅砻江 | 441 |
| 大渡河-金沙江 | 290 |
| 大渡河-雅砻江 | 212 |
| 金沙江-雅砻江 | 79 |

当前最稳妥说法:

> 若以 VAI 由正转负的反转点作为阈值,四河阈值集中在 3.16-3.68 km,四河间最大高度差约 520 m。

不能说:

> 焚风效应在相对谷底 2.4 km 后停止。

原因:

- 2.4 km 来自近河-远河 `ΔVAI` 合并样本试验,单河谷不稳定。
- 这个结论本身接近常识性衰减,目前没有明显特别性。

### 1.3 “有些山迎风背风坡差异很大,有些则不大”

确定知识:

- 5 月 5 日 Fig 4 只做到“四河谷整体差异强度”。
- 5 月 6 日新增河段强弱分级,开始接近“有些山/河段强弱不同”这个问题。

新增输出:

- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_corridor_segment_strength_20km.csv`

当前分级方法:

- 使用 20 km 河道邻域内 3 km VAI 网格。
- 按 `segment_id` 汇总。
- 每段至少 `10` 个格网。
- 强度指标为 `abs_VAI_median`。
- 按全体河段 `abs_VAI_median` 的 1/3 与 2/3 分位数划分弱/中/强。
- 当前阈值:
  - `strength_q33 = 3.09%`
  - `strength_q67 = 4.81%`

分级结果:

| 河谷 | 强 | 中 | 弱 | 河段数 |
|---|---:|---:|---:|---:|
| 大渡河 | 13 | 9 | 1 | 23 |
| 金沙江 | 15 | 4 | 14 | 33 |
| 岷江 | 1 | 7 | 5 | 13 |
| 雅砻江 | 9 | 17 | 17 | 43 |

各河段强度中位数概括:

| 河谷 | 河段数 | `|VAI|` 中位数的河谷中位值 % | `|VAI| p90` 的河谷中位值 % | `|VAI|>=10%`比例的河谷中位值 % |
|---|---:|---:|---:|---:|
| 大渡河 | 23 | 5.054 | 21.060 | 29.464 |
| 金沙江 | 33 | 3.576 | 23.524 | 25.000 |
| 岷江 | 13 | 3.705 | 19.383 | 27.586 |
| 雅砻江 | 43 | 3.321 | 12.794 | 19.481 |

解释:

- 这比“四河平均强度”更接近赵导的“有些山差异大、有些不大”。
- 但当前河段单元仍不是严格山体单元,只能称为“河道邻域河段强弱差异”。

## 2. 5 月 6 日新增工作审计

## 2.1 河谷内外 VAI 海拔分析

代码:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_buffer_inner_outer_altitude_gradient.py`
- 单河谷版本位于:
  - `F:\PyProJect\dry_hot_valley\Src\valley_analysis\Daduhe\geo_analysis\VAI_buffer_inner_outer_altitude_gradient.py`
  - `F:\PyProJect\dry_hot_valley\Src\valley_analysis\Minjiang\geo_analysis\VAI_buffer_inner_outer_altitude_gradient.py`
  - `F:\PyProJect\dry_hot_valley\Src\valley_analysis\Jinshajiang\geo_analysis\VAI_buffer_inner_outer_altitude_gradient.py`
  - `F:\PyProJect\dry_hot_valley\Src\valley_analysis\Yalongjiang\geo_analysis\VAI_buffer_inner_outer_altitude_gradient.py`

输出:

- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_inner_outer_altitude_gradient.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_inner_outer_altitude_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_inner_outer_altitude_summary_all_valleys.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_buffer_inner_outer_altitude_gradient.png`

合并样本结果:

| zone | 有效 bins | 海拔范围 m | mean VAI % | median VAI % | max `|VAI|` % |
|---|---:|---:|---:|---:|---:|
| inner | 64 | 825-3975 | 9.157 | 8.598 | 26.109 |
| outer | 64 | 825-3975 | 2.791 | 3.021 | 4.961 |
| inner_minus_outer | 64 | 825-3975 | 6.366 | 5.363 | 23.590 |

单河谷结果:

| 河谷 | inner 有效海拔范围 m | inner mean VAI % | outer mean VAI % | inner-outer mean VAI % |
|---|---:|---:|---:|---:|
| 大渡河 | 825-3725 | 15.508 | 3.097 | 12.174 |
| 岷江 | 1325-2925 | 17.156 | 4.261 | 11.862 |
| 金沙江 | 825-3975 | 11.827 | 4.387 | 7.440 |
| 雅砻江 | 1225-3375 | 11.050 | 2.769 | 7.784 |

评价:

- 确定: 代码层面能运行,且显示 inner VAI 普遍高于 outer。
- 推断: 这说明河谷影响区内迎背风差异更强。
- 不足: 这是一个容易预期的结果,不能作为“海拔阈值”的主答案。
- 不足: 单河谷内外曲线没有形成共同阈值。内外共享海拔范围有限,尤其高海拔段支撑不足。

结论:

- 此路线保留为背景或辅助图。
- 不建议作为赵导问题主线。

## 2.2 干热河谷外参照区隔离焚风增强

代码:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_foehn_isolation_reference.py`

输出:

- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_foehn_isolation_reference.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_foehn_isolation_reference.png`

关键参数:

- `REFERENCE_MIN_DIST_M = 20_000`
- `EXCLUDE_BUFFER_M = 5_000`
- `MIN_BIN_COUNT = 20`
- `ELEV_BIN_M = 100`

注意:

- 用户设想曾提到 `>30 km`,但当前代码实际为 `>20 km`。
- `EXCLUDE_BUFFER_M = 5_000` 被定义,但当前主要分类逻辑是 `inside` 与 `dist > REFERENCE_MIN_DIST_M` 的 reference。

样本事实:

| class | 总 count | 海拔 bin 范围 m | count>=30 的海拔 bin 范围 m |
|---|---:|---:|---:|
| valley | 859 | 650-3650 | 1250-2950 |
| reference | 23771 | 1050-6050 | 1550-5050 |

评价:

- 确定: valley 与 reference 的海拔分布严重不匹配。
- 确定: valley 在高海拔阈值关键带附近样本不足。
- 推断: `VAI_ref(z)` 不是可靠的“无焚风真值”,因为 reference 区混合了不同山系、雪/温度限制、其他地形风场与非河谷坡面结构。
- 结论: 该路线没有得到有效信息,不应作为主证据。

## 2.3 河道廊道 VAI 阈值试验

代码:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_river_corridor_threshold_trial.py`

输出:

- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_river_corridor_cells.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_river_corridor_abs_elevation_gradient.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_river_corridor_relative_height_gradient.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_river_corridor_threshold_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_river_corridor_threshold_sensitivity.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_river_corridor_threshold_trial.png`

关键处理:

- 每个 3 km VAI 网格绑定最近河道中心线采样点。
- 计算:
  - `river_distance_m`
  - `nearest_river_dem_m`
  - `relative_height_m = DEM_m - nearest_river_dem_m`
- 分析:
  - 全部 `_region` 网格
  - 距河道 `<=30 km`
  - 距河道 `<=20 km`
  - 距河道 `<=10 km`

重要修正:

- 合并脚本中 `sample_centerline_dem()` 曾有中心线 DEM 采样结果按 group 追加后直接赋值的问题,会导致行顺序错配。
- 已修正为按 `group.index` 回填:
  - `samples.loc[group.index, "river_dem_m"] = valley_dem`
- 单河谷脚本不受该 bug 影响。

当前结果:

| scope | n_cells | 绝对海拔 VAI=0 反转 m | 相对河道高差 VAI=0 反转 m | 阈值附近相对高差中位数 m |
|---|---:|---:|---:|---:|
| region_all | 30544 | 3598.913 | 949.375 | 1143.215 |
| corridor_30km | 9031 | 3520.290 | 1116.123 | 1398.938 |
| corridor_20km | 6828 | 3525.139 | 1161.949 | 1398.329 |
| corridor_10km | 3830 | 3526.384 | 1221.975 | 1351.331 |

评价:

- 确定: 河道廊道过滤后,合并样本 `VAI=0` 反转仍稳定在绝对海拔约 `3.52 km`。
- 确定: 以相对河道高差表达时,`VAI=0` 反转约 `1.12-1.22 km`。
- 不足: 这仍然是 `VAI=0` 符号反转,不是焚风增强消失。
- 不足: `VAI=0` 反转“看起来和谐”是因为整条 VAI-海拔曲线本来就有正转负趋势,不是该方法自动证明焚风阈值。

结论:

- 可以作为 Fig 1-5 的河道廊道稳健性检查。
- 不能单独声称“解决了赵导的焚风阈值问题”。

## 2.4 近河-远河廊道差分

代码:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_corridor_enhancement_gradient.py`

输出:

- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_corridor_enhancement_bins.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_corridor_enhancement_threshold_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_corridor_segment_strength_20km.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_corridor_enhancement_gradient.png`

设计:

```text
ΔVAI(z) = VAI_near_river(z) - VAI_far_river(z)
```

主情景:

- 近河道: `0-10 km`
- 远河道: `20-30 km`
- 分箱: `100 m`
- 每侧最少 bin 样本: `MIN_GROUP_COUNT = 10`
- bootstrap: `500`

主情景结果:

| 河谷 | 轴 | 有效 bins | 有效范围 m | peak ΔVAI % | 最后显著正增强 m | 峰值后 LOWESS 过零 m |
|---|---|---:|---:|---:|---:|---:|
| 四河合并 | 绝对海拔 | 35 | 1150-4650 | 9.790 | 4450 | NA |
| 四河合并 | 相对河道高差 | 25 | 50-2450 | 19.466 | 2350 | 2397.830 |
| 大渡河 | 绝对海拔 | 12 | 3250-4450 | 17.022 | 4450 | NA |
| 大渡河 | 相对河道高差 | 13 | 1050-2250 | 25.585 | 2050 | NA |
| 金沙江 | 绝对海拔 | 35 | 1150-4650 | 13.461 | 3850 | 4249.260 |
| 金沙江 | 相对河道高差 | 20 | 50-2050 | 30.689 | 1150 | 1699.573 |
| 岷江 | 绝对海拔 | 2 | 3350-3450 | -1.101 | NA | NA |
| 岷江 | 相对河道高差 | 0 | NA | NA | NA | NA |
| 雅砻江 | 绝对海拔 | 27 | 1850-4450 | 7.462 | 3250 | 3692.752 |
| 雅砻江 | 相对河道高差 | 22 | 50-2150 | 14.939 | 1750 | 941.240 |

评价:

- 确定: 该方法比 `VAI=0` 更接近“额外增强”概念。
- 确定: 合并样本在相对河道高差轴上给出约 `2.35-2.40 km` 的候选消失高度。
- 不足: 单河谷不稳定。岷江样本不足; 大渡河相对高差无峰值后过零; 金沙江与雅砻江过零位置差异大。
- 不足: “近河额外增强随高差衰减”并不特别,容易被预期。
- 结论: 该路线目前不能作为核心发现,只能作为探索性结果或方法附录。

## 3. 当前研究主线应如何收敛

### 3.1 不能继续强行包装的说法

不能说:

> 川西四河谷迎背风植被差异存在近河廊道额外增强,其影响随相对河道高差升高而衰减,阈值约 2.4 km。

理由:

- 这句话没有足够回答“阈值是否存在、是多少高度差”。
- 它没有比常识更强。
- 单河谷证据不稳,尤其岷江缺失。

不能说:

> 河谷内侧增强证明了赵导问题。

理由:

- 河谷内迎背风差异更强是可预期现象。
- 这不是海拔阈值,也不是高度差。

不能说:

> 远离河谷参照区证明了焚风增强消失。

理由:

- reference 区海拔分布与 valley 区严重不匹配。
- 参照区不是无焚风真值。

### 3.2 目前还能保住的主线

最稳主线:

> 基于四河谷邻域 3 km VAI 网格,迎风坡与背风坡植被差异沿海拔存在一致的正负反转阈值。LOWESS 反转集中在 3.16-3.68 km,四河最大阈值差约 520 m。沿河道廊道过滤后,合并样本仍在约 3.52 km 发生 VAI 反转,对应相对河道高差约 1.1-1.2 km。河段尺度上,20 km 河道邻域内 `|VAI|` 中位数显示强弱差异显著。

这个主线回答赵导问题的方式:

- 阈值是否存在: 存在,定义为 `VAI=0` 海拔反转。
- 是多少高度差: 四河反转海拔差最大约 `520 m`; 河道廊道合并样本相对河道高差约 `1.1-1.2 km`。
- 有些山差异大/小: 用河段 `|VAI|` 中位数分级,而不是只看四河平均。

核心风险:

- 这回答的是“VAI 反转阈值”,不是“焚风停止阈值”。
- 如果赵导坚持问的是焚风额外效应停止高度,该主线仍不够。

## 4. 当前文件与输出索引

### 4.1 仍然重要的 5 月 5 日主线文件

代码:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\vai_altitude_gradient.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\inverse_pt.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\segmented_breakpoints.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\intensity_comparison.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\methods_forest_plot.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\threshold_summary.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\zhao_threshold_intensity.py`

关键输出:

- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\reversal_bootstrap_results.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\segmented_breakpoints.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\methods_forest_data.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\threshold_summary_table.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_threshold_height_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_segment_intensity_30km.csv`

### 4.2 5 月 6 日新增探索文件

代码:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_inner_outer_altitude_gradient.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_buffer_inner_outer_altitude_gradient.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_threshold_biclass_altitude_explore.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_foehn_isolation_reference.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_river_corridor_threshold_trial.py`
- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_corridor_enhancement_gradient.py`

关键输出:

- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_inner_outer_altitude_gradient_combined.png`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_buffer_inner_outer_altitude_gradient.png`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_foehn_isolation_reference.png`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_river_corridor_threshold_trial.png`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_corridor_enhancement_gradient.png`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_river_corridor_cells.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_corridor_segment_strength_20km.csv`

## 5. 当前风险清单更新

### 风险 1: `_region` 不是严格河谷内

状态:

- 已明确 `_region` 是河谷邻域窗口,不是严格 polygon 内部。
- 用户说明这是有意设计,用于观察河谷内外与周边山体。

影响:

- 论文表述必须改为“河谷邻域窗口”。
- 不能把 Fig 1-5 说成严格干热河谷内部结果。

### 风险 2: 样本平衡约束未落地

状态:

- 当前 VAI 栅格没有执行每侧最少像元数、像元数比、覆盖比例等严格约束。
- 用户说明严格约束后有效网格过于零散,因此暂时取消。

影响:

- 不能声称完全采用 Tian 样本平衡约束。
- 正式结果前最好输出 windward/leeward count 或做敏感性检查。

### 风险 3: “阈值”定义仍不唯一

当前候选:

- `VAI=0` 反转阈值。
- segmented 曲线结构断点。
- 相对河道高差上的 `VAI=0` 反转。
- 近河-远河 `ΔVAI` 消失高度。

当前判断:

- 只有 `VAI=0` 反转阈值目前足够稳定。
- 近河-远河 `ΔVAI` 更接近焚风额外增强,但结果不够稳定和特别。

### 风险 4: “有些山”还不是严格山体单元

状态:

- 5 月 6 日已新增河段强弱分级。
- 但河段不等于山体。

影响:

- 可向赵导说“先按河段量化强弱差异”。
- 暂不应说“已经完成山体尺度差异量化”。

## 6. 当前可对赵导汇报的短版本

最稳妥版本:

> 目前我把四条河谷的迎风/背风 VAI 沿海拔做了统一比较。若把 VAI 由正转负作为迎背风差异的海拔反转阈值,四条河都存在阈值,LOWESS 结果集中在 3160-3680 m,四河之间最大差约 520 m。为了避免只依赖外接矩形窗口,我又按河道中心线做了 10-30 km 廊道筛选,合并样本的 VAI 反转仍在约 3520 m,对应相对河道高差约 1.1-1.2 km。强弱差异方面,我已按河段统计 20 km 河道邻域内的 `|VAI|` 中位数,大渡河和金沙江部分河段强,岷江整体强段少。现在还不能把这个解释为焚风效应停止高度,因为 VAI=0 只是迎背风差异反转,不是焚风消失。

不能汇报的版本:

> 已经证明焚风效应在 2.4 km 高差后消失。

原因:

- 近河-远河 `ΔVAI` 合并样本给出约 2.4 km,但单河谷不稳,也不够特别。

## 7. 下一步建议

下一步只做一件事:

> 把“赵导的阈值”明确固定为 `VAI=0` 反转阈值,还是固定为“近河相对远河的额外增强消失阈值”。

如果选择 `VAI=0`:

- 现有 Fig 1-5 + 河道廊道稳健性检查可以继续整理。
- 重点补充表述约束: 这是迎背风植被差异反转,不是焚风停止。

如果选择“焚风额外增强消失”:

- 现有结果不足。
- 需要重新设计对照,并证明对照不是简单海拔/雪线/山系差异导致。

当前不建议:

- 继续增加新分类。
- 继续做干热河谷内外二分。
- 继续用远离河谷参照区硬做 `VAI_ref(z)`。
- 把近河-远河差分包装成主成果。

