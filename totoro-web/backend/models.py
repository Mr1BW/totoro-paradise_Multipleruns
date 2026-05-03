"""Pydantic 模型定义 - Session 模板与 API 请求/响应"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Session 模板（基于 session.json 结构定义）
# ============================================================================

class TotoroSession(BaseModel):
    """
    龙猫校园用户会话模板。

    微信登录成功后，服务端将填充此模板并持久化到 session.json。
    字段含义参考 data/session_template.json。
    """

    stuNumber: str = Field(..., description="学号")
    stuName: str | None = Field(None, description="学生姓名")
    schoolId: str | None = Field(None, description="学校 ID")
    schoolName: str | None = Field(None, description="学校名称")
    campusId: str | None = Field(None, description="校区 ID")
    campusName: str | None = Field(None, description="校区名称")
    collegeName: str | None = Field(None, description="学院名称")
    phoneNumber: str | None = Field(None, description="绑定的手机号")
    token: str = Field(..., description="登录令牌")
    serverPath: str = Field("https://app.xtotoro.com", description="服务器地址")
    path: str = Field("https://app.xtotoro.com", description="API 基础路径")
    newsUrl: str | None = Field(None, description="新闻页面 URL")
    useUrl: str | None = Field(None, description="使用说明 URL")
    registerUrl: str | None = Field(None, description="注册页面 URL")

    # 内部字段（不序列化到 JSON）
    issuedAt: int | None = Field(None, description="签发时间戳")
    expiresAt: int | None = Field(None, description="过期时间戳")


class SessionWrapper(BaseModel):
    """session.json 的顶层包装结构"""

    success: bool = True
    session: TotoroSession
    issuedAt: int | None = None
    expiresAt: int | None = None


# ============================================================================
# 微信登录相关模型
# ============================================================================

class QrCodeResponse(BaseModel):
    """获取微信二维码响应"""

    uuid: str
    imgUrl: str


class ScanStatusResponse(BaseModel):
    """扫码状态查询响应"""

    message: str | None
    code: str | None
    scanned: bool = False


class LoginRequest(BaseModel):
    """登录请求"""

    code: str


class LoginResponse(BaseModel):
    """登录响应"""

    success: bool
    session: TotoroSession | None
    message: str | None = None


# ============================================================================
# 跑步相关模型
# ============================================================================

class Point(BaseModel):
    """GPS 坐标点"""

    longitude: str
    latitude: str


class RouteInfo(BaseModel):
    """路线信息"""

    taskId: str
    pointId: str
    pointName: str


class RunPoint(BaseModel):
    """跑步任务中的路线点"""

    taskId: str
    pointId: str
    pointName: str
    longitude: str
    latitude: str
    pointList: list[Point]
    signLongitude: str | None = None
    signLatitude: str | None = None
    signQrcode: str | None = None


class RunPaperResponse(BaseModel):
    """获取今日跑步任务响应"""

    status: str | None = None
    code: str | None = None
    ifHasRun: str = "0"
    mileage: str = "3.20"
    minTime: str = "10"
    maxTime: str = "25"
    minSpeed: str = "3"
    maxSpeed: str = "15"
    startTime: str = "06:00"
    endTime: str = "23:00"
    offsetRange: str = "300"
    fitDegree: str = "0.60"
    runPointList: list[RunPoint] = []
    runTimeRuleList: list[dict[str, Any]] = []


class SubmitRunRequest(BaseModel):
    """提交跑步请求"""

    routeId: str | None = None
    distance: float | None = None
    startTime: str | None = Field(None, description="开始时间，格式 HH:MM")
    runDate: str | None = Field(None, description="跑步日期，格式 YYYY-MM-DD。为空则使用今天")
    durationMin: int | None = Field(None, description="跑步时长（分钟），默认15，范围13-23")


class SubmitRunResponse(BaseModel):
    """提交跑步响应"""

    success: bool
    scantronId: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


# ============================================================================
# 历史记录相关模型
# ============================================================================

class TermInfo(BaseModel):
    """学期信息"""

    termId: str
    termName: str
    isCurrent: str = "0"


class MonthInfo(BaseModel):
    """月份信息"""

    monthId: str
    monthName: str


class RunRecord(BaseModel):
    """跑步记录"""

    scoreId: str | None = None
    runDate: str | None = None
    mileage: str | None = None
    usedTime: str | None = None
    avgSpeed: str | None = None
    status: str | None = None


# ============================================================================
# API 通用响应包装
# ============================================================================

class ApiResponse(BaseModel):
    """通用 API 响应包装"""

    success: bool
    data: Any | None = None
    message: str | None = None
