"""Session 管理 API"""

from fastapi import APIRouter

from backend.api.auth import load_session
from backend.models import ApiResponse, SessionWrapper

router = APIRouter(prefix="/session", tags=["session"])


@router.get("", response_model=ApiResponse)
async def get_session() -> ApiResponse:
    """获取当前登录 session"""
    session = load_session()
    if not session:
        return ApiResponse(success=False, message="未登录", data=None)
    return ApiResponse(success=True, data=session.model_dump(mode="json"))


@router.delete("", response_model=ApiResponse)
async def clear_session() -> ApiResponse:
    """清除当前 session（退出登录）"""
    from pathlib import Path

    from backend.config import SESSION_FILE

    path = Path(SESSION_FILE)
    if path.exists():
        path.unlink()
    return ApiResponse(success=True, message="已退出登录")


@router.get("/check", response_model=ApiResponse)
async def check_login() -> ApiResponse:
    """检查登录状态"""
    session = load_session()
    if not session:
        return ApiResponse(success=False, message="未登录")
    return ApiResponse(
        success=True,
        data={
            "stuName": session.session.stuName,
            "stuNumber": session.session.stuNumber,
            "schoolName": session.session.schoolName,
            "token": session.session.token[:20] + "..." if session.session.token else None,
        },
    )
