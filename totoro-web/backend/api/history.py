"""历史记录 API"""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from backend.api.auth import _call_totoro, load_session
from backend.models import ApiResponse

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/terms", response_model=ApiResponse)
async def get_school_terms() -> ApiResponse:
    """获取学期列表"""
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    try:
        result = await _call_totoro(
            "platform/course/getSchoolTerm",
            {
                "schoolId": session.session.schoolId or "",
                "token": session.session.token,
            },
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取学期失败: {e}")


@router.get("/months", response_model=ApiResponse)
async def get_school_months(term_id: str) -> ApiResponse:
    """获取学期月份"""
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    try:
        result = await _call_totoro(
            "platform/course/getSchoolMonthByTerm",
            {
                "schoolId": session.session.schoolId or "",
                "stuNumber": session.session.stuNumber,
                "token": session.session.token,
                "termId": term_id,
            },
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取月份失败: {e}")


@router.get("/arch", response_model=ApiResponse)
async def get_run_history(month_id: str, term_id: str) -> ApiResponse:
    """获取历史跑步记录"""
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    try:
        result = await _call_totoro(
            "sunrun/getSunrunArch",
            {
                "campusId": session.session.campusId or "",
                "schoolId": session.session.schoolId or "",
                "stuNumber": session.session.stuNumber,
                "token": session.session.token,
                "runType": "0",
                "monthId": month_id,
                "termId": term_id,
            },
        )
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, message=f"获取历史记录失败: {e}")


# ============================================================================
# 日历视图：获取本学期所有跑步记录（按日期聚合）
# ============================================================================

@router.get("/calendar", response_model=ApiResponse)
async def get_calendar_data() -> ApiResponse:
    """
    获取本学期所有月份的跑步记录，按日期聚合，用于日历视图。

    返回格式：
    {
        "termId": "...",
        "termName": "2025-2026学年第二学期",
        "startDate": "2026-02-17",
        "endDate": "2026-07-01",
        "records": {
            "2026-03-01": { "mileage": "3.20", "usedTime": "00:15:30", "status": "1" },
            "2026-03-02": null,
            ...
        }
    }
    """
    session = load_session()
    if not session:
        raise HTTPException(401, "未登录")

    try:
        # Step 1: 获取学期列表，找到当前学期
        terms_result = await _call_totoro(
            "platform/course/getSchoolTerm",
            {
                "schoolId": session.session.schoolId or "",
                "token": session.session.token,
            },
        )

        terms = terms_result.get("data", []) or terms_result.get("termList", [])
        if not terms:
            return ApiResponse(success=False, message="无学期数据")

        current_term = None
        for t in terms:
            if t.get("isCurrent") == "1":
                current_term = t
                break
        if not current_term:
            current_term = terms[-1]

        term_id = current_term["termId"]
        term_name = current_term.get("termName", "")

        # Step 2: 获取当前学期的所有月份
        months_result = await _call_totoro(
            "platform/course/getSchoolMonthByTerm",
            {
                "schoolId": session.session.schoolId or "",
                "stuNumber": session.session.stuNumber,
                "token": session.session.token,
                "termId": term_id,
            },
        )

        months = months_result.get("monthList", [])
        if not months:
            return ApiResponse(success=False, message="无月份数据")

        # Step 3: 逐月获取跑步记录，按日期聚合
        all_records: dict[str, dict | None] = {}

        for month in months:
            month_id = month["monthId"]
            month_name = month.get("monthName", "")

            try:
                arch_result = await _call_totoro(
                    "sunrun/getSunrunArch",
                    {
                        "campusId": session.session.campusId or "",
                        "schoolId": session.session.schoolId or "",
                        "stuNumber": session.session.stuNumber,
                        "token": session.session.token,
                        "runType": "0",
                        "monthId": month_id,
                        "termId": term_id,
                    },
                )

                run_list = arch_result.get("data", [])
                for record in run_list:
                    run_time = record.get("runTime", "")
                    if run_time:
                        # runTime 格式: "2026-03-01 14:30:00"
                        run_date = run_time.split(" ")[0]
                        all_records[run_date] = {
                            "mileage": record.get("mileage", "0"),
                            "usedTime": record.get("usedTime", ""),
                            "status": record.get("status", "1"),
                            "scoreId": record.get("scoreId", ""),
                        }
            except Exception:
                # 某个月份失败不影响其他月份
                continue

        # Step 4: 确定学期日期范围（从月份名推断）
        # 月份格式通常是 "2026年03月" 或 "3月"
        start_date = None
        end_date = None
        if months:
            # 提取第一个和最后一个月的日期
            first_month = months[0].get("monthName", "")
            last_month = months[-1].get("monthName", "")
            # 简单推断：月初到月末
            # 实际使用时前端根据当前日期渲染即可
            try:
                # 尝试从月份名解析，格式可能是 "2026年03月"
                import re as _re
                m = _re.search(r"(\d{4})年(\d{1,2})月", first_month)
                if m:
                    year, month_num = int(m.group(1)), int(m.group(2))
                    start_date = f"{year}-{month_num:02d}-01"
                m = _re.search(r"(\d{4})年(\d{1,2})月", last_month)
                if m:
                    year, month_num = int(m.group(1)), int(m.group(2))
                    # 月末
                    if month_num == 12:
                        end_date = f"{year + 1}-01-01"
                    else:
                        end_date = f"{year}-{month_num + 1:02d}-01"
            except Exception:
                pass

        return ApiResponse(
            success=True,
            data={
                "termId": term_id,
                "termName": term_name,
                "startDate": start_date,
                "endDate": end_date,
                "records": all_records,
            },
        )

    except Exception as e:
        return ApiResponse(success=False, message=f"获取日历数据失败: {e}")
