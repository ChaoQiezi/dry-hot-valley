# 方向矫正：山体两侧（河谷侧 vs 外侧）坡面对比方法论调研报告

**调研背景**：赵导师指出，对比对象不是"河谷左岸 vs 右岸"，而是**同一山体的两侧坡面**——对于河谷左岸的某像元，应与该像元所在山脉**另一侧**对应的像元进行对比；右岸亦然。即"河谷侧坡面 (valley-facing slope) vs 外侧坡面 (outward-facing slope)"的配对比较。  
**调研日期**：2026年4月  
**关键词覆盖**：hillslope asymmetry, opposing slope comparison, drainage divide extraction, ridge-line segmentation, slope unit, aspect-driven vegetation asymmetry, paired transect, valley-facing vs outward-facing

---

## 一、核心概念框架：从"左右岸"到"同一山体两侧"

### 1.1 概念区分

| 旧范式（已弃用） | 新范式（赵导师矫正） |
|---|---|
| 以河流中心线为轴，左岸 vs 右岸 | 以**山脊线/分水岭**为轴，河谷侧 vs 外侧 |
| 比较对象位于同一河谷内 | 比较对象位于**同一山体的两个坡面** |
| 关注河谷内部的南北坡差异 | 关注焚风/地形遮蔽/水汽输送等在**山体两侧**造成的植被差异 |
| 边界 = 河流中心线 | 边界 = **分水岭 (drainage divide) / 山脊线 (ridgeline)** |

### 1.2 实际含义

以大渡河干热河谷为例：大渡河左岸（西岸）的某像元A位于某山脉的**东坡**（朝向河谷），新范式要求找到该山脉**西坡**（背离河谷、朝向外侧流域）的对应像元A'进行配对比较。两个像元以山脊线为对称轴，分属同一山脉的不同侧面。

---

## 二、坡面不对称性（Hillslope Asymmetry）的量化方法

### 2.1 Poulos et al. (2012, GRL) — 滑动窗口坡面不对称性指数 (HAI)

**核心思想**：用滑动窗口在DEM上逐像元计算对向坡面的坡度差异，生成连续的坡面不对称性图。

**方法要点**：
- 基于DEM导出**坡度 (slope)** 和**坡向 (aspect)** 栅格
- 坡向划分为4个90°象限：N (315°–45°), E (45°–135°), S (135°–225°), W (225°–315°)
- 在**5×5 km²**滑动窗口内，逐像元将坡度按坡向分箱
- 计算N–S方向的HAI：

$$I_{N-S} = \log_{10}\left(\frac{\tilde{\theta}_N}{\tilde{\theta}_S}\right)$$

其中 $\tilde{\theta}_N$, $\tilde{\theta}_S$ 为窗口内北坡和南坡像元的**中位数坡度**

- 正值 = 北坡更陡；负值 = 南坡更陡；0 = 对称
- 同理可计算 $I_{E-W}$
- 排除坡度 < 5° 的平坦区域
- 平滑步骤：在5×5 km窗口内取中位数 HAI

**适用性**：该方法直接在栅格层面操作，无需预先提取山脊线。可推广为**NDVI不对称性指数**（用NDVI替代坡度）。

> 来源：Poulos, M. J., Pierce, J. L., Flores, A. N., & Benner, S. G. (2012). Hillslope asymmetry maps reveal widespread, multi-scale organization. *Geophysical Research Letters*, 39, L06406. [PDF](http://geomorphology.sese.asu.edu/Papers/Poulos_et_al_2012_GRL.pdf)

---

### 2.2 Smith & Bookhagen (2021, JGR-Earth Surface) — 全球坡面不对称性的椭圆拟合法

**核心思想**：将每个分析窗口内的坡度-坡向分布视为椭圆，椭圆质心偏移量即为坡面不对称性。

**方法要点**：
- 使用30m SRTM DEM，分析窗口为 **0.25° × 0.25°**（约25 km）
- 对每个窗口，以1°坡向间隔统计中位坡度，得到360个数据点
- 将坡度-坡向分布拟合为椭圆（Fitzgibbon et al., 1996最小二乘法）
- **椭圆质心偏移** = 地形不对称性：
  - x方向偏移 > 0 → 北坡更陡
  - y方向偏移 > 0 → 东坡更陡
- 植被不对称性用归一化比值：

$$\text{Vegetation Asymmetry} = \frac{V_a - V_b}{V_a + V_b}$$

其中 $V_a$, $V_b$ 为对向坡面（如N vs S）的中位植被覆盖度

- 数据源：Landsat VCF (30m), MODIS NDVI (1km), TanDEM-X森林覆盖 (50m)

**关键发现**：
- 全球74%的不对称地形中，**向极坡 (pole-facing)** 比向赤道坡更陡
- 向极坡的植被覆盖度几乎普遍高于向赤道坡
- 中纬度、干旱区植被不对称性最大
- 代码开源：[Zenodo](https://doi.org/10.5281/zenodo.3839251)

> 来源：Smith, T., & Bookhagen, B. (2021). Climatic and biotic controls on topographic asymmetry at the global scale. *Journal of Geophysical Research: Earth Surface*, 126, e2020JF005692. [链接](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020JF005692)

---

### 2.3 Xie et al. (2025, GRL) — 青藏高原东西坡草地绿度不对称性 (GAI)

**核心思想**：以固定网格为单元，计算东西坡平均NDVI的比值，揭示微气候驱动的植被差异。

**方法要点**：
- 东坡像元：坡向 45°–135°，坡度 5°–25°
- 西坡像元：坡向 225°–315°，坡度 5°–25°
- 以 **3×3 km** 网格为单元（包含100×100个30m Landsat像元）
- **GAI (Greenness Asymmetry Index)**：

$$\text{GAI} = \frac{\overline{\text{NDVI}}_{\text{west}}}{\overline{\text{NDVI}}_{\text{east}}}$$

- GAI > 1 → 西坡更绿；GAI < 1 → 东坡更绿
- 使用7–8月峰值NDVI，1991–2020年时间序列
- 统计检验：双尾t检验 (p < 0.01)；趋势分析：线性回归

**关键发现**：
- 63.38%区域GAI > 1（西坡更绿），主要在青藏高原西部/中部（水分限制区）
- 36.62%区域GAI < 1（东坡更绿），主要在东部（温度限制区）
- 降水是主导驱动因子（R = -0.83）

**对本研究的启示**：GAI方法可直接迁移——将"东坡 vs 西坡"替换为"河谷侧坡 vs 外侧坡"，在固定网格中比较两类像元的平均NDVI。

> 来源：Xie, J., Yan, X., Chen, R., et al. (2025). Microclimate driven grassland greenness asymmetry between west- and east-facing slopes on the Tibetan Plateau. *Geophysical Research Letters*, 52, e2024GL113327. [链接](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024GL113327)

---

## 三、山脊线/分水岭提取方法（划分"河谷侧"与"外侧"的关键技术）

### 3.1 方法一：DEM反转法提取山脊线（Esri推荐流程）

**原理**：山脊线是"反向水系"——将DEM取反后，原来的山脊变为"河谷"，可用标准水文分析工具提取。

**步骤**（[Esri Knowledge Base](https://support.esri.com/en-us/knowledge-base/identify-ridgelines-from-a-dem-1462481744099-000011289)）：
1. **Fill** DEM消除洼地
2. **Raster Calculator**: DEM × (−1)，反转高程
3. 对反转DEM运行 **Flow Direction**（勾选 Force all edge cells to flow outward）
4. **Flow Accumulation** 计算汇流累积
5. 设定阈值提取"河道"→ 即为原始DEM的山脊线
6. **Stream to Feature** 矢量化

**优点**：简单直观，可在ArcGIS/QGIS中快速实现  
**缺点**：阈值选择需人工调整；在平坦地形可能产生噪声

---

### 3.2 方法二：TopoToolbox分水岭网络提取（Schwanghart & Scherler, 2020）

**核心思想**：自动提取分水岭网络（drainage divide network），并赋予层级排序，适合大区域系统分析。

**方法要点**（[Earth Surface Dynamics论文](https://esurf.copernicus.org/articles/8/245/2020/)）：
1. D8算法计算流向 → 设定汇水面积阈值（如0.1 km²）提取水系
2. 在所有支流交汇处和出口提取流域边界 → 初始分水岭线段
3. 组织为**分水岭网络**：
   - 端点 (endpoints) = 分水岭末端
   - 交汇点 (junctions) = 分水岭分叉处
   - 合并/拆分线段，处理D8连通性问题
4. **排序** (tree-pruning from endpoints)：从端点向内逐步移除，建立有向无环图
5. **分水岭距离 (divide distance, dd)**：沿排序网络从端点的最大距离
6. **排序方案**：Strahler、Shreve、Topo（新提出）

**工具**：**TopoToolbox v2** (MATLAB)，免费开源  
**核心产出**：分层级的分水岭线，可直接作为"山体两侧"划分的边界

> 来源：Schwanghart, W., & Scherler, D. (2020). Drainage divide networks – Part 1: Identification and ordering in digital elevation models. *Earth Surface Dynamics*, 8, 245–259. DOI: [10.5194/esurf-8-245-2020](https://esurf.copernicus.org/articles/8/245/2020/)

---

### 3.3 方法三：r.slopeunits — 以山脊线和谷线分割坡度单元

**核心思想**：将地形自动分割为以**山脊线 (ridge lines)** 和**谷线 (valley lines)** 为边界的坡度单元 (slope units)，每个单元代表一个完整的坡面。

**方法要点**（[Alvioli et al., 2016, GMD](https://gmd.copernicus.org/articles/9/3975/2016/)）：
- 输入：DEM + 几个参数
- 基于 **GRASS GIS** 的 **r.watershed** 工具
- 正地形（DEM原始）→ 提取谷线
- 负地形（DEM×(−1)）→ 提取山脊线
- 叠加谷线和山脊线 → 分割为坡度单元
- 每个坡度单元由一条山脊线和一条谷线围成，代表**一个坡面**
- 优化参数以适应研究区地形

**工具**：GRASS GIS插件 **r.slopeunits**（[官方文档](https://grass.osgeo.org/grass-stable/manuals/addons/r.slopeunits.html)），包含4个子模块：
- `r.slopeunits.create`：创建坡度单元
- `r.slopeunits.clean`：清理碎片
- `r.slopeunits.metrics`：计算指标
- `r.slopeunits.optimize`：优化参数

**对本研究的核心价值**：坡度单元天然以山脊线为边界划分，**同一山脊两侧的两个坡度单元** = 河谷侧坡面 + 外侧坡面，可直接配对比较。

> 来源：Alvioli, M., Marchesini, I., Reichenbach, P., et al. (2016). Automatic delineation of geomorphological slope units with r.slopeunits v1.0. *Geoscientific Model Development*, 9, 3975–3991. DOI: [10.5194/gmd-9-3975-2016](https://gmd.copernicus.org/articles/9/3975/2016/)

---

### 3.4 方法四：改进标记分水岭法（Zhou & Cheng, 2018）

**核心思想**：先用标记分水岭分割DEM为山体对象，再对山体进行正/负地形分割以提取山脊线和谷线，最终叠加得到坡面单元。

**步骤**：
1. 标记分水岭分割 → 提取山体对象
2. 对山体对象的正地形（凸起部分）用分水岭分割 → 山脊线
3. 对山体对象的负地形（凹入部分）用分水岭分割 → 谷线
4. 山脊线 + 谷线叠加 → 坡面单元

> 来源：Zhou, B., & Cheng, L. (2018). A new slope unit extraction method based on improved marked watershed. *MATEC Web of Conferences*, 232, 04070. DOI: [10.1051/matecconf/201823204070](https://www.matec-conferences.org/articles/matecconf/pdf/2018/91/matecconf_eitce2018_04070.pdf)

---

## 四、对向坡面配对比较的经典范式

### 4.1 北坡 vs 南坡（向极坡 vs 向赤道坡）的实地配对

**经典案例：Yang, El-Kassaby & Guan (2020, Scientific Reports)**  
研究区：**岷江上游干旱河谷**（与川西干热河谷属同一区域）

**配对设计**（[论文全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7536199/)）：
- 3个样地沿河谷分布（石大关、飞虹、汶川）
- 每个样地设置V形双样带：**北坡**样带 + **南坡**样带
- 5×5 m样方，沿样带每隔约20m海拔设置一个
- 共42个样方（北坡18，南坡24）
- 环境变量：海拔、坡度、坡位、土壤含水量、有机质等同步采集

**统计方法**：
- 群落组成：NMDS + ANOSIM（R = 0.46, p = 0.001）
- 植被结构：单因素ANOVA（整体和单站点层面）
- 多样性：γ（稀疏法）、α（Fisher/Shannon/Simpson）、β（距心距离法）

**核心结果**：北坡生物量是南坡的2.7倍（6568 vs 2430 kg/ha），高度差3.6倍（108 vs 30 cm），覆盖度差显著（69% vs 49%）。

**对本研究的启示**：
1. V形配对样带设计可推广为"山脊线两侧配对样带"
2. 在遥感像元尺度，可用类似逻辑——以山脊线为轴，两侧对应像元配对
3. 该论文恰好研究岷江干旱河谷，结论可直接作为验证参考

---

### 4.2 分水岭两侧的地形不对称性度量（Scherler & Schwanghart, 2020）

**Divide Asymmetry Index (DAI)**（[Earth Surface Dynamics论文](https://esurf.copernicus.org/articles/8/261/2020/)）：

$$\text{DAI} = \left|\frac{\Delta HR}{HR_{\max} + HR_{\min}}\right|$$

其中 $HR_{\max}$, $HR_{\min}$ 为分水岭两侧像元到最近河流的高程差（最大/最小值）。

- DAI = 0 → 完全对称；DAI → 1 → 极度不对称
- 也可将HR替换为其他指标（NDVI、流距、χ值等）

**同理可构建 NDVI Divide Asymmetry Index**：

$$\text{NDVI-DAI} = \frac{|\text{NDVI}_{\text{valley-side}} - \text{NDVI}_{\text{outer-side}}|}{\text{NDVI}_{\text{valley-side}} + \text{NDVI}_{\text{outer-side}}}$$

---

### 4.3 Cannon et al. (2016, Landscape Ecology) — 配对窗口法

**方法**（[PDF](https://cfri.colostate.edu/wp-content/uploads/sites/22/2018/04/2016-Cannon-et-al.-2016-Landscape-Ecology.pdf)）：
- 识别与干扰路径垂直的山脊
- 在山脊的**迎风侧**和**背风侧**各放置 150×150 m 采样窗口
- 要求每侧坡面至少150m长
- **配对t检验**比较两侧

虽然该研究对象为龙卷风损害，但其**配对窗口法**可直接迁移：在山脊线两侧各取等面积窗口，提取NDVI进行配对比较。

---

### 4.4 Jin et al. (2024, Science Bulletin) — 全球山地植被沿地形梯度的变异

**方法**（[Lund University链接](https://www.nateko.lu.se/hongxiao-jin/publication/5ae41a92-75bb-4ccc-ad68-8c6a61af55e8)）：
- 使用Sentinel-2高分辨率数据
- 在**0.15° × 0.15°** 山区网格内量化坡向、坡度、海拔对植被的差异效应
- 两个物候指标：最大植被绿度 + 季节绿度振幅

**关键发现**：25.9%的山区网格中，**坡向是造成植被模式最大差异的因素**。

---

## 五、综合方法论建议：川西干热河谷"同一山体两侧"NDVI对比

### 5.1 推荐技术路线

```
步骤1：提取山脊线/分水岭网络
   ├─ 方案A：DEM反转法（简便，ArcGIS/QGIS）
   ├─ 方案B：r.slopeunits（自动坡面单元，GRASS GIS）
   └─ 方案C：TopoToolbox分水岭网络（系统化，MATLAB）

步骤2：将像元分类为"河谷侧"与"外侧"
   ├─ 基于坡向+山脊线位置关系
   ├─ 河谷侧 = 坡向朝向河谷（flow direction → 河流方向）
   └─ 外侧 = 坡向背离河谷（flow direction → 外侧流域方向）

步骤3：像元配对与NDVI差异计算
   ├─ 方案A：固定网格平均法（Xie et al. 2025 GAI模式）
   │    → 3×3 km网格内，分别平均河谷侧和外侧像元NDVI
   │    → 计算 Valley Asymmetry Index = NDVI_valley / NDVI_outer
   ├─ 方案B：滑动窗口法（Poulos et al. 2012 HAI模式）
   │    → 在滑动窗口内按坡向分箱，计算对向NDVI比值
   └─ 方案C：逐山脊线配对法（Cannon et al. 2016模式）
        → 沿山脊线等距设置配对窗口，两侧各取缓冲区
        → 配对t检验

步骤4：控制混杂变量
   ├─ 海拔匹配（仅配对海拔相近的像元对）
   ├─ 坡度筛选（排除<5°平地和>25°悬崖）
   ├─ 土地利用排除（排除城镇、农田、水体）
   └─ 气候带分区（干热河谷内/外分别分析）

步骤5：统计分析
   ├─ 配对t检验/Wilcoxon符号秩检验
   ├─ 线性回归/趋势分析（多年时间序列）
   └─ 空间自相关检验（Moran's I）
```

### 5.2 三种方案的优劣对比

| 方案 | 代表文献 | 优点 | 缺点 | 适用场景 |
|---|---|---|---|---|
| **固定网格平均法** | Xie et al. (2025 GRL) | 简单，空间覆盖完整，可大面积制图 | 网格内混入不同山体；无法保证"同一山脊两侧"的严格配对 | 区域尺度宏观分析 |
| **滑动窗口法** | Poulos et al. (2012 GRL); Smith & Bookhagen (2021) | 连续制图，尺度可调，方法成熟 | 窗口内可能包含多个山脊；无法追踪单个山体 | 大区域趋势分析 |
| **坡面单元配对法** | r.slopeunits + DAI思路 | **最严格匹配"同一山脊两侧"**；地貌学含义清晰 | 需要高质量DEM；参数调优复杂；小坡面单元可能碎片化 | 精细尺度机理分析（推荐） |

### 5.3 推荐的最优方案：坡面单元配对法 + 网格法互补

**主方案**（精细尺度）：
1. 使用 **r.slopeunits** 或 **DEM反转法** 提取山脊线
2. 以山脊线为边界，将每段山脊线两侧的坡面单元视为**配对**
3. 筛选条件：
   - 一侧属于干热河谷边界内（基于范建容2022数据）→ 标记为"河谷侧"
   - 另一侧属于干热河谷边界外 → 标记为"外侧"
4. 对每对坡面单元，提取平均NDVI，计算差值/比值
5. 配对检验（Wilcoxon / 配对t）

**辅方案**（区域尺度）：
1. 仿照 Xie et al. (2025) 的GAI方法
2. 以3×3 km网格为单元
3. 将网格内像元按"河谷侧/外侧"分类（基于山脊线和坡向）
4. 计算 Valley Greenness Asymmetry Index (VGAI)

### 5.4 坡向定义与"河谷侧 vs 外侧"的判定

传统方法按N/S/E/W固定象限分类坡向，但在川西河谷中，河流走向多变（如金沙江南北向、大渡河近南北向、雅砻江先南北后东西），**固定象限无法准确反映"朝向河谷 vs 背离河谷"**。

**推荐做法**：
1. 基于河流中心线计算每个像元到河流的**方位角 (azimuth to river)**
2. 计算每个像元的**坡向 (aspect)**
3. 若 |aspect − azimuth_to_river| < 90° → 河谷侧（坡面朝向河谷）
4. 若 |aspect − azimuth_to_river| ≥ 90° → 外侧（坡面背离河谷）
5. 这个判定可在山脊线两侧分别进行验证

---

## 六、关键参考文献汇总

### 6.1 坡面不对称性量化

| 文献 | 方法 | 核心指标 | 链接 |
|---|---|---|---|
| Poulos et al. (2012) GRL | 滑动窗口HAI | log₁₀(θ_N / θ_S) | [PDF](http://geomorphology.sese.asu.edu/Papers/Poulos_et_al_2012_GRL.pdf) |
| Smith & Bookhagen (2021) JGR-ES | 椭圆拟合法 | (V_a − V_b)/(V_a + V_b) | [Wiley](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020JF005692) |
| Xie et al. (2025) GRL | 3km网格GAI | NDVI_west / NDVI_east | [Wiley](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024GL113327) |
| Scherler & Schwanghart (2020) ESurf | 分水岭DAI | \|ΔHR\| / (HR_max + HR_min) | [Copernicus](https://esurf.copernicus.org/articles/8/261/2020/) |

### 6.2 山脊线/分水岭提取

| 文献/工具 | 方法 | 工具 | 链接 |
|---|---|---|---|
| Esri Knowledge Base | DEM反转+水文分析 | ArcGIS | [Esri](https://support.esri.com/en-us/knowledge-base/identify-ridgelines-from-a-dem-1462481744099-000011289) |
| Schwanghart & Scherler (2020) ESurf | 分水岭网络自动提取 | TopoToolbox (MATLAB) | [Copernicus](https://esurf.copernicus.org/articles/8/245/2020/) |
| Alvioli et al. (2016) GMD | 坡面单元自动分割 | r.slopeunits (GRASS GIS) | [GMD](https://gmd.copernicus.org/articles/9/3975/2016/) |
| Zhou & Cheng (2018) MATEC | 改进标记分水岭法 | 自编程序 | [DOI](https://doi.org/10.1051/matecconf/201823204070) |

### 6.3 对向坡面植被对比的实证研究

| 文献 | 区域 | 对比类型 | 链接 |
|---|---|---|---|
| Yang, El-Kassaby & Guan (2020) Sci Rep | **岷江干旱河谷** | N vs S坡，实地V形样带 | [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7536199/) |
| Cannon et al. (2016) Landscape Ecol | 美国Appalachian山脉 | 迎风vs背风配对窗口 | [PDF](https://cfri.colostate.edu/wp-content/uploads/sites/22/2018/04/2016-Cannon-et-al.-2016-Landscape-Ecology.pdf) |
| Różycka et al. (2022) IJGI | 综述 | DTM分水岭分析工具综述 | [DOI](https://doi.org/10.3390/ijgi11020116) |
| Jin et al. (2024) Science Bulletin | 全球山区 | 0.15°网格，坡向驱动 | [Link](https://www.nateko.lu.se/hongxiao-jin/publication/5ae41a92-75bb-4ccc-ad68-8c6a61af55e8) |

### 6.4 扩展参考（坡面不对称性驱动机理）

| 文献 | 主题 | 链接 |
|---|---|---|
| Istanbulluoglu et al. (2008) GRL | 生态-地貌坡面不对称 | [Nebraska](https://digitalcommons.unl.edu/cgi/viewcontent.cgi?article=1642&context=natrespapers) |
| Donaldson/Dralle et al. (2024) JGR-Bio | PFS vs EFS坡向驱动ET/NDVI差异 | [DOI: 10.1029/2024JG008054](https://doi.org/10.1029/2024JG008054) |

---

## 七、与前版报告的关系

本报告**替代**前版 `task2_literature_review.md` 中关于"左右岸划分"的核心内容。前版报告中以下部分仍有参考价值：
- 子问题A中的河流中心线提取方法（可辅助确定"河谷方向"）
- 子问题C中的NDVI提取与预处理方法
- 子问题D中关于坡度、海拔等混杂变量控制的讨论

但核心分析范式已从"河流中心线两侧"转变为"**山脊线/分水岭两侧**"。
