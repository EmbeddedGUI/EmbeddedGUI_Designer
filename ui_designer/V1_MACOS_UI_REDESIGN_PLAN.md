# UI Designer macOS 风格改造 — AI 可执行实施文档

## 0. 文档用途

本文件聚焦“macOS 风格 UI 重构”，用于后续 AI/开发者持续推进视觉与信息架构改造，不丢上下文。

- 范围：仅 UI/视觉/信息架构（不涉及核心渲染与业务逻辑）
- 目标：解决“界面丑、信息杂乱、视觉层级弱”
- 原则：先结构、后视觉、再细节；可灰度、可回滚

---

## 1. 设计目标（macOS 风格核心）

1. **层级清晰**：强区块划分 + 视觉节奏统一
2. **更少边框**：用背景层级替代硬边框
3. **一致圆角**：卡片/控件统一圆角（推荐 8~10）
4. **低饱和配色**：主色只用于关键动作与选中态
5. **系统感控件**：分段控件、图标工具栏、侧栏列表
6. **适度阴影/毛玻璃**：轻量使用，避免过度装饰

---

## 2. 范围与不做事项

### 2.1 做

- 主界面三栏视觉重排（左侧导航/控件库、中间画布、右侧属性）
- 统一基础控件外观（按钮/输入框/列表/Tab/分组容器）
- 统一间距、字号、颜色、圆角、阴影体系
- 顶部工具栏重构为 macOS 风格图标按钮栏
- 右侧 Inspector 分组/折叠统一样式

### 2.2 不做

- 不改变功能逻辑
- 不大规模改动渲染引擎
- 不重写控件库数据结构

---

## 3. 设计 Token（建议值，落地后可微调）

### 3.1 间距

- `SPACE_4 = 4`
- `SPACE_8 = 8`
- `SPACE_12 = 12`
- `SPACE_16 = 16`
- `SPACE_20 = 20`

### 3.2 圆角

- `RADIUS_S = 6`
- `RADIUS_M = 8`
- `RADIUS_L = 10`

### 3.3 字体

- 主要字体：`system-ui` / `SF Pro` 风格（Qt 对应系统字体）
- 标题：14~15
- 正文：12~13
- 辅助：11

### 3.4 颜色

- `BG_BASE = #F5F5F7`
- `BG_PANEL = #FFFFFF`
- `BG_SUBTLE = #F0F1F3`
- `TEXT_PRIMARY = #1C1C1E`
- `TEXT_SECONDARY = #6E6E73`
- `BORDER_SUBTLE = #E5E5EA`
- `ACCENT = #0A84FF`（macOS 蓝）

### 3.5 阴影

- 轻阴影：`0 1px 2px rgba(0,0,0,0.08)`
- 面板分层：`0 4px 10px rgba(0,0,0,0.10)`

---

## 4. 执行顺序（结构优先）

1. **三栏骨架**：统一分栏、分隔、背景
2. **控件统一**：按钮/输入框/列表/Tab/分组容器
3. **Inspector 面板**：分组折叠/字段布局/标签样式
4. **工具栏**：图标按钮、分组间距、hover/active
5. **细节**：滚动条、hover、空状态、分割线

---

## 5. 可执行任务清单（AI 执行格式）

> 状态枚举：`todo | doing | blocked | done`

### 5.1 Sprint M1（结构与壳层）

```yaml
- id: UI-M1-001
  title: 盘点现有 UI 样式入口与主题文件
  status: todo
  deps: []
  output:
    - theme.py / stylesheets 入口清单
    - main_window 中可改 UI 容器
  acceptance:
    - 可明确哪些组件由统一主题控制

- id: UI-M1-002
  title: 统一主界面背景与三栏容器背景
  status: todo
  deps: [UI-M1-001]
  output:
    - 主背景/面板背景 token 接入
  acceptance:
    - 主界面视觉层级清晰可见
```

### 5.2 Sprint M2（控件统一）

```yaml
- id: UI-M2-001
  title: 统一按钮风格（primary/secondary/ghost）
  status: todo
  deps: [UI-M1-002]
  output:
    - theme 中按钮样式基类
  acceptance:
    - 常用按钮视觉统一

- id: UI-M2-002
  title: 统一输入框/下拉框/搜索框样式
  status: todo
  deps: [UI-M1-002]
  output:
    - 输入控件样式 token 接入
  acceptance:
    - 输入控件风格一致、占位文字柔和

- id: UI-M2-003
  title: 统一列表/树控件样式
  status: todo
  deps: [UI-M1-002]
  output:
    - tree/list 行高、hover、选中态统一
  acceptance:
    - 列表结构更清晰，选中态与 hover 明确
```

### 5.3 Sprint M3（Inspector 与工具栏）

```yaml
- id: UI-M3-001
  title: Inspector 分组容器视觉重构
  status: todo
  deps: [UI-M2-001, UI-M2-002]
  output:
    - collapsible_group 样式升级
  acceptance:
    - 分组层级明确，折叠视觉友好

- id: UI-M3-002
  title: 顶部工具栏 macOS 风格改造
  status: todo
  deps: [UI-M2-001]
  output:
    - 图标按钮/分隔/hover 统一
  acceptance:
    - 工具栏视觉更轻量且操作清晰
```

### 5.4 Sprint M4（细节与一致性）

```yaml
- id: UI-M4-001
  title: 统一滚动条与边界分隔线样式
  status: todo
  deps: [UI-M2-003]
  output:
    - scrollbars / separators token 接入
  acceptance:
    - 滚动体验一致、边界层次干净

- id: UI-M4-002
  title: 空状态与轻提示样式统一
  status: todo
  deps: [UI-M3-001]
  output:
    - 空状态/提示文本样式 token 接入
  acceptance:
    - 界面更干净、易扫读
```

---

## 6. AI 执行 SOP

```text
请按 V1_MACOS_UI_REDESIGN_PLAN.md 执行：
1) 从任务清单里挑选所有 deps 满足且 status=todo 的任务。
2) 一次最多完成 1~2 个任务，完成后更新状态。
3) 优先修改 theme.py 与集中式样式入口，减少散落式改动。
4) 每次改动后进行最小 UI 验证（启动应用查看关键面板）。
5) 输出：改动文件列表、完成任务ID、未解决风险、下一个建议任务ID。
```

---

## 7. 执行状态跟踪区（持续更新）

```yaml
last_update: 2026-03-30
current_sprint: M1
completed: []
in_progress: []
blocked: []
next_recommended:
  - UI-M1-001
notes: []
```
