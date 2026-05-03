"""微信登录 API - 实现完整的扫码登录流程"""

import asyncio
import hashlib
import re

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import (
    API_PREFIX,
    BASE_URL,
    DEFAULT_HEADERS,
    SESSION_FILE,
    WECHAT_QR_URL,
    WECHAT_SCAN_URL,
)
from backend.crypto import rsa_encrypt, try_decrypt_response
from backend.models import (
    LoginRequest,
    LoginResponse,
    QrCodeResponse,
    ScanStatusResponse,
    SessionWrapper,
    TotoroSession,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# 内存中临时存储扫码状态（生产环境应使用 Redis）
_scan_cache: dict[str, dict] = {}


# ============================================================================
# Step 1: 获取微信二维码
# ============================================================================

@router.get("/qr", response_model=QrCodeResponse)
async def get_wechat_qr() -> QrCodeResponse:
    """
    获取微信登录二维码。

    向微信服务器请求二维码页面，解析 HTML 提取 uuid 和二维码图片 URL。
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) "
                "AppleWebKit/600.1.4 (KHTML, like Gecko) "
                "Mobile/12A365 MicroMessenger/5.4.1 NetType/WIFI WebView/doc"
            ),
        }
        try:
            resp = await client.get(WECHAT_QR_URL, headers=headers)
            resp.raise_for_status()
            html = resp.text

            # 解析 uuid
            uuid_match = re.search(r'uuid:\s*"([^"]+)"', html)
            if not uuid_match:
                raise HTTPException(502, "无法解析二维码 UUID")
            uuid = uuid_match.group(1)

            # 解析二维码图片 URL
            img_match = re.search(r'auth_qrcode"\s+src="([^"]+)"', html)
            if not img_match:
                raise HTTPException(502, "无法解析二维码图片 URL")
            img_url = img_match.group(1)

            # 确保 URL 完整
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/"):
                img_url = "https://open.weixin.qq.com" + img_url

            # 缓存 uuid（用于后续轮询）
            _scan_cache[uuid] = {"status": "pending", "code": None}

            return QrCodeResponse(uuid=uuid, imgUrl=img_url)

        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"微信服务器错误: {e.response.status_code}")
        except Exception as e:
            raise HTTPException(500, f"获取二维码失败: {str(e)}")


# ============================================================================
# Step 2: 查询扫码状态（SSE 长轮询）
# ============================================================================

@router.get("/scan/{uuid}")
async def check_scan_status(uuid: str) -> ScanStatusResponse:
    """
    查询微信扫码状态。

    向微信长连接服务器轮询，检查用户是否已扫码。
    若已扫码，从返回的 URL 中提取 code。
    """
    cache = _scan_cache.get(uuid)
    if not cache:
        return ScanStatusResponse(message="二维码已过期，请重新获取", code=None)

    # 如果已经获取到 code，直接返回
    if cache.get("code"):
        return ScanStatusResponse(message=None, code=cache["code"], scanned=True)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        try:
            url = f"{WECHAT_SCAN_URL}?uuid={uuid}&f=url"
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text

            # 解析 code
            code_match = re.search(r"://oauth\?code=(\w+)&", text)
            if code_match:
                code = code_match.group(1)
                cache["code"] = code
                cache["status"] = "scanned"
                return ScanStatusResponse(message=None, code=code, scanned=True)

            # 未扫码或等待中
            return ScanStatusResponse(message="等待扫码...", code=None, scanned=False)

        except httpx.HTTPStatusError:
            return ScanStatusResponse(message="等待扫码...", code=None, scanned=False)
        except Exception as e:
            return ScanStatusResponse(message=f"查询失败: {str(e)}", code=None)


@router.get("/scan/{uuid}/sse")
async def scan_status_sse(uuid: str):
    """
    SSE 方式轮询扫码状态（前端实时推送）。

    每秒查询一次，直到扫码成功或超时（5分钟）。
    """
    async def event_generator():
        for _ in range(300):  # 最多 300 秒
            cache = _scan_cache.get(uuid)
            if not cache:
                yield "event: error\ndata: {\"message\": \"二维码已过期\"}\n\n"
                return

            if cache.get("code"):
                yield f"event: scanned\ndata: {{\"code\": \"{cache['code']}\"}}\n\n"
                return

            # 主动查询
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10) as c:
                    url = f"{WECHAT_SCAN_URL}?uuid={uuid}&f=url"
                    resp = await c.get(url)
                    text = resp.text
                    code_match = re.search(r"://oauth\?code=(\w+)&", text)
                    if code_match:
                        code = code_match.group(1)
                        cache["code"] = code
                        yield f"event: scanned\ndata: {{\"code\": \"{code}\"}}\n\n"
                        return
            except Exception:
                pass

            yield "event: heartbeat\ndata: {}\n\n"
            await asyncio.sleep(1)

        yield "event: timeout\ndata: {\"message\": \"扫码超时\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ============================================================================
# Step 3: 使用 code 完成龙猫登录
# ============================================================================

async def _call_totoro(endpoint: str, payload: dict, encrypted: bool = True) -> dict:
    """调用龙猫官方 API（带详细日志，用于调试）"""
    import logging

    logger = logging.getLogger("totoro")

    url = f"{BASE_URL}{API_PREFIX}/{endpoint}"
    headers = dict(DEFAULT_HEADERS)

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        if encrypted:
            body = rsa_encrypt(payload)
            # 与原项目保持一致：Content-Type 使用 application/json
            headers["Content-Type"] = "application/json; charset=utf-8"
            logger.info(f"[Totoro API] POST {url}")
            logger.info(f"[Totoro API] Payload: {payload}")
            logger.info(f"[Totoro API] Encrypted body (first 80 chars): {body[:80]}...")
            resp = await client.post(url, content=body, headers=headers)
        else:
            headers["Content-Type"] = "application/json"
            logger.info(f"[Totoro API] POST {url} (plaintext JSON)")
            logger.info(f"[Totoro API] Payload: {payload}")
            resp = await client.post(url, json=payload, headers=headers)

        logger.info(f"[Totoro API] Response status: {resp.status_code}")
        raw_text = resp.text
        logger.info(f"[Totoro API] Response text (first 200 chars): {raw_text[:200]}")

        resp.raise_for_status()
        result = try_decrypt_response(raw_text)
        logger.info(f"[Totoro API] Decrypted/parsed result: {result}")
        return result


@router.post("/login", response_model=LoginResponse)
async def login_with_code(req: LoginRequest) -> LoginResponse:
    """
    使用微信 code 完成龙猫校园登录。

    流程：
    1. getLesseeServer(code) → 获取 token
    2. login(token) → 获取用户信息
    3. 获取辅助信息（可选）
    4. 保存 session
    """
    code = req.code

    # Step 1: 用 code 换 token
    try:
        lessee_resp = await _call_totoro(
            "platform/serverlist/getLesseeServer", {"code": code}
        )
    except Exception as e:
        return LoginResponse(success=False, message=f"获取 token 失败: {e}", session=None)

    token = lessee_resp.get("token")
    if not token:
        msg = lessee_resp.get("message", "未知错误")
        return LoginResponse(success=False, message=f"微信授权失败: {msg}", session=None)

    # Step 2: 用 token 登录获取个人信息
    try:
        login_resp = await _call_totoro(
            "platform/login/login",
            {
                "code": "",
                "latitude": "",
                "loginWay": "",
                "longitude": "",
                "password": "",
                "phoneNumber": "",
                "token": token,
            },
        )
    except Exception as e:
        return LoginResponse(success=False, message=f"登录失败: {e}", session=None)

    # 构建 Session
    try:
        session = TotoroSession(
            stuNumber=str(login_resp.get("stuNumber", "")),
            stuName=login_resp.get("stuName"),
            schoolId=str(login_resp.get("schoolId", "")) if login_resp.get("schoolId") else None,
            schoolName=login_resp.get("schoolName"),
            campusId=login_resp.get("campusId"),
            campusName=login_resp.get("campusName"),
            collegeName=login_resp.get("collegeName"),
            phoneNumber=login_resp.get("phoneNumber"),
            token=token,
            serverPath=login_resp.get("serverPath", "https://app.xtotoro.com"),
            path=login_resp.get("path", "https://app.xtotoro.com"),
            newsUrl=login_resp.get("newsUrl"),
            useUrl=login_resp.get("useUrl"),
            registerUrl=login_resp.get("registerUrl"),
        )
    except Exception as e:
        return LoginResponse(
            success=False, message=f"解析用户信息失败: {e}", session=None
        )

    # Step 3: 调用辅助 API（可选，让服务端认为我们是正常客户端）
    try:
        basic_req = {
            "campusId": session.campusId or "",
            "schoolId": session.schoolId or "",
            "stuNumber": session.stuNumber,
            "token": session.token,
        }
        await _call_totoro("platform/login/getAppFrontPage", basic_req)
        await _call_totoro("platform/serverlist/getAppSlogan", basic_req)
        await _call_totoro(
            "platform/serverlist/updateAppVersion",
            {**basic_req, "version": "1.2.14", "deviceType": "2"},
        )
        await _call_totoro(
            "platform/serverlist/getAppNotice", {**basic_req, "version": ""}
        )
    except Exception:
        pass  # 辅助 API 失败不影响登录

    # 保存 session
    wrapper = SessionWrapper(
        success=True,
        session=session,
        issuedAt=int(asyncio.get_event_loop().time()),
    )
    _save_session(wrapper)

    return LoginResponse(success=True, session=session)


# ============================================================================
# Session 持久化
# ============================================================================

def _save_session(wrapper: SessionWrapper) -> None:
    """保存 session 到文件"""
    import json
    from pathlib import Path

    path = Path(SESSION_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wrapper.model_dump(mode="json"), f, ensure_ascii=False, indent=2)


def load_session() -> SessionWrapper | None:
    """从文件加载 session"""
    import json
    from pathlib import Path

    path = Path(SESSION_FILE)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SessionWrapper.model_validate(data)
    except Exception:
        return None
