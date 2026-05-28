# @Author  : ChaoQiezi
# @Time    : 2026/05/28
# @Email   : chaoqiezi.one@qq.com
# @Wechat  : GIS茄子
# @FileName: river_net.py

# -*- coding: utf-8 -*-
"""
川西干热河谷 - 河流中心线提取工具（含河流分级）
基于DEM水文分析 + Strahler分级提取河谷范围内的主干河流
"""

import os
import time

import arcpy
from arcpy.sa import *

# 【第一部分】参数配置
workspace = r"E:\GeoProjects\dry_hot_valley\valley_area\river_net"

dem_input = r"G:\GeoProjects\dry_hot_valley\geo_factor\DEM\GLO-30\elevation_10m_projected.tif"
valley_polygon = r"E:\GeoProjects\dry_hot_valley\valley_area\valley.shp"

buffer_distance = 2000
stream_threshold = 10000
# stream_order_mode = "auto"  # 自动分级, 默认保留最高级和次高级
stream_order_mode = 4  # 保留大于等于4的河流段

# 【第二部分】环境设置


def setup_environment():
    """初始化 ArcGIS Spatial Analyst 扩展和工作空间环境"""
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
        print("[OK] Spatial Analyst 扩展已启用")
    else:
        raise RuntimeError("Spatial Analyst 扩展不可用")

    if not os.path.exists(workspace):
        os.makedirs(workspace)

    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True
    arcpy.env.mask = None
    arcpy.env.extent = None

    scratch_folder = os.path.join(workspace, "scratch")
    if not os.path.exists(scratch_folder):
        os.makedirs(scratch_folder)
    arcpy.env.scratchWorkspace = scratch_folder
    print(f"[OK] 工作空间: {workspace}")


# 【第三部分】处理步骤

def step1_buffer_and_clip():
    """对河谷多边形做缓冲区后裁剪 DEM，返回裁剪后的 DEM 路径"""
    print("\n" + "=" * 60)
    print("步骤1：缓冲区裁剪DEM")
    print("=" * 60)

    valley_dissolved = os.path.join(workspace, "valley_dissolved.shp")
    valley_buffer = os.path.join(workspace, "valley_buffer.shp")
    dem_clipped = os.path.join(workspace, "dem_clipped.tif")

    arcpy.management.Dissolve(valley_polygon, valley_dissolved)
    arcpy.analysis.Buffer(valley_dissolved, valley_buffer,
                          f"{buffer_distance} Meters", dissolve_option="ALL")
    ExtractByMask(dem_input, valley_buffer).save(dem_clipped)

    desc = arcpy.Describe(dem_clipped)
    print(f"  [OK] 裁剪后: {desc.width} x {desc.height} 像元")
    return dem_clipped


def step2_fill(dem_clipped):
    """对裁剪后的 DEM 执行填洼处理"""
    print("\n" + "=" * 60)
    print("步骤2：DEM填洼")
    print("=" * 60)

    filled_dem = os.path.join(workspace, "filled_dem")
    t = time.time()
    Fill(dem_clipped).save(filled_dem)
    print(f"  [OK] 耗时: {time.time() - t:.1f}秒")
    return filled_dem


def step3_flow_direction(filled_dem):
    """基于填洼后的 DEM 计算流向栅格"""
    print("\n" + "=" * 60)
    print("步骤3：计算流向")
    print("=" * 60)

    flow_dir = os.path.join(workspace, "flow_dir")
    t = time.time()
    FlowDirection(filled_dem, force_flow="NORMAL").save(flow_dir)
    print(f"  [OK] 耗时: {time.time() - t:.1f}秒")
    return flow_dir


def step4_flow_accumulation(flow_dir):
    """计算汇流累积量栅格"""
    print("\n" + "=" * 60)
    print("步骤4：计算汇流累积量")
    print("=" * 60)

    flow_acc = os.path.join(workspace, "flow_acc")
    t = time.time()
    FlowAccumulation(flow_dir, data_type="DOUBLE").save(flow_acc)
    elapsed = time.time() - t

    raster = arcpy.Raster(flow_acc)
    if raster.maximum is None:
        raise RuntimeError("Flow Accumulation输出全为NoData！")
    print(f"  [OK] 值范围: {raster.minimum} ~ {raster.maximum}")
    print(f"  耗时: {elapsed:.1f}秒")
    return flow_acc


def step5_extract_stream(flow_acc):
    """按阈值提取河网栅格"""
    print("\n" + "=" * 60)
    print(f"步骤5：提取河网（阈值={stream_threshold}）")
    print("=" * 60)

    stream_raster = os.path.join(workspace, "stream_raster")
    Con(Raster(flow_acc) >= stream_threshold, 1).save(stream_raster)
    print(f"  [OK] 河网栅格: {stream_raster}")
    return stream_raster


def step6_stream_order(stream_raster, flow_dir):
    """对提取的河网执行 Strahler 河流分级"""
    print("\n" + "=" * 60)
    print("步骤6：Strahler河流分级")
    print("=" * 60)

    order_raster = os.path.join(workspace, "stream_order")
    StreamOrder(stream_raster, flow_dir, "STRAHLER").save(order_raster)

    raster = arcpy.Raster(order_raster)
    max_order = int(raster.maximum)
    print(f"  最高河流级别: {max_order}")

    print("  各级分布:")
    with arcpy.da.SearchCursor(order_raster, ["VALUE", "COUNT"]) as cursor:
        for row in cursor:
            order_val, count = row
            marker = " <-- 主干" if order_val >= max_order - 1 else ""
            print(f"    {order_val}级: {count} 像元{marker}")

    return order_raster, max_order


def step7_filter_main_trunk(order_raster, max_order):
    """根据分级模式筛选主干河流（保留指定级别以上的河段）"""
    print("\n" + "=" * 60)
    print("步骤7：筛选主干河流")
    print("=" * 60)

    main_stream = os.path.join(workspace, "main_stream")

    if stream_order_mode == "auto":
        min_keep = max(max_order - 1, 1)
        print(f"  自动模式：保留 >= {min_keep} 级")
    else:
        min_keep = int(stream_order_mode)
        print(f"  手动模式：保留 >= {min_keep} 级")

    Con(Raster(order_raster) >= min_keep, Raster(order_raster)).save(main_stream)
    print(f"  [OK] 主干河网栅格: {main_stream}")
    return main_stream, min_keep


def step8_stream_to_feature(main_stream, flow_dir):
    """将主干河网栅格转换为矢量线要素"""
    print("\n" + "=" * 60)
    print("步骤8：主干河网矢量化")
    print("=" * 60)

    stream_vector = os.path.join(workspace, "main_stream_vector.shp")
    arcpy.sa.StreamToFeature(main_stream, flow_dir, stream_vector, simplify="SIMPLIFY")

    count = int(arcpy.management.GetCount(stream_vector)[0])
    print(f"  [OK] 河段数量: {count}")
    return stream_vector


def step9_clip_to_valley(stream_vector):
    """将河网矢量裁剪到河谷多边形范围内"""
    print("\n" + "=" * 60)
    print("步骤9：裁剪到河谷范围")
    print("=" * 60)

    stream_clipped = os.path.join(workspace, "stream_in_valley.shp")
    arcpy.analysis.Clip(stream_vector, valley_polygon, stream_clipped)

    count = int(arcpy.management.GetCount(stream_clipped)[0])
    print(f"  [OK] 河谷内河段: {count}")
    return stream_clipped


def step10_select_main_per_valley(stream_clipped):
    """
    步骤10：为每个河谷保留最高级别的河段
    """
    print("\n" + "=" * 60)
    print("步骤10：按河谷筛选主干")
    print("=" * 60)

    # 10.1 空间连接：给每条河段标记所属河谷
    stream_joined = os.path.join(workspace, "stream_joined.shp")
    arcpy.analysis.SpatialJoin(
        stream_clipped, valley_polygon, stream_joined,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option="WITHIN"
    )

    # 10.2 计算长度
    arcpy.management.AddGeometryAttributes(stream_joined, "LENGTH", "METERS")

    # 10.3 先探测实际字段名
    field_names = [f.name for f in arcpy.ListFields(stream_joined)]
    print(f"  属性表字段: {field_names}")

    # 查找河谷ID字段
    valley_id_field = None
    for candidate in ["TARGET_FID", "FID_valley", "FID_valle", "Join_FID"]:
        if candidate in field_names:
            valley_id_field = candidate
            break

    # 查找河谷名称字段
    valley_name_field = None
    for candidate in ["Name", "name", "NAME", "河谷名称"]:
        if candidate in field_names:
            valley_name_field = candidate
            break

    final_stream = os.path.join(workspace, "centerline_final.shp")

    if valley_id_field is None:
        print("  [!] 未找到河谷ID字段，输出全部河段")
        arcpy.management.CopyFeatures(stream_joined, final_stream)
    else:
        print(f"  河谷ID字段: {valley_id_field}")
        if valley_name_field:
            print(f"  河谷名称字段: {valley_name_field}")

        # 10.4 找出每个河谷内的最高grid_code
        valley_max_order = {}
        valley_names = {}

        read_fields = [valley_id_field, "grid_code"]
        if valley_name_field:
            read_fields.append(valley_name_field)

        with arcpy.da.SearchCursor(stream_joined, read_fields) as cursor:
            for row in cursor:
                vid = row[0] if row[0] is not None else -1
                gc = row[1] if row[1] is not None else 0
                if vid not in valley_max_order or gc > valley_max_order[vid]:
                    valley_max_order[vid] = gc
                if valley_name_field and len(row) > 2 and row[2]:
                    valley_names[vid] = row[2]

        # 打印每个河谷的情况
        print("\n  各河谷最高河流级别:")
        for vid, max_gc in sorted(valley_max_order.items()):
            if vid < 0:
                continue
            name = valley_names.get(vid, f"河谷{vid}")
            print(f"    {name}: 最高 {max_gc} 级")

        # 10.5 构建筛选条件：每个河谷只保留最高级别的河段
        arcpy.management.MakeFeatureLayer(stream_joined, "stream_lyr")

        where_parts = []
        for vid, max_gc in valley_max_order.items():
            if vid >= 0:
                where_parts.append(
                    f'("{valley_id_field}" = {vid} AND "grid_code" = {max_gc})'
                )

        if where_parts:
            where_clause = " OR ".join(where_parts)
            print(f"\n  筛选条件: {where_clause}")
            arcpy.management.SelectLayerByAttribute(
                "stream_lyr", "NEW_SELECTION", where_clause
            )
            arcpy.management.CopyFeatures("stream_lyr", final_stream)
        else:
            arcpy.management.CopyFeatures(stream_joined, final_stream)

    count = int(arcpy.management.GetCount(final_stream)[0])
    print(f"\n  [OK] 最终主干河段: {count} 条")

    # 打印最终每个河谷的河段统计
    if valley_id_field and valley_id_field in [f.name for f in arcpy.ListFields(final_stream)]:
        read_fields_final = [valley_id_field, "grid_code", "LENGTH"]
        if valley_name_field and valley_name_field in [f.name for f in arcpy.ListFields(final_stream)]:
            read_fields_final.append(valley_name_field)

        print("\n  最终河段详情:")
        with arcpy.da.SearchCursor(final_stream, read_fields_final) as cursor:
            for row in cursor:
                vid = row[0]
                gc = row[1]
                length = row[2]
                name = row[3] if len(row) > 3 else f"河谷{vid}"
                print(f"    {name} | {gc}级 | 长度: {length:.0f}m")

    return final_stream


# 【第四部分】主函数

def main():
    """按顺序执行河流中心线提取的完整处理流程"""
    print("=" * 60)
    print("  川西干热河谷 - 主干河流中心线提取")
    print(f"  河网阈值: {stream_threshold}")
    print(f"  分级模式: {stream_order_mode}")
    print("=" * 60)

    total_start = time.time()
    setup_environment()

    dem_clipped = step1_buffer_and_clip()
    filled_dem = step2_fill(dem_clipped)
    flow_dir = step3_flow_direction(filled_dem)
    flow_acc = step4_flow_accumulation(flow_dir)
    stream_raster = step5_extract_stream(flow_acc)
    order_raster, max_order = step6_stream_order(stream_raster, flow_dir)
    main_stream, min_keep = step7_filter_main_trunk(order_raster, max_order)
    stream_vector = step8_stream_to_feature(main_stream, flow_dir)
    stream_clipped = step9_clip_to_valley(stream_vector)
    final = step10_select_main_per_valley(stream_clipped)

    arcpy.CheckInExtension("Spatial")

    print("\n" + "=" * 60)
    print(f"  完成！总耗时: {(time.time() - total_start) / 60:.1f}分钟")
    print(f"  最终输出: {final}")
    print("=" * 60)
    print("\n  后续操作：")
    print("  1. 在ArcGIS Pro中打开 centerline_final.shp 叠加河谷polygon检查")
    print("  2. 如果某个河谷内仍有多条河段，手动删除非主干")
    print("  3. 用中心线分割河谷polygon为左右岸")


if __name__ == "__main__":
    # main()

    # 只执行第7-10步
    setup_environment()
    order_raster = os.path.join(workspace, "stream_order")
    flow_dir = os.path.join(workspace, "flow_dir")
    main_stream, min_keep = step7_filter_main_trunk(order_raster, 6)
    stream_vector = step8_stream_to_feature(main_stream, flow_dir)
    stream_clipped = step9_clip_to_valley(stream_vector)
    final = step10_select_main_per_valley(stream_clipped)
