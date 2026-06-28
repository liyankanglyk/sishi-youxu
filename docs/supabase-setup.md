# Supabase 部署指南

四时有序使用 [Supabase](https://supabase.com) 提供用户认证和云端数据同步。

---

## 1. 创建 Supabase 项目

1. 访问 [supabase.com](https://supabase.com)，注册/登录
2. 点击 **New Project**
3. 填写项目名称（如 `sishi-youxu`），设置数据库密码
4. 选择离你最近的区域（亚洲推荐 Singapore 或 Tokyo）
5. 等待项目初始化（约 2 分钟）

## 2. 获取 API 密钥

1. 进入项目 Dashboard → **Settings → API**
2. 复制 **Project URL**（格式：`https://xxxxx.supabase.co`）
3. 复制 **anon public key**

## 3. 配置环境变量

在项目根目录创建 `.env` 文件（参考 `.env.example`）：

```env
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 4. 执行数据库迁移

1. Supabase Dashboard → **SQL Editor**
2. 复制 `supabase/migrations/001_schema.sql` 的全部内容
3. 粘贴到 SQL Editor 中，点击 **Run**

> 这会创建 `sishi_tasks` 和 `sishi_tags` 表，启用 Row-Level Security，每个用户只能访问自己的数据。

## 5. 配置认证

### Email + Password 登录（主要方式）

无需额外配置，Supabase 默认开启。用户在应用内注册邮箱+密码即可登录。

**注册确认**：
- 开发阶段：**Authentication → Settings** → 关闭 **Confirm email**（注册后无需邮件验证）
- 生产环境：建议开启 **Confirm email**

### Magic Link（免密码登录）

同样无需额外配置。用户输入邮箱 → 收邮件 → 点链接自动登录。

### 手机号登录（预留）

项目代码中已预留入口（显示"即将推出"）。如需开启：
1. Supabase Dashboard → **Authentication → Providers** → **Phone**
2. 配置短信服务商（Twilio / MessageBird 等）
3. 取消 LoginPage 中手机号按钮的 `disabled` 属性

### URL Configuration

**Authentication → URL Configuration**：
- Site URL：`http://localhost:5173`（开发）/ 生产域名
- Redirect URLs：添加 `http://localhost:5173` 和生产域名

## 6. 启动应用

```bash
npm install          # 确保依赖已安装
npm run dev          # 启动开发服务器
```

打开 `http://localhost:5173`，你会看到登录页面。输入邮箱 → 收件箱点击链接 → 自动登录。

---

## 可选：开启实时同步

数据库迁移中已包含 `ALTER PUBLICATION supabase_realtime ADD TABLE`，实时同步默认开启。

如需手动开启：
1. Supabase Dashboard → **Database → Replication**
2. 确保 `sishi_tasks` 和 `sishi_tags` 表在 publication 中

---

## 本地开发 vs 生产

| 环境 | Supabase 项目 | .env |
|------|-------------|------|
| 本地开发 | 可以用同一个项目 | `.env` |
| 生产部署 | 建议单独项目 | 部署平台的环境变量配置 |
