# Totoro Web

南航龙猫校园，支持一天不同日期多次跑步，一天满足跑步需求

## 功能

- **微信扫码登录**：通过二维码获取微信授权，自动完成登录流程
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
6. 选择日历，选择路线，时间点，系统自动跑步


