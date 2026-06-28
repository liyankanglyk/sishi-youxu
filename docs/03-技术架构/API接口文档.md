# API 接口文档

> 📌 本文档与代码（FastAPI 自动生成的 OpenAPI 规范）严格对齐。每次后端路由变更后，请同步更新本文件及 [`同步协议.md`](./同步协议.md)。
>
> **基础信息**
> - 基础路径：`/api/v1`（统一前缀，由 `main.py` 挂载）
> - 总端点数：**98 条 HTTP 操作 + 2 条 WebSocket（共 100 路由）**（用户端 51 + 管理端 45 + 元端点 2 + WebSocket 2；其中 13 条管理端 skeleton 占位待 Phase 4 实现）
> - 文档生成：`/docs`（RapiDoc，中文友好）/ `/openapi.json`（OpenAPI 3.1 规范）
> - 健康检查：`GET /health`（无需鉴权，DB/Redis 状态独立于启动探测）
> - 当前服务：四时有序 v0.x — Phase 0~3 后端完成（98 HTTP 操作全部真实业务逻辑）；用户端前端、管理端前端（Phase 4~5）待开发

---

## 目录

1. [请求规范](#请求规范)
2. [响应格式](#响应格式)
3. [幂等性](#幂等性)
4. [HTTP 状态码](#http-状态码)
5. [业务错误码](#业务错误码)
6. [统一响应外壳与中间件约定](#统一响应外壳与中间件约定)
7. [鉴权与依赖项](#鉴权与依赖项)
8. [用户端 API](#用户端-api)
   - 1) 认证（auth）— 15 条
   - 2) 用户资料（users）— 11 条
   - 3) 任务（tasks）— 7 条
   - 4) 检查项（checklist）— 4 条
   - 5) 标签（tags）— 4 条
   - 6) 通知（notifications）— 5 条
   - 7) 反馈（feedback）— 2 条
   - 8) 同步（sync）— 3 条
9. [管理端 API](#管理端-api)
   - 1) 管理员认证 — 4 条
   - 2) 用户管理 — 11 条
   - 3) 仪表盘 — 2 条
   - 4) 审计 — 3 条
   - 5) 反馈 — 3 条
   - 6) 系统配置 — 2 条
   - 7) 内容管理（任务/标签）— 10 条
   - 8) Phase 4 占位（skeleton）— 12 条
10. [元端点 / 健康检查](#元端点--健康检查)
11. [WebSocket](#websocket)
12. [限流](#限流)
13. [OpenAPI / RapiDoc](#openapi--radoc)
14. [接口总览（102 条）](#接口总览102-条)

---

## 请求规范

| 项 | 说明 |
| --- | --- |
| `Content-Type` | 除文件上传外一律 `application/json; charset=utf-8` |
| `Accept-Language` | 可选，默认 `zh-CN` |
| `Authorization` | `Bearer <access_token>`（除公开端点外所有路由均要求） |
| 时间戳 | ISO 8601 字符串，**UTC**（前端按本地时区展示） |
| 字段命名 | JSON 入参 / 响应统一 **camelCase**；DB 字段为 snake_case；ORM→API 由 Service 层转换 |
| 路径参数 | UUID v4 字符串 |

---

## 响应格式

### 成功

```json
{
  "success": true,
  "data": { /* 业务数据 */ }
}
```

- `data` 类型：
  - 资源对象（单条）
  - `{ "items": [...], "meta": { "total", "page", "pageSize", "hasMore" } }`（列表分页）
  - `null`（删除成功 / 无返回体的成功操作）
- 列表分页默认 `page=1, pageSize=20, pageSize ∈ [1, 100]`
- 写入响应在 header 中附带 `X-Request-ID`（UUIDv4）与 `X-Elapsed-ms`

### 错误

```json
{
  "success": false,
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "账号或密码错误",
    "detail": { "field": "reason" }
  }
}
```

- `code`：业务错误码，前端可作 i18n key
- `message`：服务端可读消息（已汉化）
- `detail`：字段级或调试信息（生产环境不返回敏感字段）

### 通用响应头

| Header | 说明 |
| --- | --- |
| `X-Request-ID` | 客户端可传入 `X-Request-ID`；缺省服务端自动生成 |
| `X-Elapsed-ms` | 服务端处理耗时（毫秒） |

---

## 幂等性

| 接口 | 幂等策略 | 重复行为 |
| --- | --- | --- |
| `DELETE /tasks/{uuid}` | 资源级 | 第二次返回 `404 TASK_NOT_FOUND` |
| `DELETE /tags/{uuid}` | 资源级 | 同上 |
| `POST /tasks/batch` | `idempotencyKey`（Redis 24h） | 相同 key 直接返回缓存结果 |
| `POST /sync/push` | 每个 op 内 `opId`（Redis 24h） | 相同 opId 直接返回上次结果 |
| `POST /auth/tokens/refresh` | refresh_token 一次性 | 旧 token 撤销后再用 → `401 AUTH_REFRESH_TOKEN_INVALID` |
| `POST /auth/tokens/logout` | 幂等 | 重复调用均返回 `200` |
| `PUT /users/me/auth-linkage/{provider}` | 资源级 | 已绑定 → `409 AUTH_PROVIDER_ALREADY_LINKED` |
| `DELETE /users/me/auth-linkage/{provider}` | 资源级 | 未绑定 → `404 AUTH_PROVIDER_NOT_LINKED` |
| `POST /auth/password/reset` | 令牌级 | 同一 `reset_token` 第二次 → `400 AUTH_RESET_TOKEN_INVALID` |
| `POST /auth/captcha/verify` | 一次性 | 同一 `captcha_id` 第二次 → 验证失败 |
| `POST /auth/ws-ticket` | 一次性 | ticket 只能被消费一次 |

---

## HTTP 状态码

| 状态码 | 含义 | 说明 |
| --- | --- | --- |
| `200 OK` | 成功 | GET / PATCH / DELETE / 部分 POST |
| `201 Created` | 已创建 | 创建资源类 POST |
| `400 Bad Request` | 请求错误 | 参数校验失败、格式错误、令牌无效 |
| `401 Unauthorized` | 未认证 | 缺少 token / token 过期 / token 无效 |
| `403 Forbidden` | 禁止访问 | 已认证但无权限（管理端 / 黑名单） |
| `404 Not Found` | 资源不存在 | 资源不存在或已软删除 |
| `409 Conflict` | 资源冲突 | 重复（标签名、Provider 重复绑定等） |
| `422 Unprocessable Entity` | 语义错误 | 请求体格式正确但语义错误（保留） |
| `429 Too Many Requests` | 触发限流 | 携带 `Retry-After` |
| `500 Internal Server Error` | 服务器错误 | 内部异常；`detail` 在生产环境不返回敏感信息 |

---

## 业务错误码

| 错误码 | HTTP | 含义 | 出现位置 |
| --- | --- | --- | --- |
| `AUTH_INVALID_CREDENTIALS` | 401 | 账号或密码错误 | `POST /auth/tokens`、`/admin/auth/tokens` |
| `AUTH_TOKEN_EXPIRED` | 401 | access_token 过期 | 全局鉴权 |
| `AUTH_TOKEN_INVALID` | 401 | access_token 无效 | 全局鉴权 |
| `AUTH_REFRESH_TOKEN_INVALID` | 401 | refresh_token 无效或已吊销 | `tokens/refresh`、`logout` |
| `AUTH_LINK_TOKEN_INVALID` | 401 | `link_token` 无效或已过期 | `/users/me/auth-linkage/{provider}` |
| `AUTH_RESET_TOKEN_INVALID` | 400 | 密码重置令牌无效或过期 | `password/reset` |
| `AUTH_CODE_INVALID` | 400 | 验证码错误（短信/邮箱/微信 code） | `/auth/sms/login`、`/auth/email/login`、`/auth/wechat/login` |
| `AUTH_CODE_EXPIRED` | 400 | 验证码过期 | 同上 |
| `AUTH_CAPTCHA_INVALID` | 400 | 图形验证码错误 | `/auth/captcha/verify`、`/auth/sms/send` |
| `AUTH_PROVIDER_ALREADY_LINKED` | 409 | Provider 已被当前账号绑定 | `PUT /users/me/auth-linkage/{provider}` |
| `AUTH_PROVIDER_NOT_LINKED` | 404 | Provider 未被当前账号绑定 | `DELETE /users/me/auth-linkage/{provider}` |
| `USER_NOT_FOUND` | 404 | 用户不存在 | 管理端用户接口 |
| `USER_ALREADY_EXISTS` | 409 | 用户已存在（邮箱/手机号重复） | `POST /users` |
| `TASK_NOT_FOUND` | 404 | 任务不存在或已删除 | 任务相关接口 |
| `TAG_NOT_FOUND` | 404 | 标签不存在 | 任务写入 / 标签接口 |
| `TAG_NAME_CONFLICT` | 409 | 标签名称重复 | `POST /tags` |
| `CHECKLIST_NOT_FOUND` | 404 | 检查项不存在 | `PATCH/DELETE /tasks/{task_uuid}/checklist/{item_uuid}` |
| `NOTIFICATION_NOT_FOUND` | 404 | 通知不存在 | `PATCH/DELETE /notifications/{uuid}` |
| `FEEDBACK_NOT_FOUND` | 404 | 反馈不存在 | 管理端 `DELETE /admin/feedback/{uuid}` |
| `VALIDATION_ERROR` | 400 | 请求参数校验失败（`detail` 含字段级错误） | 全局 |
| `ADMIN_FORBIDDEN` | 403 | 非管理员 / 权限不足 | 管理端任意接口 |
| `RATE_LIMITED` | 429 | 触发限流 | 限流中间件 |
| `RESOURCE_DELETED` | 404 | 资源已软删除（不可再恢复） | 部分恢复类操作 |
| `INTERNAL_ERROR` | 500 | 内部服务器错误 | 全局兜底 |
| `WS_TICKET_INVALID` | 401 | WebSocket ticket 无效或已消费 | WebSocket 握手 |

> 错误码命名规范：`<域>_<语义>`，大写下划线；前端可直接 `t('errors.AUTH_INVALID_CREDENTIALS')`。

---

## 统一响应外壳与中间件约定

中间件链（外层 → 内层）：`CORSMiddleware` → `BusinessExceptionMiddleware` → `RequestIDMiddleware`。
业务层**禁止** `raise HTTPException`，必须抛 `src.core.exceptions.BusinessException` 子类（`NotFoundException` / `UnauthorizedException` / `ForbiddenException` / `ConflictException` / `RateLimitedException` / `ValidationException`），由中间件统一翻译为错误外壳。

---

## 鉴权与依赖项

`src/core/deps.py` 提供：

| 依赖 | 行为 | 适用端点 |
| --- | --- | --- |
| `DbSession` | 注入 `AsyncSession` | 全部 |
| `CurrentUser` | 可选鉴权，匿名返回 `{"uuid": None, "authenticated": False}` | 公开+鉴权混合 |
| `RequiredUser` | 强制鉴权，从 JWT 解析 user 主体 | 用户端绝大部分 |
| `RequireAdmin` | 强制管理员，校验 `role ∈ {admin, super_admin}` | 管理端全部 |
| `WsUser` | WebSocket 握手依赖 | WS 路由 |

**管理员 vs 用户** 两套 JWT 完全独立：`POST /auth/tokens`（用户端）和 `POST /admin/auth/tokens`（管理端）签发不同 `audience`，token 不可跨域使用。

---

## 用户端 API

> 前缀：`/api/v1`，鉴权：`Authorization: Bearer <access_token>`（公开端点除外）。

### 1) 认证（auth）— 15 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/auth/tokens` | 公开 | 账号登录（password / phone_sms / email_code） |
| `POST` | `/auth/tokens/refresh` | 公开 | 刷新 access_token；旧 refresh_token 立即撤销 |
| `POST` | `/auth/tokens/logout` | 公开* | 撤销指定 refresh_token（幂等） |
| `POST` | `/auth/tokens/logout-all` | RequiredUser | 撤销当前用户所有 refresh_token |
| `POST` | `/auth/wechat/login` | 公开 | 微信小程序 `wx.login()` code 换 JWT |
| `POST` | `/auth/ws-ticket` | RequiredUser | 签发一次性 WebSocket ticket（Redis 30~60s TTL） |
| `GET` | `/auth/login-methods` | 公开 | 返回当前可用登录方式 + 验证码开关 |
| `GET` | `/auth/captcha` | 公开 | 返回 SVG 图形验证码（5min TTL） |
| `POST` | `/auth/captcha/verify` | 公开 | 校验图形验证码（一次性） |
| `POST` | `/auth/sms/send` | 公开 | 发送短信验证码（mock 模式：日志） |
| `POST` | `/auth/sms/login` | 公开 | 短信验证码登录 |
| `POST` | `/auth/email/send` | 公开 | 发送邮箱验证码（mock 模式：日志） |
| `POST` | `/auth/email/login` | 公开 | 邮箱验证码登录 |
| `POST` | `/auth/password/reset-request` | 公开 | 请求密码重置（邮件，mock 模式） |
| `POST` | `/auth/password/reset` | 公开 | 使用 `reset_token` 重置密码 |

> `* POST /auth/tokens/logout` 业务上需 refresh_token 自身有效，但路由层未强制 user 鉴权（已登录用户调用）。

#### `POST /auth/tokens` — 账号登录

请求体：

```json
{
  "provider": "password | phone_sms | email_code | wechat",
  "payload": { "...": "依 provider 不同" }
}
```

`provider` → `payload` 字段映射：

| provider | payload 必填字段 | 备注 |
| --- | --- | --- |
| `password` | `identifier` (email/手机号) + `password` | identifier 与历史 UserIdentity 匹配 |
| `phone_sms` | `phone` + `code` | 先调 `/auth/sms/send` |
| `email_code` | `email` + `code` | 先调 `/auth/email/send` |
| `wechat` | 单独走 `/auth/wechat/login` | 此处 provider=wechat 也可，但通常用专用接口 |

响应（`LoginResponse`）：

```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "rt_...",
    "token_type": "Bearer",
    "expires_in": 1800,
    "user": {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "nickname": "用户名",
      "avatar_url": "https://cdn.example.com/avatars/xxx.jpg",
      "role": "user",
      "status": "active",
      "locale": "zh-CN"
    },
    "is_new_user": false
  }
}
```

错误：`401 AUTH_INVALID_CREDENTIALS` / `400 AUTH_CODE_INVALID` / `400 AUTH_CAPTCHA_INVALID` / `429 RATE_LIMITED`。

#### `POST /auth/tokens/refresh`

```json
{ "refresh_token": "rt_..." }
```

→ `TokenRefreshResponse`（`access_token` / `refresh_token` / `token_type` / `expires_in`）。
旧 `refresh_token` 立即失效并写入 Redis 黑名单（TTL=剩余有效期），重复使用返回 `401 AUTH_REFRESH_TOKEN_INVALID`。

#### `POST /auth/tokens/logout`

```json
{ "refresh_token": "rt_..." }
```

→ `{ revokedCount: number }`，幂等。匿名调用也允许（需 `refresh_token` 格式合法）。

#### `POST /auth/tokens/logout-all`

撤销该用户所有未过期 refresh_token，并把对应 access_token 写入 Redis 黑名单。
→ `{ revokedCount: number }`。

#### `POST /auth/wechat/login`

```json
{
  "code": "wx_login_code",
  "encrypted_data": "可选",
  "iv": "可选",
  "invite_code": "可选"
}
```

→ 与 `/auth/tokens` 相同 `LoginResponse`，并通过 `is_new_user` 标识是否首次登录。  
`WX_LOGIN_MOCK=true` 时不调微信接口，凭 `code` 直接 mock 出 `openid`（仅 dev/test）。

#### `POST /auth/ws-ticket`

```json
{ }
```

→ `WsTicketResponse`：

```json
{
  "ticket": "wt_xxx...",
  "expires_in": 30,
  "ws_url_template": "/ws/notifications?token={ticket}"
}
```

> ticket 30~60s 有效，连接时一次性消费。**必须**用于小程序 WS 连接（`Sec-WebSocket-Protocol` 头在 `wx.connectSocket` 不可用）。

#### `GET /auth/login-methods`

```json
{
  "methods": [
    { "provider": "password", "identifierType": "email", "enabled": true },
    { "provider": "phone_sms", "identifierType": "phone", "enabled": true },
    { "provider": "email_code", "identifierType": "email", "enabled": true }
  ],
  "captchaEnabled": true
}
```

> `enabled` 来自 `sishiyouxu_config` 中的 `smsLoginEnabled` / `emailLoginEnabled` / `registrationEnabled`。

#### `GET /auth/captcha`

→ `CaptchaResponse`：

```json
{
  "captcha_id": "uuid",
  "image": "data:image/svg+xml;base64,..."
}
```

TTL 5min，存 Redis 一次性消费。

#### `POST /auth/captcha/verify`

```json
{ "captcha_id": "uuid", "captcha_solution": "abcd" }
```

→ `{ verified: boolean }`。

#### `POST /auth/sms/send`

```json
{
  "phone": "+8613800000000",
  "purpose": "login | register | bind",
  "captcha_id": "可选",
  "captcha_solution": "可选"
}
```

`SMS_PROVIDER=mock` 时验证码写日志 + Redis（60s TTL）。连续失败需先过图形验证码。  
→ `{ "sent": true, "expires_in": 60 }`。

#### `POST /auth/sms/login`

```json
{ "phone": "+8613800000000", "code": "123456" }
```

→ `LoginResponse`。

#### `POST /auth/email/send`

```json
{ "email": "user@example.com", "purpose": "login | register | bind" }
```

→ `{ "sent": true, "expires_in": 300 }`。

#### `POST /auth/email/login`

```json
{ "email": "user@example.com", "code": "123456" }
```

→ `LoginResponse`。

#### `POST /auth/password/reset-request`

Query：`?email=user@example.com`。  
无论邮箱是否存在都返回 `200`（防枚举），mock 模式写日志。

#### `POST /auth/password/reset`

```json
{ "reset_token": "rt_xxx", "new_password": "Secret123" }
```

→ `{ "message": "密码重置成功" }`。  
成功后该用户所有 refresh_token 失效。

---

### 2) 用户资料（users）— 11 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/users` | 公开 | 注册新用户（合并注册+自动登录） |
| `GET` | `/users/me` | RequiredUser | 当前用户完整资料 |
| `PATCH` | `/users/me` | RequiredUser | 更新昵称 / locale |
| `POST` | `/users/me/password` | RequiredUser | 修改密码（成功后强制 logout-all） |
| `POST` | `/users/me/avatar` | RequiredUser | 上传头像（multipart） |
| `GET` | `/users/me/auth-linkage` | RequiredUser | 查询已绑定的登录方式 |
| `POST` | `/users/me/auth-linkage/token` | RequiredUser | 生成绑定临时 token（5min） |
| `PUT` | `/users/me/auth-linkage/{provider}` | RequiredUser | 绑定新登录方式 |
| `DELETE` | `/users/me/auth-linkage/{provider}` | RequiredUser | 解绑登录方式 |
| `GET` | `/users/me/reminder-channels` | RequiredUser | 获取提醒渠道（骨架） |
| `PATCH` | `/users/me/reminder-channels` | RequiredUser | 更新提醒渠道（骨架） |

#### `POST /users` — 注册

```json
{
  "nickname": "用户名",
  "provider": "password | phone_sms | email_code",
  "payload": { "依 provider" }
}
```

| provider | payload 必填 |
| --- | --- |
| `password` | `identifier`(email) + `password`(≥8 位含大小写数字) |
| `phone_sms` | `phone` + `code` |
| `email_code` | `email` + `code` |

成功 `201` → `LoginResponse`（`is_new_user: true`）。  
错误：`400 VALIDATION_ERROR` / `409 USER_ALREADY_EXISTS` / `400 AUTH_CODE_INVALID`。

> ❗ 旧文档中的 `POST /users/phone` 和 `POST /users/email` 已合并为 `POST /users`，请勿再调用。

#### `GET /users/me`

→ `UserProfileResponse`：

```json
{
  "uuid": "550e8400-...",
  "nickname": "用户名",
  "avatarUrl": "https://...",
  "role": "user",
  "status": "active",
  "locale": "zh-CN",
  "createdAt": "2026-06-01T10:00:00.000Z",
  "updatedAt": "2026-06-27T10:00:00.000Z"
}
```

#### `PATCH /users/me`

```json
{ "nickname": "新昵称", "locale": "en-US" }
```

字段均可选；`nickname` 长度 2-20。

#### `POST /users/me/password`

```json
{ "oldPassword": "Secret123", "newPassword": "NewSecret123" }
```

成功 → 强制调用 logout-all 撤销该用户全部 refresh_token。

#### `POST /users/me/avatar`

`Content-Type: multipart/form-data`，字段 `file`（JPG/PNG/WebP，≤2MB）。
→ `{ "avatarUrl": "...", "updatedAt": "..." }`。

#### `GET /users/me/auth-linkage`

→ `AuthLinkageListResponse`：

```json
{
  "items": [
    { "provider": "password", "identifier": "u***@example.com", "boundAt": "2026-06-01T10:00:00.000Z" },
    { "provider": "phone_sms", "identifier": "+86 138****1234", "boundAt": "2026-06-15T14:30:00.000Z" }
  ]
}
```

#### `POST /users/me/auth-linkage/token`

→ `LinkTokenResponse`：

```json
{ "link_token": "lt_...", "expires_in": 300 }
```

#### `PUT /users/me/auth-linkage/{provider}`

Path: `provider ∈ { phone_sms, email_code }`。

```json
{ "link_token": "lt_...", "payload": { "phone/email": "...", "code": "123456" } }
```

→ `BindProviderResponse`：

```json
{ "provider": "phone_sms", "identifier": "+86 138****1234", "boundAt": "..." }
```

错误：`401 AUTH_LINK_TOKEN_INVALID` / `409 AUTH_PROVIDER_ALREADY_LINKED` / `400 AUTH_CODE_INVALID`。

#### `DELETE /users/me/auth-linkage/{provider}`

→ `data: null`。错误：`404 AUTH_PROVIDER_NOT_LINKED` / 业务规则：至少保留一种登录方式。

#### `GET / PATCH /users/me/reminder-channels`（骨架）

`GET` → `{ channels: [{ type: "web_push", enabled: true, label: "浏览器推送" }, ...] }`  
`PATCH` 入参：

```json
{
  "channels": [
    { "type": "web_push", "enabled": true },
    { "type": "wechat_subscribe", "enabled": false }
  ]
}
```

> 提醒渠道的真实持久化与推送实现在 Phase 4 之后接入。

---

### 3) 任务（tasks）— 7 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/tasks` | RequiredUser | 查询任务列表（分页 + 过滤） |
| `POST` | `/tasks` | RequiredUser | 创建任务（`201`） |
| `GET` | `/tasks/{uuid}` | RequiredUser | 任务详情（含完整 tag 对象） |
| `PATCH` | `/tasks/{uuid}` | RequiredUser | 部分更新 |
| `DELETE` | `/tasks/{uuid}` | RequiredUser | 软删除（幂等） |
| `POST` | `/tasks/{uuid}/restore` | RequiredUser | 恢复已软删除任务 |
| `POST` | `/tasks/batch` | RequiredUser | 批量操作（delete / restore / move / complete），`idempotencyKey` 幂等 |

#### `GET /tasks`

Query：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `since` | ISO 8601 | 否 | 仅返回 `updated_at >= since` 的任务 |
| `completed` | boolean | 否 | 筛选完成状态 |
| `q` | string | 否 | 标题关键词 |
| `page` | int | 否 | 默认 1 |
| `pageSize` | int | 否 | 默认 20，最大 100 |

响应（`data` 内 `items` 元素字段）：

```json
{
  "uuid": "...",
  "title": "...",
  "urgencyLevel": 2,
  "importanceLevel": -1,
  "dueDate": "2026-06-25",
  "recurrence": null,
  "note": "markdown",
  "tags": ["uuid1", "uuid2"],
  "checklistTotal": 5,
  "checklistCompleted": 3,
  "completed": false,
  "completedAt": null,
  "sortOrder": 0,
  "createdAt": "...",
  "updatedAt": "..."
}
```

> 列表接口中 `tags` 为 UUID 数组；**详情接口**中 `tags` 为完整 `[{uuid, name, color}]` 对象。

#### `POST /tasks` — 创建任务（`201`）

```json
{
  "title": "周二产品评审会议准备",
  "urgencyLevel": 2,
  "importanceLevel": -1,
  "dueDate": "2026-06-25",
  "recurrence": "RRULE:FREQ=DAILY;INTERVAL=2",
  "note": "## 议程\n- ...",
  "tags": ["uuid1"],
  "remindAt": "2026-06-25T09:00:00Z",
  "remindOffsetMinutes": 15,
  "sortOrder": 0
}
```

| 字段 | 必填 | 约束 |
| --- | --- | --- |
| `title` | 是 | 1-200 字符 |
| `urgencyLevel`, `importanceLevel` | 否（默认 0） | -4..4 整数（紧急度 / 重要度） |
| `dueDate` | 否 | `YYYY-MM-DD` |
| `recurrence` | 否 | RRULE 字符串 |
| `note` | 否 | Markdown |
| `tags` | 否 | 标签 UUID 列表（必须为当前用户可见） |
| `remindAt` | 否 | ISO 8601 |
| `remindOffsetMinutes` | 否 | 整数；与 `dueDate` 配合生成后续提醒 |
| `sortOrder` | 否 | 默认 0 |

响应：与列表元素相同结构（创建时 `checklistTotal/Completed` 默认为 0）。  
错误：`400 VALIDATION_ERROR` / `404 TAG_NOT_FOUND`。

#### `GET /tasks/{uuid}`

→ 任务对象，`tags` 为完整对象数组。

```json
{
  "...": "同列表元素",
  "tags": [
    { "uuid": "uuid1", "name": "工作", "color": "#A78BFA" },
    { "uuid": "uuid2", "name": "会议", "color": "#60A5FA" }
  ]
}
```

#### `PATCH /tasks/{uuid}`

入参字段同 `POST`（全部可选），不能写 `checklistTotal/Completed`（只读聚合）。  
错误：`404 TASK_NOT_FOUND`。

#### `DELETE /tasks/{uuid}`

软删除（设置 `deletedAt`），幂等；已删除的再次调用 → `404 TASK_NOT_FOUND`。

#### `POST /tasks/{uuid}/restore`

```json
{ }
```

→ `{ uuid, title, status: "restored", restoredAt }`。  
错误：`404 TASK_NOT_FOUND` / `409 RESOURCE_DELETED`（任务未删除）。

#### `POST /tasks/batch` — 批量操作

```json
{
  "action": "delete | restore | move | complete",
  "taskUuids": ["uuid1", "uuid2"],
  "idempotencyKey": "client-uuid",
  "quadrant": 2
}
```

`action` 行为：

| action | 行为 |
| --- | --- |
| `delete` | 软删除（幂等） |
| `restore` | 恢复（幂等） |
| `move` | 调整 `urgencyLevel`/`importanceLevel` 到目标象限（`quadrant` 必填，1-4；正值表紧急/重要） |
| `complete` | 设置 `completed=true` + `completedAt=now()` |

响应：

```json
{ "affected": 2, "succeeded": ["uuid1","uuid2"], "failed": [] }
```

`failed` 元素示例：`{ "taskUuid": "uuid3", "reason": "TASK_NOT_FOUND" }`。  
错误：`400 VALIDATION_ERROR` / `404 TASK_NOT_FOUND`（部分任务不存在时仍执行成功部分，并在 `failed` 中列出）。

#### 任务对象

```json
{
  "uuid": "uuid",
  "title": "...",
  "urgencyLevel": 2,
  "importanceLevel": -1,
  "dueDate": "2026-06-25",
  "recurrence": null,
  "note": "markdown",
  "tags": ["uuid1", "uuid2"],
  "checklistTotal": 5,
  "checklistCompleted": 3,
  "completed": false,
  "completedAt": null,
  "sortOrder": 0,
  "createdAt": "...",
  "updatedAt": "..."
}
```

> `urgencyLevel`（紧急度 -4..4 整数）、`importanceLevel`（重要度 -4..4 整数）确定任务在四象限画布中的位置；象限判定以 0 为分界（>0 表紧急/重要）。`sortOrder` 同象限内排序，值越小越靠前。**这两个字段直接入库**（DB `urgency_level` / `importance_level` 为 `INT NOT NULL DEFAULT 0`），不是由浮点 `posX`/`posY` 派生的。`checklistTotal` / `checklistCompleted` 为只读聚合字段，**禁止**客户端写入。DB 字段 `urgency_level` / `importance_level` / `sort_order` / `user_uuid` 等为 snake_case，API 统一 camelCase。

---

### 4) 检查项（checklist）— 4 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/tasks/{task_uuid}/checklist` | RequiredUser | 获取任务下所有检查项 |
| `POST` | `/tasks/{task_uuid}/checklist` | RequiredUser | 创建检查项（`201`） |
| `PATCH` | `/tasks/{task_uuid}/checklist/{item_uuid}` | RequiredUser | 更新检查项 |
| `DELETE` | `/tasks/{task_uuid}/checklist/{item_uuid}` | RequiredUser | 软删除检查项 |

#### `POST /tasks/{task_uuid}/checklist`

```json
{ "title": "准备 PPT", "completed": false, "sortOrder": 0 }
```

→ 检查项对象（`{ uuid, taskUuid, title, completed, sortOrder, createdAt, updatedAt }`）。

#### `PATCH /tasks/{task_uuid}/checklist/{item_uuid}`

字段可选；至少传一个。错误：`404 CHECKLIST_NOT_FOUND`。

#### `DELETE /tasks/{task_uuid}/checklist/{item_uuid}`

→ `data: null`。

---

### 5) 标签（tags）— 4 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/tags` | RequiredUser | 当前用户所有标签 + 预设标签 |
| `POST` | `/tags` | RequiredUser | 创建标签（`201`） |
| `PATCH` | `/tags/{uuid}` | RequiredUser | 更新标签（预设标签不可改） |
| `DELETE` | `/tags/{uuid}` | RequiredUser | 删除标签（预设不可删） |

#### `POST /tags`

```json
{ "name": "工作", "color": "#A78BFA" }
```

`color` 必须匹配 `^#[0-9a-fA-F]{6}$`。  
响应：标签对象 `{ uuid, name, color, isPreset: false, createdAt, updatedAt }`。  
错误：`400 VALIDATION_ERROR` / `409 TAG_NAME_CONFLICT`。

#### `PATCH /tags/{uuid}`

字段均可选；预设标签修改会拒绝。

#### `DELETE /tags/{uuid}`

→ `data: null`。删除时会同时软删除 `sishiyouxu_task_tag` 关联行。

---

### 6) 通知（notifications）— 5 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/notifications` | RequiredUser | 分页列表（`isRead` 过滤） |
| `GET` | `/notifications/unread-count` | RequiredUser | 未读数量 |
| `PATCH` | `/notifications/{uuid}/read` | RequiredUser | 标记已读 |
| `POST` | `/notifications/read-all` | RequiredUser | 全部已读 |
| `DELETE` | `/notifications/{uuid}` | RequiredUser | 软删除通知 |

#### `GET /notifications`

Query：`isRead` (boolean, 可选) / `page` / `pageSize`。

```json
{
  "items": [
    {
      "uuid": "...",
      "kind": "task_reminder",
      "title": "任务到期提醒",
      "body": "您有一个任务即将到期：《周二产品评审》",
      "taskUuid": "uuid or null",
      "isRead": false,
      "createdAt": "2026-06-25T10:00:00.000Z"
    }
  ],
  "meta": { "total": 50, "page": 1, "pageSize": 20, "hasMore": true }
}
```

`kind` 取值：`task_reminder`（任务到期）、`task_assigned`（预留）、`system_announcement`（系统公告）。

#### `GET /notifications/unread-count`

→ `{ unreadCount: number }`。

#### `PATCH /notifications/{uuid}/read`

→ `{ uuid, isRead: true, readAt }`。错误：`404 NOTIFICATION_NOT_FOUND`。

#### `POST /notifications/read-all`

→ `{ affected: number }`。

#### `DELETE /notifications/{uuid}`

→ `data: null`。错误：`404 NOTIFICATION_NOT_FOUND`。

---

### 7) 反馈（feedback）— 2 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/feedback` | 公开（CurrentUser） | 提交反馈（匿名或登录态） |
| `GET` | `/feedback` | RequiredUser | 查询我的反馈 |

#### `POST /feedback`

```json
{ "content": "希望增加任务提醒功能", "contact": "user@example.com" }
```

`content` 1-2000 字符，必填；`contact` 可空。  
`201` → `{ uuid, content, contact, status: "pending", createdAt }`。

#### `GET /feedback`

Query：`page` / `pageSize`。  
响应（`items` 元素同 `POST` 响应 + 缺失 `content` 字段）：

```json
{
  "items": [
    { "uuid": "fb-001", "content": "...", "contact": "...", "status": "pending", "createdAt": "..." }
  ],
  "meta": { "total": 1, "page": 1, "pageSize": 20, "hasMore": false }
}
```

---

### 8) 同步（sync）— 3 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/sync/push` | RequiredUser | 批量推送本地 ops（opId 幂等） |
| `GET` | `/sync/pull` | RequiredUser | 拉取 `since` 之后变更 |
| `GET` | `/sync/status` | 公开 | 服务端时间校准 |

详见 [同步协议.md](./同步协议.md)。本节只列 API 形态。

#### `POST /sync/push`

```json
{
  "ops": [
    {
      "opId": "client-uuid-1",
      "entity": "task | tag | taskTag | checklistItems",
      "action": "upsert | delete",
      "payload": { "...完整实体记录..." },
      "clientTs": 1719480000000
    }
  ]
}
```

- `ops` 长度 1-100；服务端按 opId 24h 幂等。
- 响应：

```json
{
  "results": [
    {
      "opId": "client-uuid-1",
      "status": "applied | conflict | rejected",
      "serverRecord": { "...": "可选，更新后记录" },
      "serverTime": "2026-06-27T16:00:00.000Z",
      "reason": "可选，rejected 时附原因"
    }
  ],
  "serverTime": "2026-06-27T16:00:00.005Z"
}
```

错误：`400 VALIDATION_ERROR`（ops 超过 100 条）。

#### `GET /sync/pull`

Query：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `since` | ISO 8601 | 否 | 仅返回 `updated_at >= since` |
| `entities` | 逗号分隔 | 否 | 单数实体值：`task` / `tag` / `taskTag` / `checklistItems`；默认全部 |

响应：

```json
{
  "tasks":      { "items": [TaskListItem...], "deleted": ["uuid-of-soft-deleted"] },
  "tags":       { "items": [TagItem...] },
  "taskTags":   { "items": [{ "taskUuid": "...", "tagUuid": "..." }] },
  "checklistItems": { "items": [ChecklistItem...] },
  "serverAt":   "2026-06-27T16:00:00.000Z"
}
```

#### `GET /sync/status`

```json
{
  "serverAt": "2026-06-27T16:00:00.000Z",
  "serverTimeMs": 1719480000000,
  "timezone": "Asia/Shanghai"
}
```

---

## 管理端 API

> 前缀：`/api/v1/admin`，鉴权：`Authorization: Bearer <admin_access_token>`，依赖项：`RequireAdmin`（校验 `role ∈ {admin, super_admin}`）。
> 错误：`401 AUTH_TOKEN_*` / `403 ADMIN_FORBIDDEN`。

### 1) 管理员认证 — 3 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/admin/auth/tokens` | 公开 | 管理员登录（username + password） |
| `POST` | `/admin/auth/tokens/refresh` | 公开 | 刷新管理员 token |
| `DELETE` | `/admin/auth/tokens` | 公开* | 管理员登出（撤销 refresh_token） |
| `POST` | `/admin/auth/password` | RequireAdmin | 管理员修改自己密码 |

> `DELETE /admin/auth/tokens` 业务上需 refresh_token，但路由层不强制管理员鉴权。

#### `POST /admin/auth/tokens`

```json
{ "username": "admin", "password": "123456" }
```

→ `LoginResponse`（`user.role` 为 `admin` 或 `super_admin`）。  
错误：`401 AUTH_INVALID_CREDENTIALS` / `403 ADMIN_FORBIDDEN`（非管理员账号）。

#### `POST /admin/auth/tokens/refresh`

```json
{ "refresh_token": "rt_..." }
```

#### `DELETE /admin/auth/tokens`

```json
{ "refresh_token": "rt_..." }
```

→ `{ revokedCount }`。

#### `POST /admin/auth/password`

Request（RequireAdmin）：
```json
{ "oldPassword": "当前密码", "newPassword": "新密码（最少 8 位）" }
```

→ `{ "message": "密码修改成功" }`。成功后所有设备的 refresh token 被撤销，强制重新登录。

### 2) 用户管理 — 11 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/admin/users` | RequireAdmin | 用户列表（分页 + 过滤） |
| `GET` | `/admin/users/{uuid}` | RequireAdmin | 用户详情 |
| `PATCH` | `/admin/users/{uuid}` | RequireAdmin | 更新用户状态 |
| `DELETE` | `/admin/users/{uuid}` | RequireAdmin | 软删除用户 |
| `POST` | `/admin/users/{uuid}/disable` | RequireAdmin | 禁用用户 |
| `POST` | `/admin/users/{uuid}/enable` | RequireAdmin | 启用用户 |
| `POST` | `/admin/users/{uuid}/force-logout` | RequireAdmin | 强制下线该用户所有设备（含 access token） |
| `POST` | `/admin/users/{uuid}/reset-password` | RequireAdmin | 管理员重置用户密码 |
| `POST` | `/admin/users/batch` | RequireAdmin | 批量 disable / enable / delete |
| `GET` | `/admin/users/export` | RequireAdmin | 导出用户 CSV（`text/csv`） |
| `GET` | `/admin/users/me` | RequireAdmin | 当前管理员信息 |

#### `GET /admin/users`

Query：`page` / `pageSize` / `keyword` / `status` (active/disabled) / `role` / `startTime` / `endTime`。

响应 `items` 元素：

```json
{
  "uuid": "...",
  "nickname": "张三",
  "avatarUrl": "https://...",
  "role": "user",
  "status": "active",
  "locale": "zh-CN",
  "createdAt": "2026-06-01T10:00:00.000Z"
}
```

#### `GET /admin/users/{uuid}`

→ 用户详情（含 `authIdentities`、`taskCount`、`completedTaskCount`）。错误：`404 USER_NOT_FOUND`。

#### `PATCH /admin/users/{uuid}`

```json
{ "status": "active | disabled" }
```

#### `POST /admin/users/{uuid}/disable` / `/enable`

→ 用户对象。会自动写审计日志 + 通知用户（任务提醒场景）。

#### `POST /admin/users/{uuid}/force-logout`

撤销该用户所有 refresh token，同时在 Redis 中记录 force-logout 时间戳（TTL = access token 有效期）。后续该用户的任何 API 请求，若 access token 签发时间早于 force-logout 时间戳，将被拒绝（`AUTH_FORCE_LOGOUT`）。

→ `{ revokedCount }`。

#### `POST /admin/users/{uuid}/reset-password`

Request（RequireAdmin）：
```json
{ "newPassword": "新密码（最少 8 位）" }
```

管理员直接覆盖目标用户的密码（无需旧密码）。仅对已绑定 `password` provider 的用户有效 → `{ "message": "密码已重置" }`。成功后撤销该用户所有 refresh token。

#### `POST /admin/users/batch`

```json
{ "action": "disable | enable | delete", "uuids": ["uuid1","uuid2"] }
```

→ `{ affected, succeeded, failed }`，`failed` 元素：`{ uuid, reason }`。

#### `GET /admin/users/export`

→ `text/csv; charset=utf-8`，`Content-Disposition: attachment; filename=users.csv`。

#### `GET /admin/users/me`

→ 当前管理员对象（与 `RequireAdmin` 注入的 `admin` 字典一致）。

---

### 3) 仪表盘 — 2 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/admin/dashboard/stats` | RequireAdmin | 仪表盘统计（总用户、DAU/MAU、象限分布等） |
| `GET` | `/admin/dashboard/charts/{metric}` | RequireAdmin | 图表数据（按 `metric` 区分） |

`/stats` 响应（`AdminService.get_stats()` 真实输出）：

```json
{
  "totalUsers": 10234,
  "activeUsersToday": 1234,
  "totalTasks": 45678,
  "completedTasksToday": 567,
  "quadrantDistribution": { "q1": 12000, "q2": 18000, "q3": 8000, "q4": 7678 },
  "dau":  { "date": "2026-06-27", "count": 1234 },
  "mau":  { "month": "2026-06", "count": 5678 }
}
```

`/charts/{metric}`：`metric` 可由后端自由扩展（`AdminService.get_chart(metric)`），常见值见 `AdminService` 实现。

---

### 4) 审计 — 3 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/admin/audit` | RequireAdmin | 审计日志列表（分页 + 过滤） |
| `GET` | `/admin/audit/{uuid}` | RequireAdmin | 单条审计日志详情 |
| `GET` | `/admin/login-logs` | RequireAdmin | 登录日志（**Phase 4 待实现**，当前返回 skeleton） |

#### `GET /admin/audit`

Query：`page` / `pageSize` / `userUuid` / `action` / `resourceType` / `startTime` / `endTime`。

`items` 元素：

```json
{
  "uuid": "audit-uuid-001",
  "userUuid": "...",
  "userNickname": "管理员",
  "action": "user_disable",
  "resourceType": "user",
  "resourceUuid": "...",
  "ipAddress": "1.2.3.4",
  "detail": { "targetUser": "张三", "reason": "违规内容" },
  "createdAt": "2026-06-25T10:00:00.000Z"
}
```

`action` 取值参考：`user_disable` / `user_enable` / `user_delete` / `feedback_process` / `config_update` / `force_logout` 等。

#### `GET /admin/audit/{uuid}`

→ 单条详情。

#### `GET /admin/login-logs`

> ⚠️ 当前为 skeleton 占位：返回 `{ status: "skeleton", items: [] }`。**Phase 4** 将接入 `sishiyouxu_login_log` 表。

---

### 5) 反馈 — 3 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/admin/feedback` | RequireAdmin | 反馈列表（分页 + 状态过滤） |
| `PATCH` | `/admin/feedback/{uuid}` | RequireAdmin | 更新反馈状态（processing / resolved） |
| `DELETE` | `/admin/feedback/{uuid}` | RequireAdmin | 软删除反馈 |

#### `GET /admin/feedback`

Query：`status` (pending/processing/resolved) / `page` / `pageSize`。

```json
{
  "items": [
    {
      "uuid": "fb-001",
      "userUuid": "...",
      "content": "...",
      "contact": "...",
      "status": "pending",
      "createdAt": "2026-06-25T10:00:00.000Z"
    }
  ],
  "meta": { "total": 50, "page": 1, "pageSize": 20, "hasMore": true }
}
```

#### `PATCH /admin/feedback/{uuid}`

```json
{ "status": "processing | resolved" }
```

→ `{ uuid, status, handledBy, handledAt }`。

#### `DELETE /admin/feedback/{uuid}`

→ `data: null`。错误：`404 FEEDBACK_NOT_FOUND`。

---

### 6) 系统配置 — 2 条

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/admin/config` | RequireAdmin | 获取系统配置 |
| `PATCH` | `/admin/config` | RequireAdmin | 更新系统配置（部分字段） |

`AdminConfigUpdateRequest`（PATCH 入参）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `siteName` | string | 站点名称 |
| `siteLogo` | string | Logo URL |
| `icpNumber` | string | 备案号 |
| `registrationEnabled` | boolean | 是否开放注册 |
| `smsLoginEnabled` | boolean | 是否开启短信登录 |
| `emailLoginEnabled` | boolean | 是否开启邮箱登录 |
| `sensitiveWordFilterEnabled` | boolean | 是否开启敏感词过滤 |
| `maintenanceMode` | boolean | 是否开启维护模式 |
| `maintenanceMessage` | string | 维护模式提示信息 |

错误：`403 ADMIN_FORBIDDEN`（无写权限）。

---

### 7) 内容管理（任务/标签）— 10 条

> 管理员可按条件检索、查看、管理所有用户的任务和标签数据。

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/admin/tasks` | RequireAdmin | 任务列表（分页/按用户搜索/按象限筛选/按完成状态筛选/按标签筛选/按日期范围筛选）|
| `GET` | `/admin/tasks/{uuid}` | RequireAdmin | 任务详情（含完整 tag 对象、所属用户信息）|
| `DELETE` | `/admin/tasks/{uuid}` | RequireAdmin | 任务软删除 |
| `POST` | `/admin/tasks/batch` | RequireAdmin | 批量删除/恢复 |
| `GET` | `/admin/tags` | RequireAdmin | 标签列表（分页/按用户搜索/按名称模糊搜索）|
| `GET` | `/admin/tags/{uuid}` | RequireAdmin | 标签详情（名称/颜色/使用任务数/使用该标签的用户列表）|
| `PATCH` | `/admin/tags/{uuid}` | RequireAdmin | 标签编辑（修改名称/颜色）|
| `DELETE` | `/admin/tags/{uuid}` | RequireAdmin | 标签删除（自动解除关联任务）|
| `GET` | `/admin/users/{uuid}/tasks` | RequireAdmin | 用户任务列表（分页/按象限筛选/按完成状态筛选）|
| `GET` | `/admin/users/{uuid}/tags` | RequireAdmin | 用户标签列表（含颜色/使用任务数）|

#### `GET /admin/tasks`

Query：`page` / `pageSize` / `userUuid` / `quadrant` (1-4) / `completed` (boolean) / `tagUuid` / `startTime` / `endTime`。

响应 `items` 元素：

```json
{
  "uuid": "...",
  "title": "...",
  "urgencyLevel": 2,
  "importanceLevel": -1,
  "completed": false,
  "completedAt": null,
  "tags": [{ "uuid": "...", "name": "工作", "color": "#A78BFA" }],
  "userUuid": "...",
  "userNickname": "张三",
  "createdAt": "...",
  "updatedAt": "..."
}
```

#### `GET /admin/tasks/{uuid}`

→ 任务对象（同列表元素 + `note` / `recurrence` / `checklist` 数组 / `sortOrder`）。

#### `GET /admin/users/{uuid}/tasks`

Query：`page` / `pageSize` / `quadrant` / `completed`。  
→ 该用户的所有任务列表。

#### `GET /admin/users/{uuid}/tags`

Query：`page` / `pageSize`。  
→ 该用户的所有标签列表：`{ uuid, name, color, taskCount }`。

#### `GET /admin/tags`

Query：`page` / `pageSize` / `userUuid` / `q`（名称模糊搜索）。

响应 `items` 元素：

```json
{
  "uuid": "...",
  "name": "工作",
  "color": "#A78BFA",
  "isPreset": false,
  "taskCount": 12,
  "userUuid": "...",
  "userNickname": "张三",
  "createdAt": "..."
}
```

#### `GET /admin/tags/{uuid}`

→ 标签对象 + `taskCount` + `users`（使用该标签的用户列表：`[{ uuid, nickname }]`）。

#### `PATCH /admin/tags/{uuid}`

```json
{ "name": "新名称", "color": "#FF5722" }
```

#### `DELETE /admin/tags/{uuid}`

→ `data: null`。删除后自动解除 `sishiyouxu_task_tag` 关联行。

### 8) Phase 4 占位（skeleton）— 12 条

> 这些路由当前返回 `{ status: "skeleton", endpoint, items? }`，**实际业务逻辑在 Phase 4 实现**。前端可临时接入但不应在生产环境使用。

#### 敏感词

| 方法 | 路径 | 鉴权 |
| --- | --- | --- |
| `GET` | `/admin/sensitive-words` | RequireAdmin |
| `POST` | `/admin/sensitive-words` | RequireAdmin |
| `PATCH` | `/admin/sensitive-words/{uuid}` | RequireAdmin |
| `DELETE` | `/admin/sensitive-words/{uuid}` | RequireAdmin |
| `POST` | `/admin/sensitive-words/import` | RequireAdmin |

#### IP 黑名单

| 方法 | 路径 | 鉴权 |
| --- | --- | --- |
| `GET` | `/admin/security/ip-blacklist` | RequireAdmin |
| `POST` | `/admin/security/ip-blacklist` | RequireAdmin |
| `DELETE` | `/admin/security/ip-blacklist/{uuid}` | RequireAdmin |

#### 公告

| 方法 | 路径 | 鉴权 |
| --- | --- | --- |
| `GET` | `/admin/announcements` | RequireAdmin |
| `POST` | `/admin/announcements` | RequireAdmin |
| `PATCH` | `/admin/announcements/{uuid}` | RequireAdmin |
| `DELETE` | `/admin/announcements/{uuid}` | RequireAdmin |

---

## 元端点 / 健康检查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查（无鉴权） |
| `GET` | `/` | 服务根信息（无鉴权） |
| `GET` | `/openapi.json` | OpenAPI 3.1 规范 |
| `GET` | `/docs` | RapiDoc 文档页 |
| `GET` | `/redoc` | （保留） |
| `GET` | `/static/*` | Swagger 静态资源（本地化） |

`/health` 响应：

```json
{
  "success": true,
  "data": { "status": "ok", "version": "0.x", "env": "dev" }
}
```

---

## WebSocket

> 路径独立于 `/api/v1`，**不走 API 版本路由层**。

### 1) 用户端通知 WS

```
WS /ws/notifications?token=<ws-ticket>
```

握手流程：

1. 客户端用 access_token 调 `POST /api/v1/auth/ws-ticket` 获取一次性 ticket。
2. 客户端使用 `wss://host/ws/notifications?token=<ticket>` 建立连接。
3. 服务端校验 ticket（一次性消费、Redis 校验），无效关闭并 code=4401。
4. 校验通过后服务端推送 `hello` 事件：
   ```json
   { "event": "hello", "channel": "notifications", "userUuid": "..." }
   ```
5. 客户端发送 `ping`，服务端回复 `pong`（用于心跳，90s 无心跳则主动断开）。
6. 通知推送（Phase 5 接入）：
   ```json
   {
     "event": "notification",
     "data": {
       "uuid": "...",
       "kind": "task_reminder | system_announcement",
       "title": "...",
       "body": "...",
       "taskUuid": "...",
       "createdAt": "..."
     }
   }
   ```

> ⚠️ **小程序兼容**：微信 `wx.connectSocket` 不支持自定义 Header，所以必须用 query `?token=<ticket>`；浏览器如需避免 ticket 进 URL 日志，可改用 `Sec-WebSocket-Protocol: bearer, <access_token>`（当前 main.py **未**实现此备选路径，统一走 ticket 方式）。

### 2) 管理端通知 WS

```
WS /admin/ws/notifications?token=<ws-ticket>
```

握手流程同上，`hello` 事件 `channel: "admin.notifications"`。

### 错误码

| code | 含义 |
| --- | --- |
| `4401` | ws-ticket 缺失 / 无效 / 已消费 |
| `4001` | （历史定义，保留）token 无效 |
| `4002` | 用户被禁用或账号异常 |
| `4003` | 权限不足（普通用户访问 admin WS） |
| `4009` | 心跳超时 |

---

## 限流

> 实现：基于 Redis 的滑动窗口。匿名按 IP 限流；需认证按 user_uuid 限流。

| 端点 | 限制 | 维度 |
| --- | --- | --- |
| `POST /api/v1/auth/tokens` | 10 次/分钟 | IP |
| `POST /api/v1/auth/sms/send` | 1 次/分钟 | IP + phone |
| `POST /api/v1/auth/email/send` | 1 次/分钟 | IP + email |
| `POST /api/v1/sync/push` | 60 次/分钟 | user |
| `GET /api/v1/sync/status`（公开） | 120 次/分钟 | IP |
| 其他需认证接口 | 120 次/分钟 | user |

超限返回 `429`：

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "请求过于频繁，请稍后再试",
    "detail": { "retry_after": 60 }
  }
}
```

---

## OpenAPI / RapiDoc

| 资源 | 路径 | 说明 |
| --- | --- | --- |
| 交互式 API 文档 | `/docs` | RapiDoc，本地 JS/CSS，中文 UI |
| ReDoc | `/redoc` | （保留） |
| OpenAPI 规范 | `/openapi.json` | OpenAPI 3.1 JSON 规范 |
| 健康检查 | `/health` | 无鉴权，DB/Redis 启动期不可用时仍返回 `ok` |

所有路由均使用 Pydantic 模型定义入参与响应，Swagger 自动展示完整 schema（含字段约束、enum、example）。

---

## 接口总览（93 条）

> 由 `python -c "from src.main import app; print(len(app.openapi()['paths']))"` 实时生成。（当前 93 条。）

### 元端点（5）

- `GET /`
- `GET /health`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`

### 用户端 — 认证（15）

- `POST /api/v1/auth/tokens`
- `POST /api/v1/auth/tokens/refresh`
- `POST /api/v1/auth/tokens/logout`
- `POST /api/v1/auth/tokens/logout-all`
- `POST /api/v1/auth/wechat/login`
- `POST /api/v1/auth/ws-ticket`
- `GET /api/v1/auth/login-methods`
- `GET /api/v1/auth/captcha`
- `POST /api/v1/auth/captcha/verify`
- `POST /api/v1/auth/sms/send`
- `POST /api/v1/auth/sms/login`
- `POST /api/v1/auth/email/send`
- `POST /api/v1/auth/email/login`
- `POST /api/v1/auth/password/reset-request`
- `POST /api/v1/auth/password/reset`

### 用户端 — 用户资料（11）

- `POST /api/v1/users`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
- `POST /api/v1/users/me/password`
- `POST /api/v1/users/me/avatar`
- `GET /api/v1/users/me/auth-linkage`
- `POST /api/v1/users/me/auth-linkage/token`
- `PUT /api/v1/users/me/auth-linkage/{provider}`
- `DELETE /api/v1/users/me/auth-linkage/{provider}`
- `GET /api/v1/users/me/reminder-channels`
- `PATCH /api/v1/users/me/reminder-channels`

### 用户端 — 任务（7）

- `GET /api/v1/tasks`
- `POST /api/v1/tasks`
- `GET /api/v1/tasks/{uuid}`
- `PATCH /api/v1/tasks/{uuid}`
- `DELETE /api/v1/tasks/{uuid}`
- `POST /api/v1/tasks/{uuid}/restore`
- `POST /api/v1/tasks/batch`

### 用户端 — 检查项（4）

- `GET /api/v1/tasks/{task_uuid}/checklist`
- `POST /api/v1/tasks/{task_uuid}/checklist`
- `PATCH /api/v1/tasks/{task_uuid}/checklist/{item_uuid}`
- `DELETE /api/v1/tasks/{task_uuid}/checklist/{item_uuid}`

### 用户端 — 标签（4）

- `GET /api/v1/tags`
- `POST /api/v1/tags`
- `PATCH /api/v1/tags/{uuid}`
- `DELETE /api/v1/tags/{uuid}`

### 用户端 — 通知（5）

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `PATCH /api/v1/notifications/{uuid}/read`
- `POST /api/v1/notifications/read-all`
- `DELETE /api/v1/notifications/{uuid}`

### 用户端 — 反馈（2）

- `POST /api/v1/feedback`
- `GET /api/v1/feedback`

### 用户端 — 同步（3）

- `POST /api/v1/sync/push`
- `GET /api/v1/sync/pull`
- `GET /api/v1/sync/status`

### 管理端 — 认证（4）

- `POST /api/v1/admin/auth/tokens`
- `POST /api/v1/admin/auth/tokens/refresh`
- `DELETE /api/v1/admin/auth/tokens`
- `POST /api/v1/admin/auth/password`

### 管理端 — 用户管理（11 条）

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/me`
- `GET /api/v1/admin/users/{uuid}`
- `PATCH /api/v1/admin/users/{uuid}`
- `DELETE /api/v1/admin/users/{uuid}`
- `POST /api/v1/admin/users/{uuid}/disable`
- `POST /api/v1/admin/users/{uuid}/enable`
- `POST /api/v1/admin/users/{uuid}/force-logout`
- `POST /api/v1/admin/users/{uuid}/reset-password`
- `POST /api/v1/admin/users/batch`
- `GET /api/v1/admin/users/export`
- `GET /api/v1/admin/users/{uuid}/tasks`
- `GET /api/v1/admin/users/{uuid}/tags`

### 管理端 — 仪表盘（2 条）

- `GET /api/v1/admin/dashboard/stats`
- `GET /api/v1/admin/dashboard/charts/{metric}`

### 管理端 — 审计（3）

- `GET /api/v1/admin/audit`
- `GET /api/v1/admin/audit/{uuid}`
- `GET /api/v1/admin/login-logs`

### 管理端 — 反馈（3）

- `GET /api/v1/admin/feedback`
- `PATCH /api/v1/admin/feedback/{uuid}`
- `DELETE /api/v1/admin/feedback/{uuid}`

### 管理端 — 系统配置（2 条）

- `GET /api/v1/admin/config`
- `PATCH /api/v1/admin/config`

### 管理端 — 内容管理（10 条）

- `GET /api/v1/admin/tasks`
- `GET /api/v1/admin/tasks/{uuid}`
- `DELETE /api/v1/admin/tasks/{uuid}`
- `POST /api/v1/admin/tasks/batch`
- `GET /api/v1/admin/tags`
- `GET /api/v1/admin/tags/{uuid}`
- `PATCH /api/v1/admin/tags/{uuid}`
- `DELETE /api/v1/admin/tags/{uuid}`
- `GET /api/v1/admin/users/{uuid}/tasks`
- `GET /api/v1/admin/users/{uuid}/tags`

## 接口总览（102 路由）

> 98 条 HTTP 操作 + 2 条 WebSocket 路由。用户端 51 + 管理端 45 + 元端点 2 + WebSocket 2 = 100。

### 元端点（2 操作）

- `GET /`
- `GET /health`

### 用户端 — 认证（15 条）

- `POST /api/v1/auth/tokens`
- `POST /api/v1/auth/tokens/refresh`
- `POST /api/v1/auth/tokens/logout`
- `POST /api/v1/auth/tokens/logout-all`
- `POST /api/v1/auth/wechat/login`
- `POST /api/v1/auth/ws-ticket`
- `GET /api/v1/auth/login-methods`
- `GET /api/v1/auth/captcha`
- `POST /api/v1/auth/captcha/verify`
- `POST /api/v1/auth/sms/send`
- `POST /api/v1/auth/sms/login`
- `POST /api/v1/auth/email/send`
- `POST /api/v1/auth/email/login`
- `POST /api/v1/auth/password/reset-request`
- `POST /api/v1/auth/password/reset`

### 用户端 — 用户资料（11 条）

- `POST /api/v1/users`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`
- `POST /api/v1/users/me/password`
- `POST /api/v1/users/me/avatar`
- `GET /api/v1/users/me/auth-linkage`
- `POST /api/v1/users/me/auth-linkage/token`
- `PUT /api/v1/users/me/auth-linkage/{provider}`
- `DELETE /api/v1/users/me/auth-linkage/{provider}`
- `GET /api/v1/users/me/reminder-channels`
- `PATCH /api/v1/users/me/reminder-channels`

### 用户端 — 任务（7 条）

- `GET /api/v1/tasks`
- `POST /api/v1/tasks`
- `GET /api/v1/tasks/{uuid}`
- `PATCH /api/v1/tasks/{uuid}`
- `DELETE /api/v1/tasks/{uuid}`
- `POST /api/v1/tasks/{uuid}/restore`
- `POST /api/v1/tasks/batch`

### 用户端 — 检查项（4 条）

- `GET /api/v1/tasks/{task_uuid}/checklist`
- `POST /api/v1/tasks/{task_uuid}/checklist`
- `PATCH /api/v1/tasks/{task_uuid}/checklist/{item_uuid}`
- `DELETE /api/v1/tasks/{task_uuid}/checklist/{item_uuid}`

### 用户端 — 标签（4 条）

- `GET /api/v1/tags`
- `POST /api/v1/tags`
- `PATCH /api/v1/tags/{uuid}`
- `DELETE /api/v1/tags/{uuid}`

### 用户端 — 通知（5 条）

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `PATCH /api/v1/notifications/{uuid}/read`
- `POST /api/v1/notifications/read-all`
- `DELETE /api/v1/notifications/{uuid}`

### 用户端 — 反馈（2 条）

- `POST /api/v1/feedback`
- `GET /api/v1/feedback`

### 用户端 — 同步（3 条）

- `POST /api/v1/sync/push`
- `GET /api/v1/sync/pull`
- `GET /api/v1/sync/status`

### 管理端 — 认证（4 条）

- `POST /api/v1/admin/auth/tokens`
- `POST /api/v1/admin/auth/tokens/refresh`
- `DELETE /api/v1/admin/auth/tokens`
- `POST /api/v1/admin/auth/password`

### 管理端 — 用户管理（11 条）

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/me`
- `GET /api/v1/admin/users/{uuid}`
- `PATCH /api/v1/admin/users/{uuid}`
- `DELETE /api/v1/admin/users/{uuid}`
- `POST /api/v1/admin/users/{uuid}/disable`
- `POST /api/v1/admin/users/{uuid}/enable`
- `POST /api/v1/admin/users/{uuid}/force-logout`
- `POST /api/v1/admin/users/{uuid}/reset-password`
- `POST /api/v1/admin/users/batch`
- `GET /api/v1/admin/users/export`

### 管理端 — 仪表盘（2 条）

- `GET /api/v1/admin/dashboard/stats`
- `GET /api/v1/admin/dashboard/charts/{metric}`

### 管理端 — 审计（3 条）

- `GET /api/v1/admin/audit`
- `GET /api/v1/admin/audit/{uuid}`
- `GET /api/v1/admin/login-logs`

### 管理端 — 反馈（3 条）

- `GET /api/v1/admin/feedback`
- `PATCH /api/v1/admin/feedback/{uuid}`
- `DELETE /api/v1/admin/feedback/{uuid}`

### 管理端 — 系统配置（2 条）

- `GET /api/v1/admin/config`
- `PATCH /api/v1/admin/config`

### 管理端 — 内容管理（8 条）

- `GET /api/v1/admin/tasks`
- `GET /api/v1/admin/tasks/{uuid}`
- `DELETE /api/v1/admin/tasks/{uuid}`
- `POST /api/v1/admin/tasks/batch`
- `GET /api/v1/admin/tags`
- `GET /api/v1/admin/tags/{uuid}`
- `PATCH /api/v1/admin/tags/{uuid}`
- `DELETE /api/v1/admin/tags/{uuid}`

### 管理端 — Phase 4 skeleton（13 条）

> 以下路由返回 `{ status: "skeleton", endpoint: "..." }`，实际业务逻辑在 Phase 4 实现。

- `GET /api/v1/admin/sensitive-words`
- `POST /api/v1/admin/sensitive-words`
- `PATCH /api/v1/admin/sensitive-words/{uuid}`
- `DELETE /api/v1/admin/sensitive-words/{uuid}`
- `POST /api/v1/admin/sensitive-words/import`
- `GET /api/v1/admin/security/ip-blacklist`
- `POST /api/v1/admin/security/ip-blacklist`
- `DELETE /api/v1/admin/security/ip-blacklist/{uuid}`
- `GET /api/v1/admin/announcements`
- `POST /api/v1/admin/announcements`
- `PATCH /api/v1/admin/announcements/{uuid}`
- `DELETE /api/v1/admin/announcements/{uuid}`
- `GET /api/v1/admin/login-logs`

### WebSocket（2）

- `WS /ws/notifications`
- `WS /admin/ws/notifications`

---

## 修改记录

| 日期 | 变更 |
| --- | --- |
| 2026-06-28 | 与 开发进度.md 对齐：Phase 4 仍标记为「未开始」（13 条 skeleton 占位）；修正 admin 用户管理为 10 条（移除重复的 `users/{uuid}/tasks` 和 `users/{uuid}/tags`）；接口总览 = 100 路由 = 98 HTTP 操作 + 2 WebSocket |
| 2026-06-28 | 修正接口总览：删除大量重复粘贴的端点列表，更新端点计数为 98 HTTP + 2 WebSocket（用户端 51 + 管理端 45 + 元端点 2）；修正各小节计数（auth 15, users 11, 用户管理 12, skeleton 13）；/docs 文档名从 Swagger UI 更正为 RapiDoc |
| 2026-06-27 | 全文重写 + 内容管理实现：补齐 67 条端点（auth/users/tasks/tags/notifications/feedback/sync 等）；新增管理端内容管理 10 条端点（admin/tasks, admin/tags, admin/users/{uuid}/tasks, admin/users/{uuid}/tags），总计 98 条端点 |
| 2026-06-28 | 新增：`POST /admin/auth/password`（管理员修改自己密码）、`POST /admin/users/{uuid}/reset-password`（管理员重置用户密码）；force-logout 现在同时通过 Redis 失效 access token；总端点 102（100 HTTP + 2 WS） |
| 2026-06-28 | 文档对齐：总端点数统一为 100（98 HTTP + 2 WS）；同步 entities 参数名规范（push 用单数 entity 值 task/tag/taskTag/checklistItems，pull 响应顶层用复数键 tasks/tags/taskTags/checklistItems）；路由数与 CLAUDE.md 对齐 |
| 2026-06-27 | 全文重写：基于 OpenAPI 67 条端点补齐缺失路由（ws-ticket、sms/email、captcha、reminder-channels、admin dashboard/charts/audit/feedback/config、sensitive-words/ip-blacklist/announcements skeleton 等），修正 `/admin/auth/tokens` 登出方法为 `DELETE`、移除已废弃的 `/users/phone` 与 `/users/email`、补全错误码、限流、WebSocket 错误码 |
