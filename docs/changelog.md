# 四时有序 — 变更记录

---

## v1.5 (2026-06-19)

### 🔧 精简 + 健壮性

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 等级范围收窄 | -5~5 → -4~4（9 档），坐标 6%~94%，彻底消灭卡片溢出 | `types/index.ts`, `db/index.ts` |
| 主题简化 | 移除"跟随系统"模式，仅保留 ☀️ 浅色 / 🌙 深色二态直切 | `useStore.ts`, `App.tsx`, `index.css` |
| sync.ts 重写 | 去 `DEBUG_SYNC` 硬编码→`import.meta.env.DEV`，SupabaseRow 统一类型，报错优雅降级 | `lib/sync.ts` |
| 安全增强 | TaskCard 去 `dangerouslySetInnerHTML`→纯文本，侧边栏拖拽 ref 解决闭包过期 | `TaskCard.tsx`, `App.tsx` |
| DRY | `getQuadrant()` 替代 4 处手写象限判断，`QUADRANT_ORDER` 统一引用 | `useStore.ts`, `StatsPanel.tsx` |
| 标签同步修复 | 云端按名称合并标签 + ID 映射修正，预设标签改云端创建（确定性 UUID v5） | `lib/sync.ts`, `db/index.ts`, `useStore.ts` |
| Realtime 修复 | `subscribeToChanges` async + 防重入 + `unsubscribeChanges` 异步清理 | `lib/sync.ts`, `useStore.ts` |
| 登录页优化 | 邮箱密码 + Magic Link + 手机号预留，错误信息全中文化 | `LoginPage.tsx`, `useStore.ts` |

### 📄 文档

| 变更 | 涉及文件 |
|------|----------|
| 目录结构清单 | `docs/directory-structure.md` |
| 更新全部文档 | `README.md`, `requirements.md`, `changelog.md` |

---

## v1.4 (2026-06-19)

### 🎨 Taste-skill UI 优化 + 🎉 庆祝动画 + 🔧 重复任务精确修复

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 卡片密度真正区分 | 紧凑（44px/仅标题）、标准（68px/标题+日期+标签色点）、详细（90px/级别+标题+日期+标签名+备注摘要），`min-h` 固定高度解决有无日期卡片高矮不一 | `TaskCard.tsx` |
| Phosphor 图标库 | 替换全部手写 SVG → `@phosphor-icons/react`，移除 📝🔄 等 emoji 指示符，tree-shaking 仅增 ~6KB | `App.tsx`, `TaskCard.tsx`, `TaskList.tsx` |
| 完成庆祝动画 | `canvas-confetti` 粒子爆发——中心 burst 50 粒 + 1.5s 持续扇形喷射，象限五色，`prefers-reduced-motion` 自动禁用，批量操作不触发 | `App.tsx`, `useStore.ts`, `types/canvas-confetti.d.ts` |
| 重复任务精确修复 | Task 新增 `generatedNextId`，完成时写回关联 → 恢复/撤销时精确删除下一期，消除完成→恢复循环导致的卡片复制 | `types/index.ts`, `useStore.ts`, `db/index.ts` |
| 按钮圆角统一 | 主 CTA 改为 `rounded-xl`（与其他按钮一致），密集段选器统一 `rounded-xl` | `App.tsx`, `TaskForm.tsx` |
| 阴影降噪 | 取消主按钮紫色阴影 `shadow-purple-200/40`，过期卡片改用 `ring-1` 替代 `shadow` | `App.tsx`, `TaskCard.tsx` |

### 🔌 新增依赖

| 包 | 用途 |
|------|------|
| `@phosphor-icons/react` | 图标库（Phosphor，替代手写 SVG） |
| `canvas-confetti` | 轻量粒子庆祝动画 |

### 📄 文档

| 变更 | 涉及文件 |
|------|----------|
| README 同步最新功能 + 技术栈 | `README.md` |
| changelog v1.4 | `docs/changelog.md` |
| requirements 更新 | `docs/requirements.md` |

---

## v1.3 (2026-06-19)

### 📊 统计 + 🔄 重复任务 + 🌓 深色模式全量修复

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 统计仪表盘 | 活跃/已完成/完成率概览卡片、过期/今天/本周计数、象限柱状图、标签分布、近7天完成趋势图（纯 CSS 实现） | `StatsPanel.tsx`, `App.tsx` |
| 重复任务 | Task 新增 `recurrence` 字段（无/每天/每周/每月），完成时自动生成下一期，撤销时清理 | `types/index.ts`, `useStore.ts`, `TaskForm.tsx`, `TaskCard.tsx`, `TaskList.tsx`, `db/index.ts` |
| 深色模式全量修复 | `@variant dark` 声明 + 60+ Tailwind 类名全局映射（bg/text/border/shadow/hover/ring）、象限背景 CSS 变量化、卡片渐变变量化、滚动条/range 适配 | `index.css`, `TaskCard.tsx`, `QuadrantCanvas.tsx` |

### 📄 文档

| 变更 | 涉及文件 |
|------|----------|
| README 全量重写（功能补全 + 快捷键 + 技术栈 + 项目结构） | `README.md` |
| requirements P2 状态更新 + 深色主题描述修正 | `docs/requirements.md` |
| changelog v1.3 补充 | `docs/changelog.md` |

---

## v1.2 (2026-06-19)

### 🎨 增强功能（P2）

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 深色主题手动切换 | 💻/🌙/☀️ 三态切换（跟随系统/深色/浅色），`data-theme` 属性驱动 CSS 变量 | `index.css`, `useStore.ts`, `App.tsx` |
| 浏览器 + 原生到期通知 | Web 端 Notification API，Android/iOS 端 Capacitor Local Notifications 插件，过期/今天任务自动弹窗提醒 | `App.tsx`, `useStore.ts`, `capacitor.config.ts` |
| 标签管理面板 | 独立弹窗：标签列表（颜色+名称+使用计数）、点击编辑、颜色选择器、预设保护、快捷色板 | `TagManager.tsx`, `useStore.ts`, `db/index.ts` |
| 富文本备注 | marked.js Markdown 渲染，TaskForm 编辑/预览切换，TaskCard 详细模式渲染备注，TaskList 备注指示器 📝 | `TaskForm.tsx`, `TaskCard.tsx`, `TaskList.tsx`, `index.css` |

### 🔌 新增依赖

| 包 | 用途 |
|------|------|
| `marked` | Markdown → HTML 渲染（备注富文本） |
| `@capacitor/local-notifications` | 原生平台本地通知（Android/iOS） |

---

## v1.1 (2026-06-19)

### 📱 Capacitor 跨平台集成

| 变更 | 说明 | 涉及文件 |
|------|------|----------|
| Capacitor 安装 | `@capacitor/core` + `@capacitor/cli` + `@capacitor/android` + `@capacitor/ios` | `package.json` |
| Capacitor 配置 | `appId: com.xiaohua.sishiyouxu`，appName: 四时有序 | `capacitor.config.ts` |
| Vite 多 mode 构建 | `--mode web`（PWA 离线） / `--mode capacitor`（相对路径，无 SW） | `vite.config.ts` |
| 多平台 npm scripts | `build:web` / `build:android` / `build:ios` / `build:all` | `package.json` |
| 一键打包脚本 | PowerShell 脚本：构建 → 同步 → 可选打开 IDE | `scripts/build-all.ps1` |
| Android 原生工程 | Capacitor 生成的 Android Studio 工程，支持 APK/AAB 签名打包 | `android/` |
| iOS 原生工程 | Capacitor 生成的 Xcode 工程，支持 IPA 打包上架 App Store | `ios/` |
| .gitignore 更新 | 忽略原生构建产物（build/、.gradle、Pods/ 等），保留平台配置 | `.gitignore` |

### 📄 文档更新

| 变更 | 涉及文件 |
|------|----------|
| README 增加跨平台说明 + 打包发布指南 | `README.md` |
| 需求文档增加跨平台架构图 + 技术说明 | `docs/requirements.md` |

---

## v1.0 (2026-06-19)

### 🎯 核心功能（P0）

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 四象限画布 | Q1-Q4 彩色象限背景 + 坐标轴 + 箭头标注 | `QuadrantCanvas.tsx` |
| 拖拽任务 | @dnd-kit 鼠标+触屏拖拽，实时坐标更新并持久化 | `QuadrantCanvas.tsx`, `TaskCard.tsx` |
| 任务 CRUD | 新建（按钮/双击/长按）、编辑、完成、删除 | `TaskForm.tsx`, `useStore.ts`, `db/index.ts` |
| 标签系统 | 4 条预设（工作/学习/生活/健康）+ 自定义颜色标签 | `types/index.ts`, `db/index.ts`, `TaskForm.tsx` |
| IndexedDB 持久化 | Dexie.js，tasks + tags 两张表，v3 schema | `db/index.ts` |
| JSON 导出 | 一键导出含 tasks/tags/timestamp 的备份文件 | `useStore.ts`, `App.tsx` |
| JSON 导入 | 上传备份文件，支持跳过/覆盖/新建三种冲突策略 | `db/index.ts`, `useStore.ts`, `App.tsx` |
| PWA 支持 | Service Worker 离线缓存 + 可安装 + 自动更新 | `vite.config.ts` |

### ✨ 增强功能（P1）

| 功能 | 说明 | 涉及文件 |
|------|------|----------|
| 三种视图密度 | 紧凑（4.5rem）/ 标准（6.5rem）/ 详细（8.5rem）| `TaskCard.tsx`, `App.tsx` |
| 今日焦点模式 | 📌 一键高亮近期任务，非紧急任务降至 35% 透明度 | `TaskCard.tsx`, `useStore.ts`, `App.tsx` |
| 侧边栏拖拽调节 | 桌面端侧边栏宽度可拖拽调节（200px-50vw），存 localStorage | `App.tsx` |
| 响应式布局 | 桌面端侧边栏 / 移动端底部抽屉 / 平板侧抽屉 | `App.tsx`, `index.css` |
| 搜索 + 多维筛选 | 文本模糊搜索 + 象限按钮 + 日期标签 + 标签色块组合筛选 | `TaskList.tsx`, `useStore.ts` |
| 已完成任务面板 | 侧边栏底部折叠区域，完成时间倒序，支持恢复和永久删除 | `TaskList.tsx`, `useStore.ts`, `db/index.ts` |
| 截止日期状态 | 过期（红色左边框+辉光）、今天（橙色标签）、本周（黄色标签）| `TaskCard.tsx`, `TaskList.tsx`, `types/index.ts` |
| 一键排列 | 象限分组 → 优先级排序 → 等级驱动坐标 → 黄金角碰撞避让 | `useStore.ts` |
| 撤销 / 重做 | 全部任务操作自动记录历史（50 条上限），Ctrl+Z/Y 快捷键 | `useStore.ts`, `App.tsx` |
| 批量操作 | Ctrl+Click 多选 → 批量完成/删除（可撤销），Esc 取消 | `TaskCard.tsx`, `useStore.ts`, `App.tsx` |
| 键盘快捷键 | N / Esc / / / D / Ctrl+Z / Ctrl+Y | `App.tsx` |
| 暗色主题感知 | CSS 变量自动跟随系统 `prefers-color-scheme` | `index.css` |
| 移动端优化 | 安全区域适配、下拉刷新禁用、低端设备关 backdrop-blur | `index.css`, `App.tsx` |

### 🛠️ 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | React + TypeScript | 19.x / ~6.0 |
| 构建 | Vite (Rolldown) | ^8.0.12 |
| 样式 | Tailwind CSS | ^4.3.1 |
| 状态管理 | Zustand | ^5.0.14 |
| 拖拽 | @dnd-kit/core | ^6.3.1 |
| 数据库 | Dexie.js (IndexedDB) | ^4.4.4 |
| UUID | uuid | ^14.0.0 |
| PWA | vite-plugin-pwa | ^1.3.0 |

### 📁 文件统计

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/types/index.ts` | ~160 | 类型定义、常量、象限/日期工具函数 |
| `src/store/useStore.ts` | ~530 | Zustand 全局状态（含历史、筛选、多选） |
| `src/db/index.ts` | ~180 | Dexie CRUD + 导入/导出 + 批量操作 |
| `src/App.tsx` | ~430 | 根组件：布局、快捷键、导入对话框、批量操作栏 |
| `src/components/QuadrantCanvas.tsx` | ~170 | 四象限画布 + DnD Context |
| `src/components/TaskCard.tsx` | ~180 | 拖拽卡片 + 日期状态 + 选中/焦点模式 |
| `src/components/TaskList.tsx` | ~270 | 侧边栏：搜索、筛选器、已完成面板 |
| `src/components/TaskForm.tsx` | ~304 | 创建/编辑弹窗 |
| `src/index.css` | ~165 | 全局样式 + 主题变量 |
| **总计** | **~2,400** | |
