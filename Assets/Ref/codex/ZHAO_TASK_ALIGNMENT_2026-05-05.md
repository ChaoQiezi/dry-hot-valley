# 赵导问题对齐记录 2026-05-05

本文档记录当前项目针对赵导三句话的最新工作口径。依据为实际代码、栅格、矢量和输出表; 不以 `LOG.MD` 或 Claude 文档作为执行事实。

## 1. 用户澄清后修正的判断

### 1.1 `_region` 不是误裁剪

确定知识:

- 四河 `*_region.tif` 是有意保留的河谷邻域窗口。
- 目的不是严格只看干热河谷 polygon 内部,而是同时观察干热河谷内外及两侧山地的 VAI 空间差异。

后续表述:

- 可以称为“四河谷邻域窗口”或“河谷段邻域分析窗口”。
- 不应称为“严格干热河谷 polygon 内部样本”。

### 1.2 迎/背风样本平衡是暂时放宽,不是忘记

确定知识:

- 严格执行每侧像元数和比例平衡后,有效网格会过于零散,难以继续做海拔阈值和空间异质性分析。
- 当前 VAI 面是为了保留分析连续性而采用的工作版本。

后续处理:

- 不应把“未执行严格平衡约束”写成单纯错误。
- 但正式结果前仍建议输出 `windward_count` / `leeward_count` 栅格,并做敏感性检查,说明放宽约束是否改变阈值位置。

### 1.3 “高度差”现在必须重新定义

确定知识:

- 之前 `Table1_threshold_summary.csv` 中的“谷底海拔”只是最低有效海拔 bin,不能当真实谷底。

当前可用定义:

- 定义 A: 四河 LOWESS 反转阈值之间的绝对海拔差。
- 定义 B: LOWESS 反转阈值相对河流中心线 DEM 低位基准的高差。
- 定义 C: LOWESS 反转阈值附近 3 km 网格相对最近河道 DEM 的局地高差。

最稳妥汇报顺序:

1. 先报定义 A,因为它直接来自 VAI-海拔曲线。
2. 再报定义 C,因为它更接近“山坡相对河道抬升多少米后发生转变”。
3. 定义 B 只作为河谷尺度参考,不作为最终机制解释。

## 2. 新增脚本

新增:

- `F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\zhao_threshold_intensity.py`

输入:

- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\reversal_bootstrap_results.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\methods_forest_data.csv`
- `E:\GeoProjects\dry_hot_valley\{Valley}\VAI\VAI_3km_region.tif`
- `E:\GeoProjects\dry_hot_valley\{Valley}\VAI\DEM_3km_region.tif`
- `E:\GeoProjects\dry_hot_valley\{Valley}\geo_factor\elevation_10m_projected_region.tif`
- `E:\GeoProjects\dry_hot_valley\valley_area\river_net\centerline_final.shp`

输出:

- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\river_centerline_dem_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_threshold_height_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_reversal_pairwise_height_diff.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_grid_intensity_by_valley.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_segment_intensity_30km.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\zhao_segment_intensity_summary.csv`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\Fig6_zhao_segment_intensity_30km.png`

关键参数:

- `HIGH_CONF_LOW = 1500`
- `HIGH_CONF_HIGH = 4500`
- `CENTERLINE_SAMPLE_STEP_M = 100`
- `SEGMENT_LENGTH_M = 30000`
- `MAX_RIVER_DISTANCE_M = 30000`
- `THRESHOLD_BAND_M = 100`
- `MIN_GRID_PER_SEGMENT = 10`

## 3. 当前结果

### 3.1 阈值是否存在

确定知识:

| 河谷 | LOWESS 反转海拔 m | 95% CI m |
|---|---:|---|
| 岷江 | 3164.5 | 3110.0-3212.9 |
| 大渡河 | 3394.0 | 3230.6-3547.2 |
| 金沙江 | 3684.2 | 3594.6-3720.9 |
| 雅砻江 | 3605.6 | 3402.2-3736.7 |

解释:

- 四河均存在 VAI 由正转负的 LOWESS 反转点。
- 反转阈值集中在 3.16-3.68 km。
- 这可以正面回答“迎风/背风坡效应的海拔阈值效应是否存在”。

### 3.2 阈值之间是多少高度差

确定知识:

| 河谷对 | 反转海拔差 m |
|---|---:|
| 岷江-大渡河 | 230 |
| 岷江-金沙江 | 520 |
| 岷江-雅砻江 | 441 |
| 大渡河-金沙江 | 290 |
| 大渡河-雅砻江 | 212 |
| 金沙江-雅砻江 | 79 |

解释:

- 四河最大阈值差约 520 m。
- 金沙江与雅砻江最接近,差约 79 m。

### 3.3 阈值相对河道/谷底是多少高度差

确定知识:

| 河谷 | 河道 DEM p05 m | 反转海拔 - 河道 p05 m | 阈值附近局地相对河道高差中位数 m |
|---|---:|---:|---:|
| 岷江 | 1245.7 | 1918.8 | 1427.4 |
| 大渡河 | 1217.9 | 2176.1 | 1300.1 |
| 金沙江 | 539.4 | 3144.8 | 1085.1 |
| 雅砻江 | 1229.2 | 2376.5 | 1614.0 |

解释:

- “反转海拔 - 河道 p05”是河谷尺度低位基准差,会受整条河纵向落差影响,尤其金沙江。
- “阈值附近局地相对河道高差”更接近坡面相对最近河道抬升高度,当前范围约 1.09-1.61 km。
- 这只是工作定义,但已经比“最低有效海拔 bin”更接近赵导的“高度差”。

### 3.4 有些山强,有些山弱

当前用 30 km 河段邻域作为最小可行替代,不是正式山体单元。

确定知识:

| 河谷 | 有效河段数 | 河段 \|VAI\| 中位数 % | 强河段比例(\|VAI\|中位数>=10%) | 弱河段比例(\|VAI\|中位数<=3%) |
|---|---:|---:|---:|---:|
| 岷江 | 13 | 3.70 | 0.00% | 30.77% |
| 大渡河 | 23 | 4.78 | 13.04% | 4.35% |
| 金沙江 | 28 | 2.80 | 25.00% | 53.57% |
| 雅砻江 | 41 | 3.20 | 0.00% | 43.90% |

解释:

- 大渡河整体河段强度最高,弱河段比例最低。
- 金沙江总体中位强度低,但存在若干强河段,说明“有些山很强、有些不强”的空间异质性最明显。
- 岷江和雅砻江当前没有达到 `|VAI|中位数 >= 10%` 的强河段。

## 4. 当前可向赵导说的话

可以说:

> 我现在按四条川西河谷邻域窗口做了迎风/背风 VAI 的海拔剖面。四条河都出现了 VAI 从正到负的反转,LOWESS bootstrap 的反转海拔分别是岷江 3165 m、大渡河 3394 m、金沙江 3684 m、雅砻江 3606 m,集中在 3.16-3.68 km,最大河谷间差约 520 m。分段回归在三条河给出 3.8-3.9 km 附近结构断点,所以目前更稳妥地说是 3.2-3.9 km 的过渡带。

可以补充:

> 我重新用河流中心线和 10 m DEM 估算了相对河道高差。若看阈值附近 3 km 网格到最近河道的局地相对高差,中位数约 1.09-1.61 km,比之前用最低有效海拔 bin 更合理。

可以说但要加限定:

> 关于“有些山差异大、有些不大”,我暂时用沿河 30 km 河段邻域做量化。大渡河整体强度最高; 金沙江整体中位强度不高,但强河段比例最高,说明空间异质性明显。这个结果还不是正式山体单元,但已经从四河平均推进到河段尺度。

不能说:

> 已经完成严格干热河谷 polygon 内部分析。

> 已经完成迎/背风样本平衡后的最终阈值。

> 已经用正式山体单元回答了“有些山”。

## 5. 下一步只做一件事

先检查 `Fig6_zhao_segment_intensity_30km.png` 中强弱河段的空间连续性:

- 如果强河段连续,下一步做河段空间分布图。
- 如果强河段零散,先回查这些河段的 `n_grid`、河距和 DEM 分布,判断是否是低样本/远离河道导致。

目的:

- 检查强弱河段是否是连续地理段,还是零散噪声。
- 直接服务赵导“有些山差异大、有些不大”。
