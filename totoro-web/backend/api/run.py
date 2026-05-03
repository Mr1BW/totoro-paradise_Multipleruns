"""跑步相关 API - 获取任务、生成轨迹、提交记录"""

import hashlib
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.api.auth import _call_totoro, load_session
from backend.models import ApiResponse, SubmitRunRequest
from backend.route_generator import (
    generate_route_for_point_id,
    get_route_filename,
    get_run_time_window,
    load_route,
    save_route,
)

router = APIRouter(prefix="/run", tags=["run"])


# ============================================================================
# 获取今日跑步任务
# ============================================================================

@router.get("/paper", response_model=ApiResponse)
async def get_run_paper() -> ApiResponse:
    """获取今日跑步任务（路线、距离要求等）"""
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    try:
        result = await _call_totoro(
            "sunrun/getSunrunPaper",
            {
                "campusId": session.session.campusId or "",
                "schoolId": session.session.schoolId or "",
                "stuNumber": session.session.stuNumber,
                "token": session.session.token,
            },
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取任务失败: {e}")


# ============================================================================
# 生成轨迹并保存
# ============================================================================

@router.post("/generate", response_model=ApiResponse)
async def generate_route(data: dict) -> ApiResponse:
    """
    根据路线 ID 生成轨迹并保存到 JSON 文件。

    请求体：
    {
        "routeId": "sunrunLine-20230208000001",
        "distance": 3.2,
        "runDate": "2026-03-01",
        "startTime": "06:00",
        "durationMin": 15
    }
    """
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    route_id = data.get("routeId")
    distance = data.get("distance", 3.2)
    run_date = data.get("runDate")
    start_time = data.get("startTime")
    duration_min = data.get("durationMin")

    if not route_id:
        return ApiResponse(success=False, message="缺少 routeId")

    try:
        route_data = generate_route_for_point_id(
            point_id=route_id,
            distance_km=float(distance),
            run_date=run_date,
            start_time_str=start_time,
            duration_min=duration_min,
        )

        filename = get_route_filename(run_date or datetime.now().strftime("%Y-%m-%d"), route_id)
        file_path = save_route(route_data, run_date=run_date, filename=filename)

        return ApiResponse(
            success=True,
            data={
                "filePath": file_path,
                "routeInfo": route_data["routeInfo"],
                "pointCount": route_data["pointCount"],
                "distance": route_data["distance"],
                "startTime": route_data["startTime"],
                "endTime": route_data["endTime"],
                "usedTime": route_data["usedTime"],
                "avgSpeed": route_data["avgSpeed"],
            },
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"生成轨迹失败: {e}")


# ============================================================================
# 提交跑步记录
# ============================================================================

def _generate_mac(stu_number: str) -> str:
    """生成设备 MAC 地址"""
    hash_hex = hashlib.sha256(stu_number.encode()).hexdigest()[:12]
    return ":".join(hash_hex[i : i + 2] for i in range(0, 12, 2))


@router.post("/submit", response_model=ApiResponse)
async def submit_run(req: SubmitRunRequest) -> ApiResponse:
    """
    提交跑步记录。

    流程（与 submit_run.py 一致）：
    1. 读取已生成的轨迹 JSON
    2. getRunBegin
    3. sunRunExercises（汇总）
    4. sunRunExercisesDetail（GPS 轨迹）
    """
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    s = session.session
    token = s.token
    stu_number = s.stuNumber
    school_id = s.schoolId or ""
    campus_id = s.campusId or ""

    # ========== 读取已生成的轨迹 JSON ==========
    run_date = req.runDate or datetime.now().strftime("%Y-%m-%d")
    route_id = req.routeId
    if not route_id:
        return ApiResponse(success=False, message="缺少 routeId")
    filename = get_route_filename(run_date, route_id)

    try:
        route_data = load_route(filename)
    except FileNotFoundError:
        return ApiResponse(
            success=False,
            message=f"轨迹文件不存在: {filename}。请先调用 /api/run/generate 生成轨迹。",
        )

    mock_route = route_data["mockRoute"]
    start_time_str = route_data["startTime"]
    end_time_str = route_data["endTime"]
    used_time = route_data["usedTime"]
    avg_speed = route_data["avgSpeed"]
    evaluate_date = route_data["evaluateDate"]
    target_distance = route_data["targetDistance"]
    route_info = route_data["routeInfo"]

    # ========== 判断是否为当日实时提交 ==========
    # ifLocalSubmit: 当日 + 在规定时间段内 → "0"（实时提交），否则 → "1"（补跑/替跑）
    try:
        run_date_obj = datetime.strptime(run_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        now_time = datetime.now().time()
        win_start_str, win_end_str = get_run_time_window()
        win_start = datetime.strptime(win_start_str, "%H:%M").time()
        win_end = datetime.strptime(win_end_str, "%H:%M").time()
        if run_date_obj == today and win_start <= now_time <= win_end:
            if_local_submit = "0"
        else:
            if_local_submit = "1"
    except Exception:
        if_local_submit = "1"

    # Step 1: getRunBegin（与 submit_run.py 一致，异常仅警告不阻断）
    try:
        await _call_totoro(
            "sunrun/getRunBegin",
            {
                "campusId": campus_id,
                "schoolId": school_id,
                "stuNumber": stu_number,
                "token": token,
            },
        )
    except Exception:
        pass  # submit_run.py 中此处仅打印警告，继续执行

    # Step 2: sunRunExercises（汇总）
    summary = {
        "LocalSubmitReason": "",
        "avgSpeed": avg_speed,
        "baseStation": "",
        "endTime": end_time_str,
        "evaluateDate": evaluate_date,
        "fitDegree": "1",
        "flag": "1",
        "headImage": "",
        "ifLocalSubmit": if_local_submit,
        "km": target_distance,
        "mac": _generate_mac(stu_number),
        "phoneInfo": "$CN11/iPhone15,4/17.4.1",
        "phoneNumber": "",
        "pointList": "",
        "routeId": route_info["pointId"],
        "runType": "0",
        "sensorString": "",
        "startTime": start_time_str,
        "steps": route_data["steps"],
        "stuNumber": stu_number,
        "taskId": route_info["taskId"],
        "token": token,
        "usedTime": used_time,
        "version": "1.2.14",
        "warnFlag": "0",
        "warnType": "",
        "faceData": "",
    }

    try:
        result = await _call_totoro(
            "platform/recrecord/sunRunExercises", summary
        )
    except Exception as e:
        return ApiResponse(success=False, message=f"提交汇总失败: {e}")

    scantron_id = result.get("scantronId")
    if not scantron_id:
        return ApiResponse(
            success=False, message=f"未获取到 scantronId: {result}"
        )

    # Step 3: sunRunExercisesDetail（GPS 轨迹，明文 JSON）
    try:
        track_payload = {
            "pointList": mock_route,
            "scantronId": scantron_id,
            "stuNumber": stu_number,
            "token": token,
        }
        await _call_totoro(
            "platform/recrecord/sunRunExercisesDetail",
            track_payload,
            encrypted=False,
        )
    except Exception as e:
        return ApiResponse(
            success=False, message=f"提交轨迹失败: {e}", data={"scantronId": scantron_id}
        )

    return ApiResponse(
        success=True,
        data={
            "scantronId": scantron_id,
            "distance": target_distance,
            "usedTime": used_time,
            "avgSpeed": avg_speed,
            "points": len(mock_route),
        },
    )
