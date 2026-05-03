"""Totoro Web - FastAPI 入口"""

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.auth import router as auth_router
from backend.api.history import router as history_router
from backend.api.run import router as run_router
from backend.api.session import router as session_router
from backend.crypto import rsa_decrypt, rsa_encrypt, try_decrypt_response

# FastAPI 应用实例
app = FastAPI(
    title="Totoro Web",
    description="龙猫校园 Web 客户端 - Python 实现",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(auth_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(run_router, prefix="/api")
app.include_router(history_router, prefix="/api")

# 静态文件
_frontend_dir = Path(__file__).parent.parent / "frontend"
_static_dir = _frontend_dir / "static"

if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def root() -> FileResponse:
    """首页"""
    return FileResponse(_frontend_dir / "index.html")


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    """Favicon"""
    # 如果没有 favicon，返回空响应
    favicon_path = _frontend_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    from fastapi.responses import Response

    return Response(content=b"", media_type="image/x-icon")


# ============================================================================
# Debug 路由（用于诊断登录问题）
# ============================================================================

@app.post("/api/debug/rsa")
async def debug_rsa(data: dict) -> JSONResponse:
    """测试 RSA 加解密是否正确"""
    try:
        original = data.get("text", '{"test": "hello"}')
        encrypted = rsa_encrypt(original)
        decrypted = rsa_decrypt(encrypted)
        return JSONResponse(
            {
                "success": True,
                "original": original,
                "encrypted_preview": encrypted[:60] + "...",
                "decrypted": decrypted,
                "match": json.dumps(json.loads(original), sort_keys=True)
                == json.dumps(decrypted, sort_keys=True),
            }
        )
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/debug/login-raw")
async def debug_login_raw(data: dict) -> JSONResponse:
    """
    直接测试 getLesseeServer API，返回原始响应。
    用于诊断登录失败问题。
    """
    import httpx

    from backend.config import API_PREFIX, BASE_URL, DEFAULT_HEADERS

    code = data.get("code", "")
    if not code:
        return JSONResponse({"success": False, "error": "缺少 code 参数"})

    url = f"{BASE_URL}{API_PREFIX}/platform/serverlist/getLesseeServer"
    headers = dict(DEFAULT_HEADERS)
    headers["Content-Type"] = "application/json; charset=utf-8"

    payload = {"code": code}
    encrypted = rsa_encrypt(payload)

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.post(url, content=encrypted, headers=headers)

    return JSONResponse(
        {
            "success": True,
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "raw_text_preview": resp.text[:500],
            "raw_text_length": len(resp.text),
            "parsed": try_decrypt_response(resp.text),
        }
    )


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
