# EmbeddedGUI Designer UI Minimal Redesign Plan

## 1. 文档目的

这份文档描述本轮极简化改版的最终落地状态，而不是概念方案。
目标很明确：

1. 回到 IDE / Studio 风格的工作界面。
2. 让页面树、画布、属性编辑重新成为主角。
3. 删除长期占空间但不承担主任务的信息层。
4. 保持可访问性和状态可读性，但不再把这些信息做成显眼的可视结构。

当前实现已经完成本轮计划中的核心结构收缩。

## 2. 设计原则

### 2.1 结构优先

- 优先减少层级，不再继续通过新增卡片、说明区、统计块来“优化”界面。
- 同一类状态信息只能有一个主要归属位置，避免多面板重复表达。

### 2.2 文本优先

- 有文字就不加图标。
- 导航、模式切换、资源管理、页签切换默认使用纯文本入口。
- 图标只保留在少数必要的状态或运行控制场景。

### 2.3 面板优先级清晰

- 左侧负责结构与入口。
- 中间负责编辑与预览。
- 右侧负责属性。
- 底部负责诊断、历史、调试等辅助信息。

### 2.4 兼容但不回退

- 为了保持现有自动化校验和可访问性元数据稳定，代码中保留了部分隐藏的 metadata 代理对象。
- 这些对象不是新的可见 UI，不会重新把界面拖回原来的复杂状态。

## 3. 已实施的结构调整

### 3.1 Workspace Shell

- `main_window.py`
  - 顶部只保留一条命令条。
  - 删除可见的 command header、workspace context card、toolbar indicator strip。
  - `Save / Undo / Redo / Copy / Paste / Build / Stop` 等文字命令统一采用纯文字，不再附带图标。
  - `Release Build / Release History / Show Grid / Grid Size` 等带明确文字标签的菜单入口也统一去图标化，保持命令面与菜单面的规则一致。
  - workspace context、health、runtime 仍保留隐藏的 metadata 代理，用于状态同步和测试稳定性。
  - 底部状态栏继续承担当前页、选择状态、警告数量和下一步提示。

### 3.2 Center Area

- `editor_tabs.py`
  - 删除可见 header、mode chip、summary block。
  - Design / Split / Code 只保留一处简洁切换入口。
  - 保留隐藏的 header metadata 代理，避免破坏辅助信息和回归验证。

- `preview_panel.py`
  - 删除可见 preview header。
  - 预览状态、指针状态、缩放信息统一收敛到下方状态行。
  - 保留隐藏的 preview header / metrics metadata 代理。

### 3.3 Left Panel

- `project_workspace.py`
  - header 收敛为标题 + 视图切换按钮 + Settings 入口。
  - 去掉可见的 eyebrow、summary block、metrics strip、view chip。
  - 缩略图视图保留，但降级为次级入口。
  - 页面缩略图区已缩小卡片尺寸与外层圆角，提升同屏页数。
  - 相关 summary / chip 仅以隐藏 metadata 方式保留。

- `project_dock.py`
  - compact 模式下进一步隐藏低频设置区，减少左侧纵向占用。

### 3.4 Right Inspector

- `property_panel.py`
  - 去掉可见 overview 卡片。
  - 去掉可见单选 / 多选 header card。
  - 去掉可见 metric grid、状态 chip 行。
  - 保留顶部简短上下文标题与搜索入口。
  - 搜索引导优先收敛到输入框 placeholder，不再额外占用一整行解释文案。
  - 属性编辑区域直接进入 Layout / Basic / Appearance / Data / Callbacks / Designer 分组。
  - 仅在确实存在锁定、隐藏、布局托管等情况时，显示简短的交互提示。
  - 原有 header / size chip 等对象只作为隐藏兼容层存在。

### 3.5 Resource Panel

- `resource_panel.py`
  - 删除可见顶部 header 与 metrics 区。
  - 首屏改为 list-first：上方资源列表，下方详情区。
  - 详情区改为 `Preview / Usage` 切换，不再并排长期占用空间。
  - 可见 usage 摘要收紧为更短的统计句式，详细描述交给 tooltip / accessibility metadata。
  - 多余的标题、提示、说明文字不再作为可见结构存在。
  - 原 header / metric / hint 仅保留隐藏 metadata 版本。

## 4. 视觉与交互约束

### 4.1 Typography

- 主工作区只保留三类主要文字层级：
  - 标题：13 到 14，semibold
  - 正文：13，regular
  - 辅助信息：12，regular
- eyebrow、营销式副标题、说明段不再作为默认结构层。

### 4.2 Radius

- 主要工作壳层和面板外框使用小圆角或更接近直角的处理。
- 按钮、输入框保留轻量圆角，避免完全生硬。
- 不再使用大圆角卡片去制造层级感。
- 主命令条、左侧导航、模式切换、资源页签等高频工作区控件已进一步收紧为矩形化边角；页面缩略图仅保留较小外层圆角。

### 4.3 Surface

- 允许单层背景 + 单层边框。
- 不再允许 card 套 card。
- 状态摘要不再以 context card / metric card / summary card 的方式长期占位。

### 4.4 Icons

- 文本按钮默认无图标。
- 导航、页签、模式切换采用纯文字。
- 只在错误、警告、消息框等缺少明确文字承载或需要系统语义提示的场景保留必要图标。
- 主题切换和密度切换不再依赖“重新清空图标”的兜底逻辑，文本优先入口在初始化和刷新后都应天然保持无图标。

## 5. 当前实现中的兼容层说明

以下对象仍然存在，但默认不作为可见结构：

- `main_window` 中的 command header、context card、health/runtime chip
- `editor_tabs` 中的 header / summary / mode chip
- `preview_panel` 中的 header / metrics chip
- `project_workspace` 中的 summary / meta / view chip / metrics strip
- `property_panel` 中的 selection header / size chip
- `resource_panel` 中的 header / metrics / preview hint / usage hint

保留这些对象的原因只有两个：

1. 保持辅助信息、tooltip、accessible name 的连续性。
2. 控制重构范围，避免为结构收缩引入新的行为回归。

这类对象后续可以继续清理，但前提是先把对应的元数据责任迁移完毕，而不是直接删除。

## 6. 验收标准

本轮改版以以下结果为准：

1. 顶部不再出现二层 header、context card、runtime indicator strip。
2. 中间编辑区和预览区不再有独立的大标题头部。
3. 属性面板首屏优先给真实字段，而不是概览卡片和状态块。
4. 资源面板首屏优先给资源列表，而不是统计说明。
5. 页面主要导航、模式切换、资源操作可以在纯文本条件下完成。
6. 状态信息仍可读，但主要集中在底部状态栏、底部工具区和 tooltip / accessibility metadata 中。

## 7. 验证结果

已通过与本轮改版直接相关的 UI 测试：

- `ui_designer/tests/ui/test_editor_tabs.py`
- `ui_designer/tests/ui/test_preview_workspace.py`
- `ui_designer/tests/ui/test_project_workspace.py`
- `ui_designer/tests/ui/test_property_panel_file_flow.py`
- `ui_designer/tests/ui/test_resource_panel_file_flow.py`
- `ui_designer/tests/ui/test_main_window_runtime_indicator_visibility.py`
- `ui_designer/tests/ui/test_theme.py`

另外补跑了主窗口中与本轮改动直接相关的 workspace / toolbar / command surface / chip 元数据测试，并覆盖了 theme / density 切换后的无图标约束，结果通过。

## 8. 后续建议

如果继续推进下一轮极简化，建议按这个顺序做：

1. 把隐藏 metadata 代理进一步抽成统一辅助层，减少各面板重复代码。
2. 继续收紧主工作区壳层的圆角和边框密度。
3. 对结构树、组件浏览器、底部工具区做同级别的结构瘦身，而不是再加新的状态块。
4. 在不破坏可访问性的前提下，逐步移除旧结构遗留对象。
