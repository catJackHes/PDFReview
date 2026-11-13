本轮完成：审查 API 现在创建快照并投递 Redis/RQ；Worker 独立会话执行规则并更新阶段/进度，保存证据和审计。补回审查历史/详情/结果查询路由，并修复先前提交的 requirements.txt 路径误覆盖（原文件内容实际被错误写入代码）。

注意：未运行测试（按用户要求）。Redis 不可用时，任务会持久化为 failed 并返回运行 ID/状态；启动 worker：`cd backend && python -m rq worker --url "$REDIS_URL" "$QUEUE_NAME"`。`Idempotency-Key` 目前记录在审查快照中，但还没有数据库唯一约束/重复请求回用，后续需迁移支持。