# 用户端 UI 设计规范

> 版本：V1.1.0 | 参考：Things 3、Bear、Notion | 更新日期：2026-07-05

---

## 设计哲学

**目标**：让产品像真实落地的产品，而非AI模板。克制、精准、零渐变、字体承载视觉表达。

**核心原则**：1px border+极轻阴影表达层次 | 8档灰阶+降饱和语义色 | 动效仅作反馈 | 零渐变（轻玻璃允许用于浮层）| 关键节点 spring overshoot 增加手感

---

## 不像 AI 检查清单

每页设计/开发完成前逐条核对：
- [ ] 颜色不超过 4 个：1 个品牌主色 + 3 档灰阶 + 红/绿/橙各 1
- [ ] **零渐变（玻璃仅用于 Header / Modal 蒙层 / 抽屉 / Toast）**
- [ ] 阴影只用 2 档：pop 和 modal
- [ ] 圆角单调：chip 6 / input 10 / button 10 / card 14 / modal 20
- [ ] 标题字距负值 `letter-spacing: -0.02em`
- [ ] 占位文案真实（如"周二产品评审会议准备"而非"请输入任务"）
- [ ] 主按钮仅 1 色；二级按钮用灰底，不用 outline
- [ ] 动效曲线只用 `--ease-standard`（关键节点）或 `--ease-spring`（4 处）

---

## 整体布局

```
┌──────────────────────────────────────────────────────────────────┐
│  Header（56px，固定顶部）  Logo  搜索  撤销/重做  密度  帮助  +新建  通知 头像 │
├──────────────────────────────────────────────────────────────────┤
│  任务列表侧边栏（默认 280px）   │    四象限画布（满屏自适应）          │
│ ┌──────────────────┐          │    ┌─────────────┼─────────────┐  │
│ │ 🔍 搜索...      ⇅ │          │    │    Q2       │     Q1      │  │
│ ├──────────────────┤          │    │  (薄荷绿)   │    (粉)     │  │
│ │ 全部 今天 本周   │          │    │  重要       │  重要       │  │
│ ├──────────────────┤          │    │  不紧急     │  紧急       │  │
│ │ 🔴 需要关注 (3)  │          │    ├─────────────┼─────────────┤ │
│ │   ● ○ 任务A      │          │    │    Q4       │     Q3      │  │
│ │   ● ○ 任务B      │          │    │   (黄)      │    (蓝)     │  │
│ │ 🟡 即将到来 (5)  │          │    │  不重要     │  不重要     │  │
│ │   ● ○ 任务C      │          │    │  不紧急     │  紧急       │  │
│ │ 🔵 计划中 (12)   │          │    └─────────────┴─────────────┘  │
│ │   ● ○ 任务D      │          │       · · · · · ·  (网格点阵)     │
│ │ ✅ 已完成 (8)    │          │              X轴(紧急度)→          │
│ └──────────────────┘          │                                   │
└──────────────────────────────────────────────────────────────────┘

任务列表侧边栏（默认 280px，可拖拽调节）：
┌────────────────────────────┐
│ 🔍 搜索任务...        [⚙] │  ← 搜索 + 更多筛选按钮
├────────────────────────────┤
│ [全部] [今天] [本周]        │  ← 主筛选 chips
├────────────────────────────┤
│ ▼ 排序方式                   │  ← 更多筛选展开时（内嵌在面板内）
│   📅 按截止日期       ✓    │
│   ⚡ 按紧急度             │
│   🔤 按标题               │
│ ▼ 象限                       │
│   [全部][Q1][Q2][Q3][Q4]   │
│ ▼ 标签                       │
│   [工作][学习][生活] ...    │
│ ▼ 截止日期                   │
│   [已过期][本月]            │
│   清除所有筛选                │
├────────────────────────────┤
│ 🔴 需要关注 (3)             │  ← 时间分组 header（可折叠）
│   ● ○ 任务A    明天        │  ← ● 象限色点 | ○ 完成勾选
│   ● ○ 任务B    7/5 已过期  │
│ 🟡 即将到来 (5)             │
│   ● ○ 任务C    周三        │
│ 🔵 计划中 (12)              │
│   ● ○ 任务D    下月        │
│ ✅ 已完成 (8)         [▶]   │
└────────────────────────────┘
```

**尺寸体系**：Header 56px | 象限分割线 1px --c-gray-200 | 卡片最大宽度 220px | 列表侧边栏 280px（可拖拽调节）

### 四象限画布 — 网格参考点

四象限画布上叠加一层 **dot grid**（SVG pattern）作为坐标系视觉锚点：

- **次级点**：每 10px 一个，半径 0.9px，颜色 `--c-gray-400`，透明度 0.18
- **主要点**：每 20px 一个，半径 1.4px，颜色 `--c-gray-500`，透明度 0.22
- 深色模式：使用 `rgba(255,255,255,0.15)` / `rgba(255,255,255,0.22)`
- `pointer-events: none` + `z-index: 0`，不干扰卡片交互
- 作用：让 9×9 坐标系统直观可见；空画布时不会觉得空洞；拖拽卡片时能看到落点参考

### 任务列表 — 筛选与排序

TaskList 顶部搜索栏右侧只有 **一个 ⚙ 按钮**，点击展开**直接内嵌在面板里**的筛选面板（灰底），自上而下分五组：

1. **排序方式** — 三选一单选（按截止日期 / 按紧急度 / 按标题），含图标 + 文案 + ✓ 选中标记
2. **象限** — 全部 / Q1~Q4 mini chips
3. **标签** — 所有标签 mini chips（按 tag.color 高亮）
4. **截止日期** — 已过期 / 本月 toggle chips
5. **清除所有筛选** — 仅当任一筛选激活时显示

按钮激活指示：筛选/排序非默认时高亮（蓝色背景），右上角小圆点提示。

### 任务列表 — 排序规则

| 排序方式 | 文案 | 图标 | 排序规则 |
|---------|------|------|---------|
| 默认 | 按截止日期 | 📅 | 截止日期升序（无日期排最后），同日期按 urgencyLevel 降序 |
| 紧急度 | 按紧急度 | ⚡ | urgencyLevel 降序 → importanceLevel 降序 |
| 标题 | 按标题 | 🔤 | 中文 localeCompare，A-Z 字母序 |

### 任务列表 — 时间分组

任务按 `getDueStatus()` 结果分组：

| 分组 | 图标 | 包含 | 颜色 |
|------|------|------|------|
| 需要关注 | 🔴 | 已过期 + 今天到期 | 红色 `--c-danger` |
| 即将到来 | 🟡 | 本周内（不含今天）| 橙色 `--c-warning` |
| 计划中 | 🔵 | 本月 / 以后 / 无截止日期 | 蓝色 |
| 已完成 | ✅ | 已完成任务（折叠）| 灰色 |

每个任务条目左侧加 **象限色点**（6px 圆点）替代原来的象限分组 header。

---

## 色彩系统

### 象限配色（浅色/深色）

| 象限 | 语义 | 浅色背景 | 深色背景 |
|------|------|---------|---------|
| Q1 | 重要+紧急 | `#F2A7B3` | `#5C2B35` |
| Q2 | 重要+不紧急 | `#B5D9C4` | `#2B4A35` |
| Q3 | 不重要+紧急 | `#C5D5E8` | `#2B3A5C` |
| Q4 | 不重要+不紧急 | `#FBE4A0` | `#5C4A1E` |

### 品牌主色

`--c-brand-50`: #EEF2FF | `--c-brand-500`: #2E5BFF | `--c-brand-600`: #1E40D0

### 灰阶 8 档

`--c-gray-50`~`--c-gray-900`：#FAFAFA~#18181B（浅）/ #18181B~#FAFAFA（深）

### 语义色

`--c-success`: #059669 | `--c-warning`: #D97706 | `--c-danger`: #DC2626

### 截止日期状态

已过期：左边框3px --c-danger | 今日到期：右上角标签 --c-warning | 本周到期：右上角标签 #FBBF24

### 标签 chip 颜色（iOS 系统色板 + 自定义）

标签 chip 默认使用 iOS 系统色，用户可在新建/编辑时从调色板自选。

**预置 8 色**（与 SF Symbols tint 一致）：

| 色板 | 色值 | 适用场景 |
|------|------|----------|
| systemBlue | #007AFF | 工作、默认 |
| systemGreen | #34C759 | 学习、健康 |
| systemIndigo | #5856D6 | 思考、规划 |
| systemOrange | #FF9500 | 提醒、待办 |
| systemYellow | #FFCC00 | 灵感、想法 |
| systemTeal | #5AC8FA | 生活、个人 |
| systemPink | #FF2D55 | 紧急、关注 |
| systemPurple | #AF52DE | 创意、项目 |

**默认值**：`#A1A1AA`（--c-gray-400），新建标签的 fallback 仍为灰，保持克制。

**用户自选**：标签编辑弹窗提供完整调色板（含 8 个预置 + 自由取色器），自选色存入 `Tag.color` 字段。

---

## 任务卡片

### 卡片结构

```
┌──────────────────────────┐
│ [标签chip]                │
│ [可选🔖] 任务标题（单行截断）│
│ ☑️ 3/5          📅 6月30日│
└──────────────────────────┘
```

### 尺寸与状态

宽度最大260px | 内边距12px | 圆角14px | 间距8px

| 状态 | 样式 |
|------|------|
| 默认 | 白色背景，border 1px --c-gray-200 |
| hover | 阴影 --sh-pop，cursor: grab |
| 拖拽中 | 阴影 --sh-modal，opacity 0.9 |
| 选中 | 边框2px --c-brand-500 |
| 已完成 | 删除线，颜色--c-gray-400，opacity 0.7 |

### 交互

单击/双击：打开编辑弹窗 | hover：显示✓和× | 拖拽：实时移动 | 长按（触屏）：拖拽模式

---

## 任务编辑弹窗

最大宽度520px | 圆角20px | 阴影--sh-modal | 动画 fadeIn 200ms + scale(0.95→1)

包含：标题输入 | 象限选择器（2×2网格）| 日期选择 | 重复规则 | 标签选择 | 检查项列表 | Markdown备注

---

## Header 顶栏

高度56px固定定位 | Logo左侧120px | 搜索居中（/键触发）| 右侧通知+头像

通知：有未读显示红点 | 用户菜单：个人中心/设置/主题切换/登出

---

## 主题切换

跟随系统（prefers-color-scheme）| 手动Segmente控制（浅色/深色/跟随系统）| localStorage['sishi-theme']

---

## 玻璃效果（Light Glass · iOS 标准）

玻璃效果仅用于**浮层元素**，不应用于内容层（象限色块、任务卡片）。渐变仍禁用，玻璃单独存在以保持克制。

### 应用范围

| 元素 | 玻璃参数 | 备注 |
|------|----------|------|
| Header 顶栏 | `backdrop-filter: blur(20px) saturate(180%)` + 半透明白/黑底 | iOS 标准 translucent nav bar，滚动时背景象限色若隐若现 |
| Modal 背景蒙层 | `backdrop-filter: blur(8px)` + 30% 黑色叠加 | Modal 出现时整个画布轻度模糊 |
| 侧边栏抽屉 | 抽屉外区域 `blur(12px)` | Control Center 风 |
| Toast / 通知浮层 | `blur(16px) saturate(160%)` + 半透明白 | 短暂出现的浮层 |

### 不加玻璃的元素

- 四象限背景色块 — 语义识别层，必须保持实色
- 任务卡片 — 必须 100% 不透明以保证内容可读
- FAB 按钮 — 保持实色圆形，避免在象限色上"飘"得过分
- 二级页面背景 — 同象限实色

### 浅色 / 深色模式

浅色模式：玻璃底色 `rgba(255,255,255,0.72)`
深色模式：玻璃底色 `rgba(24,24,27,0.72)`

### 浏览器兼容

`backdrop-filter` 不支持时（如 Firefox 默认未开启），降级为 `background-color: rgba(255,255,255,0.95)`（浅色）或 `rgba(24,24,27,0.95)`（深色）的实色方案，保留层级关系但不模糊。

---

## 字体/间距/圆角/阴影

| 类型 | 规范 |
|------|------|
| 字号 | display 26px / title 18px / body 15px / caption 13px |
| 标题字间距 | letter-spacing: -0.02em |
| 字体栈 | -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif |
| 间距 | s-1:4px / s-2:8px / s-3:12px / s-4:16px / s-5:20px / s-6:24px |
| 圆角 | chip:6px / input:10px / button:10px / card:14px / modal:20px |
| 阴影 | pop: 0 1px 3px rgba(0,0,0,0.08) / modal: 0 4px 16px rgba(0,0,0,0.12) |

---

## 动效规范

双曲线分工：`--ease-standard` 覆盖绝大多数交互；`--ease-spring` 仅用于 4 个关键节点以提供 iOS 原生"手感"。

### ease-standard（默认）

`--ease-standard: cubic-bezier(0.4, 0, 0.2, 1)`，时长≤300ms。

适用范围：hover 阴影、侧边栏 slide、输入框 focus 边框、主题切换、同步指示器旋转、状态切换等所有普通交互。

### ease-spring（关键节点）

`--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)`，带轻微 overshoot。

仅用于 4 个节点，克制使用以避免界面过度"弹"：

| 节点 | 动画 | 时长 |
|------|------|------|
| 任务编辑 Modal 出现 | scale(0.95 → 1) + fadeIn | 280ms |
| 任务勾选完成 | ✓ 勾选 + 卡片淡出 | 300ms |
| 拖拽释放归位 | scale + position 弹回原位 | 250ms |
| 任务删除 | scale(1 → 0.6) + fadeOut（向上微 overshoot）| 260ms |

### 无障碍

尊重 `prefers-reduced-motion`：用户开启时所有动画时长置0，spring 退化为 ease-standard 的瞬时版本。

---

## 键盘快捷键

按 `?` 弹出快捷键速查面板（KeyboardHelp.vue）。所有快捷键在输入框（input/textarea/select/contenteditable）中不会触发，避免干扰文字输入。

### 完整列表

| 按键 | 作用 |
|------|------|
| `?` | 打开 / 关闭快捷键速查面板 |
| `/` | 聚焦到顶部搜索框 |
| `N` | 新建任务（默认在中心 Q2 位置） |
| `Ctrl+N` | 新建任务（同 N） |
| `D` | 切换视图密度（紧凑 → 标准 → 详细） |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Shift+Z` | 重做 |
| `Esc` | 关闭弹窗 / 取消多选 / 关闭速查面板 |

### 速查面板（KeyboardHelp.vue）

- **触发**：全局 `?` 键 或 Header 工具栏键盘图标按钮
- **样式**：居中弹层 540px，scrim 25% 黑色 + blur(6px)
- **内容**：分「全局」「弹窗」两组，每行 `<kbd>` 键位 + 中文说明
- **`<kbd>` 样式**：min-width 24px、height 24px、底部加粗 2px border 模拟物理按键
- **过渡**：scrim fade 200ms + 面板 scale(0.92→1) spring 250ms
- **关闭**：× 按钮 / 「知道了」按钮 / 点击 scrim / Esc 键

---

## 视图密度

| 密度 | 卡片高度 | 显示内容 |
|------|---------|---------|
| 紧凑 | 44px | 仅标题+完成状态 |
| 标准 | 68px | 标题+标签+日期 |
| 详细 | 90px | 标题+标签+日期+备注摘要 |

---

## 组件清单

QuadrantCanvas.vue（四象限容器，含 dot grid 网格点阵）| TaskList.vue（侧边栏任务列表，含搜索/筛选/排序/时间分组）| TaskCard.vue | TaskModal.vue | AppHeader.vue（顶栏，含键盘帮助按钮）| NotificationBell.vue（通知下拉）| KeyboardHelp.vue（快捷键速查面板）| StatsPanel.vue（右侧统计）| TagChip.vue | AppButton.vue | AppModal.vue | ConfettiCanvas.vue（完成动画）| CaptchaInput.vue | SyncStatusBadge.vue | ConflictDialog.vue

---

## 状态管理

**Pinia**: auth.ts（用户信息）| task.ts（任务列表/筛选/密度）| ui.ts（主题/侧边栏/弹窗）

**Dexie 7个store**: tasks / tags / taskTags / checklistItems / pendingOps / syncMeta / authSession

---

## 响应式

>1024px完整四象限+侧边栏 | 768-1024px象限保持+侧边栏折叠图标 | <768px象限缩放+底部抽屉

---

## 加载与空状态

骨架屏：象限区域脉冲动画占位矩形 | 空状态：文字"还没有任务，按N新建第一个任务"，--c-gray-400居中显示

同步状态指示器：✓已同步（绿）| ↻同步中（旋转）| ⊘离线（灰）| ⚠️冲突（橙）

---

## CSS 变量完整列表

```css
:root {
  /* 灰阶 */
  --c-gray-50: #FAFAFA; --c-gray-100: #F4F4F5; --c-gray-200: #E4E4E7;
  --c-gray-300: #D4D4D8; --c-gray-400: #A1A1AA; --c-gray-500: #71717A;
  --c-gray-600: #52525B; --c-gray-700: #3F3F46; --c-gray-800: #27272A;
  --c-gray-900: #18181B;
  /* 品牌色 */
  --c-brand-50: #EEF2FF; --c-brand-500: #2E5BFF; --c-brand-600: #1E40D0;
  /* 语义色 */
  --c-success: #059669; --c-warning: #D97706; --c-danger: #DC2626;
  /* 象限色（浅色）*/
  --q1-bg: #F2A7B3; --q2-bg: #B5D9C4; --q3-bg: #C5D5E8; --q4-bg: #FBE4A0;
  /* 象限色（深色）*/
  --q1-bg-dark: #5C2B35; --q2-bg-dark: #2B4A35;
  --q3-bg-dark: #2B3A5C; --q4-bg-dark: #5C4A1E;
  /* 字号/间距/圆角/阴影/动效/布局 */
  --t-display-size: 26px; --t-title-size: 18px; --t-body-size: 15px; --t-caption-size: 13px;
  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 20px; --s-6: 24px;
  --r-chip: 6px; --r-input: 10px; --r-button: 10px; --r-card: 14px; --r-modal: 20px;
  --sh-pop: 0 1px 3px rgba(0,0,0,0.08); --sh-modal: 0 4px 16px rgba(0,0,0,0.12);
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --glass-header: blur(20px) saturate(180%);
  --glass-modal-scrim: blur(8px);
  --glass-sidebar: blur(12px);
  --glass-toast: blur(16px) saturate(160%);
  --glass-bg-light: rgba(255, 255, 255, 0.72);
  --glass-bg-dark: rgba(24, 24, 27, 0.72);
  /* iOS 系统色板（标签 chip 预置色）*/
  --ios-blue: #007AFF; --ios-green: #34C759; --ios-indigo: #5856D6;
  --ios-orange: #FF9500; --ios-yellow: #FFCC00; --ios-teal: #5AC8FA;
  --ios-pink: #FF2D55; --ios-purple: #AF52DE;
  --header-height: 56px; --sidebar-width: 320px; --task-card-max-width: 260px;
}
```
