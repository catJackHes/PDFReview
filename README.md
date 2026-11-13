# PDF 招投标审查系统

本仓库按《PDF 招投标审查系统技术方案与实施计划》迭代，使用 FastAPI + SQLAlchemy 后端、React + TypeScript + Vite 前端。

## 当前阶段

MVP 原型支持项目/PDF 文件管理、页面预览与文本读取、规则审查雏形、人工复核/标注和 HTML/JSON 报告。OCR、生产级数据库迁移升级、任务幂等恢复及完整安全验收仍未完成。扫描件和无文本证据不得被自动视为通过；系统输出不能代替法律审查。

开发进度交接请优先阅读 [`DEVLOG.md`](DEVLOG.md)，每轮工作后追加简短记录。

## 本地开发

复制 `.env.example` 为 `.env`，将示例密钥和管理员口令替换为本地强随机值。首次启动时，只有配置 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD` 才会创建初始管理员；不开放公开注册。已有 SHA-256 口令在成功登录时会升级为 Argon2id。

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

浏览器访问 `http://localhost:5173`，API 文档为 `http://localhost:8000/docs`。
