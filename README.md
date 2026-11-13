# PDF 招投标审查系统

本仓库按《PDF 招投标审查系统技术方案与实施计划》迭代，使用 FastAPI + SQLAlchemy 后端、React + TypeScript + Vite 前端。

## 当前阶段

MVP 支持项目/PDF 文件管理、页面预览与文本读取、规则审查雏形、人工复核/标注和 HTML/JSON 报告。纯扫描件 OCR 可选启用，采用本地 PaddleOCR CPU 适配器；默认关闭以避免未经样本/许可证确认即下载模型。OCR 输出仅为定位线索，需人工核验，不能替代法律审查。

开发进度交接请优先阅读 [`DEVLOG.md`](DEVLOG.md)，每轮工作后追加简短记录。

## 安装可选 OCR 依赖

OCR 依赖较大且需要模型，按目标 Python/CPU 平台核实 PaddlePaddle 安装方式和许可后安装：

```bash
cd backend
pip install -r requirements-ocr.txt
```

然后在 `.env` 中显式启用：

```dotenv
OCR_ENABLED=true
OCR_LANGUAGE=ch
OCR_DPI=180
OCR_MIN_TEXT_CHARS=24
```

首次初始化模型可能需要网络下载；内网/离线环境需按 PaddleOCR 官方方式预置模型并配置 `OCR_MODEL_DIR`。未启用、OCR 失败或无识别文本会保留页级状态并要求人工复核；系统不会将扫描页面静默报告为通过。

## 本地开发

复制 `.env.example` 为 `.env`，将示例密钥和管理员口令替换为本地强随机值。首次启动时，只有配置 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD` 才会创建初始管理员。

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

打开 `http://localhost:5173`，API 文档为 `http://localhost:8000/docs`。
