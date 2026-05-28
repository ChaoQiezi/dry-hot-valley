# 平均抵消效应分析前置链路整理（2026-05-28）

## BLUF

下一步不要直接进入最终 VAI 解释，应先把三个前置输入固定住：

1. `windward_leeward.tif`：等待当前风场链条跑完，并确认边界异常已消除；
2. `NDVI_2019-2025`：已由 `Src/preprocessing/ndvi_preprocess.py` 完成，可作为下游输入；
3. 河道中心线：已改为总预处理统一生成，不再在 `Minjiang/preprocessing` 内临时提取。

岷江试验的当前入口应是：

```text
总预处理河流中心线
-> Minjiang/unify_dataset.py 裁剪最新 windward/leeward
-> Minjiang 或四河 VAI_spatial_distribution_buffer.py
-> VAI_height_band_trial.py 检验“低高度带信号被全高度平均稀释”
```

## 当前已完成

- DEM：西南 Albers 10m 与 100m 版本已由 `Src/preprocessing/geo/*` 链条补齐。
- ERA5 / Wind Direction：`Src/preprocessing/wind/run_wind_pipeline.py` 正在跑，当前已到 SAGA Wind Effect 100m -> 10m 回升阶段。
- NDVI：`Src/preprocessing/ndvi_preprocess.py` 已完成 2019-2025 年度输出。
- 河流中心线：新增 `Src/preprocessing/river/extract_xinan_rivers.py`，从全国河流数据提取西南河流并按名称拆分。

## 河流中心线新产物

输入：

```text
E:\GeoProjects\dry_hot_valley\river_net\river-1j.shp
E:\GeoProjects\dry_hot_valley\valley_area\Xinan\Xinan.shp
E:\GeoProjects\dry_hot_valley\valley_area\Chuanxi\*_valley.shp
```

输出：

```text
E:\GeoProjects\dry_hot_valley\river_net\xinan\xinan_rivers.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\by_name\岷江.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\by_name\金沙江.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\by_name\雅砻江.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\by_name\大渡河(马柯河、大金川).shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\valley_centerlines\Minjiang_centerline.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\valley_centerlines\Daduhe_centerline.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\valley_centerlines\Jinshajiang_centerline.shp
E:\GeoProjects\dry_hot_valley\river_net\xinan\valley_centerlines\Yalongjiang_centerline.shp
```

验证摘要：

| 河谷 | 中心线要素数 | 裁剪长度 |
|---|---:|---:|
| 大渡河 | 2 | 324.4 km |
| 金沙江 | 26 | 663.7 km |
| 岷江 | 5 | 149.8 km |
| 雅砻江 | 6 | 298.6 km |

说明：金沙江干热河谷 polygon 中有 1 段 `通天河` 与主河段相交，当前纳入 `Jinshajiang_centerline.shp`，后续出图前建议在 GIS 中人工核验是否保留。

## 已调整的分析入口

以下脚本已改为读取总预处理中心线：

```text
Src/valley_analysis/geo_analysis/VAI_spatial_distribution_buffer.py
Src/valley_analysis/geo_analysis/VAI_altitude_gradient_buffer.py
Src/valley_analysis/geo_analysis/VAI_height_band_trial.py
Src/valley_analysis/Minjiang/geo_analysis/VAI_spatial_distribution_buffer.py
Src/valley_analysis/Minjiang/geo_analysis/VAI_altitude_gradient_buffer.py
```

已删除：

```text
Src/valley_analysis/Minjiang/preprocessing/generate_centerline.py
```

原因：河流提取属于总预处理，不应放在单河谷内部。

## 走到岷江平均抵消效应前还需要做什么

1. 等当前 `run_wind_pipeline.py` 完成 Step 3 和 Step 4。
2. 检查 `wind_effect.tif`：
   - `-99999` 不应进入最终有效区；
   - 左边界、上边界不应再连续归为背风坡；
   - wind direction 无效区应在 `windward_leeward.tif` 中为 255。
3. 用 ArcGISPro 环境重跑岷江 `unify_dataset.py`，至少更新：
   - `E:\GeoProjects\dry_hot_valley\valley_analysis\Minjiang\geo_factor\windward_leeward_region.tif`
4. 运行岷江 buffer VAI：

```powershell
D:/Softwares/Anaconda3/envs/geo/python.exe F:\PyProJect\dry_hot_valley\Src\valley_analysis\Minjiang\geo_analysis\VAI_spatial_distribution_buffer.py
```

5. 运行高度分层试验：

```powershell
D:/Softwares/Anaconda3/envs/geo/python.exe F:\PyProJect\dry_hot_valley\Src\valley_analysis\geo_analysis\VAI_height_band_trial.py
```

6. 判断平均抵消效应时优先看：
   - `cap_0_200/300/400/500m` 相对 `full_buffer` 的配对 `|VAI|` 是否增加；
   - 互斥高度带中高处 VAI 是否明显弱化；
   - 是否真的存在正负号混合抵消，还是只是高处弱信号稀释近河强信号。

## 当前判断

- `Src/geo_analysis` 与 `Src/plot` 仍主要是旧川西阶段遗留脚本，不应作为当前主线入口。
- 当前主线应以 `Src/preprocessing/*` 生成统一输入，以 `Src/valley_analysis/geo_analysis/*` 承接四河或岷江试验。
- 岷江内部的 `geo_analysis` 脚本可以保留为快速单河谷试验入口，但不再承担数据提取职责。
