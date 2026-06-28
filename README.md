<p align="center">
  <h1 align="center">四时有序 · Sishi Youxu</h1>
  <p align="center"><strong>基于艾森豪威尔矩阵的个人任务管理工具</strong></p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue 3">
  <img src="https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Node.js-20+-339933?logo=nodedotjs&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/MySQL-8.0+-4479A1?logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Redis-6.0+-DC382D?logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
</p>

---

## 📖 项目简介

**四时有序** 是一款全栈个人任务管理应用，以 **艾森豪威尔矩阵**（Eisenhower Matrix）为核心交互模型。用户将任务按照「重要性」和「紧急性」两个维度拖拽定位到四个象限中，从而获得清晰直观的任务优先级视图。

> 艾森豪威尔矩阵将任务分为四类：**重要且紧急**（立即处理）、**重要不紧急**（计划安排）、**紧急不重要**（尽快完成）、**不紧急不重要**（有空再做）。

- **用户端**：四象限拖拽画布 + 离线优先同步
- **管理后台**：用户管理、内容审核、数据仪表盘
- **多端兼容**：Web / PWA / 微信小程序（后端 API 已就位）

---

## ✨ 功能特性

### 用户端

| 模块 | 功能 |
|------|------|
| 🎯 四象限画布 | 拖拽定位任务卡片，按重要/紧急双维度分布，象限自动判定 |
| ✅ 任务管理 | 创建/编辑/完成/删除/恢复任务，支持检查项（Checklist）子资源 |
| 🔁 重复任务 | 每日/每周/每月自动生成下一期任务 |
| 🏷️ 标签系统 | 4 个预设标签 + 自定义标签，多标签筛选 |
| 🔐 多方式登录 | 账号密码 / 手机短信 / 邮箱验证码 / 微信授权 |
| 📡 离线同步 | IndexedDB 本地存储 + 云端同步，冲突可视化解决 |
| 🌓 主题与密度 | 浅色/深色/跟随系统主题，紧凑/标准/详细视图密度 |
| ⌨️ 键盘快捷键 | N 新建 / Esc 关闭 / Ctrl+Z/Y 撤销重做 / D 切换密度 |

### 管理后台

| 模块 | 功能 |
|------|------|
| 📊 数据仪表盘 | DAU/MAU、任务完成率、象限分布图表（ECharts） |
| 👥 用户管理 | 列表/详情/禁用/启用/强制登出/批量操作/CSV 导出 |
| 📝 内容管理 | 任务审核、标签管理、敏感词过滤 |
| 🔒 安全运营 | IP 黑名单、登录日志、操作审计 |
| 📢 公告管理 | 系统公告发布/编辑/置顶/定时 |
| ⚙️ 系统配置 | 站点信息、注册开关、功能开关、维护模式 |

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | Python 3.12 + FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) + aiomysql |
| **数据库** | MySQL 8.0 |
| **缓存** | Redis |
| **认证** | JWT（access + refresh token）+ bcrypt |
| **多 Provider** | password / phone_sms / email_code / wechat |
| **用户端前端** | Vue 3 + TypeScript + Vite + Pinia + Dexie.js |
| **管理后台前端** | Vue 3 + Element Plus + ECharts |
| **实时通信** | WebSocket（ws-ticket 鉴权） |
| **API 文档** | RapiDoc（中文友好） |

---

## 📸 系统截图

> 📌 截图待补充 — 请在此处放置系统截图。

<!--
### 用户端
![四象限画布](docs/screenshots/quadrant.png)
![任务编辑](docs/screenshots/task-edit.png)

### 管理后台
![仪表盘](docs/screenshots/admin-dashboard.png)
![用户管理](docs/screenshots/admin-users.png)
-->

---

## 🚀 快速开始

### 环境要求

- **Python** 3.12+
- **Node.js** 20+
- **MySQL** 8.0+
- **Redis** 6.0+

### 1. 克隆项目

```bash
git clone https://github.com/your-username/sishi-youxu.git
cd sishi-youxu
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env              # 按需修改数据库/Redis/JWT 配置

# 初始化数据库
mysql -u root -p < scripts/init_db.sql
mysql -u root -p sishi_youxu < scripts/seed.sql

# 创建默认管理员（admin / 123456）
python scripts/init_admin.py

# 启动服务
python -m uvicorn src.main:app --reload --port 8000
```

启动后可访问：
- 健康检查：http://127.0.0.1:8000/health
- API 文档：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc

### 3. 启动用户端

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

### 4. 启动管理后台

```bash
cd admin
npm install
npm run dev        # http://localhost:4000
```

### 5. 运行测试

```bash
cd backend
python scripts/run_tests.py
```

---

## 📂 项目结构

```
sishi-youxu/
├── backend/                    # FastAPI 后端（端口 8000）
│   ├── src/
│   │   ├── apps/
│   │   │   ├── user/          # 用户端 API（auth/tasks/tags/sync/notifications）
│   │   │   └── admin/         # 管理端 API（users/dashboard/audit/config）
│   │   ├── core/              # 配置、数据库、Redis、安全、异常、中间件
│   │   ├── models/            # SQLAlchemy ORM（16 张表）
│   │   └── repositories/      # 数据访问层
│   ├── scripts/               # init_db.sql / seed.sql / init_admin.py
│   └── tests/                 # pytest 测试
├── web/                        # Vue 3 用户端（端口 3000）
│   └── src/
│       ├── api/               # REST API 封装（6 个模块）
│       ├── components/        # 通用组件（common/task/quadrant/layout）
│       ├── db/                # Dexie 本地数据库（7 个 store）
│       ├── stores/            # Pinia 状态管理
│       └── views/             # 页面（Login/Register/Home/Settings）
├── admin/                      # Vue 3 管理后台（端口 4000）
│   └── src/
│       ├── api/               # 管理端 API 封装
│       ├── stores/            # Pinia 状态管理
│       └── views/             # 13 个管理页面
├── docs/                       # 项目文档（10 份）
├── capacitor/                  # Capacitor 移动端（占位）
└── e2e/                        # Playwright E2E 测试（占位）
```

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [系统开发需求](docs/01-概览/系统开发需求-完整版.md) | 完整功能需求（P0/P1/P2） |
| [开发阶段规划](docs/01-概览/开发阶段规划.md) | Phase 0~8 详细计划 |
| [开发进度](docs/01-概览/开发进度.md) | 当前代码完成度看板 |
| [用户端 UI 设计规范](docs/02-设计规范/用户端UI设计规范.md) | 四象限主页 UI 规范与设计系统 |
| [管理后台 UI 设计规范](docs/02-设计规范/管理后台UI设计规范.md) | 管理后台 UI 规范 |
| [API 接口文档](docs/03-技术架构/API接口文档.md) | REST API 完整规范（100 端点） |
| [数据库设计文档](docs/03-技术架构/数据库设计文档.md) | ER 图与表结构 |
| [技术规格](docs/03-技术架构/技术规格.md) | 架构、Redis、JWT、限流 |
| [同步协议](docs/03-技术架构/同步协议.md) | 离线同步协议 |
| [工程指南](docs/04-工程与部署/工程指南.md) | 部署、测试、开发规范 |

---

## 🗺️ 开发阶段

| Phase | 名称 | 状态 |
|:-----:|------|:----:|
| 0 | 项目骨架 | ✅ 已完成 |
| 1 | 管理端核心（后端 + 前端） | ✅ 已完成 |
| 2 | 用户端核心（后端 API） | ✅ 已完成 |
| 3 | 认证与同步 | ⚠️ 后端完成 / 前端 0% |
| 4 | 管理端增强 | ✅ 已完成 |
| 5 | 用户端增强 | ❌ 未开始 |
| 6 | 测试与部署 | ⚠️ 仅烟雾测试 |
| 7 | 微信小程序扩展 | ⏸ 远期 |
| 8 | 移动端（Capacitor） | ⏸ 远期 |

**当前整体进度：约 65%**（Phase 0~4 全部完成，Phase 3 前端待开发）

详见 [开发阶段规划](docs/01-概览/开发阶段规划.md)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。请遵循项目内的 Git 提交规范：

```
<type>(<scope>): <description>
```

类型：`feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `chore`

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<p align="center">
  <sub>Made with ❤️ for better task management</sub>
</p>
