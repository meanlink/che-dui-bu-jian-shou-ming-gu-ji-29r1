# 车队部件寿命估计

寿命建模的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
数据接入（JSON/CSV、字段验证、批次指纹）→ 参数化分析（异步 Python worker）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256）；另有业务总览和审计轨迹。
三个贯穿全栈的实体：Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Audit、Delivery。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18216；后端文档 http://localhost:19216/docs；数据库宿主端口 17716。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
角色在本车队内生效；同一账号可属于多个车队，登录后可切换。

|账号|密码|车队与真实权限|
|---|---|---|
|admin@demo.local|Demo123!|鹭湾业务负责人（也可切到青屿负责人）：接入、执行、批准、分发、暂停、成员与历史认领、读取与下载|
|analyst@demo.local|Demo123!|鹭湾分析员：接入、执行、读取与下载；不能批准、安排分发、管理成员或认领历史|
|viewer@demo.local|Demo123!|鹭湾观察员：只读与下载|
|owner@qingyu.local|Demo123!|青屿业务负责人|
|analyst@qingyu.local|Demo123!|青屿分析员|

## 车队隔离与历史迁移
样本、试算、简报计划、归档与审计均带所属车队；列表只返回本车队，按 id 跨队访问或下载一律拒绝（外部车队 id 视同不存在）。登录令牌绑定车队成员关系与版本号：移出成员立即作废其旧令牌，并在同一事务内停用该成员创建的待发简报；重新加入需重新登录。所有权限仍由服务端校验，页面仅隐藏入口。

迁移前旧数据统一封存（`fleet_id` 为空且带 `sealed_at`），不参与任何车队的列表、计算或投递，仅业务负责人可见。认领以数据批次为链根，整条链（批次→分析→计划→归档）在一个事务中迁移；已被其他车队持有的链路返回 409 且零变更，同一车队重复认领幂等、不重复迁移。真实容器、权限与截图结果统一记录在对应 `TESTING.md`，本说明不把未执行的检查写成通过。

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；PostgreSQL 16；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；JobStatus：queued/running/completed/failed。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py（`current_scope` 解析车队成员上下文），页面按相同角色控制操作入口。车队与成员模型在 backend/src/models/fleet.py，成员服务 backend/src/services/fleets.py，封存与认领 backend/src/services/legacy.py；前端成员页 frontend/src/pages/members.js、历史认领页 frontend/src/pages/legacy.js。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=fleet-weibull；FRONTEND_PORT=18216；BACKEND_PORT=19216；DB_PORT=17716；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。
运行隔离与迁移检查：`cd backend && python -m pytest tests -q`（使用临时 SQLite 库，不依赖容器）。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。容器内权限、迁移与截图等真实环境结果记录在对应 TESTING.md，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。
