"""跑步轨迹生成器 - 基于 map.json 路线数据生成 GPS 轨迹"""

import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# 加载 map.json 路线数据（在 test/ 目录下）
_MAP_JSON_PATH = Path(__file__).parent.parent.parent / "map.json"
_map_data: dict[str, Any] | None = None


def _load_map_data() -> dict[str, Any]:
    """加载 map.json 路线数据，缓存结果"""
    global _map_data
    if _map_data is not None:
        return _map_data
    
    if not _MAP_JSON_PATH.exists():
        raise FileNotFoundError(f"map.json 不存在: {_MAP_JSON_PATH}")
    
    with open(_MAP_JSON_PATH, "r", encoding="utf-8") as f:
        _map_data = json.load(f)
    return _map_data


def get_run_time_window() -> tuple[str, str]:
    """从 map.json 获取跑步时间窗口（startTime, endTime），默认 06:00-23:00"""
    try:
        data = _load_map_data()
        return data.get("startTime", "06:00"), data.get("endTime", "23:00")
    except FileNotFoundError:
        return "06:00", "23:00"


def _normal_random(mean: float, std: float) -> float:
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


def _distance_between_points(p1: list[float], p2: list[float]) -> float:
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


def _distance_of_line(points: list[list[float]]) -> float:
    """计算路径总距离（米）"""
    total = 0.0
    for i in range(len(points) - 1):
        total += _distance_between_points(points[i], points[i + 1])
    return total


def generate_route_for_point_id(
    point_id: str,
    distance_km: float,
    run_date: str | None = None,
    start_time_str: str | None = None,
    duration_min: int | None = None,
) -> dict[str, Any]:
    """
    根据路线 pointId 从 map.json 读取数据，生成跑步轨迹。

    Args:
        point_id: 路线 pointId，如 "sunrunLine-20230208000001"
        distance_km: 目标距离（公里）
        run_date: 跑步日期，格式 YYYY-MM-DD，默认今天
        start_time_str: 开始时间，格式 HH:MM，默认 06:00
        duration_min: 跑步时长（分钟），默认根据距离计算

    Returns:
        dict: 包含 mockRoute, routeInfo, startTime, endTime 等
    """
    map_data = _load_map_data()
    run_point_list = map_data.get("runPointList", [])
    
    # 查找指定路线
    target_route = None
    for rp in run_point_list:
        if rp.get("pointId") == point_id:
            target_route = rp
            break
    
    if not target_route:
        raise ValueError(f"路线 {point_id} 不存在于 map.json")
    
    # 解析日期和时间
    if run_date:
        base_date = datetime.strptime(run_date, "%Y-%m-%d")
    else:
        base_date = datetime.now()
    
    if start_time_str:
        start_h, start_m = map(int, start_time_str.split(":"))
    else:
        start_h, start_m = 6, 0
    
    start_time = base_date.replace(hour=start_h, minute=start_m, second=0)
    
    # 计算时长（与 xicao_route.py 一致）
    if duration_min:
        duration_seconds = duration_min * 60
    else:
        # 默认配速约 8 km/h -> 20 分钟基准，再用正态分布生成 10-25 分钟
        avg_speed_kmh = distance_km / (20 / 60)
        duration_seconds = int((distance_km / avg_speed_kmh) * 3600)
        
        min_time = 10 * 60  # 10 分钟
        max_time = 25 * 60  # 25 分钟
        avg_time = (min_time + max_time) / 2
        duration_seconds = int(_normal_random(avg_time, (max_time - avg_time) / 3))
        duration_seconds = max(min_time, min(max_time, duration_seconds))
    
    # 添加 ±30 秒随机波动
    time_deviation = int((random.random() - 0.5) * 60)
    duration_seconds = duration_seconds + time_deviation
    
    end_time = start_time + timedelta(seconds=duration_seconds)
    
    # 生成轨迹
    std = 1 / 50000
    step_length = 0.0001
    distance_m = distance_km * 1000
    
    # 1. 转换路径点为 [经度, 纬度] 数组
    route = [
        [float(p["longitude"]), float(p["latitude"])]
        for p in target_route["pointList"]
    ]
    
    # 2. 对路径点之间插值
    def add_points(point_a: list[float], point_b: list[float]) -> list[list[float]]:
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
    
    combined_points: list[list[float]] = []
    for i in range(len(route) - 1):
        points = add_points(route[i], route[i + 1])
        combined_points.extend(points[:-1])  # 不重复添加终点
    combined_points.append(route[-1])
    
    # 3. 从随机起点截取 + 加偏移
    start_idx = random.randint(0, len(combined_points) - 1)
    idx = start_idx
    
    def add_deviation(point: list[float]) -> list[float]:
        return [_normal_random(point[0], std), _normal_random(point[1], std)]
    
    points = [add_deviation(combined_points[start_idx])]
    current_dist = 0.0
    max_points = min(int(distance_m / 2) + 100, 3000)
    
    while current_dist < distance_m and len(points) < max_points:
        idx += 1
        if idx >= len(combined_points) - 2:
            idx = 0
        
        point = add_deviation(combined_points[idx])
        points.append(point)
        current_dist = _distance_of_line(points)
    
    # 4. 格式化输出
    mock_route = [
        {"longitude": f"{p[0]:.6f}", "latitude": f"{p[1]:.6f}"}
        for p in points
    ]
    
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    used_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    avg_speed = f"{distance_km / (duration_seconds / 3600):.2f}"
    
    return {
        "routeInfo": {
            "taskId": target_route["taskId"],
            "pointId": target_route["pointId"],
            "pointName": target_route["pointName"],
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
        "steps": f"{1000 + random.randint(0, 1000)}",
    }


def save_route(route_data: dict[str, Any], run_date: str | None = None, filename: str | None = None) -> str:
    """
    保存轨迹到 JSON 文件。

    Args:
        route_data: generate_route_for_point_id 返回的数据
        run_date: 跑步日期 YYYY-MM-DD，优先用于文件名
        filename: 文件名，默认使用 {run_date}_{pointId}.json

    Returns:
        保存的文件路径
    """
    data_dir = Path(__file__).parent.parent / "data" / "routes"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    if not filename:
        date_str = run_date or route_data["evaluateDate"]
        point_id = route_data["routeInfo"]["pointId"]
        filename = f"{date_str}_{point_id}.json"
    
    file_path = data_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(route_data, f, ensure_ascii=False, indent=2)
    
    return str(file_path)


def load_route(filename: str) -> dict[str, Any]:
    """从 JSON 文件加载轨迹"""
    data_dir = Path(__file__).parent.parent / "data" / "routes"
    file_path = data_dir / filename
    
    if not file_path.exists():
        raise FileNotFoundError(f"轨迹文件不存在: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_route_filename(run_date: str, point_id: str) -> str:
    """根据日期和路线 ID 生成文件名"""
    return f"{run_date}_{point_id}.json"
