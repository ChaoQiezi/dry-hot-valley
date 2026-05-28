# @Author  : ChaoQiezi
# @Time    : 2026/5/28
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: extract_xinan_rivers.py

"""
从全国河流数据中提取西南地区河流, 并按河道名称输出单独 shapefile。

输出分两类:
1. xinan_rivers.shp: 西南边界内的全部河流;
2. by_name/*.shp: 按全国河流数据中的“名称”字段拆分;
3. valley_centerlines/*_centerline.shp: 裁剪到四条干热河谷 polygon 内的分析中心线。

后续 valley_analysis 只读取本脚本生成的中心线产物, 不再在单个河谷目录内
临时从河网中相交提取。
"""

from __future__ import annotations

import os
from pathlib import Path
import re

import geopandas as gpd
import pandas as pd

# 0. Configuration
NATIONAL_RIVER_PATH = Path(r"E:\GeoProjects\dry_hot_valley\river_net\river-1j.shp")
XINAN_BOUNDARY_PATH = Path(r"E:\GeoProjects\dry_hot_valley\valley_area\Xinan\Xinan.shp")
VALLEY_AREA_DIR = Path(r"E:\GeoProjects\dry_hot_valley\valley_area\Chuanxi")

OUT_ROOT = Path(r"E:\GeoProjects\dry_hot_valley\river_net\xinan")
OUT_XINAN_RIVERS = OUT_ROOT / "xinan_rivers.shp"
OUT_BY_NAME_DIR = OUT_ROOT / "by_name"
OUT_VALLEY_CENTERLINE_DIR = OUT_ROOT / "valley_centerlines"
OUT_INDEX = OUT_ROOT / "xinan_river_index.csv"
OUT_VALLEY_INDEX = OUT_ROOT / "valley_centerline_index.csv"

# 全国河流数据中“名称”字段对应的主河道名称。
# 金沙江干热河谷 polygon 中有一段通天河, 暂纳入金沙江中心线, 避免上游河段被截断。
VALLEY_CENTERLINES = [
    {
        "slug": "Daduhe",
        "valley_name": "大渡河干旱河谷",
        "river_names": ["大渡河(马柯河、大金川)"],
        "valley_path": VALLEY_AREA_DIR / "Daduhe_valley.shp",
    },
    {
        "slug": "Jinshajiang",
        "valley_name": "金沙江干旱河谷",
        "river_names": ["金沙江", "通天河"],
        "valley_path": VALLEY_AREA_DIR / "Jinshajiang_valley.shp",
    },
    {
        "slug": "Minjiang",
        "valley_name": "岷江干旱河谷",
        "river_names": ["岷江"],
        "valley_path": VALLEY_AREA_DIR / "Minjiang_valley.shp",
    },
    {
        "slug": "Yalongjiang",
        "valley_name": "雅砻江干旱河谷",
        "river_names": ["雅砻江"],
        "valley_path": VALLEY_AREA_DIR / "Yalongjiang_valley.shp",
    },
]

ENCODING = "UTF-8"
FORCE_RERUN = True


# 1. Helpers
def remove_shapefile(path: Path) -> None:
    """删除指定路径的 shapefile 及其附属文件"""
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".shp.xml"):
        sidecar = path.with_suffix(ext)
        if sidecar.exists():
            sidecar.unlink()


def safe_filename(name: str) -> str:
    """将名称字符串转换为安全的文件名，替换非法字符"""
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(name)).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "unnamed"


def read_vector(path: Path) -> gpd.GeoDataFrame:
    """读取矢量文件，文件不存在时抛出 FileNotFoundError"""
    if not path.exists():
        raise FileNotFoundError(path)
    return gpd.read_file(path)


def find_river_name_column(rivers: gpd.GeoDataFrame) -> str:
    """从字段列表中自动查找包含河流名称的文本字段，优先返回"名称"字段"""
    if "名称" in rivers.columns:
        return "名称"
    text_cols = [
        col for col in rivers.columns
        if col != rivers.geometry.name and pd.api.types.is_object_dtype(rivers[col])
    ]
    if not text_cols:
        raise RuntimeError("No text column found for river names.")
    return text_cols[0]


def normalize_output_columns(
    gdf: gpd.GeoDataFrame,
    name_col: str,
    output_name: str | None = None,
) -> gpd.GeoDataFrame:
    """统一输出字段结构为 RiverName/Name/TARGET_FID/SrcID/SrcGB/SrcLevel/LenM，并计算长度"""
    out = gdf.copy()
    out["RiverName"] = out[name_col].astype(str)
    out["Name"] = output_name if output_name is not None else out["RiverName"]
    out["TARGET_FID"] = out.get("RIVER1_ID", out.index).astype("int64")
    out["SrcID"] = out.get("RIVER1_ID", out.index).astype("int64")
    out["SrcGB"] = out.get("GB", pd.Series([pd.NA] * len(out), index=out.index))
    out["SrcLevel"] = out.get("分级", pd.Series([pd.NA] * len(out), index=out.index))
    out["LenM"] = out.geometry.length

    keep = ["Name", "RiverName", "TARGET_FID", "SrcID", "SrcGB", "SrcLevel", "LenM", "geometry"]
    return out[keep].copy()


def write_shapefile(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """写入 shapefile 并附带 UTF-8 编码的 .cpg 文件，已存在且非强制重跑时跳过"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if FORCE_RERUN:
        remove_shapefile(path)
    if path.exists():
        print(f"  exists, skip: {path}")
        return
    gdf.to_file(path, driver="ESRI Shapefile", encoding=ENCODING)
    path.with_suffix(".cpg").write_text(ENCODING, encoding="ascii")
    print(f"  -> {path} ({len(gdf)} features)")


def length_summary(gdf: gpd.GeoDataFrame, name_col: str) -> pd.DataFrame:
    """按河流名称分组统计河段数量和总长度，按长度降序排列"""
    work = gdf.copy()
    work["_length_m"] = work.geometry.length
    summary = (
        work.groupby(name_col, dropna=False)["_length_m"]
        .agg(["count", "sum"])
        .reset_index()
        .rename(columns={name_col: "river_name", "count": "segment_count", "sum": "length_m"})
        .sort_values("length_m", ascending=False)
    )
    return summary


# 2. Main steps
def extract_xinan_rivers(rivers: gpd.GeoDataFrame, xinan: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, str]:
    """用西南地区边界裁剪全国河流数据，自动检测名称字段并返回裁剪结果"""
    name_col = find_river_name_column(rivers)
    xinan_in_river_crs = xinan.to_crs(rivers.crs)
    clipped = gpd.clip(rivers, xinan_in_river_crs, keep_geom_type=True)
    clipped = clipped[~clipped.geometry.is_empty].copy()
    if clipped.empty:
        raise RuntimeError("No rivers intersect the Xinan boundary.")
    return clipped, name_col


def write_by_name_outputs(xinan_rivers: gpd.GeoDataFrame, name_col: str) -> pd.DataFrame:
    """将西南河流按名称字段拆分输出为单独 shapefile，同时输出西南全量河流和索引 CSV"""
    by_name = normalize_output_columns(xinan_rivers, name_col)
    write_shapefile(by_name, OUT_XINAN_RIVERS)

    summary = length_summary(xinan_rivers, name_col)
    OUT_BY_NAME_DIR.mkdir(parents=True, exist_ok=True)
    for river_name, group in xinan_rivers.groupby(name_col, dropna=False):
        river_name = str(river_name)
        out_path = OUT_BY_NAME_DIR / f"{safe_filename(river_name)}.shp"
        out_gdf = normalize_output_columns(group, name_col)
        write_shapefile(out_gdf, out_path)

    summary.to_csv(OUT_INDEX, index=False, encoding="utf-8-sig", float_format="%.1f")
    print(f"  -> {OUT_INDEX}")
    return summary


def write_valley_centerlines(xinan_rivers: gpd.GeoDataFrame, name_col: str) -> pd.DataFrame:
    """提取四条干热河谷的河道中心线并输出 shapefile 和索引 CSV

    按 VALLEY_CENTERLINES 配置逐河谷裁剪主河道，输出中心线 shapefile
    并生成包含河谷、河道名称、段数和长度的汇总索引。

    参数说明:
        xinan_rivers: 西南地区河流 GeoDataFrame
        name_col: 河流名称所在字段名
    """
    rows = []
    for cfg in VALLEY_CENTERLINES:
        valley = read_vector(cfg["valley_path"]).to_crs(xinan_rivers.crs)
        selected = xinan_rivers[xinan_rivers[name_col].isin(cfg["river_names"])].copy()
        if selected.empty:
            raise RuntimeError(f"No river records matched {cfg['river_names']!r}.")

        clipped = gpd.clip(selected, valley, keep_geom_type=True)
        clipped = clipped[~clipped.geometry.is_empty].copy()
        if clipped.empty:
            raise RuntimeError(f"No selected river intersects {cfg['valley_name']}.")

        out_gdf = normalize_output_columns(
            clipped,
            name_col=name_col,
            output_name=cfg["valley_name"],
        )
        out_path = OUT_VALLEY_CENTERLINE_DIR / f"{cfg['slug']}_centerline.shp"
        write_shapefile(out_gdf, out_path)

        by_river = length_summary(clipped, name_col)
        for _, row in by_river.iterrows():
            rows.append({
                "slug": cfg["slug"],
                "valley_name": cfg["valley_name"],
                "river_name": row["river_name"],
                "segment_count": int(row["segment_count"]),
                "length_m": float(row["length_m"]),
                "output": str(out_path),
            })

    summary = pd.DataFrame(rows).sort_values(["slug", "length_m"], ascending=[True, False])
    summary.to_csv(OUT_VALLEY_INDEX, index=False, encoding="utf-8-sig", float_format="%.1f")
    print(f"  -> {OUT_VALLEY_INDEX}")
    return summary


def main() -> None:
    """运行完整流程：提取西南河流 -> 按名称拆分 -> 提取河谷中心线"""
    print("=" * 72)
    print("Extract Xinan named rivers from national river dataset")
    print("=" * 72)
    print(f"National river: {NATIONAL_RIVER_PATH}")
    print(f"Xinan boundary : {XINAN_BOUNDARY_PATH}")
    print(f"Output root    : {OUT_ROOT}")

    rivers = read_vector(NATIONAL_RIVER_PATH)
    xinan = read_vector(XINAN_BOUNDARY_PATH)
    xinan_rivers, name_col = extract_xinan_rivers(rivers, xinan)

    print(f"\nRiver name field: {name_col}")
    print(f"Xinan river segments: {len(xinan_rivers)}")
    print(f"Unique river names  : {xinan_rivers[name_col].nunique()}")

    print("\nWriting Xinan rivers by name ...")
    by_name_summary = write_by_name_outputs(xinan_rivers, name_col)
    print(by_name_summary.to_string(index=False))

    print("\nWriting dry-hot valley centerlines ...")
    valley_summary = write_valley_centerlines(xinan_rivers, name_col)
    print(valley_summary.to_string(index=False))

    print("\nDone.")


if __name__ == "__main__":
    main()
