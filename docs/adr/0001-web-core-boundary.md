# ADR-0001: Web 与科学核心边界

- 状态：已接受
- 日期：2026-08-27

## 决策

依赖方向固定为 `ssscreen_web -> ssscreen`。科学算法继续只存在于 `src/ssscreen/`；Web
后端通过公开 Python 函数调用科学核心，不以子进程包装 Click CLI。核心包不增加 FastAPI、
SQLAlchemy、Celery、Redis 或前端依赖。

## 结果

Web 后端使用独立 `web/backend/pyproject.toml`，可以独立演进控制层，同时保持 CLI 用户的
安装体积和科学测试边界不变。后续 StageRunner 必须位于 Web 应用/Worker 层。

