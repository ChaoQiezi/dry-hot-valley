# 2026-05-08 项目进展系统性分析

分析时间: 2026-05-08 晚  
分析者: Codex  
依据材料:

- `F:\PyProJect\dry_hot_valley\Assets\Ref\claude\PROGRESS_2026-05-08.md`
- 当前代码与输出表图，尤其是 `VAI_buffer_threshold_summary_all.csv`
- 2026-05-08 新增的 `slope > 5°` 迎/背风坡过滤与 valley buffer 结果重跑

## 0. 一句话结论

截至 2026-05-08 晚，项目主线已经从早期 `_region` 外接矩形 VAI 海拔剖面，转到 **4 km 河道 buffer 内重新计算 3 km VAI，并用 LOWESS + bootstrap 估计迎/背风坡植被差异的海拔反转阈值**。

今天最重要的变化是：迎风坡/背风坡二分类栅格已在上游加入 `slope > 5°` 过滤，因此最新 valley buffer 阈值结果已经替换 Claude 早些时候记录的 pre-slope5 结果。当前四河合并结果为：

- 绝对海拔反转阈值: **3721 m**，95% CI **3632-3869 m**，bootstrap **500/500**。
- 相对河道高差反转阈值: **1406 m**，95% CI **1320-1569 m**，bootstrap **500/500**。

边界必须说清楚：这回答的是 **VAI 正负反转阈值**，不是直接证明“焚风效应在该高度停止”。

## 1. 当前主线到底是什么

### 1.1 旧主线: `_region` 外接矩形

`_region` 是每条河谷矩形窗口内的 VAI 分析。优点是样本多、曲线平滑；问题是包含大量不属于干热河谷核心影响带的山体。5 月 5 日 Fig 1-5 的结果主要来自这条线。

当前判断：

- `_region` 可作为背景或 baseline。
- 不适合作为给赵导汇报的主线。
- 原因不是代码必然错，而是研究对象口径不够干净。

### 1.2 试验线: strict polygon

strict polygon 只在干热河谷 polygon 内重算 VAI。概念更严格，但样本量过少，尤其高海拔段不足，bootstrap 不稳定。

当前判断：

- 可作为方法对照。
- 不适合作主线。

### 1.3 当前主线: 4 km river buffer

当前最可汇报的主线是：以四条河流中心线为基准，建立 4 km buffer，在 buffer 内重新计算 3 km VAI，然后估计 VAI 随绝对海拔和相对河道高差的正负反转阈值。

这条线的优势：

- 不再使用外接矩形大窗口。
- 比 strict polygon 有更稳定的样本量。
- 四条河可以用同一套规则比较。
- 能同时回答“多少海拔”和“多少高度差”。

推荐表述：

> 以河道中心线 4 km buffer 作为干热河谷核心影响带，在该范围内重新计算 3 km VAI，并分析迎风坡/背风坡植被差异随海拔和相对河道高差的反转阈值。

## 2. 今天新增的关键方法修正

### 2.1 迎/背风坡二分类加入 `slope > 5°`

问题：之前 `windward_leeward.tif` 没有剔除低坡度区域，导致平缓像元也被分为迎风坡或背风坡。

当前处理：

- 修正位置: `F:\PyProJect\dry_hot_valley\Src\preprocessing\windward_leeward_divide.py`
- 输入 slope: `E:\GeoProjects\dry_hot_valley\GeoFactor\Slope\slope_10m_projected.tif`
- 规则: `slope <= 5°` 或 slope nodata 的像元设为 `255`
- 后续所有读取 `windward_leeward.tif` 的 VAI 计算自动继承该过滤

这是正确的上游修正方式，不应在每个下游 VAI 脚本里重复加 slope 判断。

### 2.2 ERA5 生长季月份从 6-8 月改为 5-9 月

修正位置:

- `F:\PyProJect\dry_hot_valley\Src\preprocessing\era5\era5_u_v_preprocess.py`

当前代码：

```python
start_month = 5
end_month = 9
```

重要边界：

- 代码已改。
- 但 5-9 月 ERA5 风场是否已经完整传播到 `wind_effect.tif`，当前不能从结果表直接证明。
- 因此当前 valley buffer 最新结果可以确认使用了 `slope > 5°` 的迎/背风坡二分类；但是否已经使用 5-9 月重算风效应，需要后续单独核验完整风场链条。

### 2.3 阈值脚本海拔分箱改为 50 m

当前 git diff 显示四个单河谷和整体 threshold 脚本的分箱参数已从 100 m 改为 50 m：

```python
ABS_BIN_M = 50
REL_BIN_M = 50
```

这会让剖面曲线更细，但也更依赖样本量。当前 `MIN_BIN_COUNT = 10`，合并图可用；单河谷低样本段仍需要谨慎解释。

## 3. 当前最新结果，以 slope5 之后为准

输出表：

`E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_threshold_summary_all.csv`

最新结果如下：

| 河谷 | n cells | ABS 反转 m | ABS 95% CI | ABS boot | REL 反转 m | REL 95% CI | REL boot |
|---|---:|---:|---|---:|---:|---|---:|
| 大渡河 | 542 | 3535 | 3478-3645 | 500/500 | 1333 | 1267-1530 | 487/500 |
| 金沙江 | 508 | 4176 | 3999-4445 | 475/500 | 1649 | 1519-1755 | 53/500 |
| 岷江 | 253 | 3218 | 3092-3433 | 490/500 | 1318 | 1203-1568 | 486/500 |
| 雅砻江 | 740 | 3539 | 3466-3625 | 500/500 | 1229 | 1126-1406 | 498/500 |
| 整体 | 2043 | 3721 | 3632-3869 | 500/500 | 1406 | 1320-1569 | 500/500 |

与 pre-slope5 结果相比：

| 指标 | pre-slope5 | slope5 后 | 变化 |
|---|---:|---:|---:|
| 整体 n cells | 2049 | 2043 | -6 |
| 整体 ABS 反转 | 3735 m | 3721 m | -14 m |
| 整体 REL 反转 | 1406 m | 1406 m | 约 0 m |
| 金沙江 REL boot | 37/500 | 53/500 | 略有改善但仍不稳 |

结论：`slope > 5°` 修正没有推翻 buffer 主结果，但让方法口径更干净。

## 4. ABS 和 REL 分别回答什么

ABS 使用 3 km 网格平均海拔：

```text
ABS = DEM_m
```

它回答：

> 迎/背风坡 VAI 反转大约发生在多少米绝对海拔？

REL 使用网格平均海拔减去最近河道海拔：

```text
REL = grid DEM - nearest river DEM
```

它回答：

> 相对谷底/河道抬升多少米后，迎/背风坡 VAI 发生反转？

赵导说的“是多少高度差”，更接近 REL。但论文或汇报里不应只报 REL，因为 ABS 更直观，也更容易和植被带、雪线或高山环境解释联系起来。

当前建议汇报两套值：

- 总体绝对海拔反转: **约 3.72 km**
- 总体相对河道高差反转: **约 1.41 km**

## 5. LOWESS、bootstrap 和 CI 的实际含义

### 5.1 LOWESS

LOWESS 是局部平滑，不假设 VAI 与海拔是直线关系。当前代码使用：

```python
LOWESS_FRAC = 0.35
```

含义：每个局部拟合大致使用 35% 邻近样本，用来从散乱的 3 km 网格点中提取总体趋势。

### 5.2 反转阈值

当前阈值定义为 LOWESS 平滑曲线第一次从正值穿过 0 变为负值的位置：

```text
VAI_smooth > 0  ->  VAI_smooth < 0
```

所以它是“迎风坡更绿”转为“背风坡更绿”的交点。

### 5.3 bootstrap 95% CI

bootstrap 当前重复 500 次。每次从 cell-level 样本中有放回重采样，重新拟合 LOWESS，重新找 VAI=0 交点。

95% CI 是这些 bootstrap 交点的 2.5% 和 97.5% 分位数。

注意：这个 CI 只反映样本重采样不确定性，不包括：

- NDVI 误差
- DEM 误差
- 风向分类误差
- buffer 宽度选择误差
- LOWESS 参数选择误差
- 5-9 月风场是否已完全传播的误差

## 6. 这些结果怎么回答赵导

### 6.1 “海拔阈值效应是否存在？”

可以回答：存在一个清晰的 VAI 正负反转阈值。

推荐表述：

> 在 4 km 河道 buffer 内重新计算 3 km VAI 后，四河合并样本显示迎/背风坡植被差异随海拔升高发生稳定正负反转。整体绝对海拔反转点约为 3721 m，95% bootstrap CI 为 3632-3869 m。

不要说：

> 焚风效应在 3721 m 停止。

### 6.2 “是多少高度差？”

可以用 REL 回答：

> 若以相对河道高差表示，四河合并反转点约为 1406 m，95% bootstrap CI 为 1320-1569 m。

但要补充：

> 大渡河、岷江、雅砻江的 REL 反转较接近，约 1.2-1.3 km；金沙江 REL 反转 bootstrap 支持较弱，仅 53/500，说明金沙江沿相对高差的反转不稳定。

### 6.3 “有些山差异大，有些不大”

当前还没有完全回答。

已经能回答的是：

- 四条河谷之间的阈值位置不同。
- 金沙江 ABS 反转最高，岷江最低。
- 大渡河和雅砻江 ABS 反转几乎一致。

还没充分回答的是：

- 同一条河谷内哪些河段/山段迎背风差异强，哪些弱。

下一步应使用 buffer cell 结果做河段强弱分级，而不是继续堆更多阈值图。

建议指标：

- `median(|VAI|)`
- `p90(|VAI|)`
- `pct(|VAI| >= 10%)`
- 单位: 30 km 河段或已有 `segment_id`

## 7. 当前图件和表格状态

### 7.1 主结果图

当前主图：

`E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_buffer_threshold_all.png`

用途：

- 放 PPT 主结果页。
- A/B 展示 ABS 和 REL 梯度。
- C 展示样本支撑。
- D 展示四河和整体的 forest plot。

### 7.2 中文 VAI 空间分布图

新增脚本：

`F:\PyProJect\dry_hot_valley\Src\plot\VAI_spatial_distribution_ppt_cn.py`

输出：

- `E:\GeoProjects\dry_hot_valley\Result\Chart\VAI_spatial_distribution_ppt_cn.png`
- `E:\GeoProjects\dry_hot_valley\Result\Chart\VAI_spatial_distribution_map_only_cn.png`

用途：

- `ppt_cn.png`: 可直接放组会 PPT。
- `map_only_cn.png`: 适合单独作为底图，在 PPT 里自行加标题和说明。

当前统计：

- 有效 3 km 网格: 33,432
- VAI 中位数: -1.17%
- VAI > 0: 41.8%
- VAI < 0: 58.2%

注意：这张空间分布图基于整体 `VAI_3km.tif`，展示全域空间格局，不等同于 4 km buffer 阈值主结果。

## 8. 当前不能说什么

不能说：

> 3721 m 是焚风效应停止高度。

应说：

> 3721 m 是 4 km river buffer 约束下 VAI 由正转负的整体反转海拔。

不能说：

> 四条河谷相对高差阈值完全一致。

应说：

> 大渡河、岷江、雅砻江 REL 阈值较接近；金沙江 REL 反转不稳定。

不能说：

> 已经完整回答“有些山差异大，有些不大”。

应说：

> 已经看到河谷间差异；同一河谷内河段强弱分级仍需补。

不能说：

> 5-9 月 ERA5 风场已经完整更新到所有下游结果。

应说：

> ERA5 预处理代码已改为 5-9 月，但完整风效应链条是否重跑需要单独确认。

## 9. 现阶段 PPT 建议结构

### Slide 1: 赵导问题拆解

只写三句：

- 是否存在迎/背风坡效应的海拔阈值？
- 阈值是多少海拔或相对河道高差？
- 哪些河谷/河段差异强，哪些弱？

### Slide 2: 为什么不用 `_region` 作主线

放 `_region`、strict、4 km buffer 三者对比：

| 方法 | 优点 | 问题 | 当前定位 |
|---|---|---|---|
| `_region` | 样本多 | 包含大量河谷外山体 | baseline |
| strict polygon | 边界严格 | 样本不足、不稳定 | 对照 |
| 4 km buffer | 河道约束、样本较稳 | buffer 宽度需敏感性 | 主线 |

### Slide 3: 方法流程

```text
河道中心线
-> 4 km buffer
-> 10 m NDVI + DEM + slope5 后迎/背风坡分类
-> 3 km VAI
-> LOWESS
-> bootstrap 反转阈值
```

### Slide 4: 四河合并结果

放 `VAI_buffer_threshold_all.png` 的核心部分。

讲法：

- ABS: 3721 m [3632, 3869]
- REL: 1406 m [1320, 1569]

### Slide 5: 分河谷差异

讲：

- 金沙江 ABS 最高: 4176 m
- 岷江 ABS 最低: 3218 m
- 大渡河和雅砻江接近: 3535 m 与 3539 m
- 金沙江 REL 不稳定: 53/500

### Slide 6: 空间格局

放中文空间分布图：

`VAI_spatial_distribution_ppt_cn.png`

讲：

- VAI 正负在空间上不是随机噪声。
- 高值/低值带与河谷和山体结构有空间组织性。
- 这张图用于说明空间异质性，不直接替代阈值分析。

### Slide 7: 仍需补的关键一页

题目：

> 哪些河段迎/背风坡差异强，哪些弱？

下一步输出：

- 30 km 河段强弱分级图
- 指标: `median(|VAI|)`, `p90(|VAI|)`, `pct(|VAI| >= 10%)`
- 这才更直接回应赵导第三句话。

## 10. 当前工程状态

当前 `git status` 显示：

- 修改了 5 个 `VAI_buffer_valley_threshold*.py` 脚本，主要是 ABS/REL 分箱从 100 m 调整到 50 m。
- 新增 `Src/plot/VAI_spatial_distribution_ppt_cn.py`。

当前重要输出：

- 最新主结果表: `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_threshold_summary_all.csv`
- slope5 前备份表: `E:\GeoProjects\dry_hot_valley\Result\Table\altitude\VAI_buffer_threshold_summary_all_pre_slope5.csv`
- 主结果图: `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\VAI_buffer_threshold_all.png`
- 中文空间图: `E:\GeoProjects\dry_hot_valley\Result\Chart\VAI_spatial_distribution_ppt_cn.png`

## 11. 我对当前进展的判断

确定知识：

- 4 km buffer 主线已经四河跑通。
- slope > 5° 后的迎/背风坡分类已经用于最新 valley buffer 输出。
- slope5 后整体 ABS 和 REL 阈值仍然稳定。
- 最新合并结果比 pre-slope5 结果略有变化，但主结论不变。

合理推断：

- 当前最适合给赵导看的核心数字是 **3721 m** 和 **1406 m**。
- 4 km buffer 比 `_region` 更能回应“河谷”问题，比 strict polygon 更稳。
- 金沙江可能是后续讨论区域分异的关键河谷，因为它 ABS 阈值高、REL 阈值不稳定。

不确定：

- 4 km 是否是最佳 buffer 宽度。
- 5-9 月 ERA5 是否已经完整传播到 SAGA wind effect 和下游 VAI。
- 高海拔负 VAI 是否受雪、裸地、植被带或 NDVI 饱和/低值影响。
- 河段强弱差异尚未用最新 slope5 buffer cells 重新分级。

## 12. 给后续工作的直接建议

下一步不要再继续扩展新概念，先补最贴近赵导第三句话的结果：

1. 用 slope5 后的 `VAI_buffer_cells_all.csv` 做 30 km 河段强弱分级。
2. 输出每条河的强弱空间图和汇总表。
3. 再做 3/4/5 km buffer 宽度敏感性，确认 3721 m 和 1406 m 是否稳定。
4. 单独确认 5-9 月 ERA5 是否已经重跑到 `wind_effect.tif`。

最小可汇报版本：

> 我们已在四条河谷的 4 km 河道 buffer 内重算 3 km VAI，并在迎/背风坡分类中加入 slope>5° 过滤。结果显示，四河合并的 VAI 正负反转海拔约为 3721 m，相对河道高差约为 1406 m。分河谷看，金沙江反转海拔最高、岷江最低，大渡河和雅砻江接近；但金沙江相对高差阈值不稳定，说明河谷间确实存在差异。下一步将用河段尺度的 |VAI| 强弱分级回答“哪些山/河段差异大，哪些不大”。

