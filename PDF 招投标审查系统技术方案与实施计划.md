# PDF 招投标合同审查系统：技术方案、数据库/API 与实施验收补充

> 本文是《PDF 招投标合同审查 Web 系统方案》的实施级补充，细化技术架构、数据库/API、里程碑和验收标准。与主方案不一致时，以已确认的业务边界为准：项目制、多 PDF、支持扫描件、人工维护主体公司、页面证据标注和人工复核；系统只辅助审查，不作法律结论或印章真伪鉴定。

## 1. 技术方案

### 1.1 首期技术基线

| 层 | 建议方案 | 说明 |
|---|---|---|
| Web 前端 | React + TypeScript + Vite | 项目、文件、规则、审查结果和复核界面 |
| PDF 预览/标注 | PDF.js（`pdfjs-dist`）+ 独立 SVG/Canvas 标注层 | 支持页码导航、缩放、文本/矩形高亮、人工调整标注框 |
| API | Python + FastAPI + Pydantic | REST API、认证、输入校验及 OpenAPI 文档 |
| ORM/迁移 | SQLAlchemy 2.x + Alembic | 结构化数据和可追踪的数据库迁移 |
| 数据库 | PostgreSQL | 业务数据、规则版本、结果、复核和审计记录 |
| 后台队列 | Redis + RQ | PDF 解析、OCR、规则执行、报告生成；不使用第二套队列 |
| PDF 解析 | PyMuPDF | 文本、页面尺寸、旋转、渲染、文本坐标抽取 |
| OCR | PaddleOCR 本地适配器（经样本和部署环境验证后固定版本） | 扫描页/低文本层页面处理；保存版本、置信度和失败信息 |
| 文件存储 | 本地受控目录 | 原件、页图和报告；以随机存储键保存，数据库不存绝对路径 |
| 部署 | Docker Compose | Web、API、Worker、Redis、PostgreSQL；开发/生产配置分开 |

依赖必须固定版本并纳入 lock/约束文件。OCR 模型、语言包、中文字体及其许可、下载/离线安装方式应在部署说明中记录。首期无需 GPU 才能启动；若 OCR 在目标 CPU 上无法满足业务时限，再评估硬件或独立 OCR 服务。

### 1.2 模块边界

采用模块化单体，不因技术组件不同提前拆成微服务。建议后端按以下领域拆分：

- `auth`：单账号登录、会话和用户身份接口；不开放公开注册。
- `companies`：主体公司及允许名称/别名维护。
- `projects`：项目元数据和项目级主体公司。
- `files`：安全上传、文件类型、PDF 元数据和授权下载。
- `processing`：任务状态、解析、OCR、规则执行和报告生成。
- `rules`：规则定义、版本、适用文件类型和启停。
- `findings`：机器结果、证据定位和结果查询。
- `reviews`：人工结论、标注编辑和操作历史。
- `reports`：基于已保存审查结果生成 HTML/JSON 报告。

前端只经 API 访问业务数据和文件，不直连数据库或存储目录。Worker 通过共享应用服务和队列执行任务；PDF/OCR 处理置于非 root 容器，限制 CPU、内存、处理时长和临时文件空间。

### 1.3 文档处理流水线

1. 上传时检查扩展名、MIME、文件头、大小、PDF 可打开性、加密状态和页数上限；生成 UUID 存储名并计算 SHA-256。不得执行 PDF 脚本、附件或链接，不主动访问外部资源。
2. 创建处理任务及文件记录，使用幂等键避免客户端重试导致重复任务。明确记录已接收文件和失败原因。
3. 按页抽取文本、页面大小、旋转角度及文本块坐标。根据文本层质量识别原生页、扫描页或混合页；对扫描页和文本不足页运行 OCR。
4. 统一页码从 1 开始；证据框统一为 PDF 页面坐标，原点为旋转校正后的页面左上角，单位 point。前端将 PDF 坐标变换为屏幕坐标，缩放/旋转后仍须对齐。页面旋转、裁切框和高 DPI 渲染需有回归测试。
5. 依次运行公司名称、格式/完整性、条款/关键词、跨文件字段和签章线索规则。语义文本只作为定位/线索，确定性检查与图像识别结果分开记录。
6. 签章检查可组合：签章相关文字/签署区线索、疑似红色印章区域检测、按文件类型配置的强制要求（例如某文件每页应有章）。输出“检测到疑似区域/未检测到/无法判断”；区域完整性或红色像素特征只能作为线索，不表示印章真实、有效或法律上齐备。无稳定定位时创建无 bbox 的 finding，并要求人工核验。
7. 每次重新执行审查创建新的不可变 `review_run`，记录当时使用的规则版本、解析器/OCR 版本、文件 SHA-256 和配置快照。新运行不覆盖历史结果。
8. 报告仅从已保存的运行结果生成，不在下载时重新解析文件或重新调用模型。

推荐任务状态：`queued → validating → extracting → ocr → analyzing → reporting → completed`；可出现 `partial`（存在可见的部分结果）或 `failed`。各阶段应记录进度、错误码、可安全展示的错误信息和重试次数。OCR 个别页面失败不应丢弃同一文件的其他有效结果。

### 1.4 规则执行原则

- 规则采用版本化 JSON DTO；代码只执行白名单中的检查类型，禁止 `eval`、动态导入、任意 Python 代码和不受限正则。
- 规则版本包括名称、类别、适用文件类型、检查参数、预期条件、缺失/不一致时的提示、标签、严重程度和人工复核要求。
- 首期可以有全局默认规则模板，项目审查运行时记录所用版本；具体格式规范可在确认后配置为项目规则。默认规则不得冒称所有招投标项目都适用的官方规范。
- 规则变更产生新版本，不回写旧审查运行。修改规则后，用户需主动重新运行审查。
- OCR/视觉置信度是识别可信程度，不等于业务严重度；低置信度不能静默标为通过。

### 1.5 PDF 预览与标注

- PDF.js 负责页面渲染；SVG/Canvas 独立图层绘制自动证据框和人工标注，避免修改原 PDF。
- 标注记录保存 `page_number`、PDF 页面坐标 bbox、标注类型、标签、来源、创建/更新时间；页面显示坐标只在前端临时计算。
- 用户修改自动框时保留原始机器 bbox，并把调整后的 bbox 作为人工标注版本保存；机器原始结果不可被覆盖。
- 页面侧栏支持项目文件、页面和问题列表联动；点击 finding 跳至对应文件/页/区域。

### 1.6 登录、安全与运行

- MVP 支持单用户账号密码登录，账号通过受控初始化流程创建；禁止默认弱密码和公开注册。密码仅保存 Argon2id 哈希。
- 使用 HttpOnly、SameSite 会话 Cookie；生产 HTTPS 场景启用 Secure 与 CSRF 防护。登录失败限速，不在日志中记录密码、合同全文或敏感字段。
- API 从首期开始解析当前用户身份，并在项目、文件、报告查询中统一执行授权检查；后续多人化时可替换用户/角色实现，而不需重写业务接口。
- 上传大小、页数、解析时限、并发数和队列容量由配置决定；具体数值在目标机器和样本评测后确定，不在方案阶段虚构。
- 原件、渲染图和报告使用随机存储键并按项目分目录隔离；API 不暴露服务器绝对路径。配置文件、密钥、合同样本、模型权重和运行数据不得提交 Git。
- 失败重试有限且幂等；worker 重启可恢复排队任务。定期备份数据库并验证恢复，文件备份加密与数据保留期限需在上线前确认。

## 2. 数据库设计

### 2.1 关系概览

```text
users ──< projects >── companies
projects ──< project_files
projects ──< review_runs ──< findings ──< evidence
                         ├──< review_actions
                         └──< reports
rules ──< rule_versions ──< review_run_rules
project_files ──< file_pages ──< text_blocks
findings ──< annotations
users ──< audit_events
```

所有主键建议使用 UUID。时间统一保存 UTC `timestamptz`，API 以 ISO-8601 返回。数据库保存相对存储键，不存绝对文件路径或 PDF 二进制。

### 2.2 核心表

| 表 | 核心字段与用途 |
|---|---|
| `users` | `id`、`username`（唯一）、`password_hash`、`is_active`、`created_at`；首期单用户，保留扩展身份字段 |
| `companies` | `id`、`canonical_name`、`is_active`、`created_at`、`updated_at`；统一维护主体公司 |
| `company_aliases` | `id`、`company_id`、`alias_name`、`alias_type`、`is_approved`；保存经人工确认的名称变体 |
| `projects` | `id`、`name`、`description`、`subject_company_id`、`status`、`created_by`、时间戳；主体公司可空但空时名称比较需标为无法判断 |
| `project_files` | `id`、`project_id`、`file_type`、`display_name`、`storage_key`、`sha256`、`size_bytes`、`page_count`、`pdf_type`、`status`、`created_by`、时间戳；上传替换应新增记录而非覆盖原文件 |
| `file_pages` | `id`、`file_id`、`page_number`、`width_pt`、`height_pt`、`rotation`、`text_quality`、`ocr_status`、`render_storage_key`；唯一约束 `(file_id, page_number)` |
| `text_blocks` | `id`、`file_page_id`、`text`、`bbox`（JSON 数组/结构化数值）、`source`、`confidence`；保存必要的页面级识别结果，避免日志重复存全文 |
| `processing_tasks` | `id`、`project_id`、`file_id`（可空）、`task_type`、`status`、`progress`、`idempotency_key`、`attempt_count`、`error_code`、`safe_error_message`、时间戳 |
| `rules` | `id`、`stable_key`、`current_version`、`is_enabled`、时间戳；规则逻辑版本不直接覆盖 |
| `rule_versions` | `id`、`rule_id`、`version`、`name`、`category`、`applies_to`、`check_type`、`parameters` JSONB、`severity`、`message_template`、`suggestion_template`、`review_required`、创建人/时间；唯一约束 `(rule_id, version)` |
| `review_runs` | `id`、`project_id`、`status`、`started_at`、`completed_at`、`engine_version`、`config_snapshot` JSONB、`created_by`；每次执行独立留档 |
| `review_run_files` | `review_run_id`、`file_id`、`sha256_snapshot`、解析器/OCR 版本及文件角色快照；确保历史运行可追溯 |
| `review_run_rules` | `review_run_id`、`rule_version_id`、`config_snapshot` JSONB；明确运行时生效规则 |
| `findings` | `id`、`review_run_id`、`project_id`、`file_id`（跨文件问题可空）、`rule_version_id`、`category`、`status`、`severity`、`message`、`confidence`、`source`、时间戳 |
| `evidence` | `id`、`finding_id`、`file_id`、`page_number`、`text_excerpt`、`bbox` JSONB、`source`、`confidence`；一个 finding 可有多份文件/页面证据 |
| `annotations` | `id`、`finding_id`、`file_id`、`page_number`、`bbox`、`label`、`source`（machine/manual）、`supersedes_id`、`created_by`、时间戳；修改通过新增/版本关联留痕 |
| `review_actions` | `id`、`finding_id`、`actor_id`、`action`、`previous_status`、`new_status`、`remark`、`created_at`；追加写，不覆盖历史操作 |
| `reports` | `id`、`review_run_id`、`format`、`storage_key`、`sha256`、`created_at`；报告对应明确审查运行 |
| `audit_events` | `id`、`actor_id`、`action`、`resource_type`、`resource_id`、`metadata` JSONB（脱敏）、`created_at`；登录、上传、审查、人工操作、规则变更等事件 |

### 2.3 状态、约束与索引

- 文件类型：`contract`、`tender_document`、`bid_document`、`template`、`supplement`、`other`；可在后续增加字典表。
- PDF 类型：`native`、`scanned`、`mixed`、`unknown`。
- Finding 机器状态建议独立于人工复核状态，避免复核覆盖机器结论：`machine_result = detected | not_detected | uncertain`；`review_status = pending | confirmed_issue | confirmed_ok | unable_to_judge`。未定位的机器结果可没有 bbox，但必须说明原因。
- 对 `projects(created_at, status)`、`project_files(project_id, created_at)`、`review_runs(project_id, created_at)`、`findings(review_run_id, review_status, category)`、`audit_events(created_at)` 建索引。
- 对 `processing_tasks.idempotency_key` 建唯一索引（按用户/项目作用域）；对公司别名和用户名按规范化值建立唯一性约束。
- 外键使用明确删除策略。默认项目软删除或归档；物理删除需按保留策略清理原件、页图、报告和关联数据，并写审计事件。保留期限待业务确认。
- JSONB 仅用于规则参数、快照和灵活元数据；项目、状态、类型、时间、关系等核心字段应保持关系型字段，便于约束与查询。

### 2.4 历史一致性

审查运行需记录运行时输入快照：项目主体公司及名称别名、文件 SHA-256、文件类型、启用规则版本、解析/OCR 版本。用户后续修改公司别名或规则，不改变历史结果。重新审查创建新 `review_run`，报告始终绑定运行 ID。

## 3. API 设计

### 3.1 通用约定

- 前缀：`/api/v1`；JSON 使用 UTF-8；上传使用 `multipart/form-data`。
- UUID 用于资源 ID；时间为 ISO-8601 UTC；列表采用 `limit`、`cursor` 分页，并支持明确白名单过滤字段。
- 错误统一返回：`{"error":{"code":"...","message":"...","request_id":"..."}}`。不得将堆栈、服务器路径或合同正文放入错误响应。
- `POST` 创建/触发任务接受 `Idempotency-Key`；重复请求返回原资源/任务，不重复执行。
- 文件查看、页图、报告下载都走后端鉴权，不返回本地绝对路径或长期公开 URL。
- 写操作校验请求体并记录审计事件；所有项目资源均校验项目归属和调用者授权。

### 3.2 端点清单

| 方法与路径 | 用途 |
|---|---|
| `GET /health/live` | 存活检查 |
| `GET /health/ready` | 检查数据库、Redis/队列等依赖 |
| `POST /auth/login` | 单用户登录，创建受保护会话 |
| `POST /auth/logout` | 注销当前会话 |
| `GET /auth/me` | 当前用户信息/身份接口 |
| `GET /companies`、`POST /companies` | 公司列表与新增 |
| `PATCH /companies/{company_id}` | 编辑规范名称/状态 |
| `GET /companies/{company_id}/aliases`、`POST /companies/{company_id}/aliases` | 查询/新增允许名称变体 |
| `DELETE /companies/{company_id}/aliases/{alias_id}` | 停用或删除名称变体（按审计策略） |
| `GET /projects`、`POST /projects` | 项目列表/创建；支持名称、主体公司和备注 |
| `GET /projects/{project_id}`、`PATCH /projects/{project_id}` | 项目详情/修改 |
| `POST /projects/{project_id}/files` | 上传一个或多个 PDF；校验类型并创建解析任务 |
| `GET /projects/{project_id}/files` | 项目文件列表 |
| `GET /projects/{project_id}/files/{file_id}` | 文件元数据、解析和任务状态 |
| `DELETE /projects/{project_id}/files/{file_id}` | 移除文件；物理清理按保留策略执行 |
| `POST /projects/{project_id}/reviews` | 创建新的审查运行；可指定规则集/配置快照 |
| `GET /projects/{project_id}/reviews` | 项目审查运行历史 |
| `GET /projects/{project_id}/reviews/{run_id}` | 运行状态、进度及摘要 |
| `GET /projects/{project_id}/reviews/{run_id}/findings` | 分页获取结果，支持类别、文件、状态过滤 |
| `GET /projects/{project_id}/files/{file_id}/pages/{page}/image` | 授权后的页面预览图/渲染结果 |
| `GET /projects/{project_id}/files/{file_id}/pages/{page}/text` | 页面 OCR/文本块及坐标（按需授权） |
| `POST /findings/{finding_id}/actions` | 提交人工确认、驳回/确认无问题、无法判断和备注 |
| `POST /findings/{finding_id}/annotations` | 新增或调整页面标注框；不覆盖机器原始框 |
| `GET /findings/{finding_id}/history` | 查询该 finding 的人工操作历史 |
| `GET /rules`、`POST /rules` | 查询/创建规则 |
| `GET /rules/{rule_id}`、`PATCH /rules/{rule_id}` | 获取/创建新规则版本，不修改旧版本 |
| `GET /reports/{run_id}?format=html` | 生成或下载 HTML/JSON 已保存结果报告 |
| `GET /audit-events` | 管理端审计查询；首期可仅内部/受限使用 |

### 3.3 典型请求与响应

创建项目：

```json
{
  "name": "示例招投标项目",
  "description": "项目备注",
  "subject_company_id": "uuid"
}
```

上传文件：`POST /api/v1/projects/{project_id}/files`，每个文件有 `file_type` 和可选 `company_id_override`。只允许 PDF；服务端不得信任客户端文件名/MIME。

触发审查：

```json
{
  "file_ids": ["uuid", "uuid"],
  "rule_set": "default",
  "options": {"enable_ocr": true}
}
```

响应包含 `review_run_id`、`status`、`created_at`。运行状态接口返回总体及阶段进度；部分页失败应呈现 `partial` 和页级错误，而非隐藏错误。

结果示例：

```json
{
  "finding_id": "uuid",
  "review_run_id": "uuid",
  "file_id": "uuid",
  "category": "seal",
  "machine_result": "uncertain",
  "review_status": "pending",
  "label": "签章待核",
  "message": "在签署区域附近检测到疑似印章，请人工核验完整性。",
  "severity": "medium",
  "confidence": 0.72,
  "evidence": [{"page": 3, "text_excerpt": "盖章处", "bbox": [120, 350, 260, 470], "source": "ocr_and_vision"}],
  "engine_versions": {"ocr": "配置的版本", "rules": "配置的版本"}
}
```

人工复核请求：

```json
{
  "action": "confirmed_issue",
  "remark": "印章边缘被扫描裁切，需补充完整文件",
  "annotation": {"page": 3, "bbox": [118, 348, 264, 474]}
}
```

允许的动作包括 `confirmed_issue`、`confirmed_ok`、`unable_to_judge`、`update_annotation`。机器状态与人工状态分别保存；每次动作追加审计记录。

### 3.4 鉴权与 API 版本兼容

- 所有业务路由（除登录和健康检查）默认要求有效会话。
- 将当前用户封装为依赖注入的身份对象，后续可接入多用户、角色权限，而无需改变项目资源接口语义。
- API 采用 `/api/v1` 版本前缀；兼容性破坏变更增加新版本或明确迁移策略。
- OpenAPI 文档作为契约；前端类型可从 OpenAPI 生成，CI 检查接口模型一致性。

## 4. 开发里程碑与验收标准

各阶段使用脱敏且经授权的 PDF 样本。识别准确率、误报率、文件容量和性能阈值须根据阶段 0 样本、目标机器和业务方评估后确定，不预先虚构数值。每个阶段均要求自动化测试通过、迁移可重放、README 操作步骤更新。

### 阶段 0：需求基线与样本评估

**交付物**：文件类型字典、主体公司名称维护流程、规则模板初稿、脱敏样本集、目标部署环境和数据保留决策清单。

**验收**：每项首期检查都具有正例、反例、无法判断样例；确认主体公司与别名维护方式、签章要求按文件类型配置方式；确认 OCR/图像模型许可证、离线安装和硬件条件；记录尚未确定的容量指标及负责人。

### 阶段 1：工程骨架、登录、项目和上传

**交付物**：React/FastAPI 工程、Compose、数据库迁移、单用户登录、项目/公司维护、PDF 上传和任务状态。

**验收**：新环境按文档可启动；登录状态受保护且登出有效；可创建项目并绑定公司、上传多个 PDF 和选择文件类型；非 PDF、损坏、加密未授权、超限文件被拒绝并返回明确错误；同一幂等请求不会重复创建任务；数据和文件在服务重启后保持一致。

### 阶段 2：PDF 原生解析、扫描 OCR 与页面证据

**交付物**：逐页解析、PDF 类型识别、OCR 适配器、页面渲染、坐标转换和解析状态接口。

**验收**：原生、扫描、混合 PDF 均能产生逐页状态；扫描页支持 OCR；OCR 失败页保留失败原因并标记人工复核，其他成功页结果仍可用；页码从 1 开始；旋转页、多尺寸页和不同缩放下 bbox 叠加测试通过；日志无合同全文。

### 阶段 3：规则库与可追溯审查运行

**交付物**：受限规则 DTO/执行器、规则版本、公司名称检查、基础格式/页码规则、条款存在性和跨文件候选比对、签章线索接口。

**验收**：规则参数非法时拒绝保存；规则引擎不执行任意代码；运行记录固定输入文件哈希和规则版本；重新运行生成新运行，不覆盖旧结果；公司主体缺失、识别低置信度或文件缺失时返回无法判断/需复核；签章输出只使用疑似/未检测到/无法判断措辞，不宣称真伪或法律效力。

### 阶段 4：预览标注、人工复核和审计

**交付物**：PDF 页面预览、结果侧栏、标注图层、人工结论和操作历史。

**验收**：finding 可跳转到对应文件/页/定位框；自动标注与人工框区分显示；用户可以确认问题、确认无问题、无法判断、添加备注和调整框；机器原始状态及坐标保留，人工每次更改均有用户/时间/前后状态；未定位结果有明确“无可用定位”提示。

### 阶段 5：报告、历史记录和安全加固

**交付物**：HTML/JSON 报告、项目/审查历史、授权检查、限额、审计查询、备份恢复和部署手册。

**验收**：报告与对应 `review_run` 中保存的数据一致，显示文件、证据、机器结果、人工状态、规则/引擎版本和免责声明；下载/预览未授权时拒绝；路径穿越和恶意/异常 PDF 用例得到安全失败；worker 崩溃后队列任务可恢复且不会重复生成 findings；完成一次备份恢复演练；保留/删除策略由业务确认后实现。

### 阶段 6：内网试点与规则校准

**交付物**：试点部署、样本评测结果、已确认规则模板、问题清单和发布记录。

**验收**：业务方使用真实流程完成“创建项目—上传—自动审查—人工复核—导出报告”；评测按文件类型/原生与扫描/规则类别分别统计识别效果和无法判断比例；所有未达标能力降级为人工复核，不以单一汇总准确率掩盖漏报；依赖许可、离线部署、升级和回滚步骤通过检查。

### 上线发布门槛

- 安全上传、认证授权、路径隔离、错误脱敏和限额测试通过。
- 关键路径具备单元、集成和端到端测试；迁移可从空数据库执行。
- 页面 bbox 在规定样本的旋转、缩放和裁剪场景下正确定位。
- 低置信度、OCR 失败、无证据定位等情形不会被报告为“通过”。
- 人工复核和历史运行可审计；报告可复现到明确的文件哈希与规则版本。
- OCR/视觉检测的验收指标须由业务样本评测确定；未经验证的能力必须关闭或标为实验性。

## 5. 开发实施建议

1. 先完成阶段 0 的样本和规则确认，尤其明确“哪些文件/页必须签字盖章”与格式要求来源。
2. 采用单仓库或明确的前后端目录组织；CI 至少运行 Python lint/type/test、前端 lint/type/test、迁移检查和容器构建。
3. 先建立端到端数据契约与数据库迁移，再实现页面和 Worker，避免前后端分别定义不兼容状态。
4. 首期将规则检查和 OCR/视觉识别作为独立能力开关；无模型或模型失败时，系统仍可完成项目管理、原生 PDF 检查、人工复核和报告流程。
5. 以真实但脱敏的样本迭代规则，不依据市场通用描述宣称规范适用于所有招投标项目。

## 6. 仍需业务确认、但不阻塞架构的事项

以下内容不影响当前技术架构，可在阶段 0/试点前定案：

- 文件大小、页数、并发量和响应时间上限。
- 数据保留期限、历史项目删除及备份周期。
- 哪些具体文件类型、页面或签署区必须盖章/签字，以及按页强制盖章规则的适用范围。
- 正式格式规范原文、规则审核责任人及公司名称别名审核流程。
- PDF 报告是否在 HTML/JSON 后列入下一阶段。
- 目标硬件上的 OCR 模型版本、推理速度和业务验收阈值。
