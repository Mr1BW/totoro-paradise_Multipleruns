# Totoro Web

Python + FastAPI 实现的龙猫校园 Web 客户端，支持微信扫码登录和跑步数据模拟。

## 功能

- **微信扫码登录**：通过二维码获取微信授权，自动完成登录流程
- **Session 管理**：基于 session.json 模板结构，持久化用户会话
- **跑步模拟**：生成 GPS 轨迹并提交跑步记录
- **历史查询**：查看学期、月份、历史跑步记录

## 快速开始

```bash
# 使用 uv 安装依赖
uv sync

# 启动服务
uv run python -m backend.main

# 或使用 uvicorn
uv run uvicorn backend.main:app --reload --port 8000
```

## 登录流程

1. 访问 `http://localhost:8000`
2. 页面显示微信登录二维码
3. 使用微信扫码
4. 点击"确认登录"按钮
5. 系统自动完成：
   - 获取微信 code
   - 换取龙猫 token
   - 登录获取个人信息
   - 保存 session 到 `data/session.json`

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端首页 |
| GET | `/api/auth/qr` | 获取微信二维码 |
| GET | `/api/auth/scan/{uuid}` | 查询扫码状态（SSE 轮询） |
| POST | `/api/auth/login` | 使用 code 完成登录 |
| GET | `/api/session` | 获取当前 session |
| DELETE | `/api/session` | 清除 session |
| GET | `/api/run/paper` | 获取今日跑步任务 |
| POST | `/api/run/submit` | 提交跑步记录 |
| GET | `/api/history/terms` | 获取学期列表 |
| GET | `/api/history/arch` | 获取历史记录 |

## 项目结构

```
totoro-web/
├── backend/
│   ├── main.py          # FastAPI 入口
│   ├── models.py        # Pydantic 模型 / Session 模板
│   ├── config.py        # 配置常量
│   ├── crypto.py        # RSA 加密解密
│   └── api/
│       ├── auth.py      # 微信登录
│       ├── run.py       # 跑步相关
│       └── session.py   # Session 管理
├── frontend/
│   ├── index.html       # 主页面
│   └── static/
│       ├── app.js       # 前端逻辑
│       └── style.css    # 样式
├── data/
│   └── session_template.json  # Session 模板
└── pyproject.toml
```

## License

AGPL-3.0
