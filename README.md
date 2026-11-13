# PDF 招投标审查系统

本仓库按《PDF 招投标审查系统技术方案与实施计划》迭代，当前开发分支实现 FastAPI + SQLAlchemy 后端和 React + TypeScript + Vite 前端基础流程。

## 当前能力

- 登录后访问项目、文件和审查结果
- 上传 PDF 并记录 SHA-256、页数与 PDF 类型
- 创建审查运行并查询 Finding / Evidence
- 人工复核：确认问题、确认无问题、无法判断；保存备注及历史记录
- 导出 JSON / HTML 审查报告
- Docker Compose 配置 PostgreSQL、Redis、API 和 Worker

## 本地开发

复制 `.env.example` 为 `.env` 并设置强密钥和管理员密码。当前后端示例开发配置使用环境变量初始化单一管理员，不开放公开注册。

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`，API 文档位于 `http://localhost:8000/docs`。

> 当前规则结果/部分识别证据仍为演示性实现，不能替代业务审查或法律意见。上传与解析验收应使用已授权、脱敏的 PDF 样本。
