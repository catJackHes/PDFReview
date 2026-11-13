# PDF 招投标审查系统

本仓库按《PDF 招投标审查系统技术方案与实施计划》迭代，使用 FastAPI + SQLAlchemy 后端、React + TypeScript + Vite 前端。

## 当前阶段

已具备 MVP 原型：项目与 PDF 文件管理、PDF 页面预览/文本读取、审查结果与人工复核/标注、基础报告接口、确定性规则引擎初步实现。OCR、生产级认证、迁移、队列和正式验收尚未完成；不能将当前结果视为法律意见或自动合规结论。

开发进度交接请优先阅读 [`DEVLOG.md`](DEVLOG.md)，每轮工作后追加简短记录。

## 本地开发

复制 `.env.example` 为 `.env`，设置强密钥与管理员口令。当前代码处于开发阶段，默认配置不可用于生产。

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
