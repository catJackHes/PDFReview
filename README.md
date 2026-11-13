# PDF 招投标审查系统

本仓库按技术方案逐步实现本地运行的 PDF 辅助审查系统。当前是开发/MVP 阶段：包含项目与文件管理、PyMuPDF 页面预览与文本读取、后台 RQ 审查任务、人工复核/标注和 HTML/JSON 报告入口。

## 数据库迁移

新数据库由 Alembic 管理。Compose 启动 API 前会执行 `alembic upgrade head`。开发环境可手动执行：

```bash
cd backend
alembic upgrade head
```

当前初始迁移面向空数据库。原先由 `create_all` 创建的开发数据库应先备份；请勿直接在有重要数据的数据库上执行初始迁移。迁移与既有 schema 对齐策略后续补充。

## 开发交接

每轮变更、当前限制和下一步记录在 [`DEVLOG.md`](DEVLOG.md)，新会话请先读该文件再检查相关代码。

## 运行

```bash
cp .env.example .env
# 编辑 .env 设置足够强的 SECRET_KEY 和 ADMIN_PASSWORD
docker compose up --build
```

打开 `http://localhost:8000/docs`。前端仍按 frontend 目录的 Vite 开发方式单独运行。

> 当前 OCR 尚未接入；文本关键词规则不适用于纯扫描件。规则结果只辅助定位和复核，不是法律意见或自动合规结论。当前尚未运行自动化测试。
