新增长期后台任务入口：API 将审查运行写入数据库后投递到 RQ，Worker 使用独立 SQLAlchemy 会话执行规则、持久化 finding/evidence 并更新运行阶段与进度。需要同时启动 Redis 和 Worker；本地 Worker 示例：

```bash
cd backend
python -m rq worker --url "$REDIS_URL" "$QUEUE_NAME"
```
