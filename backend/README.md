# 四时有序 — Backend

FastAPI 后端服务。**三端兼容**：Web (Vue 3) / Capacitor (Android/iOS) / 微信小程序。

Phase 0~4 后端已全部完成：认证、用户管理、任务/标签 CRUD、同步引擎、管理端 API（含敏感词、IP 黑名单、公告、内容管理），共 98 个 HTTP 端点 + 2 个 WebSocket 端点。

---

## 目录结构

```
backend/
├── src/
│   ├── apps/
│   │   ├── user/          # 用户端 API
│   │   │   ├── api/v1/    #   auth / users / tasks / tags / sync / notifications / feedback
│   │   │   ├── schemas/v1/
│   │   │   └── services/
│   │   └── admin/         # 管理端 API
│   │       ├── api/v1/    #   auth / users / dashboard / audit / feedback / config
│   │       ├── schemas/v1/
│   │       └── services/
│   ├── core/              # 配置、数据库、Redis、安全、异常、响应、中间件
│   ├── models/            # SQLAlchemy ORM（16 张表）
│   ├── repositories/      # 数据访问层（含软删除基类）
│   └── utils/
├── scripts/
│   ├── init_db.sql        # DDL：建库 + 全部表 + 索引
│   ├── seed.sql           # DML：预设标签 / 权限矩阵 / 系统配置默认值
│   ├── init_admin.py      # 创建默认超管 admin / 123456
│   └── run_tests.py       # 一键 pytest 入口
├── tests/                 # conftest + 烟雾测试
├── requirements.txt
├── .env.example
└── README.md
```

---

## 快速启动

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 准备环境变量
cp .env.example .env
# 默认配置：MySQL/Redis 都在 127.0.0.1:3306 / 6379，连接失败也允许框架启动

# 3. 初始化数据库（含管理员账号 + 演示数据）
mysql -u root -p < scripts/init_db.sql
mysql -u root -p sishi_youxu < scripts/seed.sql

# 4. 启动
python -m uvicorn src.main:app --reload --port 8000
```

启动后访问：

- 健康检查：`http://127.0.0.1:8000/health`
- API 文档（RapiDoc）：`http://127.0.0.1:8000/docs`
- OpenAPI Schema：`http://127.0.0.1:8000/openapi.json`

> 启动时 MySQL/Redis 不可用也会继续启动（仅警告），方便先把前端/接口规范跑通。真正用到对应资源的接口在被调用时才会报错。

---

## 三端兼容要点

| 端 | 鉴权方式 | WebSocket | 时间校准 |
|---|---|---|---|
| Web (Vue 3) | `Authorization: Bearer <access_token>` | `wss://...?token=<ticket>` | `/api/v1/sync/status` |
| Capacitor | 同 Web（WebView 内） | 同 Web | 同 Web |
| 微信小程序 | `Authorization: Bearer <access_token>` | **`wx.connectSocket` 不支持 Header，必须用 ticket** | 同 Web |
| 管理端 | 同 Web + admin 角色 | `wss://.../admin/ws/notifications?token=<ticket>` | — |

### WebSocket ticket 流程（小程序关键）

```
1. 客户端：wx.login() → 拿到 access_token
2. 客户端：POST /api/v1/auth/ws-ticket  (Header: Authorization: Bearer <access_token>)
   服务端：返回 { ticket, expires_at, ws_url_template: "/ws/notifications?token={ticket}" }
3. 客户端：wx.connectSocket({ url: "wss://host/ws/notifications?token=<ticket>" })
   服务端：消费 ticket（GETDEL），握手成功
4. 心跳：客户端每 30s 发 "ping"，服务端回 "pong"
```

为什么不直接用 JWT？JWT 太长（>200 字符）会撑爆 URL，且无法在握手成功后立即撤销。ticket 一次性 + 60s TTL，用完即焚。

### 平台识别

请求带上 `X-Client-Platform: web | capacitor | miniapp`，便于审计/限流/敏感词过滤等按平台差异化处理；不传时按 `User-Agent` 启发式识别（`micromessenger` → `miniapp`）。

---

## 响应/错误格式

```jsonc
// 成功
{ "success": true, "data": { ... } }
// 失败
{ "success": false, "error": { "code": "AUTH_INVALID_CREDENTIALS", "message": "...", "detail": {} } }
```

所有路由统一由 `src.core.middleware.BusinessExceptionMiddleware` 包装；业务层应抛出 `BusinessException` 子类，**禁止**直接 `raise HTTPException`。

错误码前缀约定：`AUTH_` / `TASK_` / `TAG_` / `SYNC_` / `ADMIN_` / `WS_` / `RATE_LIMITED` / `VALIDATION_`。

---

## 已注册的路由（共 100 条 = 98 HTTP + 2 WS）

前缀：`/api/v1`

### 用户端
- **认证**：`/auth/tokens`（登录/刷新/登出/全设备登出）、`/auth/wechat/login`、`/auth/ws-ticket`、`/auth/captcha`（获取/校验）、`/auth/sms/*`、`/auth/email/*`、`/auth/password/*`、`/auth/login-methods`
- **用户**：`/users`（注册）、`/users/me`（信息/改密/头像/Provider 绑定解绑/提醒渠道）
- **任务**：`/tasks` CRUD + 批量 + 恢复 + 检查项子资源
- **标签**：`/tags` CRUD
- **通知**：`/notifications` 列表/未读数/标记已读/全部已读/删除
- **反馈**：`/feedback` 提交/查询
- **同步**：`/sync/push`、`/sync/pull`、`/sync/status`

### 管理端（`/admin`）
- **认证**：`/admin/auth/tokens`（登录/刷新/登出）
- **用户管理**：`/admin/users` 列表/详情/更新/删除/禁用启用/强制登出/批量/导出
- **仪表盘**：`/admin/dashboard/stats` + `/admin/dashboard/charts/{metric}`
- **审计**：`/admin/audit` 列表/详情
- **反馈**：`/admin/feedback` 列表/状态更新/删除
- **配置**：`/admin/config` 获取/更新
- **内容管理**：`/admin/tasks` 列表/详情/删除/批量、`/admin/tags` 列表/详情/编辑/删除
- **用户详情增强**：`/admin/users/{uuid}/tasks`、`/admin/users/{uuid}/tags`
- **敏感词**：`/admin/sensitive-words` CRUD + 批量导入
- **安全**：`/admin/security/ip-blacklist` CRUD
- **公告**：`/admin/announcements` CRUD
- **登录日志**：`/admin/login-logs` 列表

### WebSocket
- `/ws/notifications`（用户端）
- `/admin/ws/notifications`（管理端）

---

## 当前实现状态

| 模块 | 状态 | 说明 |
|------|:----:|------|
| AuthService | ✅ | 797 行 — 多 Provider 注册/登录/刷新/登出/微信/ws-ticket/验证码/密码重置 |
| UserService | ✅ | 440 行 — 资料/密码/头像/Provider 绑定解绑/提醒渠道 |
| TaskService | ✅ | 731 行 — 任务 CRUD/批量/检查项/象限分组/重复任务生成 |
| TagService | ✅ | 212 行 — 标签 CRUD/预设标签 |
| SyncService | ✅ | 完整实现 — push/pull/status（opId 幂等/增量拉取/时间校准） |
| AdminService | ✅ | 1,439 行 — 管理员认证/用户管理/仪表盘/审计/反馈/配置/敏感词/IP黑名单/公告/内容管理 |
| WebSocket 鉴权 | ✅ | ws-ticket 一次性消费 + hello 握手 + ping/pong |
| 提醒渠道 | ⬜ | GET/PATCH `/users/me/reminder-channels` 仍为骨架（Phase 5 待实现） |

---

## 测试

```bash
python scripts/run_tests.py
# 或
python -m pytest tests -q
```

已有 13 条烟雾测试（health、认证、业务模块端点、错误响应），全部通过。

---

## 环境变量（见 `.env.example`）

```
DATABASE_URL=                 # mysql+aiomysql://...
REDIS_URL=                    # redis://...
JWT_SECRET=                   # 必须改为强随机值
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
WS_TICKET_EXPIRE_SECONDS=60   # 一次性 ticket TTL
WX_APP_ID=                    # 微信小程序 appid
WX_APP_SECRET=                # 微信小程序 appsecret
WX_LOGIN_MOCK=true            # dev/test 默认 mock，生产必须 false
CORS_ORIGINS=["*"]
CORS_ALLOW_CREDENTIALS=false
SERVER_TIMEZONE=Asia/Shanghai
LOG_LEVEL=INFO
```
