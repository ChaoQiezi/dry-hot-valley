# 川西干热河谷左右岸NDVI差异分析——方法论文献调研

## 子问题A：河谷左右岸划分的技术方法

### A1. "左岸"与"右岸"的标准定义

在水文学与地貌学中，"左岸"（left bank）与"右岸"（right bank）的定义采用**面朝下游方向**的观察者视角：观察者面朝水流方向（下游），其左手侧为左岸，右手侧为右岸（Wikipedia: Bank (geography)）。这一定义在全球科学文献和工程实践中是通用惯例，不随观测者所站位置而改变。

在GIS操作中，确定河流流向（即下游方向）是左右岸划分的前提。对于DEM数据，可通过水文分析中的流向（flow direction）计算自动获取河流流向；对于已知河流polygon，可结合DEM高程信息判定上下游关系。

### A2. 河流中心线提取方法

已有河谷面要素polygon和DEM的情况下，将河谷一分为二的关键步骤是提取河流中心线（river centerline），然后用中心线将polygon分割。中心线提取主要有两大技术路线：

#### 路线一：基于DEM的水文分析提取河网

经典方法为D8流向算法（O'Callaghan & Mark, 1984），步骤为：DEM填洼 → 计算流向 → 计算汇流累积量 → 设定阈值提取河网。该方法在高山峡谷地形中效果较好，因为地形起伏明显，河流位置容易通过汇流累积量识别。提取的栅格河网可转为矢量线要素，即为河流中心线。

对于川西干热河谷这类深切河谷，DEM河网提取通常可靠，但需注意：阈值选择会影响河网密度；在宽河道区域，栅格河网可能偏移实际河流中心。可用"stream burning"技术将已知河道位置烧入DEM以提高精度。

**关键参考文献：**
- O'Callaghan, J.F. & Mark, D.M. (1984). The extraction of drainage networks from digital elevation data. *Computer Vision, Graphics, and Image Processing*, 28(3), 323–344.
- Jenson, S.K. & Domingue, J.O. (1988). Extracting topographic structure from digital elevation data for geographic information system analysis. *Photogrammetric Engineering and Remote Sensing*, 54(11), 1593–1600.

#### 路线二：基于河谷Polygon的中轴线（Medial Axis / Voronoi Skeleton）提取

当已有河谷polygon边界时，可直接利用计算几何方法提取polygon的中轴线（medial axis），即polygon内所有与边界距离最大的点的轨迹。中轴线本质上是polygon边界的Voronoi图的子集（Blum, 1967）。

主要算法包括：
- **中轴变换（Medial Axis Transform, MAT）**：计算polygon内所有最大内切圆圆心的轨迹，形成树状骨架线。适用于任意形状polygon，但对边界噪声敏感，需后处理去除毛刺（spurious branches）。
- **Voronoi骨架（Voronoi Skeleton）**：对polygon边界采样后构建Voronoi图，提取位于polygon内部的Voronoi边作为骨架。GRASS GIS的`v.voronoi -s`命令可直接提取面要素的骨架线或中心线。
- **Straight Skeleton**：通过polygon边界向内收缩生成的骨架，无曲线段，全为直线段，适合规则形状。
- **Delaunay三角剖分法**：对polygon进行约束Delaunay三角剖分，提取三角形中心连线作为骨架。

对于河谷polygon，推荐MAT或Voronoi骨架法。提取的中心线即为河谷的纵向轴线，可作为左右岸分割线。

**GIS实现：** 在ArcGIS中可用Polygon to Centerline工具（需ArcGIS Pro 3.0+）；在QGIS中可用Sketleton/Sketeton medial axis插件；在Python中可用`shapely`库的`centerline`扩展或`scipy.spatial.Voronoi`。

**关键参考文献：**
- Blum, H. (1967). A transformation for extracting new descriptors of shape. *Models for the Perception of Speech and Visual Form*, 362–380.
- Haunert, J.H. & Sester, M. (2008). Area collapse and road centerlines based on straight skeletons. *GeoInformatica*, 12(2), 169–191. DOI: 10.1007/s10707-007-0028-x
- Gold, C. & Snoeyink, J. (2001). A one-step crust and skeleton extraction algorithm. *Algorithmica*, 30, 144–163.

### A3. 用中心线分割Polygon为左右岸

获得中心线后，使用GIS的Split Polygon by Polyline功能将河谷polygon一分为二。然后结合河流流向，按左右岸定义为两半分别赋予"左岸"和"右岸"标签。

**具体步骤：**
1. 从DEM提取流向确定河流下游方向
2. 提取河谷polygon中心线
3. 用中心线分割polygon为两半
4. 根据流向与中心线左右关系，标记左岸（left bank）和右岸（right bank）polygon
5. 分别裁剪NDVI栅格数据到两个子polygon进行后续分析

---

## 子问题B：两岸像元级对比的分析范式

### B1. 对向坡（Opposing Slopes）NDVI不对称性研究——最成熟的文献体系

山坡不对称性（hillslope asymmetry）是地貌学和生态水文学中研究最为成熟的方向之一。核心发现是：在北半球中纬度半干旱地区，北坡（阴坡/polar-facing slope, PFS）通常植被覆盖度更高、NDVI更大，而南坡（阳坡/equatorial-facing slope, EFS）更干燥、植被更稀疏。这种差异由太阳辐射不对称驱动的水热条件差异所致。

#### 关键系列研究：

**Kumari, Saco, Srivastava等人的全球山坡不对称性研究：**

Kumari et al. (2020)在GRL发表的研究对全球60个流域18年MODIS NDVI数据进行了分析，发现70%的站点在季节尺度上表现出植被绿度的"季节性反转"——虽然半干旱生态系统中通常阴坡更绿，但在湿润冬季，阳坡可因太阳辐射优势而变得更绿。这一发现挑战了"阴坡总是更绿"的传统认识。

Srivastava et al. (2021)在*Hydrological Processes*中研究了半干旱生态系统中景观形态对土壤水分变异性的控制作用，发现坡向是控制土壤水分空间格局的关键因子。

Srivastava et al. (2022)在*Earth Surface Processes and Landforms (ESPL)*中进一步用CHILD景观演化模型耦合植被动态组件，探索了地形降水对地貌-植被共演化的影响，发现迎风侧与背风侧的植被-地貌不对称性受降水分布强烈调控。

**关键文献：**
- Kumari, N., Saco, P.M., Rodriguez, J.F., Johnstone, S.A., Srivastava, A., Chun, K.P., & Yetemen, O. (2020). The grass is not always greener on the other side: Seasonal reversal of vegetation greenness in aspect-driven semiarid ecosystems. *Geophysical Research Letters*, 47, e2020GL088918. DOI: 10.1029/2020GL088918
- Srivastava, A., Saco, P.M., Rodriguez, J.F., Kumari, N., Chun, K.P., & Yetemen, O. (2021). The role of landscape morphology on soil moisture variability in semi-arid ecosystems. *Hydrological Processes*, 35(1), e13990. DOI: 10.1002/hyp.13990
- Srivastava, A., Yetemen, O., Saco, P.M., Rodriguez, J.F., Kumari, N., & Chun, K.P. (2022). Influence of orographic precipitation on coevolving landforms and vegetation in semi-arid ecosystems. *Earth Surface Processes and Landforms*, 47, 2458–2476. DOI: 10.1002/esp.5387

**Yetemen et al. 太阳辐射驱动山坡不对称的景观演化模型：**

Yetemen et al. (2015)使用CHILD景观演化模型，耦合水-沉积物-植被连续性方程，在全球不同纬度条件下模拟了山坡不对称性的形成。研究发现太阳辐射的空间分布单独即可解释观测到的坡向相关植被差异和山谷不对称性。HAI (Hillslope Asymmetry Index)定义为对向坡中值坡度之比的对数值（log₁₀），在北半球表现为正值（北坡更陡），在南半球表现为负值。

- Yetemen, O., Istanbulluoglu, E., & Duvall, A.R. (2015). Solar radiation as a global driver of hillslope asymmetry: Insights from an ecogeomorphic landscape evolution model. *Water Resources Research*, 51, 9843–9861. DOI: 10.1002/2015WR017103

**川西干热河谷的直接相关研究：**

Yu et al. (2020)在*Scientific Reports*发表了川西岷江上游干热河谷坡向对植被的影响研究，发现北坡植被生物量、盖度、高度和物种多样性显著高于南坡，这与土壤养分的坡向差异一致。这是本研究区域最直接的参考文献之一。

- Yu, X. et al. (2020). The effect of slope aspect on vegetation attributes in a mountainous dry valley, Southwest China. *Scientific Reports*, 10, 16465. DOI: 10.1038/s41598-020-73496-0

### B2. 像元匹配/配对的具体算法

#### 方法一：横断面法（Cross-section Transect Method）

这是河谷两岸对比最直观的空间配对方法。核心思路：

1. 沿河流中心线等间隔（如每100m或500m）生成采样点
2. 在每个采样点处，生成垂直于河流中心线的横断面线（transect）
3. 在每条横断面上，中心线左侧和右侧等距离的像元自动配对
4. 可在横断面上按距离河流中心线的距离分层（如0-500m, 500-1000m, 1000-2000m等），进行分层配对

**优点：** 空间对应关系清晰，物理含义明确；可同时获取距河流的距离信息。
**参数选择：** 横断面间距需根据河谷宽度和像元分辨率确定；横断面长度需覆盖整个河谷polygon范围。

**GIS实现：** ArcGIS的Generate Transects Along Lines工具；Python中可用`shapely`的`parallel_offset`和`interpolate`方法自动生成横断面。

该方法在河流地貌学中已有广泛应用（如河道宽度提取、河岸带分析），但在两岸植被对比的文献中尚未见到标准化的大规模应用范式。横断面分析在地形剖面分析中是标准方法，GIS教科书中有详细的技术实现描述。

#### 方法二：倾向分数匹配（Propensity Score Matching, PSM）

PSM是统计因果推断中经典的准实验方法，可用于在观测性研究中控制混杂变量。在两岸对比场景中的应用思路：

1. 将"处于左岸/右岸"视为"处理"变量（treatment）
2. 将海拔、坡度、坡向、到河流距离等地形变量作为协变量
3. 估计每个像元的倾向分数（基于logistic回归等方法）
4. 在左右岸之间进行最近邻匹配，使匹配像元对在地形条件上尽可能相似
5. 对匹配后的像元对进行NDVI差异分析

PSM在生态学和遥感领域已有应用先例。例如，USGS的Arkle et al.在大型火灾恢复研究中使用PSM来控制植被恢复处理的非随机分配偏差。在国家公园保护效果评估中，PSM被用于将公园内外地形条件相似的区域配对后比较生态系统服务差异。

Papadogeorgou et al. (2019)在*Biostatistics*提出了距离调整倾向分数匹配（DAPSm），将空间邻近性信息纳入倾向分数匹配，可同时调节观测到的和空间未观测的混杂。

**关键文献：**
- Arkle, R.S. et al. Propensity score matching mitigates risk of faulty inferences in observational studies of effectiveness of restoration trials. *USGS Publications*.
- Papadogeorgou, G., Choirat, C., & Zigler, C.M. (2019). Adjusting for unmeasured spatial confounding with distance adjusted propensity score matching. *Biostatistics*, 20(2), 256–272. DOI: 10.1093/biostatistics/kxx074
- 用PSM评估普达措国家公园保护效果的研究也有参考价值：该研究将公园内外区域按地形变量（含海拔、坡度等）进行倾向分数匹配，再比较生态系统服务差异（发表于*Ecological Indicators*, 2023）。

#### 方法三：分层配对（Stratified Matching）

按海拔带 × 坡度级进行分层后，在同一层内对左右岸像元进行随机或系统配对。

1. 将海拔按等间隔（如100m一层）划分为海拔带
2. 将坡度按级别（如0-10°, 10-20°, 20-30°, >30°）分层
3. 在每个"海拔带×坡度级"的组合层内，分别提取左岸和右岸像元
4. 在同层内进行随机配对或全量比较（所有左岸像元 vs 所有右岸像元）

**优点：** 实现简单，物理意义直观，有效控制了海拔和坡度两个最重要的混杂因子。
**参数选择：** 分层间隔需权衡——太细则每层样本量不足，太粗则层内异质性大。

这种方法在生态学野外调查中是常规操作（分层随机抽样），但在遥感像元级应用中，需注意空间自相关问题。

### B3. 河谷两岸直接对比的文献（Valley-side Comparison）

直接以河流为对称轴对比两岸植被的文献相对较少，但以下研究提供了重要参考：

García-Gamero et al. (2021)在*Journal of Hydrology*发表了地中海丘陵流域中土壤水分和植被动态不对称性的研究。研究在一个牧场流域中的对向坡部署了32个土壤水分传感器，同时利用Sentinel-2 NDVI时间序列分析对向坡植被动态。发现北坡和南坡NDVI呈现完全相反的季节趋势，北坡最小值出现在冬季末，南坡最小值出现在夏季。土壤水分与NDVI在南坡有很高相关性（R=0.81），在北坡则需要考虑地下水的贡献。

- García-Gamero, V., Peña, A., Laguna, A.M., Giráldez, J.V., & Vanwalleghem, T. (2021). Factors controlling the asymmetry of soil moisture and vegetation dynamics in a hilly Mediterranean catchment. *Journal of Hydrology*, 598, 126207. DOI: 10.1016/j.jhydrol.2021.126207

### B4. 推荐的综合分析框架

针对川西干热河谷的研究情景，建议采用**横断面法为主、分层配对为辅**的策略：

1. **第一步**：提取河谷中心线，划分左右岸
2. **第二步**：沿中心线等间隔生成垂直横断面，实现像元级空间配对
3. **第三步**：在横断面配对的基础上，按海拔带分层统计，分析NDVI差异随海拔的变化
4. **第四步**：如需更严格的因果推断，可补充PSM方法，以海拔、坡度、坡向等作为协变量进行配对
5. **第五步**：使用配对统计检验（见子问题C）评估差异的统计显著性

---

## 子问题C：地形不对称性的定量指标与统计方法

### C1. Hillslope Asymmetry Index (HAI)

HAI由Poulos et al. (2012)在GRL中首次提出并系统应用于大尺度研究。其定义为：

**HA_{N-S} = log₁₀(S_N / S_S)**

其中 S_N 和 S_S 分别为某区域内北朝坡和南朝坡的**中值坡度**。

- HA > 0：北坡更陡（北半球中低纬度典型）
- HA < 0：南坡更陡
- HA ≈ 0：两坡对称

**计算方法：** 使用滑动窗口（Poulos等人使用5km × 5km）在DEM上逐像元计算。每个窗口内按坡向分为北朝（315°-360°和0°-45°）和南朝（135°-225°）两组，分别计算中值坡度后取比值的对数。

Yetemen et al. (2015)沿用了这一定义，在景观演化模型中验证了HAI与纬度的全球性关系。

**关键文献：**
- Poulos, M.J., Pierce, J.L., Flores, A.N., & Benner, S.G. (2012). Hillslope asymmetry maps reveal widespread, multi-scale organization. *Geophysical Research Letters*, 39, L06406. DOI: 10.1029/2012GL051283

### C2. Topographic Asymmetry (TA) — Smith & Bookhagen (2021)

Smith & Bookhagen (2021)在*JGR: Earth Surface*中提出了改进的地形不对称性指标。他们对全球0.25°格网内DEM数据，拟合坡度-坡向的椭圆分布，用椭圆的长短轴差异量化不对称方向和幅度。同时定义了归一化辐照不对称指标，将辐照度、植被盖度、积雪面积等多环境变量的不对称性纳入统一分析框架。

- Smith, T. & Bookhagen, B. (2021). Climatic and biotic controls on topographic asymmetry at the global scale. *Journal of Geophysical Research: Earth Surface*, 126, e2020JF005692. DOI: 10.1029/2020JF005692

### C3. Pelletier et al. (2018)综述——Critical Zone坡向控制

Pelletier et al. (2018)在*ESPL*发表了坡向控制Critical Zone过程的综述性论文，系统回顾了不同纬度和海拔下山坡不对称性的表现及其机理。他们提出了水分受限（water-limited）和温度受限（temperature-limited）两个端元的概念模型，用干旱指数、纬度、平均温度和坡度四个简约参数拟合全球HAI空间格局。

- Pelletier, J.D., Barron-Gafford, G.A., Gutiérrez-Jurado, H., et al. (2018). Which way do you lean? Using slope aspect variations to understand Critical Zone processes and feedbacks. *Earth Surface Processes and Landforms*, 43, 1133–1154. DOI: 10.1002/esp.4306

### C4. 统计检验方法

在两岸像元配对完成后，常用的统计检验包括：

1. **配对t检验（Paired t-test）**：当配对样本近似正态分布时使用。计算每对配对像元的NDVI差值，检验差值均值是否显著异于0。适用于横断面法的配对数据。

2. **Wilcoxon符号秩检验（Wilcoxon Signed-Rank Test）**：非参数检验，适用于NDVI差值不满足正态假设的情况。在生态学和地貌学研究中被广泛采用，如García-Gamero et al. (2021)在坡向水文研究中使用。

3. **Mann-Whitney U检验**：用于非配对的两组独立样本比较。当左右岸样本量不等或未严格配对时使用。

4. **效应量指标**：
   - Cohen's d：标准化均值差异
   - NDVI差值的中位数和四分位距
   - 不对称比率：NDVI_left / NDVI_right 或 (NDVI_left - NDVI_right) / (NDVI_left + NDVI_right)

5. **空间自相关校正**：由于相邻像元存在空间自相关，需用Moran's I检验残差的空间自相关性。若显著，可采用空间区组bootstrap或有效自由度校正。

### C5. 针对本研究的推荐指标体系

1. **ΔNDVI = NDVI_左岸 - NDVI_右岸**：每对配对像元的绝对差值
2. **按海拔带分层的ΔNDVI均值和标准差**：揭示不对称性随海拔的梯度变化
3. **改进的HAI-NDVI指标**：参考Poulos et al.的HAI定义，计算 log₁₀(Median_NDVI_左岸 / Median_NDVI_右岸)，用于整体量化每个河谷的NDVI不对称性方向和幅度
4. **配对Wilcoxon秩检验的p值和效应量**：分层、分季节报告
5. **空间可视化**：将ΔNDVI映射到横断面位置上，生成沿河谷的不对称性空间分布图

---

## 核心文献汇总

### 子问题A：河谷划分与中心线提取

| 作者 | 年份 | 期刊 | 方法亮点 |
|------|------|------|----------|
| O'Callaghan & Mark | 1984 | *Computer Vision, Graphics, and Image Processing* | D8流向算法，DEM河网提取的奠基性工作 |
| Blum, H. | 1967 | *Models for Perception of Speech and Visual Form* | 提出中轴变换（MAT）概念 |
| Haunert & Sester | 2008 | *GeoInformatica* | 基于直线骨架的道路/面要素中心线提取，DOI: 10.1007/s10707-007-0028-x |
| Gold & Snoeyink | 2001 | *Algorithmica* | 一步法Voronoi边界和骨架提取 |
| Thapa, P. | 2024 | *SSRN* | 基于MAT的河流中心线和宽度提取实践 |

### 子问题B：对向坡/两岸对比与像元配对

| 作者 | 年份 | 期刊 | 方法亮点 |
|------|------|------|----------|
| Kumari, Saco, Rodriguez, Johnstone, Srivastava, Chun, Yetemen | 2020 | *Geophysical Research Letters* | 全球60个流域NDVI季节性反转，PFS vs EFS分析范式。DOI: 10.1029/2020GL088918 |
| Yetemen, Istanbulluoglu, Duvall | 2015 | *Water Resources Research* | CHILD LEM耦合植被动态，太阳辐射驱动山坡不对称的模拟。DOI: 10.1002/2015WR017103 |
| Srivastava, Saco, Rodriguez, Kumari, Chun, Yetemen | 2021 | *Hydrological Processes* | 景观形态对土壤水分变异性的控制。DOI: 10.1002/hyp.13990 |
| Srivastava, Yetemen, Saco, Rodriguez, Kumari, Chun | 2022 | *Earth Surface Processes and Landforms* | 地形降水对地貌-植被共演化的影响。DOI: 10.1002/esp.5387 |
| García-Gamero, Peña, Laguna, Giráldez, Vanwalleghem | 2021 | *Journal of Hydrology* | 地中海流域对向坡土壤水分+Sentinel-2 NDVI时间序列联合分析。DOI: 10.1016/j.jhydrol.2021.126207 |
| Yu et al. | 2020 | *Scientific Reports* | 川西岷江干热河谷坡向对植被属性影响，直接相关研究区。DOI: 10.1038/s41598-020-73496-0 |
| Seyfried et al. | 2021 | *Vadose Zone Journal* | 16年MODIS NDVI对比北坡vs南坡的季节动态和土壤气候差异。DOI: 10.1002/vzj2.20158 |
| Papadogeorgou, Choirat, Zigler | 2019 | *Biostatistics* | DAPSm空间倾向分数匹配方法。DOI: 10.1093/biostatistics/kxx074 |
| Arkle et al. | — | *USGS Publications* | PSM在大型景观恢复处理效果评估中的应用范式 |

### 子问题C：不对称性指标与统计检验

| 作者 | 年份 | 期刊 | 方法亮点 |
|------|------|------|----------|
| Poulos, Pierce, Flores, Benner | 2012 | *Geophysical Research Letters* | 提出HAI指标及滑动窗口制图方法，全球首个大尺度山坡不对称性制图。DOI: 10.1029/2012GL051283 |
| Pelletier, Barron-Gafford, Gutiérrez-Jurado et al. | 2018 | *Earth Surface Processes and Landforms* | Critical Zone坡向控制综述，水分/温度受限概念模型，经验HAI模型。DOI: 10.1002/esp.4306 |
| Smith & Bookhagen | 2021 | *JGR: Earth Surface* | 全球地形不对称性分析，辐照-植被-地形不对称联合分析框架。DOI: 10.1029/2020JF005692 |
| Zwieback | 2021 | *Geophysical Research Letters* | 北极地区地形不对称性与冻融过程的关系。DOI: 10.1029/2021GL094895 |
| Burnett, Meyer, McFadden | 2008 | *JGR: Earth Surface* | 坡向微气候对坡面过程的影响，野外实测。DOI: 10.1029/2007JF000789 |
| Istanbulluoglu, Yetemen, Vivoni, Gutiérrez-Jurado, Bras | 2008 | *Geophysical Research Letters* | 生态地貌学视角的山坡不对称性分析。DOI: 10.1029/2008GL034477 |
| Singh, S. | 2018 | *Tropical Ecology* | 坡向对山地生态系统植被和土壤属性影响的综述，59, 417–430 |

---

## 方法论建议总结

### 推荐技术路线

```
DEM + 河谷Polygon
      │
      ├── Step 1: 提取河流中心线
      │     ├── 方案A: DEM水文分析 (D8 → 汇流累积量 → 河网)
      │     └── 方案B: Polygon中轴线 (MAT/Voronoi Skeleton)
      │            → 推荐两者结合互验
      │
      ├── Step 2: 中心线分割Polygon为左右岸
      │     └── 结合流向确定左右岸标签
      │
      ├── Step 3: 像元配对
      │     ├── 主方法: 横断面法 (等间隔垂直横断面)
      │     ├── 辅助: 分层配对 (海拔带 × 坡度级)
      │     └── 可选: PSM (以地形变量为协变量)
      │
      ├── Step 4: NDVI差异分析
      │     ├── ΔNDVI统计 (均值、中位数、分布)
      │     ├── 配对Wilcoxon秩检验
      │     ├── HAI-NDVI不对称指标
      │     └── 按海拔带/季节分层分析
      │
      └── Step 5: 可视化与解释
            ├── 沿河谷纵向不对称性空间分布图
            ├── 横断面NDVI剖面对比图
            └── 海拔-NDVI差异梯度图
```

### 关键参数选择依据

- **横断面间距**：建议为像元分辨率的5-10倍（如30m DEM用150-300m间距）
- **海拔分层间隔**：100-200m为宜（参考Yu et al. 2020的干热河谷研究）
- **HAI滑动窗口**：Poulos et al.使用5km×5km，可根据河谷宽度调整至1-3km
- **统计检验**：优先使用Wilcoxon符号秩检验（非参数、对NDVI分布假设宽松）
