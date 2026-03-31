# UI Designer macOS 风格改造计划（AI 连续跟进版）

## 0. 文档目标

这是一份给后续 AI/开发者持续执行的任务文档，目标是：

1. 解决 `ui_designer` 当前“功能多但界面乱、观感粗糙”的问题。
2. 将 UI 统一为 macOS 风格（克制、清晰、层级明确）。
3. 保证可分阶段落地、可回滚、可追踪。

---

## 1. 本次改造范围（V1）

### 1.1 必做

- 主工作区视觉统一：`左侧导航 / 中央画布 / 右侧属性`
- 顶部工具栏 macOS 化（分组、弱化边框、统一按钮）
- 右侧 Inspector 分组视觉统一（折叠组、字段间距、标题层级）
- 全局 Design Tokens：颜色、间距、圆角、阴影、字体、控件高度
- 深浅色主题一致性（浅色优先，深色不崩）

### 1.2 暂不做

- 全局动效系统重写
- 全量图标库替换
- 跨平台原生控件风格完全一致化（先保证主路径体验）

---

## 2. 设计原则（macOS 风）

1. **层级靠留白，不靠重边框**
2. **色彩低饱和，强调色只用于关键操作**
3. **圆角统一（建议 8）**
4. **控件高度统一（建议 28/32）**
5. **弱分割线 + 面板背景层级区分**
6. **信息密度可控：高频信息前置，低频折叠**

---

## 3. 设计 Token 草案（先定协议）

```yaml
radius:
  sm: 6
  md: 8
  lg: 10

spacing:
  xs: 4
  sm: 8
  md: 12
  lg: 16
  xl: 20

font:
  size_caption: 11
  size_body: 12
  size_title: 13
  weight_regular: 400
  weight_medium: 500

control_height:
  sm: 24
  md: 28
  lg: 32

color_light:
  bg_app: "#F5F5F7"
  bg_panel: "#FFFFFF"
  bg_subtle: "#F2F3F5"
  border_subtle: "#E5E7EB"
  text_primary: "#1F2937"
  text_secondary: "#6B7280"
  accent: "#007AFF"

shadow:
  panel: "0 1px 2px rgba(0,0,0,0.06)"
```

> 备注：实际值以当前 `ui_designer/ui/theme.py` 的现有结构兼容为优先。

---

## 4. 执行任务清单（AI 可直接执行）

状态：`todo | doing | blocked | done`

### Sprint A（结构统一，1~2 天）

```yaml
- id: MAC-A-001
  title: 盘点现有主界面样式入口（main_window/theme）
  status: todo
  deps: []
  output:
    - 可修改点清单（类名/方法名/作用域）
  acceptance:
    - 明确哪些样式在 theme.py，哪些散落在 main_window/panels

- id: MAC-A-002
  title: 统一三栏容器间距与背景层级
  status: todo
  deps: [MAC-A-001]
  output:
    - 三栏间距、面板背景、分割线统一
  acceptance:
    - 三栏视觉层级清晰，无“拼贴感”

- id: MAC-A-003
  title: 顶部工具栏分组化（主操作/次操作）
  status: todo
  deps: [MAC-A-001]
  output:
    - 工具栏按钮样式统一、间距统一
  acceptance:
    - 高低频动作视觉权重正确
```

### Sprint B（控件系统统一，2~3 天）

```yaml
- id: MAC-B-001
  title: 在 theme 中补齐 token（圆角/间距/字体/颜色）
  status: todo
  deps: [MAC-A-001]
  output:
    - 可复用 token 常量
  acceptance:
    - 关键控件不再写死像素值和颜色

- id: MAC-B-002
  title: 统一按钮/输入框/下拉框/Tab 的高度与状态
  status: todo
  deps: [MAC-B-001]
  output:
    - hover/pressed/disabled/selected 状态规则
  acceptance:
    - 常用控件状态一致，点击反馈自然

- id: MAC-B-003
  title: Inspector 分组头与字段布局统一
  status: todo
  deps: [MAC-B-001]
  output:
    - 分组标题、字段标签、编辑控件对齐规则
  acceptance:
    - Inspector 可读性明显提升，定位更快
```

### Sprint C（细节与体验，1~2 天）

```yaml
- id: MAC-C-001
  title: 列表项与树节点 macOS 风选中态优化
  status: todo
  deps: [MAC-B-002]
  output:
    - 选中/悬停态统一
  acceptance:
    - 左侧库、结构树、右侧列表视觉规则一致

- id: MAC-C-002
  title: 空状态与提示文案统一（无内容时）
  status: todo
  deps: [MAC-B-003]
  output:
    - 空状态占位样式
  acceptance:
    - 空页面不再“空白突兀”

- id: MAC-C-003
  title: 深色主题回归检查与修复
  status: todo
  deps: [MAC-B-001, MAC-B-002, MAC-B-003]
  output:
    - 深色模式关键页面可用
  acceptance:
    - 文字对比度合格、选中态可辨识
```

---

## 5. 文件改动建议（优先级）

1. `ui_designer/ui/theme.py`（最高优先，先做 token）
2. `ui_designer/ui/main_window.py`（三栏与工具栏）
3. `ui_designer/ui/panels/inspector_panel.py`（若该文件存在则优先）
4. 其他 UI 子面板文件（按实际结构补充）

---

## 6. AI 连续执行 SOP（每次照做）

每次让 AI 跟进可直接粘贴：

```text
请按 MACOS_UI_REDESIGN_AI_EXECUTION_PLAN.md 执行：
1) 选择 deps 已满足且 status=todo 的 1~2 个任务。
2) 只做最小必要改动，优先复用 theme token。
3) 完成后更新任务状态（todo -> doing -> done）。
4) 输出：改动文件、完成任务ID、截图/验证结果、下一个任务ID。
5) 若发现结构性阻塞，标记 blocked 并写明解除条件。
```

---

## 7. 验收标准（DoD）

- 主路径界面（打开项目 -> 拖拽控件 -> 编辑属性）视觉一致
- 主要控件状态统一（hover/active/disabled/selected）
- Inspector 信息层级清晰（标题/标签/输入区域）
- 深浅主题均可用，无明显对比度问题
- 文档任务状态已更新，可继续接力

---

## 8. 风险与回滚

- 风险：样式改造影响现有交互
  - 应对：只改样式层，不改业务信号链路
- 风险：深色模式出现不可读
  - 应对：浅色先达标，深色逐组回归
- 风险：局部硬编码样式覆盖 token
  - 应对：逐步收敛到 `theme.py`，先高频页面

回滚策略：按任务粒度提交，出现问题可按文件或任务回退。

---

## 9. 执行跟踪区（每次更新）

```yaml
last_update: 2026-03-30
phase: Sprint A
completed: []
in_progress: []
blocked: []
next_recommended:
  - MAC-A-001
notes:
  - 本文档为 macOS 风格专项执行计划。
  - 当前代码存在 theme/main_window/config 多文件并行改动，建议先统一 token 再分模块推进。
```
