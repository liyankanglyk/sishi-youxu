# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

**四时有序 (sishi-youxu)** —— 基于艾森豪威尔矩阵的个人任务管理工具。当前进度：Phase 0~3 后端 + Phase 1 管理端前端完成；Phase 3 用户端前端、Phase 4~6 待开发。

- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + MySQL (aiomysql) + Redis
- **用户端**: Vue 3 + TypeScript + Vite + Pinia + Dexie.js（离线优先）
- **管理后台**: Vue 3 + Element Plus + ECharts
- **认证**: JWT（python-jose）+ bcrypt；多 Provider：password / phone_sms / email_code / wechat
- **移动端**: Capacitor 骨架占位（Phase 8）
- **E2E**: Playwright 骨架

环境要求：Python 3.12+（使用 conda 环境 `sishiyouxu_env`，**勿重复安装**）/ Node.js 20+ / MySQL 8.0+ / Redis 6.0+。

---

## 仓库结构

```
sishi-youxu/
├── backend/          # FastAPI 后端（端口 8000）
├── web/              # Vue 3 用户端（端口 3000）
├── admin/            # Vue 3 管理后台（端口 4000）
├── capacitor/        # Capacitor 移动端（占位）
├── e2e/              # Playwright E2E（占位）
└── docs/             # 11 份项目文档（必读）
```

Web/Admin 的 vite 代理已把 `/api` → `http://localhost:8000`。

---

## 常用命令

### 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env              # 默认 MySQL/Redis 在 127.0.0.1，连接失败也允许启动
python -m uvicorn src.main:app --reload --port 8000
```

启动后可访问：

- `http://127.0.0.1:8000/health` — 健康检查
- `http://127.0.0.1:8000/docs` — RapiDoc API 文档（中文友好，已替代 Swagger UI）

### 用户端

```bash
cd web
npm install
npm run dev      # 开发，端口 3000
npm run build    # 类型检查 + 生产构建（vue-tsc && vite build）
```

### 管理后台

```bash
cd admin
npm install
npm run dev      # 开发，端口 4000
npm run build
```

### 测试

```bash
cd backend
python scripts/run_tests.py      # 一键 pytest
# 或
python -m pytest tests -q
```

骨架阶段有 13 条烟雾测试（health / root / 业务模块端点 / 错误响应）。

### 操作数据库

更新`backend/scripts/init_db.sql`和`backend/scripts/seed.sql`，或者新增sql文件，告诉我来执行

---

## 后端架构要点

### 分层

```
API Route (src/apps/<user|admin>/api/v1/*.py)
    ↓
Service (src/apps/<user|admin>/services/*.py)
    ↓
Repository (src/repositories/*.py)
    ↓
Model (src/models/*.py → SQLAlchemy ORM)
    ↓
Database (MySQL via aiomysql, Redis 缓存)
```

每个新功能模块的标准目录：

```
src/apps/user/api/v1/<resource>.py        # 路由（@router.get/post/...）
src/apps/user/services/<resource>_service.py # 业务逻辑
src/apps/user/schemas/v1/                  # Pydantic DTO
```

`apps/user` 和 `apps/admin` 是两套独立的 FastAPI 路由器，都在 `src/main.py` 里以 `prefix=settings.API_V1_PREFIX`（默认 `/api/v1`）挂载。

### 统一响应与异常

响应外壳由 `src/core/response.py` 提供：

```python
ok(data)                  # {"success": True, "data": ...}
fail(code, message, detail)  # {"success": False, "error": {"code", "message", "detail"}}
```

业务层 **禁止** 直接 `raise HTTPException` —— 必须抛出 `src.core.exceptions.BusinessException` 子类（`NotFoundException` / `UnauthorizedException` / `ForbiddenException` / `ConflictException` / `RateLimitedException` / `ValidationException`），由 `BusinessExceptionMiddleware` 统一翻译为错误外壳。

错误码规范：`AUTH_INVALID_CREDENTIALS` / `TASK_*` / `TAG_*` / `SYNC_*` / `ADMIN_*` / `RATE_LIMITED` 等大写下划线。

### 中间件顺序（src/core/middleware.py）

外层 → 内层：`CORSMiddleware` → `BusinessExceptionMiddleware` → `RequestIDMiddleware`。
所有响应附带 `X-Request-ID`（取自 header 或自动生成）和 `X-Elapsed-ms`。

### 数据库模型

`src/models/base.py` 提供三个 mixin：

- `UUIDMixin` — 主键 `CHAR(36)` UUID4
- `TimestampMixin` — `created_at` / `updated_at`（UTC）
- `SoftDeleteMixin` — `deleted_at`（NULL = 存活）

表名统一前缀 `sishiyouxu_`（例：`sishiyouxu_task`、`sishiyouxu_tag`、`sishiyouxu_user`）。
外键用 UUID 字符串（**逻辑外键**，不在数据库层加 FK 约束）。
所有 ORM 通过 `src/models/__init__.py` 导入注册到 `Base.metadata`。

`src/repositories/base.py` 的 `BaseRepository[T]` 已自动给 `select` 注入 `WHERE deleted_at IS NULL`（仅当 model 含 `SoftDeleteMixin`）。

### JWT / 密码

`src/core/security.py`：

- `hash_password` / `verify_password`（bcrypt）
- `create_access_token` / `create_refresh_token` 返回 `(token, jti, expires_at)`
- `decode_token(token, expected_type=...)` 校验 `type` 字段

`src/core/deps.py` 提供 `DbSession` / `CurrentUser` / `AdminUser` / `RequiredUser` / `RequireAdmin` 等 FastAPI Depends。Phase 3 已替换为真实 JWT 解析（`get_current_user_optional` / `require_current_user` / `require_admin` / `get_ws_user`），从数据库校验用户状态、角色与 token 有效性。

### Redis

`src/core/redis.py`：

- `get_redis()` 返回共享 async client
- `build_key(*parts)` 自动加 `sishiyouxu:` 前缀
- Key 规范：`sishiyouxu:{功能}:{标识}`，必须设 TTL

### WebSocket

`src/main.py` 挂了两个 WebSocket（鉴权已用真实 ws-ticket，仅推送逻辑留待 Phase 5 接入）：

- `/ws/notifications`（用户端）— ws-ticket 一次性消费 + hello 握手 + ping/pong
- `/admin/ws/notifications`（管理端）— 同上

### 路由总览（102 条 = 100 HTTP 操作 + 2 WebSocket）

- 用户端（`/api/v1`）：`auth/*` `users*` `tasks*` `tags*` `notifications/*` `feedback` `sync/*` — 全部为真实业务
- 管理端（`/api/v1/admin`）：所有 100 个 HTTP 端点均为真实业务实现，无骨架占位。包括：`auth/*`（含 `/password` 修改管理员密码） `users*`（含 `/{uuid}/reset-password` 重置用户密码） `dashboard/stats|charts/{metric}` `audit/*` `feedback/*` `config` `sensitive-words/*` `security/ip-blacklist/*` `announcements/*` `login-logs` `tasks*` `tags*` `users/{uuid}/tasks|tags`

所有 service 均已为完整实现（无 `NotImplementedError`）：
- `AuthService` 797 行（多 Provider 注册/登录、刷新、登出、微信登录、ws-ticket、图形/短信/邮箱验证码、密码重置）
- `UserService` 440 行（资料、密码、头像、Provider 绑定/解绑、提醒渠道骨架）
- `TaskService` 731 行（任务 CRUD、批量、检查项、象限分组、重复任务生成）
- `TagService` 212 行（标签 CRUD、预设标签）
- `AdminService` 1,700+ 行（管理员认证、用户管理、仪表盘统计、审计日志、反馈管理、系统配置、内容管理、敏感词、IP黑名单、公告、密码修改、用户密码重置）

---

## 前端要点

`web/` 与 `admin/` 都是 Vue 3 + Vite + TypeScript 模板，共享：

- `@` → `src` 路径别名
- `/api` 代理 → `http://localhost:8000`

`web/src` 已布局：`api/` `components/` `composables/` `db/` `lib/` `stores/` `views/`
`web` 额外依赖 `dexie`（本地 IndexedDB 离线缓存）和 `@vueuse/core`。
`admin` 额外依赖 `element-plus` 和 `echarts`（仪表盘）。

### API 封装约定

统一用 `$fetch`（Nuxt 风格）或 axios 封装 `baseURL='/api/v1'`，按域模块导出：`taskApi` / `tagApi` / `userApi` 等，统一错误处理。

### 组件组织

```
components/
├── common/        # Button/Input/Modal
├── task/         # TaskCard/TaskList
├── quadrant/     # QuadrantCanvas
└── layout/      # Header/Sidebar
```

Pinia store 命名 `useXxxStore`，结构：`ref` 状态 + `computed` 派生 + `async actions`（含错误处理）。

---

## 命名与提交规范

| 类型 | 规范 |
|------|------|
| DB 表 | `sishiyouxu_` 前缀 + 下划线 |
| Python 模块 / 函数 | 全小写下划线 |
| Python 类 | CapWords |
| Vue 组件 | PascalCase |
| Pinia Store | `use` 前缀 |
| API 路径 | 下划线（`/auth/login`）|
| Redis Key | `sishiyouxu:{功能}:{标识}` |

Git 分支：`main` `develop` `feat/<name>` `fix/<name>` `hotfix/<name>`
提交格式：`<type>(<scope>): <description>`，type ∈ `feat/fix/docs/style/refactor/perf/test/chore`。

---

## 开发阶段（重要）

> 📌 2026-06-27 调整：采用**后端先行**策略 — 先完成所有后端 API，再做管理端前端，最后做用户端前端。

| Phase | 名称 | 状态 |
|-------|------|------|
| 0 | 项目骨架 | ✅ 已完成 |
| 1 | 管理端核心（后端 + 前端） | ✅ 已完成 |
| 2 | 用户端核心（后端 API：任务/标签/通知/反馈/同步） | ✅ 已完成 |
| 3 | 认证与同步（多渠道登录、离线同步） | ⚠️ 后端完成 / 前端 0% |
| 4 | 管理端增强（敏感词、IP黑名单、公告、登录日志、内容管理） | ✅ 后端完成 / 前端完成 |
| 5 | 用户端增强（批量、撤销重做、快捷键） | ❌ 未开始 |
| 6 | 测试与部署（单元/E2E/CI/CD） | ⚠️ 仅 13 条烟雾测试 |
| 7 | 微信小程序扩展 | ⏸ 远期 |
| 8 | 移动端（Capacitor） | ⏸ 远期 |

Phase 间有依赖，后 Phase 不可抢跑。详见 `docs/01-概览/开发阶段规划.md`。

---

## 关键文档（位于 `docs/`）

- `docs/01-概览/系统开发需求-完整版.md` ⭐ — 完整功能需求（P0/P1/P2）
- `docs/01-概览/开发阶段规划.md` ⭐ — Phase 0~8 详细计划（含实际完成度标注）
- `docs/01-概览/开发进度.md` — 当前代码完成度看板
- `docs/02-设计规范/用户端UI设计规范.md` ⭐ — 四象限主页 UI 规范
- `docs/03-技术架构/API接口文档.md` ⭐ — REST API 完整规范
- `docs/03-技术架构/数据库设计文档.md` — ER 图与表结构
- `docs/03-技术架构/技术规格.md` — 架构、Redis、JWT、限流
- `docs/03-技术架构/同步协议.md` — 离线同步协议
- `docs/04-工程与部署/工程指南.md` — 开发规范、测试、CI/CD
- `docs/04-工程与部署/服务器部署指南.md` — 生产环境部署（Nginx + Systemd + HTTPS）

修改接口、模型、字段时，先查对应文档保持一致；新增功能请同步更新 `docs/`。