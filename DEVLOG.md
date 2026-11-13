## 2026-11-13 — 数据库迁移基线

- 目标：不再由 API `create_all` 隐式创建/变更 schema，为后续版本变更建立明确迁移入口。
- 改动：加入 Alembic 固定初始 schema revision；配置 API 容器先运行 `alembic upgrade head`；移除应用启动时 `create_all`；补充 SQLite batch migration 配置、Redis healthcheck 和迁移使用说明。
- 未完成/注意：迁移只面向空数据库。已有 `create_all` 开发库尚无安全 adoption/数据迁移方案；模型关系约束与后续 incremental migrations 仍需补齐。管理员口令哈希仍需从 SHA-256 改为 Argon2id。
- 验证：未运行测试（按用户要求）。
- 下一步：按迁移文件管理 schema 变更；安全迁移口令哈希和受控初始化；处理审查任务幂等与队列恢复。
