"""Totoro Web 配置常量"""

# RSA 密钥对
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
************************************************
-----END PUBLIC KEY-----"""

PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
************************************************
-----END PRIVATE KEY-----"""

# API 基础配置
BASE_URL = "https://app.*******.com"
API_PREFIX = "/app"

# 微信登录配置
WECHAT_QR_URL = (
    "https://open.weixin.qq.com/connect/app/qrconnect"
    "?appid=********************"
    "&bundleid=(com.********.******)"
    "&scope=snsapi_userinfo"
    "&state="
    "&from=message"
    "&isappinstalled=0"
)
WECHAT_SCAN_URL = "https://long.open.weixin.qq.com/connect/l/qrconnect"

# 请求头
DEFAULT_HEADERS = {
    "User-Agent": "*********************************",
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Host": "app.xtotoro.com",
}

# Session 文件路径
SESSION_FILE = "data/session.json"

# App 版本
APP_VERSION = "1.2.14"
