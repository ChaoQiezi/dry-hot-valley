# 2026/5/5 项目进展全貌（供其他 Claude 实例快速了解上下文）

## 1. 研究概要

- 研究主题：川西干旱河谷地区，迎风坡/背风坡植被（NDVI）差异随海拔梯度的变化
- 植被指标：NDVI (Sentinel-2 L2A SR, 10m, 2019-2025)
- 生长季：6-8月
- DEM：GLO-30 (OpenTopography)，重采样至 10m
- 迎风坡/背风坡划分：SAGA-GIS Wind Effect 指数 (>1 迎风, <1 背风)
- 风场数据：ERA5 600hPa u,v，生长季内风速加权聚合
- 核心指数：VAI (Vegetation Asymmetric Index = NDVI_windward - NDVI_leeward) / GAI (NDVI_windward / NDVI_leeward)
- 研究区域：大渡河、岷江、金沙江、雅砻江 四条干旱河谷（边界来自国家青藏高原科学数据中心）
- 目标期刊：顶刊

## 2. 代码目录结构

```
Src/
├── valley_analysis/                     # 河谷专题分析
│   ├── LOG.MD                           # 本文件
│   ├── run_pending_tasks.py             # 线性运行所有待补任务
│   ├── river_net.py                     # 河谷河网提取
│   ├── Minjiang/                        # 岷江（基准河谷，最先跑通）
│   ├── Daduhe/                          # 大渡河
│   ├── Jinshajiang/                     # 金沙江
│   └── Yalongjiang/                     # 雅砻江
│       ├── geo_analysis/                # 核心分析脚本（每个河谷）
│       │   ├── ndvi_altitude_gradient.py           # NDVI 高程梯度统计
│       │   ├── ndvi_spatial_distribution_by_interannual.py  # 年际均值 NDVI 栅格
│       │   ├── VAI_altitude_gradient.py            # VAI 高程梯度统计（先行于 NDVI 梯度）
│       │   ├── VAI_spatial_distribution.py         # VAI 空间分布 (3km 格网)
│       │   ├── GAI_altitude_gradient.py            # GAI 高程梯度统计
│       │   └── GAI_spatial_distribution.py         # GAI 空间分布 (3km 格网)
│       ├── plot/                        # 绘图脚本
│       │   ├── VAI_altitude_gradient.py            # VAI 高程梯度图 (三面板)
│       │   └── GAI_altitude_gradient.py            # GAI 高程梯度图
│       └── preprocessing/               # 预处理
│           └── unify_dataset.py         # 统一栅格分辨率/范围/CRS
└── plot/                                # 跨河谷综合绘图
    └── VAI_combined_altitude_gradient.py # 四河谷 VAI 折线对比图
```

## 3. 各河谷 geo_analysis 脚本运行产出状态

### 3.1 岷江 Minjiang（基准河谷，6 个脚本）

| 脚本 | 产出 | 状态 |
|---|---|---|
| GAI_spatial_distribution.py | 5 tif | 已完成 |
| GAI_altitude_gradient.py | 1 xlsx | 已完成 |
| VAI_spatial_distribution.py | 5 tif | 已完成 |
| VAI_altitude_gradient.py | 1 xlsx | 已完成 |
| ndvi_spatial_distribution_by_interannual.py | 1 tif+ovr | 已完成 |
| **ndvi_altitude_gradient.py** | **8 xlsx** (7逐年+1均值) | **缺6个**：interannual_mean 缺失；逐年仅2019-2020有新版命名(_region)，2021-2025缺失 |

### 3.2 大渡河 Daduhe（6 个脚本）

| 脚本 | 产出 | 状态 |
|---|---|---|
| GAI_spatial_distribution.py | 5 tif | 已完成 |
| GAI_altitude_gradient.py | 1 xlsx | 已完成 |
| VAI_spatial_distribution.py | 5 tif | 已完成 |
| VAI_altitude_gradient.py | 1 xlsx | 已完成 |
| **ndvi_spatial_distribution_by_interannual.py** | **1 tif** | **缺失**（仅有 _region 后缀版） |
| **ndvi_altitude_gradient.py** | **8 xlsx** | **缺1个**：逐年齐全，interannual_mean 缺失 |

### 3.3 金沙江 Jinshajiang（4 个脚本，无 GAI）

| 脚本 | 产出 | 状态 |
|---|---|---|
| VAI_spatial_distribution.py | 5 tif | 已完成 |
| VAI_altitude_gradient.py | 1 xlsx | 已完成 |
| ndvi_spatial_distribution_by_interannual.py | 1 tif | 已完成 |
| **ndvi_altitude_gradient.py** | **8 xlsx** | **缺5个**：仅2019-2021逐年齐全，2022-2025 + interannual_mean 缺失 |

### 3.4 雅砻江 Yalongjiang（4 个脚本，无 GAI）

| 脚本 | 产出 | 状态 |
|---|---|---|
| VAI_spatial_distribution.py | 5 tif | 已完成 |
| VAI_altitude_gradient.py | 1 xlsx | 已完成 |
| ndvi_spatial_distribution_by_interannual.py | 1 tif | 已完成 |
| **ndvi_altitude_gradient.py** | **8 xlsx** | **缺5个**：仅2019-2021逐年齐全，2022-2025 + interannual_mean 缺失 |

## 4. 汇总：所有待补任务

**共同缺失（四个河谷）**：ndvi_altitude_gradient.py 的 interannual_mean — 各缺 1 个 xlsx

**个别缺失**：
- 岷江：2021-2025 逐年 `_region` 版 — 5 个 xlsx（旧版无 `_region` 的有全的）
- 金沙江：2022-2025 逐年 — 4 个 xlsx
- 雅砻江：2022-2025 逐年 — 4 个 xlsx
- 大渡河：ndvi_spatial_distribution_by_interannual.py — 1 个 tif

已创建 `run_pending_tasks.py` 按依赖顺序线性执行这些任务。

## 5. 关键数据路径

所有输入/输出数据在 **E 盘**，代码在 **F 盘**：
- 基础路径：`E:\GeoProjects\dry_hot_valley\{ValleyName}\`
- NDVI：`{base}\NDVI\Yearly\NDVI_{year}_region.tif`
- NDVI 年际均值：`{base}\NDVI\Interannual\NDVI_interannual_mean.tif`
- DEM：`{base}\geo_factor\elevation_10m_projected_region.tif`（岷江无 `_region` 后缀）
- 迎风/背风坡：`{base}\geo_factor\windward_leeward_region.tif`（岷江无 `_region` 后缀）
- 结果表格：`{base}\Result\Table\`
- 结果图表：`{base}\Result\Chart\`

## 6. 代码规范

- 所有输入/输出路径在文件顶部 Configuration 区域声明
- 使用 Dask + rioxarray 进行延迟计算
- ndvi_altitude_gradient.py / VAI_altitude_gradient.py 带有 checkpoint 断点续跑机制
- Python 解释器：`D:/Softwares/Anaconda3/envs/geo/python.exe`
- 若涉及 ArcPy 模块：`D:/Softwares/anaconda3/envs/ArcGISPro/python.exe`

## 7. 已完成的绘图

- 各河谷 VAI 高程梯度三面板图（河谷 plot 目录）
- **四河谷 VAI 合并对比图**：`Src/plot/VAI_combined_altitude_gradient.py`，单面板仅均值折线无标准差阴影，输出到 `E:\GeoProjects\dry_hot_valley\Result\Chart\altitude\`

## 8. 分析框架简述

三类核心分析，均从三个维度（combined / valley_only / wind_only）进行：
1. **空间分布分析**：3km×3km 格网，GAI/VAI 及 p-value、迎风坡/背风坡 NDVI、DEM
2. **高程梯度分析**：50m 海拔 bin，迎风坡和背风坡 NDVI 统计值（mean/std/count），VAI
3. **年际变化分析**：逐年 NDVI，区分迎风坡/背风坡

当前 ndvi_altitude_gradient.py 只做了 combined 模式（因为其余两个模式耗时长）。
