# PDF 招投标审查系统

本仓库正在按《PDF 招投标审查系统技术方案与实施计划》中的首期目标实现一套可运行的工程骨架：

- 后端：FastAPI + SQLAlchemy + Pydantic
- 前端：React + TypeScript + Vite
- 数据库：PostgreSQL（Docker Compose）/SQLite（本地快速启动）
- 任务：登录、项目管理、PDF 上传、审查任务生成与结果展示
- 安全：统一 API 错误、鉴权、会话 Cookie / Bearer Token 方案

## 目录结构

- `backend/`：Python API 服务
- `frontend/`：React Web 应用
- `docker-compose.yml`：运行 PostgreSQL + Redis + API + Worker 容器
- `.env.example`：环境变量模板
- `README.md`：启动说明

## 运行前提

- Docker + Docker Compose（推荐）
- Python 3.11+
- Node.js 20+

## 快速启动（本地开发）

1. 初始化环境变量

```bash
cp .env.example .env
```

2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. 启动前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

4. 打开浏览器访问：

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8000/docs`

## 默认账号

- 用户名：`admin`
- 密码：`admin123`

## 生产/容器化启动

```bash
docker compose up --build
```

## 当前已实现内容

- 健康检查接口
- 登录接口与 JWT 认证
- 项目增删改查
- PDF 上传（本地文件存储，带 SHA-256 校验）
- 审查任务创建与 mock 结果
- React 前端登录和项目列表页
- 自动生成 OpenAPI 文档

## 后续规划

按照文档的阶段目标，后续将继续落地：

- 规则版本与执行器
- PDF 页面解析与 OCR 适配器
- 结果标注、人工复核与审计
- 报告生成与安全加固

