# EmbeddedGUI Designer — 界面整理与 macOS 风格视觉优化计划（合并版）

> **文档定位**：合并 `UI_VISUAL_AND_LAYOUT_REFINEMENT_PLAN`（信息架构 + 代码事实）与 `MACOS_UI_REDESIGN_AI_EXECUTION_PLAN`（视觉语言 + 可执行任务 ID）。供后续人工或 AI **分阶段、可接力** 落地。  
> **代码事实基准**（2026-03）：主布局在 `ui/main_window.py`（`QSplitter` + 左侧 `QStackedWidget` + 右侧 `QTabWidget` + 底栏工具区）；主题在 `ui/theme.py`；属性与折叠区块在 `ui/property_panel.py`、`ui/widgets/collapsible_group.py`、`ui/inspector/`；左栏工程向 UI 在 `ui/project_workspace.py` 等。  
> **关联文档**：原 macOS 专项条目已吸收进本文；若需对照历史表述，仍可从版本库查看 `MACOS_UI_REDESIGN_AI_EXECUTION_PLAN.md`。

---

## 0. 文档目标

1. 解决「功能多但界面乱、观感粗糙」的问题。  
2. **视觉方向**：统一为 **macOS 风**（克制、清晰、层级明确）——以留白与弱边框体现层级，而非堆砌装饰。  
3. **结构方向**：控制信息密度（Tab 深度、顶栏条带、Status/Diagnostics 重复入口），保证 **可分阶段落地、可回滚、可追踪**。

---

## 1. 范围（V1）

### 1.1 必做

- 主工作区视觉统一：**左侧导航 / 中央画布 / 右侧属性**（及底栏工具区层级清晰）。  
- **顶部工具栏 macOS 化**：分组、弱化边框、统一按钮高度与权重（主操作 / 次操作）。  
- **右侧 Inspector** 分组与字段布局统一（折叠组、间距、标题层级）；与下方「信息架构」条目配合，收敛嵌套 Tab。  
- **全局 Design Tokens**：颜色、间距、圆角、阴影、字体、控件高度；`theme.py` 为单一事实源优先。  
- **深浅色主题一致性**（浅色优先达标，深色不崩）。

### 1.2 暂不做（本阶段刻意不做）

- 全局动效系统重写。  
- 全量图标库替换。  
- 跨平台原生控件与 macOS **像素级**一致（先保证主路径体验）。  
- 更换整套 GUI 框架或重写为大屏 Web UI。  
- 为「好看」删除功能或合并高频能力。  
- 无交互稿下 **一次性** 改完所有对话框（允许按高频对话框抽样推进）。

---

## 2. 现状结构速览

| 区域 | 主要实现 | 备注 |
|------|-----------|------|
| 顶栏命令区 | `_init_toolbar`、`PrimaryPushButton`、模式按钮、状态 chips | 与 `page_tab_bar` 分属不同条带，易产生「多条顶栏」 |
| 左栏 | `_workspace_nav_frame` + `_left_panel_stack` | `project` / `structure` / `widgets` / `assets` / `status` |
| 中央 | `TabBar`（页面）+ `EditorTabs`（设计/分栏/代码） | 预览与代码共用编辑区 |
| 右栏 | `_inspector_tabs`：Properties / Animations / `Page`(Fields+Timers 嵌套 Tab) | 易出现三层 Tab：inspector → page → fields/timers |
| 底栏 | `_bottom_tabs`：Diagnostics / History / Debug | 默认可折叠 |
| 全局主题 | `apply_theme` + `theme.py` QSS + Fluent `Theme` | 需收敛 token，减少硬编码与割裂 |

**文档漂移**：`main_window.py` 顶部注释仍写「All panels are QDockWidgets」——实际为中央 `QSplitter` 嵌套工作区；改版时建议同步修正注释。

---

## 3. 问题归纳（优先级）

### P0 — 样式正确性（基线）

- **`theme.py` QSS 与 f-string**：历史上曾出现 `QPushButton:hover` 规则截断导致 **Python 语法错误或样式失效**；改版前须确认 `_build_stylesheet` 内**所有 Qt 花括号在 f-string 中已正确转义**（`{{` / `}}`），并做全文件括号配对检查。若已修复，仍应在 Sprint 0 回归中验证 hover/选中。

### P1 — 信息架构

- **横向条带过多**：工具栏 + 页面 TabBar + 右/底 Tab，缺少清晰「主 / 次」分组。  
- **右侧 nested Tab**：Page 内 Fields | Timers 增加心智负担；目标：**同时可见的 Tab 层 ≤ 2**（见 §4）。  
- **Status / Diagnostics 重叠**：顶栏 chips、左栏 `status`、底栏 Diagnostics 语义重叠，需主导入口 + 跳转联动。  
- **命名混用**：代码 `widgets` 与文案「Components」等需统一。

### P2 — 视觉与组件

- **Fluent vs 原生 Qt**：对话框与部分框架边框/圆角不一致。  
- **面板 header 密度不均**：如 `project_workspace` 有完整 header，其他面板参差不齐。  
- **图标语义**：`iconography.make_icon` 键与用途（如 copy）可对齐梳理（低成本）。

### P3 — 体验增强（Backlog）

- **布局记忆**：持久化 splitter、底栏高度、inspector 当前 tab（`config` / `ui_prefs`）。  
- **专注模式**：小屏下一键收拢侧栏（可选）。

---

## 4. 设计原则（macOS 风 + 架构约束）

**视觉（macOS）**

1. **层级靠留白**，不靠重边框。  
2. **色彩低饱和**；强调色仅用于关键操作（如系统蓝 `#007AFF` 级，可与现有 accent 对齐 token）。  
3. **圆角统一**（建议以 **8** 为主台阶，与 token 中 `md` 一致）。  
4. **控件高度统一**（建议 **28 / 32** 为主，见 token）。  
5. **弱分割线 + 面板背景层级**（app / panel / subtle）。  
6. **信息密度可控**：高频前置，低频折叠。

**信息架构（与上表配合）**

7. **区域先于装饰**：先定间距阶梯与背景层级，再改颜色。  
8. **单一主焦点**：强调一条主操作带；chips 降为次要（更小、更淡或收入 overflow）。  
9. **Tab 深度 ≤ 2**：第三层改为折叠组、列表+堆叠或侧栏。  
10. **Token 驱动**：语义化键（如 `rail_bg`、`chip_bg`）集中在 `theme_tokens`，QSS 引用；少内联 `setStyleSheet`。  
11. **改动可测**：每阶段截图对比 + `main.py` smoke；可选 `pytest` + `ui_designer_preview_smoke.py`。

---

## 5. Design Token 草案（协议优先，落地对齐 `theme.py`）

实际值以 **`ui/theme.py` 现有结构兼容** 为第一约束；可将下列键逐步映射进 `theme_tokens` / QSS。

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

深色模式：在 `theme.py` 的 `dark` token 中保持 **对比度与选中态可辨识**，随 Sprint C 回归逐项收紧。

---

## 6. 执行任务清单（统一 ID：`UI-*` = 结构/IA，`MAC-*` = macOS 视觉 Sprint）

状态：`todo | doing | blocked | done`。deps 为空表示可并行（在资源允许下）。

### Sprint 0 — 基线与文档（0.5～1 天）

| id | title | deps | acceptance |
|----|--------|------|------------|
| UI-S0-001 | 校验 `theme.py` QSS/f-string 完整性；hover、列表选中、明暗主题 smoke | — | 无语法错误；主界面核心控件状态正常 |
| UI-S0-002 | 修正 `main_window.py` 模块 docstring（Splitter 工作区，非 Dock 主导） | — | 与真实布局一致 |
| UI-S0-003 | View/Window 菜单与左/右/底面板映射清点 | UI-S0-002 | 每块主要区域有可达菜单或明确备注 |

### Sprint A — 结构统一 + 工具栏（1～2 天）【对应原 MAC-A + 整理计划「阶段 B」局部】

```yaml
- id: MAC-A-001
  title: 盘点主界面样式入口（main_window / theme / 各 panel 内联样式）
  status: done
  deps: []
  output: 可修改点清单（文件 + objectName + 是否应收敛到 theme）
  acceptance: 明确 theme 与散落样式的边界

- id: MAC-A-002
  title: 统一三栏容器间距与背景层级（左壳 / 中壳 / 右 inspector 容器）
  status: done
  deps: [MAC-A-001]
  output: 间距、panel 底、分割线一致
  acceptance: 三栏层级清晰，无「拼贴感」

- id: MAC-A-003
  title: 顶部工具栏分组化（主操作 / 次操作 / 模式 / 状态 chips）
  status: done
  deps: [MAC-A-001]
  output: 视觉权重与间距统一
  acceptance: 高低频动作层级正确；与 page_tab_bar 的上下关系更清楚
```

**信息架构（与 A 并行或紧随）**

```yaml
- id: UI-B-001
  title: 右侧 Inspector 去掉 Page 下 Fields/Timers 嵌套 Tab（改折叠组或列表+堆叠）
  status: done
  deps: [MAC-A-001]
  acceptance: 用户可见 Tab 层 ≤ 2；行为与数据绑定不变

- id: UI-B-002
  title: Status / Diagnostics / chips 主导入口与跳转联动策略（文案+点击路径）
  status: done
  deps: [MAC-A-001]
  acceptance: 仅一处像「主控制台」，其余为「打开…」

- id: UI-B-003
  title: 命名统一（Components vs widgets 等）在菜单与可见文案层
  status: done
  deps: []
  acceptance: 用户可见字符串一致
```

### Sprint B — 控件系统 + Inspector 字段（2～3 天）【对应原 MAC-B + 整理计划「阶段 C」局部】

```yaml
- id: MAC-B-001
  title: 在 theme 中补齐 token（圆角/间距/字体/颜色/阴影）并驱动 QSS
  status: done
  deps: [MAC-A-001]
  acceptance: 关键控件不再大量写死像素与色值

- id: MAC-B-002
  title: 统一按钮/输入/下拉/Tab 高度与 hover/pressed/disabled/selected
  status: done
  deps: [MAC-B-001]
  acceptance: 主路径控件反馈一致

- id: MAC-B-003
  title: Inspector 分组头与字段布局统一（含 property_panel / collapsible_group / inspector groups）
  status: done
  deps: [MAC-B-001, UI-B-001]
  acceptance: 标题/标签/输入区对齐，可读性明显提升
```

**壳层样式（可紧随 MAC-B-001）**

- [x] `QTabWidget::tab`、`#workspace_nav_rail`、`#workspace_status_chip` 等与 token 对齐。  
- [x] 高频对话框抽样：`new_project_dialog.py`、`app_selector.py`（`release_dialogs` 无硬编码色，沿用全局 QSS）。

### Sprint C — 细节与主题回归（1～2 天）【对应原 MAC-C】

```yaml
- id: MAC-C-001
  title: 列表/树节点选中与悬停 macOS 化（左栏列表、结构树、右栏列表）
  status: done
  deps: [MAC-B-002]
  acceptance: 选中/悬停规则跨面板一致

- id: MAC-C-002
  title: 空状态与提示样式统一（无工程/无选中/无资源等）
  status: done
  deps: [MAC-B-003]
  acceptance: 空界面不「死白突兀」

- id: MAC-C-003
  title: 深色主题回归与对比度修复
  status: done
  deps: [MAC-B-001, MAC-B-002, MAC-B-003]
  acceptance: 文字与选中态可辨识
```

### Backlog（阶段 D，可选）

- [x] **UI-D-001**：持久化 `_top_splitter` / `_workspace_splitter` 尺寸与底栏高度（`config` / `ui_prefs`）。  
- [x] **UI-D-002**：最小窗口宽度与小屏策略。  
- [x] **UI-D-003**：`CollapsibleGroupBox` 展开策略记忆（按 widget 类型，成本允许再做）。  
- [x] **UI-D-004**：专注模式（收拢侧栏）。

---

## 7. 关键文件索引（修正：无 `inspector_panel.py`）

| 文件 | 典型改动 |
|------|-----------|
| `ui_designer/ui/theme.py` | Token、全局 QSS、深浅色 |
| `ui_designer/ui/main_window.py` | 三栏壳、工具栏分组、`_inspector_tabs`、底栏、菜单 |
| `ui_designer/ui/property_panel.py` | 属性表单与分组 |
| `ui_designer/ui/widgets/collapsible_group.py` | 折叠组视觉 |
| `ui_designer/ui/inspector/*.py` | 分组布局与标签 |
| `ui_designer/ui/project_workspace.py` | 左栏 Project 区密度 |
| `ui_designer/ui/editor_tabs.py` | 中央编辑区外框 |
| `ui_designer/model/config.py` / `ui_designer/settings/ui_prefs.py` | 布局持久化（Backlog） |
| `ui_designer/ui/iconography.py` | 图标键与语义（次要） |

---

## 8. AI 连续执行 SOP（每次照做）

将下列模板粘贴到对话，并把「本文件」指为 `UI_VISUAL_AND_LAYOUT_REFINEMENT_PLAN.md`：

```text
请按 ui_designer/UI_VISUAL_AND_LAYOUT_REFINEMENT_PLAN.md 执行：
1) 选择 deps 已满足且 status=todo 的 1～2 个任务（MAC-* 或 UI-*）。
2) 只做最小必要改动，优先复用 theme token；不改业务信号与数据链路。
3) 在本文件 §10「执行跟踪区」更新：completed / in_progress / blocked / next_recommended。
4) 输出：改动文件列表、完成任务 ID、验证方式（main.py smoke 或 pytest）、下一推荐任务 ID。
5) 若结构性阻塞，标记 blocked 并写明解除条件。
```

**单任务深挖示例**：

```text
请阅读 ui_designer/UI_VISUAL_AND_LAYOUT_REFINEMENT_PLAN.md，完成任务 UI-B-001
（Inspector 去掉 Page 下 Fields/Timers 嵌套 Tab）。约束：行为一致；改后 main.py smoke；
可运行 pytest -c ui_designer/pyproject.toml ui_designer/tests。
```

---

## 9. 验收标准（DoD）

- 主路径（打开项目 → 编辑结构/属性 → 编译或预览相关操作）**视觉一致**。  
- 主要控件状态统一：**hover / pressed / disabled / selected**。  
- Inspector **信息层级清晰**（标题 / 标签 / 输入区）。  
- **深浅色可用**，无明显对比度问题。  
- **Tab 可见深度 ≤ 2**（Sprint B 结束后复查）。  
- 任务状态在 §10 可接续。

---

## 10. 风险与回滚

- **样式影响交互**：只改样式与布局容器，不改业务逻辑与 signal/slot 语义。  
- **深色不可读**：浅色先达标，深色随 MAC-C-003 逐组修。  
- **硬编码覆盖 token**：发现一处收一处，优先主窗口与高盘面板。

**回滚**：按任务粒度提交；配合 `git revert` 单文件或单任务分支。

---

## 11. 执行跟踪区（每次更新）

```yaml
last_update: 2026-03-31
phase: Backlog D
completed:
  - UI-S0-001
  - UI-S0-002
  - UI-S0-003
  - MAC-A-001
  - MAC-A-002
  - MAC-A-003
  - UI-B-001
  - MAC-B-001
  - MAC-B-002
  - UI-B-002
  - MAC-B-003
  - UI-B-003
  - MAC-C-001
  - MAC-C-002
  - MAC-C-003
  - UI-D-004
  - UI-D-001
  - UI-D-002
  - UI-D-003
in_progress: []
blocked: []
next_recommended:
  - 可选：分批跑 UI 子集（`ui/test_theme.py`、`ui/test_workspace_dialogs.py`、`ui/test_main_window_file_flow.py` 轻量用例）；本机全量 UI 可能触发 Qt native access violation，尽量避免一次性跑完 ui_designer/tests/ui
  - 观察到：批量跑 `ui/test_main_window_file_flow.py`（排除单个用例后仍跑大量）在本机环境可能导致原生崩溃；建议继续只跑单个/少量用例来验证
notes:
  - 回归验证（非 UI）：`pytest ui_designer/tests/{engine,generator,model,renderer,settings}` 已通过，共 667 passed
  - 集成验证：`python package_ui_designer.py --sdk-root sdk/EmbeddedGUI` 成功；产物位于 `dist/EmbeddedGUI-Designer` 与 zip 包
  - 回归验证（打包脚本）：`pytest ui_designer/tests/test_package_ui_designer.py` 通过（25 passed）
  - 回归验证（UI 子集）：`test_editor_tabs/test_diagnostics_panel/test_history_panel/test_animations_panel` 共 13 passed；`test_theme` 与 `test_workspace_dialogs` 通过（本机已验证）
  - 回归验证（UI 子集，2026-03-31）：`pytest ui_designer/tests/ui/test_theme.py`（2 passed）
  - 回归验证（UI 子集，2026-03-31）：`pytest ui_designer/tests/ui/test_workspace_dialogs.py`（37 passed）
  - MainWindow 关键用例回归（2026-03-31）：`pytest ui_designer/tests/ui/test_main_window_file_flow.py -k "inspector_group_expanded_persist_and_restore or test_main_window_clamps_to_available_screen or test_open_recent_project_can_remove_missing_entry"`（3 passed, 248 deselected）
  - PropertyPanel 关键用例回归（2026-03-31）：`pytest ui_designer/tests/ui/test_property_panel_file_flow.py -k "empty_state_and_search_metadata or file_selector_sets_accessibility_metadata or browse_file_warns_when_project_resource_dir_is_missing or browse_file_auto_imports_image_and_emits_resource_imported or single_selection_name_edit_rejects_invalid_identifier or single_selection_callback_edit_normalizes_and_updates_widget"`（6 passed, 25 deselected）
  - 回归验证（smoke 修复后）：`ui_designer_preview_smoke.py --sdk-root sdk/EmbeddedGUI` 通过；`pytest ui_designer/tests/generator/test_code_gen_edge_cases.py::TestAppEguiConfigContent` 通过
  - MainWindow 关键用例回归：`test_main_window_file_flow.py` 中 `inspector_group_expanded_persist_and_restore` / `test_main_window_clamps_to_available_screen` / `test_open_recent_project_can_remove_missing_entry` 均通过（3 passed）
  - 集成修复点：`code_generator.generate_app_config()` 在生成 `app_egui_config.h` 时增加 `EGUI_CONFIG_FUNCTION_SUPPORT_MASK=1`，保证 circle-mask 相关实现可链接
  - theme.py：布局 token（r_* / space_* / pad_* / h_tab_min / fs_*）驱动主 QSS；按钮 :pressed/:disabled、Tab :hover、导航/芯片 :pressed
  - 顶栏 SDK / Diagnostics 芯片 tooltip 区分左 Status 与底 Diagnostics
  - MAC-B-003：Inspector `_inspector_form`、property_panel 滚动根 QSS、collapsible_group 对象名与折叠高度
  - UI-B-003：菜单/工具栏/树「Widgets」与「Insert Component」命名一致；测试对齐 Data 组中的 font_file 行
  - MAC-C-001：列表/树选中态在非活动窗口下用 selection_soft；选中行 hover 保持高亮
  - MAC-C-002：欢迎页「无最近工程」与属性面板「无选中」空状态双行文案 + 面板样式
  - MAC-C-003：dark token 对比度提升（border/text/accent/selection），并让 light surface_hover 与 test_theme 基线一致
  - UI-D-004：新增 View > Focus Canvas 切换（隐藏左栏/Inspector/底栏），打开 Inspector/Tools 时自动退出专注模式
  - UI-D-001：workspace_state 新增 focus_canvas_enabled，重启后可恢复 Focus Canvas
  - UI-D-002：主窗 min 960×620、Inspector 滚动区 min 280；启动/恢复几何后按主屏 availableGeometry 收缩并校正位置
  - UI-D-003：workspace_state.inspector_group_expanded（键：widget_type + 制表符 + 组标题，多选为 __multi__ 前缀）；CollapsibleGroupBox.apply_expanded_state 恢复
  - §6 壳层：Tab 选中态与 pane 同色衔接；nav_rail / status_chip 内边距用 space_*；对话框提示色用 hintTone / dialog_muted_hint
  - 欢迎页空列表测试：断言容器 accessibleName 与子 QLabel，与 test_workspace_dialogs 一致
```

---

*文档版本：2.0 — 合并 macOS 专项与界面整理计划；任务 ID 含 UI-*（结构/IA）与 MAC-*（视觉 Sprint）。*
