# PDF 招投标合同审查 Web 系统方案

## 1. 项目定位与目标

建设一个可在本地服务器或可信内网运行的招投标合同辅助审查系统。系统支持上传招投标项目相关的 PDF 文件（如待审合同、招标文件、投标文件、模板、补充协议等），自动进行文本抽取、结构识别、规则检查和人工复核，并在 PDF 页面上进行问题标注和证据定位。

系统重点解决的问题不是代替法律意见，而是将“可验证事实”与“人工判断”分离：

- 能自动识别文档中是否存在特定文本、关键字段、签章区域和公司名称信息；
- 能明确标记“检测到/未检测到/无法判断”以及证据来源；
- 能将问题定位到具体页码、具体段落和页面坐标；
- 保留人工复核过程与审计记录，支持审查人员进行确认、驳回和补充说明。

系统定位为“辅助审查工具”，不是法律结论系统。OCR、版面分析、图像识别和模型输出均可能存在误差，因此所有结果都必须保留来源、置信度和人工可审查记录。

### 首期范围（MVP）

- 本地部署或可信内网部署；支持单用户登录，接口预留多用户能力。
- 一个招投标项目中可上传多个 PDF 文件，并为每份文件标注类别。
- 支持原生 PDF 和扫描版 PDF；扫描页需支持 OCR，识别失败时明确标记“需人工复核”。
- 支持可配置规则检查：公司名称规范性、签字/盖章齐备、格式/完整性、条款存在性、文件间一致性。
- 在 PDF 页面中直接显示问题高亮、圈注和标注框，用户可作人工确认/驳回。
- 可查看任务状态、历史项目、审查记录和导出 HTML/JSON 报告。

### 非目标与边界

- 不代替法律意见、印章真伪鉴定或签名人的身份识别。
- 不将机器识别结果直接等同于“法律风险结论”。
- 不在 MVP 中支持任意格式文档、多租户隔离、复杂审批流和互联网云模型调用。
- 视觉和 OCR 能力只允许输出“疑似存在/未检测到/无法判断”，不能宣称真伪或有效性。

## 2. 业务视角：项目制审查模型

本系统以“招投标项目”为核心单元，而不是单合同、单文件的离散任务。

### 2.1 项目结构

一个“项目”包含：

- 项目名称/时间/备注
- 项目描述
- 关联的多个 PDF 文件
- 文件类型（如待审合同、招标文件、投标文件、模板、补充协议等）
- 项目主体公司（统一维护、项目级绑定）
- 审查状态、创建时间、更新时间、历史版本

### 2.2 文件管理模型

每个文件应保存如下核心字段：

- file_id
- project_id
- original_name
- storage_name
- file_type
- sha256
- size
- page_count
- pdf_type: native | scanned | mixed | unknown
- parse_status
- ocr_status
- created_at
- updated_at

文件类型可以采用固定枚举，亦可保留扩展字段以支持后续定制化。首期建议预置：

- contract
- tender_document
- bid_document
- template
- supplement
- other

### 2.3 主体公司模型

为使公司名称检查稳定，增加统一公司主体维护模型：

- company_id
- company_name
- alias_names
- approved_name_variants
- created_by
- updated_at

项目上传文件时，可选择主体公司；必要时可在单个文件级别覆盖或补充说明。系统将以该主体名称作为比对来源，检查各类文件中的公司名称是否规范、是否一致、是否缺失。

## 3. 总体设计原则

采用“模块化单体 + 后台任务”的方式优先交付可靠的闭环。后续若出现并发增长、OCR 负载或多用户需求，再逐步拆分到独立服务。

### 3.1 总体架构

```text
浏览器 / 桌面客户端
        ↓
   React 前端
        ↓
   FastAPI API
   ├── 项目管理
   ├── 文件管理
   ├── 规则配置
   ├── 结果查询
   ├── 审核与标注
   └── 报告导出
        ↓
   PostgreSQL
   ├── 项目/文件/规则/结果/审计记录
   └── 任务元数据
        ↓
   Redis + RQ Worker
   ├── PDF 解析
   ├── OCR
   ├── 规则执行
   ├── 结果聚合
   └── 报告生成
        ↓
   本地文件存储
   ├── 原始 PDF
   ├── 页面渲染图
   ├── 标注图层
   └── 报告输出
```

### 3.2 设计原则

- 数据与业务逻辑分离：PDF 二进制不直接存入数据库。
- 规则可配置：规则是“受控的事实检查”，不是自动生成的法律结论。
- 所有识别结果均可追溯：保留文字、坐标、置信度和版本。
- 人工复核是闭环：系统提供“发现/未发现/无法判断”，人负责确认与结论修正。
- 安全优先：不执行 PDF 内嵌脚本、不自动访问外部资源、不暴露文件绝对路径。

## 4. 功能模块设计

### 4.1 项目与文件管理模块

功能目标：支持招投标项目的录入、上传、组织、查看与历史记录。

核心能力：

- 创建、编辑、删除项目
- 上传多个 PDF 文件
- 为文件标记类型、主体公司、是否需要签字/盖章
- 查看项目内文件列表、页数、解析状态和审查状态
- 历史版本与任务回放（后续增强）

建议实现：

- 项目列表页面：项目名、时间、状态、文件数
- 文件详情页面：文件类型、页数、解析质量、OCR 状态、审查结果数
- 项目编辑页面：项目名称、备注、主体公司、文件角色覆盖

### 4.2 PDF 解析与 OCR 模块

功能目标：提取可审查的结构化文本与坐标信息，支撑规则检查和标注。

能力要求：

- 解析原生 PDF 文本、页码、坐标、页面尺寸和旋转信息
- 扫描件与混合 PDF 需支持 OCR
- 记录识别状态、版本、置信度、失败原因
- 识别失败时必须明确标记“需人工复核”，不能默认为通过

示例字段：

- text_blocks: [{page, text, bbox, confidence, source}]
- ocr_status: success | failed | partial | skipped
- quality_flag: good | low_confidence | unreadable

### 4.3 规则引擎模块

功能目标：将审查规则实现为“可配置、可追踪、可解释”的结构化检查。此模块不执行任意代码，也不接收大模型直接生成的代码。

规则基础模型：

```json
{
  "rule_id": "uuid",
  "name": "公司名称一致性检查",
  "category": "company_name",
  "version": 1,
  "status": "draft | active | disabled",
  "scope": "project | file | page | region",
  "applies_to": ["contract", "tender_document", "bid_document"],
  "condition": {
    "type": "field_compare",
    "expected_value": "主体公司名称",
    "compare_mode": "exact | contains | alias_match"
  },
  "severity": "high | medium | low | info",
  "message_template": "公司名称与项目主体不一致",
  "suggestion_template": "请人工确认公司名称是否正确",
  "created_by": "user-id",
  "created_at": "ISO-8601"
}
```

建议规则类型：

- company_name
- signature
authentication
- seal
- format_structure
- page_number
- clause_presence
- cross_file_consistency
- custom_keyword

### 4.4 标注与人工复核模块

功能目标：在 PDF 页面上直观看到识别结果，并允许人工确认或调整���

核心能力：

- 在页面中圈选、绘制框、显示证据
- 高亮“缺章、缺签名、名称不一致、格式待核”等标签
- 用户可执行：确认问题、确认无问题、无法判断、添加备注
- 保存人工操作记录：修改人、修改时间、操作理由

结果状态建议：

- machine_flagged
- needs_manual_review
- confirmed
- dismissed
- unable_to_judge

示例：

- 检测到“疑似印章”但 OCR 不确定 → 结果标记为 `needs_manual_review`
- 人工确认后 → `confirmed`
- 用户判断不是问题 → `dismissed`

### 4.5 报告与留档模块

功能目标：形成审查结论并保留证据链、审计记录、人工确认痕迹。

首期建议输出：

- HTML 报告：适合浏览和打印
- JSON 报告：适合导出和二次处理
- PDF 报告：可作为后续增强功能（不在 MVP 一开始强制）

报告内容至少包括：

- 项目摘要
- 文件列表
- 检查规则版本
- 识别结果与证据
- 页面定位和截图/高亮信息
- 人工复核结果
- 免责声明

## 5. 审查规则与业务判断边界

### 5.1 公司名称检查

规则目标：检查项目中各文件的主体名称与统一维护的主体公司是否一致。

检查方式：

- 项目中统一维护主体公司和允许名称变体
- 识别各文件中出现的公司名称
- 对所有命中项做比对，标注不一致、缺失、别名不一致或无法判断

结果：

- company_name_match
- company_name_mismatch
- company_name_missing
- company_name_unconfirmed

注意：如果名称无法确认，默认标记为 `unconfirmed`，不能直接判定“合格”或“不合格”。

### 5.2 签字/盖章检查

规则目标：对文件中的签名、盖章区域或签署页进行检测，并提示是否齐备。

检查方式：

- 按文件类型和规则配置要求检查是否需要签字或盖章
- 对图像区域、文本上下文和页面特征进行检测
- 仅输出：检测到疑似区域、未检测到、无法判断

强制规则示例：

- 招标文件每页应有公章或专用章
- 合同签署页应存在签字和盖章
- 补充协议应盖章

注意：系统不得宣称“印章真实有效”，也不能判断“签字人身份”或“法律效力”。

### 5.3 格式/结构检查

规则目标：检查文件是否满足基本招投标文档结构要求。

示例检查项：

- 是否存在页码
- 是否存在章节标题/文件标题
- 是否有格式异常（页边距、分栏、空白页等）
- 是否存在空白页或解析失败页
- 是否存在明显结构缺失

结果：

- format_ok
- format_incomplete
- format_unconfirmed

### 5.4 关键条款检查

规则目标：检查文件是否具备招投标规则中规定的关键文本或条款。

示例：

- 合同主体信息是否出现
- 标的范围是否出现
- 付款方式/金额字段是否存在
- 期限、交付验收、违约责任等是否出现候选文本

输出：

- clause_detected
- clause_missing
- clause_unconfirmed

不做法律结论，不将关键词命中直接等同于条款有效。

### 5.5 跨文件一致性检查

规则目标：检查项目内多个文件的同类信息是否一致。

示例：

- 招标文件与投标文件/合同中的公司名称是否一致
- 关键字段的金额、日期、期限是否一致
- 存在缺失、单位不同或低置信度时输出“无法判断”

输出：

- consistent
- inconsistent
- missing_reference
- unable_to_judge

## 6. 数据模型补充

### 6.1 项目模型（Project）

```json
{
  "project_id": "uuid",
  "project_name": "string",
  "status": "draft | in_review | completed | archived",
  "owner_id": "uuid",
  "subject_company_id": "uuid|null",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### 6.2 文件模型（ProjectFile）

```json
{
  "file_id": "uuid",
  "project_id": "uuid",
  "file_type": "contract | tender_document | bid_document | template | supplement | other",
  "original_name": "string",
  "storage_name": "string",
  "sha256": "string",
  "size": 0,
  "page_count": 0,
  "pdf_type": "native | scanned | mixed | unknown",
  "parse_status": "pending | success | failed",
  "ocr_status": "pending | success | failed | partial",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### 6.3 审查结果模型（Finding）

```json
{
  "finding_id": "uuid",
  "project_id": "uuid",
  "file_id": "uuid|null",
  "rule_id": "uuid|null",
  "rule_version": "integer|null",
  "category": "company_name | signature | seal | format | clause | consistency",
  "severity": "high | medium | low | info",
  "status": "machine_flagged | needs_manual_review | confirmed | dismissed | unable_to_judge",
  "message": "string",
  "evidence": [{
    "page": 1,
    "text": "原文片段",
    "bbox": [0, 0, 100, 40],
    "source": "ocr | text_layer | manual"
  }],
  "suggestion": "string|null",
  "confidence": 0.0,
  "created_at": "ISO-8601"
}
```

### 6.4 审核操作模型（ReviewAction）

```json
{
  "review_id": "uuid",
  "finding_id": "uuid",
  "user_id": "uuid",
  "action": "confirm | dismiss | unable_to_judge | update_annotation",
  "remark": "string|null",
  "updated_at": "ISO-8601"
}
```

## 7. API 设计（简化版）

统一前缀 `/api/v1`。

| 路径 | 方法 | 说明 |
|---|---|---|
| `/health/live` | GET | 进程存活检查 |
| `/health/ready` | GET | 检查数据库/队列等依赖 |
| `/projects` | POST | 创建项目 |
| `/projects/{project_id}` | GET | 项目详情 |
| `/projects/{project_id}/files` | POST | 上传 PDF 文件 |
| `/projects/{project_id}/files` | GET | 文件列表 |
| `/projects/{project_id}/files/{file_id}` | GET | 文件详情 |
| `/projects/{project_id}/results` | GET | 查询审查结果 |
| `/projects/{project_id}/report` | GET | 导出 HTML/JSON 报告 |
| `/rules` | GET | 查询规则列表 |
| `/rules` | POST | 创建/编辑规则 |
| `/rules/{rule_id}` | PATCH | 更新规则版本 |
| `/review/finding/{finding_id}` | POST | 人工确认/驳回/无法判断 |
| `/annotation/{file_id}` | POST | 保存页面高亮和标注信息 |

特别说明：本阶段仅做单用户登录和内网部署，API 层保留 user_id、owner_id、role_id 等字段，用于后续扩展多人、多角色权限。

## 8. 技术选型建议

### 8.1 前端

推荐：React + PDF.js

理由：

- 支持 PDF 预览和高亮框
- 支持页面标注、缩放、拖动、圈选和批注
- 更适合审查类产品的交互需求
- 比 Streamlit 更适合精细化人工核验工作流

### 8.2 后端

推荐：FastAPI + Pydantic + SQLAlchemy + PostgreSQL

理由：

- 接口清晰，适合 OpenAPI
- 有良好的任务和规则管理能力
- 数据库成熟，适合审计和版本追踪

### 8.3 任务处理

推荐：Redis + RQ

理由：

- 适合本地部署和单机/内网环境
- 更容易做幂等、重试和任务状态管理
- 简单、轻量、便于维护

### 8.4 PDF 与 OCR

- 原生 PDF：PyMuPDF
- OCR：可选接入 PaddleOCR 或其他本地 OCR 组件
- 输出：文本、bbox、置信度、版本、失败原因

## 9. 处理流程与状态机

### 9.1 项目与文件处理流程

1. 用户创建项目
2. 上传 PDF 文件并标注文件类型/主体公司
3. API 校验大小、文件头、PDF 合法性、页数限制
4. 任务进入 `queued`
5. Worker 执行：校验 → 解析 → OCR → 规则检查 → 报告生成
6. 每个阶段记录状态和错误信息
7. 结果可在前端查看并进行人工复核
8. 导出 HTML/JSON 报告

状态参考：

`queued -> validating -> extracting -> ocr -> analyzing -> reviewing -> reporting -> completed`

失败时转 `failed`，并保留错误码和失败原因。

### 9.2 结果状态机

- `machine_flagged`
- `needs_manual_review`
- `confirmed`
- `dismissed`
- `unable_to_judge`

人工复核会保留审计记录：

- 谁确认/驳回
- 何时操作
- 备注说明
- 结果如何变更

## 10. 安全与可靠性要求

- 默认仅绑定本机/内网，不开放公网
- 上传前校验文件大小、页数、扩展名、MIME、文件头、PDF 合法性
- 不执行 PDF 内嵌脚本、不访问外部资源
- 页面下载和报告下载必须校验权限
- 日志仅记录任务 ID、阶段、耗时、错误码和必要诊断信息
- 不记录合同全文、敏感字段、密钥
- 保留文件、渲染图和报告的清理策略
- 任务具有幂等支持和有限重试

## 11. MVP 发布门槛

### M1：项目与上传闭环

- 新环境可复现部署
- 可创建项目、上传 PDF、标注文件类型
- 非 PDF/超限文件被拒绝
- 任务状态可跟踪

### M2：解析与审查闭环

- 原生 PDF 文本提取可追溯
- OCR 扫描件可使用
- 规则检查至少覆盖：公司名称、签章/盖章线索、基础格式和页码检查
- 结果可定位到页码和证据文本

### M3：人工复核与报告

- 页面预览可高亮定位
- 人工确认/驳回/无法判断可执行
- HTML/JSON 报告可导出
- 审计记录可查询

### M4：安全与试点

- 权限、日志、文件保留和备份策略完善
- 内网用户试点通过
- 常见恶意文件和扫描失败情况处理正常

## 12. 风险与应对

| 风险 | 应对 |
|---|---|
| OCR 文本误差造成漏报 | 低置信度和失败显式标记，页面交给人工复核 |
| 把关键词命中误作结论 | 结果仅描述“检测到/未检测到/无法判断”，不输出法律结论 |
| PDF 恶意文件或资源耗尽 | 限制大小/页数/内存/处理时间，并隔离 Worker |
| 工具误判签章/盖章 | 仅标注疑似区域，不判真伪、不做法律效力判断 |
| 数据泄露 | 仅内网部署、最小权限、日志脱敏、文件定期清理 |
| 项目范围过大 | 把规则与功能分阶段实施，MVP 仅保留最关键能力 |

## 13. 后续扩展能力

### 13.1 多人使用

在数据模型和接口层预留用户 ID、角色和权限字段，后续可扩展：

- 审查员
- 规则维护员
- 规则审核员
- 管理员

### 13.2 更多 OCR/视觉能力

- 章、签名区域检测
- 扫描件低置信度筛查
- 表格结构识别
- 文档版面分类

### 13.3 模型协助

- 后续可作为建议生成器，不直接参与规则执行和数据库写入
- 模型输出必须结构校验、人工审核、版本化回退、独立开关

## 14. 最终结论

本方案的核心价值在于：

- 让招投标项目审查从“单纯抽取文本”提升为“可追溯、可审计、可人工复核”的闭环管理系统；
- 用规则化检查和页面级证据定位替代不透明的“黑盒判断”；
- 在不冒法律风险、不制造误判的前提下，支持内部审查、规范化留档和后续扩展。

该方案适合用于本地部署、可信内网、招投标文件审查的 MVP 版本，并且为多人权限、OCR 扩展、视觉检测和模型辅助能力保留了良好的技术演进路径。

## 15. 备注

在本次确认中，关键结论已经确定：

- 项目制管理：接受
- 多 PDF 任务：接受
- 扫描PDF 必须支持：接受
- 公司名称统一维护与项目绑定：接受
- 签字/盖章只提示“疑似区域/未检测到”：接受
- 页面高亮标注和人工复核：接受
- 历史记录后续再完善：接受

因此，本方案可以作为后续开发的正式基线版本。
