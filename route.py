#!/usr/bin/env python3
"""
龙猫校园 - 西操场跑步轨迹生成脚本
基于 test/map.json 中的真实路线数据

使用方法:
    python xicao_route.py --start-time "14:00:00" --distance 3.2
    python xicao_route.py --help
"""

import json
import math
import random
import argparse
from datetime import datetime, timedelta


# ==================== 西操场原始路径点（来自 test/map.json） ====================

XICAO_ROUTE = {
    "taskId": "sunrunTaskPaper-20210917000004",
    "pointId": "sunrunLine-20230208000001",
    "pointName": "西操场",
    "longitude": "118.787194",
    "latitude": "31.9390495",
    "pointList": [
        {"longitude": "118.786986", "latitude": "31.939762"},
        {"longitude": "118.787101", "latitude": "31.939769"},
        {"longitude": "118.787225", "latitude": "31.939753"},
        {"longitude": "118.787388", "latitude": "31.939659"},
        {"longitude": "118.787471", "latitude": "31.939543"},
        {"longitude": "118.787536", "latitude": "31.939336"},
        {"longitude": "118.787605", "latitude": "31.939079"},
        {"longitude": "118.787672", "latitude": "31.938851"},
        {"longitude": "118.787721", "latitude": "31.938694"},
        {"longitude": "118.787710", "latitude": "31.938610"},
        {"longitude": "118.787667", "latitude": "31.938503"},
        {"longitude": "118.787576", "latitude": "31.938412"},
        {"longitude": "118.787404", "latitude": "31.938342"},
        {"longitude": "118.787243", "latitude": "31.938330"},
        {"longitude": "118.787120", "latitude": "31.938360"},
        {"longitude": "118.787010", "latitude": "31.938430"},
        {"longitude": "118.786927", "latitude": "31.938533"},
        {"longitude": "118.786774", "latitude": "31.939052"},
        {"longitude": "118.786707", "latitude": "31.939277"},
        {"longitude": "118.786667", "latitude": "31.939427"},
        {"longitude": "118.786693", "latitude": "31.939543"},
        {"longitude": "118.786766", "latitude": "31.939662"},
        {"longitude": "118.786846", "latitude": "31.939721"},
        {"longitude": "118.786980", "latitude": "31.939764"}
    ]
}

# ==================== 工具函数（与 totoro-paradise 源码一致） ====================

def normal_random(mean: float, std: float) -> float:
    """正态分布随机数（与 normalRandom.ts 一致）"""
    while True:
        u = random.random() * 2 - 1.0
        v = random.random() * 2 - 1.0
        w = u * u + v * v
        if w == 0 or w >= 1.0:
            continue
        c = math.sqrt((-2 * math.log(w)) / w)
        result = mean + u * c * std
        if mean - 3 * std <= result <= mean + 3 * std:
            return result


def distance_between_points(p1, p2):
    """计算两点间距离（米）- 使用与 distanceCalculator.ts 相同的算法"""
    d1 = 0.0174532925194329
    d2, d3 = float(p1[0]), float(p1[1])
    d4, d5 = float(p2[0]), float(p2[1])
    d2 *= d1
    d3 *= d1
    d4 *= d1
    d5 *= d1
    d6 = math.sin(d2)
    d7 = math.sin(d3)
    d8 = math.cos(d2)
    d9 = math.cos(d3)
    d10 = math.sin(d4)
    d11 = math.sin(d5)
    d12 = math.cos(d4)
    d13 = math.cos(d5)
    s11 = d9 * d8
    s12 = d9 * d6
    s13 = d7
    s21 = d13 * d12
    s22 = d13 * d10
    s23 = d11
    d14 = math.sqrt(
        (s11 - s21) * (s11 - s21) +
        (s12 - s22) * (s12 - s22) +
        (s13 - s23) * (s13 - s23)
    )
    return math.asin(d14 / 2.0) * 1.2740015798544e7


def distance_of_line(points):
    """计算路径总距离（米）"""
    total = 0
    for i in range(len(points) - 1):
        total += distance_between_points(points[i], points[i + 1])
    return total


# ==================== 轨迹生成（与 generateRoute.ts 一致） ====================

def generate_route(distance_km: float, start_time: datetime = None):
    """
    生成西操场跑步轨迹
    
    Args:
        distance_km: 目标距离（公里），如 3.2
        start_time: 开始时间（datetime对象），默认当前时间
    
    Returns:
        dict: 包含 mockRoute, distance, startTime, endTime 等
    """
    if start_time is None:
        start_time = datetime.now()
    
    std = 1 / 50000  # 与源码一致
    step_length = 0.0001
    distance_m = distance_km * 1000
    
    # 1. 转换路径点为 [经度, 纬度] 数组
    route = [[float(p["longitude"]), float(p["latitude"])] for p in XICAO_ROUTE["pointList"]]
    
    # 2. 对路径点之间插值（combinePoints）
    def add_points(point_a, point_b):
        dx = point_b[0] - point_a[0]
        dy = point_b[1] - point_a[1]
        point_vector_norm = math.hypot(dx, dy)
        num_points = max(math.floor(point_vector_norm / step_length), 1)
        
        points = [point_a]
        for i in range(1, num_points):
            ratio = i / num_points
            x = point_a[0] + dx * ratio
            y = point_a[1] + dy * ratio
            points.append([x, y])
        return points
    
    combined_points = []
    for i in range(len(route) - 1):
        points = add_points(route[i], route[i + 1])
        combined_points.extend(points[:-1])  # 不重复添加终点
    combined_points.append(route[-1])
    
    # 3. 从随机起点截取 + 加偏移（trimRoute）
    start_idx = random.randint(0, len(combined_points) - 1)
    idx = start_idx
    
    def add_deviation(point):
        return [normal_random(point[0], std), normal_random(point[1], std)]
    
    points = [add_deviation(combined_points[start_idx])]
    current_dist = 0
    max_points = min(int(distance_m / 2) + 100, 3000)
    
    while current_dist < distance_m and len(points) < max_points:
        idx += 1
        if idx >= len(combined_points) - 2:  # 与源码一致，最后两个点不计算
            idx = 0
        
        point = add_deviation(combined_points[idx])
        points.append(point)
        current_dist = distance_of_line(points)
    
    # 4. 格式化输出
    mock_route = [
        {"longitude": f"{p[0]:.6f}", "latitude": f"{p[1]:.6f}"}
        for p in points
    ]
    
    # 5. 计算时间（默认配速约 8 km/h）
    avg_speed_kmh = distance_km / (20 / 60)  # 默认20分钟
    duration_seconds = int((distance_km / avg_speed_kmh) * 3600)
    
    # 添加随机波动（15-25分钟）
    min_time = 10 * 60  # 10分钟
    max_time = 25 * 60  # 25分钟
    avg_time = (min_time + max_time) / 2
    duration_seconds = int(normal_random(avg_time, (max_time - avg_time) / 3))
    duration_seconds = max(min_time, min(max_time, duration_seconds))
    
    end_time = start_time + timedelta(seconds=duration_seconds)
    
    # 格式化时间
    duration = timedelta(seconds=duration_seconds)
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    used_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    avg_speed = f"{distance_km / (duration_seconds / 3600):.2f}"
    
    return {
        "routeInfo": {
            "taskId": XICAO_ROUTE["taskId"],
            "pointId": XICAO_ROUTE["pointId"],
            "pointName": XICAO_ROUTE["pointName"]
        },
        "mockRoute": mock_route,
        "distance": f"{(current_dist / 1000):.2f}",
        "targetDistance": f"{distance_km:.2f}",
        "pointCount": len(mock_route),
        "startTime": start_time.strftime("%H:%M:%S"),
        "endTime": end_time.strftime("%H:%M:%S"),
        "evaluateDate": end_time.strftime("%Y-%m-%d"),
        "usedTime": used_time,
        "durationSeconds": duration_seconds,
        "avgSpeed": avg_speed,
        "steps": f"{1000 + random.randint(0, 1000)}"
    }


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(description='生成西操场跑步轨迹')
    parser.add_argument('--start-time', type=str, default=None,
                        help='开始时间，格式 HH:MM:SS（默认当前时间）')
    parser.add_argument('--distance', type=float, default=3.2,
                        help='目标距离（公里），默认 3.2')
    parser.add_argument('--output', type=str, default='xicao_route.json',
                        help='输出文件名')
    parser.add_argument('--date', type=str, default=None,
                        help='日期，格式 YYYY-MM-DD（默认今天）')
    
    args = parser.parse_args()
    
    # 解析开始时间
    if args.start_time:
        try:
            time_obj = datetime.strptime(args.start_time, "%H:%M:%S").time()
            if args.date:
                date_obj = datetime.strptime(args.date, "%Y-%m-%d").date()
            else:
                date_obj = datetime.now().date()
            start_time = datetime.combine(date_obj, time_obj)
        except ValueError:
            print("错误：时间格式应为 HH:MM:SS，如 14:30:00")
            return
    else:
        start_time = datetime.now()
    
    # 生成轨迹
    result = generate_route(args.distance, start_time)
    
    # 保存到文件
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 打印摘要
    print("=" * 60)
    print("西操场跑步轨迹生成完成")
    print("=" * 60)
    print(f"路线: {result['routeInfo']['pointName']}")
    print(f"目标距离: {result['targetDistance']} km")
    print(f"实际距离: {result['distance']} km")
    print(f"轨迹点数: {result['pointCount']}")
    print(f"开始时间: {result['startTime']}")
    print(f"结束时间: {result['endTime']}")
    print(f"用时: {result['usedTime']}")
    print(f"配速: {result['avgSpeed']} km/h")
    print(f"步数: {result['steps']}")
    print(f"\n文件已保存: {args.output}")
    print("=" * 60)
    
    # 同时输出前5个和后5个轨迹点
    print("\n轨迹预览:")
    print(f"起点: {result['mockRoute'][0]}")
    print(f"...（共 {result['pointCount']} 个点）...")
    print(f"终点: {result['mockRoute'][-1]}")


if __name__ == "__main__":
    main()
