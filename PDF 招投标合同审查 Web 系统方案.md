```markdown
# PDF 招投标合同审查 Web 系统方案

## 1. 项目目标

开发一个本地运行的 PDF 招投标合同审查 Web 系统，用于审查 PDF 合同的格式、公章、签名、骑缝章、关键条款和一致性，并输出可追溯的审查结果和报告。

系统优先处理本地文件，不依赖外部云服务。

## 2. 技术栈

| 模块 | 推荐技术 | 说明 |
|---|---|---|
| 前端 | Streamlit | 上传 PDF、查看审查结果、下载报告 |
| 后端 | FastAPI | 文件上传、任务管理、规则管理、结果查询 |
| 文档解析 | PyMuPDF / pdfplumber | 原生 PDF 文本、坐标、表格提取 |
| 扫描件解析 | PaddleOCR | 扫描/拍照 PDF 文字识别 |
| 版面分析 | PP-DocLayoutV3 | 识别标题、正文、表格、签名栏、印章区 |
| 签章检测 | YOLOv8 / Seal 检测 | 检测公章、签字、骑缝章 |
| 规则引擎 | Python + JSON/PostgreSQL | 存储审查规则，执行格式与完整性校验 |
| 大模型 | 本地 LLM / Agent | 生成风险提示、缺失项判断、修改建议 |
| 数据库 | PostgreSQL | 存储任务、规则、审查结果 |
| 部署 | Docker | 本地服务器部署，便于后续扩展 |

## 3. 系统目录结构

```text
contract-review/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── api/
│   │   │   ├── contracts.py
│   │   │   ├── rules.py
│   │   │   └── reports.py
│   │   ├── services/
│   │   │   ├── pdf_parser.py
│   │   │   ├── layout_analyzer.py
│   │   │   ├── seal_detector.py
│   │   │   ├── rule_engine.py
│   │   │   └── llm_reviewer.py
│   │   └── core/
│   │       ├── config.py
│   │       └── logger.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── ai-service/
│   ├── layout_service.py
│   ├── seal_service.py
│   ├── ocr_service.py
│   ├── requirements.txt
│   └── Dockerfile
├── data/
│   ├── uploads/
│   ├── results/
│   └── pgdata/
├── rules/
│   └── contract_rules.json
├── docker-compose.yml
└── README.md
```

## 4. 核心处理流程

1. 用户上传 PDF 合同。
2. 判断 PDF 是原生 PDF 还是扫描件。
3. 原生 PDF 使用 PyMuPDF / pdfplumber 提取文本、坐标、表格。
4. 扫描件使用 PaddleOCR 进行文字识别。
5. 使用 PP-DocLayoutV3 进行版面分析，识别标题、条款、表格、签名栏、印章区。
6. 使用 YOLOv8 / Seal 检测模型检测公章、签字、骑缝章。
7. 规则引擎检查格式、必填条款、签章位置、金额日期一致性。
8. 本地大模型基于结构化内容生成风险提示和修改建议。
9. 前端展示审查结果，支持高亮原文和下载报告。

## 5. API 接口设计

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/contracts/upload` | POST | 上传 PDF，创建审查任务 |
| `/api/contracts/{task_id}/analyze` | POST | 启动审查流程 |
| `/api/contracts/{task_id}/status` | GET | 查询任务状态 |
| `/api/contracts/{task_id}/result` | GET | 获取审查结果 |
| `/api/contracts/{task_id}/report` | GET | 导出审查报告 |
| `/api/rules` | GET | 获取审查规则列表 |
| `/api/rules` | POST | 新增或修改审查规则 |
| `/api/rules/generate` | POST | 自然语言生成规则 |
| `/api/rules/review` | POST | 审核并启用规则 |

## 6. 核心数据结构

### 审查任务

```json
{
  "task_id": "string",
  "file_name": "string",
  "file_path": "string",
  "pdf_type": "native | scanned",
  "status": "pending | parsing | analyzing | reviewing | completed | failed",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 审查结果

```json
{
  "task_id": "string",
  "page": "int",
  "category": "format | seal | signature | clause | consistency",
  "level": "high | medium | low",
  "message": "string",
  "suggestion": "string",
  "bbox": [x0, y0, x1, y1],
  "confidence": 0.92
}
```

### 审查规则

```json
{
  "rule_id": "string",
  "name": "string",
  "category": "format | seal | signature | clause | consistency",
  "enabled": true,
  "level": "high | medium | low",
  "description": "string",
  "check_type": "keyword | regex | bbox | clause | llm | numeric",
  "targets": ["string"],
  "condition": "all | any | none | equals | between",
  "scope": "full_text | signature_area | seal_area | table | page",
  "action": "missing_warning | format_error | seal_missing | inconsistency | custom",
  "message_template": "string",
  "suggestion_template": "string",
  "metadata": {
    "source_text": "string",
    "created_by": "llm | manual",
    "reviewed": false
  }
}
```

## 7. 审查规则库

### 格式审查

- 合同标题是否存在。
- 页码是否连续。
- 表格是否完整。
- 字体是否明显异常。
- 签章区是否预留空白。

### 公章与签名审查

- 是否检测到甲方、乙方签章区。
- 是否检测到红色印章区域。
- 签名栏是否为空。
- 骑缝章是否覆盖关键页。
- 印章文字是否与合同主体名称匹配。

### 条款审查

- 合同主体是否完整。
- 招标范围是否明确。
- 合同金额是否清晰。
- 付款方式是否明确。
- 工期、交付、验收条款是否存在。
- 违约责任、争议解决条款是否存在。

### 一致性审查

- 合同金额是否与招标/投标文件一致。
- 合同主体是否与招标主体一致。
- 日期是否合理。
- 签章位置是否与约定一致。

## 8. 自然语言规则生成规范

用户输入一段自然语言，本地大模型将其转换为可执行规则 JSON。该流程必须严格受控，避免无限循环、超时或自动重试。

### 执行顺序

```text
接收用户文本
  ↓
调用本地大模型，单次生成
  ↓
Pydantic 校验 JSON
  ↓
校验通过：返回候选规则，状态为未审核
  ↓
校验失败：返回错误字段和原因
  ↓
不再自动重试
```

### 强制规范

1. **单轮生成**：每次请求只调用一次模型，不自动进入多轮对话。
2. **结构化输出**：模型必须输出符合 JSON Schema 的规则对象。
3. **超时限制**：模型调用超时建议设为 10～15 秒，超时直接返回失败。
4. **最大重试次数为 0 或 1**：默认不重试；如需重试，最多 1 次，且不扩展上下文。
5. **禁止自动执行**：生成的规则默认 `reviewed: false`，必须人工确认后生效。
6. **禁止模型直接操作数据库**：模型只输出 JSON，写入由后端接口完成。
7. **禁止无限追问**：信息不足时返回 `insufficient_info`，不自动澄清。
8. **禁止自动合并规则**：每次生成只产生一条新规则，不自动修改已有规则。

### 失败处理

| 情况 | 处理方式 |
|---|---|
| 模型超时 | 直接返回超时错误 |
| 模型输出非 JSON | 返回解析失败 |
| JSON 字段缺失 | 返回校验错误 |
| 规则类型不支持 | 返回不支持类型 |
| 用户描述不足 | 返回补充问题列表 |
| 模型连续失败 | 不重试，提示人工编写规则 |

### 验收标准

- 用户输入一句话，系统最多调用一次模型。
- 模型超时或输出异常时，系统不会无限重试。
- 生成的规则必须经过人工确认才能生效。
- 模型不能直接写入数据库。
- 每次规则生成请求必须有明确的成功、失败或待审核状态。

## 9. 开发阶段与任务清单

### 阶段 0：项目初始化

- S0-1：创建项目目录结构。
- S0-2：初始化 Git 仓库。
- S0-3：编写 README 和基础配置文件。

验收标准：目录结构完整，项目可启动基础服务。

### 阶段 1：FastAPI 后端骨架

- S1-1：搭建 FastAPI 应用。
- S1-2：实现健康检查接口。
- S1-3：实现文件上传接口。
- S1-4：实现任务创建接口。

验收标准：可上传 PDF 并返回 task_id。

### 阶段 2：原生 PDF 解析

- S2-1：使用 PyMuPDF / pdfplumber 提取文本。
- S2-2：提取页码、坐标、字体信息。
- S2-3：提取表格结构。

验收标准：原生 PDF 可输出结构化文本和坐标。

### 阶段 3：扫描件 OCR 解析

- S3-1：接入 PaddleOCR。
- S3-2：实现扫描件文字识别。
- S3-3：输出带坐标的识别结果。

验收标准：扫描件 PDF 可输出文字和坐标。

### 阶段 4：版面分析

- S4-1：接入 PP-DocLayoutV3。
- S4-2：识别标题、正文、表格、签名栏、印章区。
- S4-3：输出带类别和坐标的版面元素。

验收标准：可识别合同主要版面元素。

### 阶段 5：签章检测

- S5-1：接入 YOLOv8 / Seal 检测模型。
- S5-2：检测公章、签字、骑缝章。
- S5-3：输出签章位置和置信度。

验收标准：可检测并定位公章和签名区域。

### 阶段 6：规则引擎

- S6-1：设计规则 JSON 结构。
- S6-2：实现格式审查规则。
- S6-3：实现签章审查规则。
- S6-4：实现条款审查规则。
- S6-5：实现一致性审查规则。

验收标准：可基于规则输出结构化风险点。

### 阶段 7：本地大模型审查

- S7-1：接入本地 LLM。
- S7-2：实现风险提示生成。
- S7-3：实现修改建议生成。
- S7-4：限制模型调用超时和重试次数。

验收标准：可生成风险提示和修改建议，且不会无限重试。

### 阶段 8：Streamlit 前端

- S8-1：实现 PDF 上传页面。
- S8-2：实现审查结果展示页面。
- S8-3：实现原文高亮展示。
- S8-4：实现报告下载功能。

验收标准：可上传 PDF 并查看审查结果。

### 阶段 9：数据库接入

- S9-1：设计 PostgreSQL 表结构。
- S9-2：实现任务持久化。
- S9-3：实现审查结果持久化。
- S9-4：实现规则持久化。

验收标准：任务和结果可写入数据库。

### 阶段 10：Docker 部署

- S10-1：编写后端 Dockerfile。
- S10-2：编写前端 Dockerfile。
- S10-3：编写 AI 服务 Dockerfile。
- S10-4：编写 docker-compose.yml。
- S10-5：完成本地部署验证。

验收标准：所有服务可通过 Docker 启动并正常运行。

### 阶段 11：自然语言规则生成与安全控制

- S11-1：设计规则 JSON Schema。
- S11-2：实现 `/api/rules/generate` 接口。
- S11-3：接入本地大模型，限制超时 15 秒。
- S11-4：实现 Pydantic 校验，禁止自动重试。
- S11-5：实现 `/api/rules/review` 审核接口。
- S11-6：实现规则启用/禁用接口。
- S11-7：增加失败日志和调用次数限制。

验收标准：

- 用户输入一句话，系统最多调用一次模型。
- 模型超时或输出异常时，系统不会无限重试。
- 生成的规则必须经过人工确认才能生效。
- 模型不能直接写入数据库。
- 每次规则生成请求必须有明确的成功、失败或待审核状态。

## 10. 里程碑计划

| 里程碑 | 覆盖阶段 | 交付物 |
|---|---|---|
| M1 | 阶段 0～1 | 项目骨架、文件上传、任务创建 |
| M2 | 阶段 2～3 | 原生 PDF 和扫描件解析 |
| M3 | 阶段 4～5 | 版面分析和签章检测 |
| M4 | 阶段 6 | 规则引擎输出风险点 |
| M5 | 阶段 7～8 | 本地大模型审查和前端展示 |
| M6 | 阶段 9～11 | 数据库、Docker 部署、自然语言规则生成 |

## 11. 风险与注意事项

- 合同文件属于敏感数据，所有处理应在本地完成。
- 大模型输出可能存在偏差，所有风险提示需人工复核。
- 签章真伪判断不能仅依赖图像检测，需结合业务确认。
- 规则生成必须经过人工审核后才能生效。
- 模型调用必须设置超时和重试上限，避免阻塞服务。
- 审查结果应保留原文页码和坐标，便于追溯。
```

