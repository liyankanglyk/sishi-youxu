# 四时有序 — 目录结构清单

```
sishi-youxu/
│
├── .env.example                  # 环境变量模板（Supabase 密钥）
├── .gitignore                    # Git 忽略规则
├── capacitor.config.ts           # Capacitor 跨平台打包配置
├── eslint.config.js              # ESLint 代码检查配置
├── index.html                    # HTML 入口
├── package.json                  # 项目依赖 + npm scripts
├── tsconfig.json                 # TypeScript 配置入口
├── tsconfig.app.json             # App 编译配置
├── tsconfig.node.json            # Node 编译配置
├── vite.config.ts                # Vite 构建配置（多 mode + PWA）
│
├── public/                       # 静态资源（直接复制到 dist）
│   ├── favicon.svg               #   应用图标（四象限彩色）
│   ├── icon-192.png              #   PWA 图标 192px
│   ├── icon-512.png              #   PWA 图标 512px（含 maskable）
│   └── apple-touch-icon.png      #   iOS 主屏幕图标
│
├── supabase/                     # Supabase 数据库
│   └── migrations/
│       └── 001_schema.sql        #   建表 + RLS + 索引 + 实时同步
│
├── scripts/                      # 构建工具脚本
│   └── build-all.ps1             #   一键多平台构建（Web + Android + iOS）
│
├── docs/                         # 项目文档
│   ├── requirements.md           #   功能需求规格（50+ 条）
│   ├── changelog.md              #   版本变更记录
│   ├── supabase-setup.md         #   Supabase 部署指南
│   └── directory-structure.md    #   本文件：目录结构清单
│
├── android/                      # Android 原生工程（Capacitor 生成）
│   ├── app/                      #   应用主模块
│   ├── gradle/                   #   Gradle 构建
│   ├── build.gradle              #   根构建脚本
│   └── variables.gradle          #   构建变量
│
├── ios/                          # iOS 原生工程（Capacitor 生成）
│   └── App/                      #   Xcode 应用
│
└── src/                          # ═══ 应用源码（核心） ═══
    │
    ├── main.tsx                  # React 入口（挂载 #root）
    ├── App.tsx                   # 根组件：布局、路由门控、快捷键、通知、导入
    ├── index.css                 # 全局样式：Tailwind + 主题变量 + 深色覆盖
    │
    ├── types/                    # ── 类型定义与常量 ──
    │   ├── index.ts              #   Task/Tag 模型、象限常量、工具函数
    │   ├── supabase.ts           #   Supabase 数据库表类型（与 SQL Schema 对应）
    │   └── canvas-confetti.d.ts  #   canvas-confetti 库的类型声明
    │
    ├── lib/                      # ── 基础设施 ──
    │   ├── supabase.ts           #   Supabase 客户端初始化（单例）
    │   └── sync.ts               #   云端同步引擎：上传/下拉/实时订阅/标签合并
    │
    ├── store/                    # ── 全局状态 ──
    │   └── useStore.ts           #   Zustand store：认证/任务CRUD/标签/历史/筛选/多选/主题/通知
    │
    ├── db/                       # ── 本地持久化 ──
    │   └── index.ts              #   Dexie IndexedDB：tasks + tags 表，CRUD + 导入导出
    │
    └── components/               # ── UI 组件 ──
        ├── LoginPage.tsx         #   登录/注册页（邮箱密码 + Magic Link）
        ├── QuadrantCanvas.tsx    #   四象限画布（@dnd-kit 拖拽上下文）
        ├── TaskCard.tsx          #   任务卡片（拖拽、日期状态、多选、焦点模式）
        ├── TaskList.tsx          #   侧边栏列表（搜索、筛选器、已完成面板）
        ├── TaskForm.tsx          #   创建/编辑弹窗（Markdown 预览、重复规则）
        ├── TagManager.tsx        #   标签管理面板（编辑/删除/使用统计）
        └── StatsPanel.tsx        #   统计仪表盘（象限柱状图、标签分布、趋势）
```

---

## 数据流

```
用户操作
  │
  ├─→ components/  ──调用──→  store/useStore  ──读写──→  db/index (IndexedDB)
  │                              │                            │
  │                              └──同步──→  lib/sync  ──→  Supabase (云端)
  │                                             │
  │                                             └──实时──→  IndexedDB (跨设备)
  │
  └─→ App.tsx  ──门控──→  LoginPage (未登录) / 主界面 (已登录)
        │
        ├── 快捷键监听 (N/Esc///D/Ctrl+Z/Ctrl+Y)
        ├── 通知系统 (Web Notification / Capacitor Local)
        ├── 主题同步 (data-theme 属性)
        └── 庆祝动画 (canvas-confetti)
```

## 关键依赖关系

| 模块 | 依赖 |
|------|------|
| `components/*` | → `store/useStore`, `types` |
| `store/useStore` | → `db/index`, `lib/sync`, `lib/supabase`, `types` |
| `lib/sync` | → `lib/supabase`, `db/index`, `types` |
| `db/index` | → `lib/supabase`(动态), `types` |
| `types` | → 无依赖（叶子模块） |

## 文件统计

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `src/types/` | 3 | 类型、常量、工具函数 |
| `src/lib/` | 2 | 基础设施（客户端、同步） |
| `src/store/` | 1 | 全局状态（~800 行） |
| `src/db/` | 1 | 本地持久化 |
| `src/components/` | 7 | UI 组件 |
| `docs/` | 4 | 项目文档 |
| **总计** | **~20** | |
