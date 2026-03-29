# UI Designer V1 Selective Expansion — AI 可执行实施文档

## 0. 文档用途

本文件是 `ui_designer` 的 V1 改造执行蓝图，目标是让后续 AI/开发者可以直接按任务 ID 连续推进，不丢上下文。

- 范围：Selective Expansion（有限扩展）
- 周期：6~8 周
- 目标：解决“界面乱 + 预览丑 + 控件难找”
- 原则：小步快跑、双引擎并行、随时可回滚

---

## 1. 执行总览（高层）

### 1.1 V1 只做这四件事

1. 主界面三栏重排：`Library | Canvas | Inspector`
2. 控件库升级：搜索/分类/最近/收藏
3. 属性面板分组化：基础/布局/样式/事件/数据
4. 预览双引擎框架：`V1 Python Renderer` + `V2 Renderer`

### 1.2 明确不做

- 云端协作、多人编辑
- 模板市场/插件市场
- 大规模动画系统
- 全量视觉重构（仅先统一高频组件）

---

## 2. 工程约束与基线

- 当前技术栈：PyQt5（见仓库 `CLAUDE.md`）
- 现有渲染：`ui_designer/engine/python_renderer.py`
- 主窗口：`ui_designer/ui/main_window.py`
- 不可破坏：现有工程文件格式、代码生成主路径、发布流程

### 2.1 分支建议

- 建议分支名：`feat/ui-v1-selective-expansion`

### 2.2 Feature Flag（必须）

- `NEW_SHELL_ENABLED`：控制新三栏壳层
- `PREVIEW_V2_ENABLED`：控制 V2 渲染可见性

默认：都关闭；逐步灰度开启。

---

## 3. 目标目录结构（目标态）

> 说明：若已有同名文件，则优先扩展，不做重复创建。

```text
ui_designer/
  core/
    state_store.py
    design_schema.py
    event_bus.py                 # 可选
  renderer/
    base.py
    manager.py
    v1_python_renderer.py
    v2_renderer_qml.py           # 或 v2_renderer_web.py（二选一）
  services/
    component_catalog.py
    search_service.py
    recent_service.py
    favorite_service.py
  ui/
    main_window.py
    panels/
      library_panel.py
      tree_panel.py
      inspector_panel.py
      bottom_panel.py
    inspector/
      groups_basic.py
      groups_layout.py
      groups_style.py
      groups_event.py
      groups_data.py
    widgets/
      searchable_list.py
      collapsible_group.py
      tokenized_controls.py
  settings/
    preview_settings.py
    ui_prefs.py
```

---

## 4. 数据与接口契约（先协议后实现）

## 4.1 ComponentMeta（控件元数据）

```python
from dataclasses import dataclass

@dataclass
class ComponentMeta:
    id: str
    display_name: str
    category: str
    tags: list[str]
    icon: str | None = None
    usage_score: float = 0.0
    is_favorite: bool = False
    last_used_ts: float | None = None
```

## 4.2 EditorState（编辑器状态）

```python
from dataclasses import dataclass, field

@dataclass
class EditorState:
    current_page_id: str | None = None
    selected_node_id: str | None = None
    active_left_tab: str = "library"
    active_bottom_tab: str = "logs"
    preview_engine: str = "v1"
    panel_layout: dict = field(default_factory=dict)
```

## 4.3 IRenderer（渲染抽象）

```python
from typing import Protocol

class IRenderer(Protocol):
    name: str

    def mount(self, host_widget) -> None: ...
    def render(self, schema: dict) -> None: ...
    def select_node(self, node_id: str) -> None: ...
    def update_node(self, node_id: str, patch: dict) -> None: ...
    def snapshot(self) -> bytes: ...
    def dispose(self) -> None: ...
```

---

## 5. 可执行任务清单（AI 执行格式）

> 状态枚举：`todo | doing | blocked | done`
>
> 依赖字段说明：必须先完成 `deps` 再执行当前任务。

## 5.1 Sprint 1（第 1~2 周）：壳层与状态

```yaml
- id: UI-S1-001
  title: 盘点主窗口现状并标注可复用区域
  status: todo
  deps: []
  output:
    - main_window 重构边界清单
    - 需要保留的旧信号/槽列表
  acceptance:
    - 形成重构注释或文档，覆盖主面板与工具栏入口

- id: UI-S1-002
  title: 在 main_window 引入三栏布局骨架
  status: todo
  deps: [UI-S1-001]
  output:
    - Library/Canvas/Inspector 三分区可见
    - 左/右面板支持伸缩
  acceptance:
    - 启动应用可见新布局（受 NEW_SHELL_ENABLED 控制）

- id: UI-S1-003
  title: 新增 panel 布局持久化（宽度/折叠/激活 tab）
  status: todo
  deps: [UI-S1-002]
  output:
    - settings/ui_prefs.py
    - 读写布局状态逻辑
  acceptance:
    - 重启后布局状态恢复一致

- id: UI-S1-004
  title: 建立最小 state_store（页面/选中节点）
  status: todo
  deps: [UI-S1-002]
  output:
    - core/state_store.py
    - 统一 selection 更新入口
  acceptance:
    - 结构树、画布、属性面板可共享选中态
```

## 5.2 Sprint 2（第 3~4 周）：控件库可用化

```yaml
- id: UI-S2-001
  title: 抽离 component_catalog 服务
  status: todo
  deps: [UI-S1-004]
  output:
    - services/component_catalog.py
    - 控件分类与标签数据结构
  acceptance:
    - 控件数据不再散落在 UI 类内部

- id: UI-S2-002
  title: 实现 search_service（名称/标签/分类匹配）
  status: todo
  deps: [UI-S2-001]
  output:
    - services/search_service.py
    - 排序权重逻辑
  acceptance:
    - 输入关键词可返回稳定排序结果

- id: UI-S2-003
  title: 实现 recent/favorite 服务
  status: todo
  deps: [UI-S2-001]
  output:
    - services/recent_service.py
    - services/favorite_service.py
  acceptance:
    - 收藏/最近可增删查，数据可持久化

- id: UI-S2-004
  title: Library Panel 接入搜索/分类/最近/收藏
  status: todo
  deps: [UI-S2-002, UI-S2-003]
  output:
    - ui/panels/library_panel.py
  acceptance:
    - 用户可在一个面板完成控件检索与插入

- id: UI-S2-005
  title: 打通拖拽插入主流程（Library -> Canvas -> Schema）
  status: todo
  deps: [UI-S2-004]
  output:
    - 拖拽事件绑定
    - 插入后选中同步
  acceptance:
    - 拖拽控件后能出现在画布并进入选中态
```

## 5.3 Sprint 3（第 5~6 周）：属性面板分组化

```yaml
- id: UI-S3-001
  title: 建立 Inspector 分组容器（可折叠）
  status: todo
  deps: [UI-S1-004]
  output:
    - ui/widgets/collapsible_group.py
    - ui/panels/inspector_panel.py
  acceptance:
    - 面板至少支持 5 个逻辑分组

- id: UI-S3-002
  title: 实现基础/布局/样式分组
  status: todo
  deps: [UI-S3-001]
  output:
    - groups_basic.py
    - groups_layout.py
    - groups_style.py
  acceptance:
    - 常见控件可完整编辑基础属性

- id: UI-S3-003
  title: 实现事件/数据分组（最小版）
  status: todo
  deps: [UI-S3-001]
  output:
    - groups_event.py
    - groups_data.py
  acceptance:
    - 对应控件能按条件展示这些分组

- id: UI-S3-004
  title: 属性变更 patch 通道统一到 state_store
  status: todo
  deps: [UI-S3-002, UI-S3-003]
  output:
    - inspector -> state_store.update_node(patch)
  acceptance:
    - 修改属性后画布实时刷新，且可撤销
```

## 5.4 Sprint 4（第 7~8 周）：预览双引擎

```yaml
- id: UI-S4-001
  title: 定义 IRenderer 与 renderer manager
  status: todo
  deps: [UI-S1-004]
  output:
    - renderer/base.py
    - renderer/manager.py
  acceptance:
    - manager 可注册/切换引擎

- id: UI-S4-002
  title: 将现有 python_renderer 封装为 v1 adapter
  status: todo
  deps: [UI-S4-001]
  output:
    - renderer/v1_python_renderer.py
  acceptance:
    - v1 走新接口后行为与旧版一致

- id: UI-S4-003
  title: 新增 v2 renderer 最小实现（3类高频控件）
  status: todo
  deps: [UI-S4-001]
  output:
    - renderer/v2_renderer_qml.py 或 v2_renderer_web.py
  acceptance:
    - 高频控件在 v2 下能渲染并可更新属性

- id: UI-S4-004
  title: 设置页接入预览引擎切换 + 异常回退
  status: todo
  deps: [UI-S4-002, UI-S4-003]
  output:
    - settings/preview_settings.py
    - v2 失败自动回退 v1
  acceptance:
    - 切换可用，失败不会阻断编辑流程
```

---

## 6. AI 每次执行时的标准流程（SOP）

每次让 AI 继续推进时，可直接使用下面模板：

```text
请按 V1_SELECTIVE_EXPANSION_EXECUTION_PLAN.md 执行：
1) 先从任务清单里挑选所有 deps 满足且 status=todo 的任务。
2) 一次最多做 1~2 个任务，完成后把它们标记为 done。
3) 若新增文件，遵循文档目录结构；若已有文件，优先最小改动。
4) 每次改动后运行最小必要测试（或启动检查），并记录结果。
5) 输出：改动文件列表、完成任务ID、未解决风险、下一个建议任务ID。
```

---

## 7. 质量门禁（Definition of Done）

任务完成必须同时满足：

1. 功能完成：达到任务 `acceptance`
2. 稳定性：无明显回归（至少手工验证关键路径）
3. 可维护：新增模块职责清晰，不把业务逻辑塞回 UI 事件里
4. 可追踪：更新本文档中的任务状态

---

## 8. 测试与验证清单

## 8.1 单元测试建议

- `search_service`：关键词匹配、权重排序、空关键词
- `recent/favorite`：增删改查、去重、容量限制
- `renderer/manager`：注册、切换、异常回退

## 8.2 集成回归（手工）

1. 拖拽控件到画布
2. 在 Inspector 修改属性并实时生效
3. 切换 V1/V2 渲染并保证不崩溃
4. 重启后面板布局、收藏、最近记录仍在

## 8.3 建议命令

```bash
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v --tb=short
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

---

## 9. 风险与应对

- 风险：主窗口重构导致老功能入口失效
  - 应对：`NEW_SHELL_ENABLED` 灰度，先并存

- 风险：V2 渲染不稳定
  - 应对：默认 V1，V2 实验开关 + 自动回退

- 风险：控件元数据治理成本高
  - 应对：先覆盖高频控件，逐步补齐长尾

---

## 10. 回滚策略

- 任一 Sprint 可独立回滚（按任务粒度提交）
- 若新壳层问题严重：关闭 `NEW_SHELL_ENABLED`
- 若 V2 问题严重：关闭 `PREVIEW_V2_ENABLED` 并强制 v1

---

## 11. 执行状态跟踪区（持续更新）

> 后续 AI 每次执行后都要更新此处。

```yaml
last_update: 2026-03-29
current_sprint: S4
completed:
  - UI-S1-001
  - UI-S1-002
  - UI-S1-003
  - UI-S1-004
  - UI-S2-001
  - UI-S2-002
  - UI-S2-003
  - UI-S2-004
  - UI-S2-005
  - UI-S3-001
  - UI-S3-002
  - UI-S3-003
  - UI-S3-004
  - UI-S4-001
  - UI-S4-002
  - UI-S4-003
  - UI-S4-004
in_progress:
  - []
blocked:
  - []
next_recommended:
  - []
notes:
  - 已完成主窗口现状盘点，保留“左导航+中画布+右检查器+底部工具”的既有壳层能力。
  - 已新增 feature flag：NEW_SHELL_ENABLED / PREVIEW_V2_ENABLED，支持灰度切换。
  - 已新增 settings/ui_prefs.py 并接入 main_window，持久化 splitter/tab/底部面板与左侧激活面板。
  - 已新增 core/state_store.py 并接入页面切换、选中态、底部面板与左侧面板状态更新入口。
  - 已存在 services/component_catalog.py、search_service.py、recent_service.py、favorite_service.py 并在 widget_browser 中使用。
  - library_panel.py 已封装 WidgetBrowserPanel，可用于后续壳层切换。
  - 已完成拖拽插入链路：Widget Browser -> Preview Overlay -> WidgetTree insert + selection sync。
  - Inspector 已接入共享可折叠分组容器，并完成 Basic/Layout/Style/Behavior/Data/Callbacks 分组。
  - property_panel 属性变更已写入 state_store node patch 通道，便于后续统一状态观察与撤销策略。
  - 已补充 renderer/base.py 与 renderer/manager.py 的注册/切换基础能力，并在 main_window 启动阶段完成渲染器注册。
  - 已将旧 python_renderer 封装为 renderer/v1_python_renderer.py 适配器并接入 manager。
  - 已新增 settings/preview_settings.py 与 View 菜单预览引擎切换入口，支持配置持久化与运行时切换。
  - 当预览运行失败时会自动回退到 V1 引擎并同步 state_store/config，保证编辑链路不中断。
```

---

## 12. 下一步（建议立即执行）

1. 执行 `UI-S1-002`：在 `main_window.py` 引入 `NEW_SHELL_ENABLED` 分支骨架（先不替换旧逻辑）
2. 执行 `UI-S1-003`：新增 `settings/ui_prefs.py`，持久化 splitter/tab/折叠状态
3. 执行 `UI-S1-004`：抽最小 `state_store.py`，统一选中态入口

---

## 13. UI-S1-001 盘点结果（main_window 重构边界）

### 13.1 可复用区域（建议保留）

1. 工作区壳层结构已接近目标态：
   - 左侧：`_left_shell` + `_left_panel_stack`
   - 中央：`_center_shell`（含 page tab + `EditorTabs/PreviewPanel`）
   - 右侧：`_inspector_tabs`
   - 底部：`_bottom_tabs` + `_workspace_splitter`
2. 顶部命令区可复用：`_toolbar_host` + `_init_toolbar()`
3. 导航元数据与可访问性逻辑可复用：
   - `_update_workspace_nav_button_metadata`
   - `_update_workspace_layout_metadata`
   - `_update_workspace_tab_metadata`
4. 页面切换/状态同步骨架可复用：
   - `_switch_page`
   - `_set_selection`
   - `_record_page_state_change`

### 13.2 重构隔离边界（建议分层）

1. **Shell 层（新）**：只负责布局、面板装配、feature flag 切换。
2. **State 层（新）**：选中态/当前页/激活面板状态。
3. **Render 层（后续 S4）**：编译预览与 Python fallback 统一由 manager 驱动。
4. **业务动作层（保留）**：现有 `_on_*` 事件方法先不拆，避免第一阶段风险。

### 13.3 需保留的关键信号/槽链路

1. 结构树链路：
   - `widget_tree.selection_changed -> _on_tree_selection_changed`
   - `widget_tree.tree_changed -> _on_tree_changed`
2. 画布链路：
   - `preview_panel.selection_changed -> _on_preview_selection_changed`
   - `preview_panel.widget_moved/widget_resized -> _on_widget_moved/_on_widget_resized`
3. 属性链路：
   - `property_panel.property_changed -> _on_property_changed`
4. 编辑器链路：
   - `editor_tabs.xml_changed -> _on_xml_changed`
   - `editor_tabs.mode_changed -> _sync_editor_mode_controls`
5. 页面导航链路：
   - `project_dock.page_selected -> _on_page_selected`
   - `page_navigator.page_selected -> _on_page_selected`
6. 资源链路：
   - `res_panel.resource_selected -> _on_resource_selected`
   - `res_panel.resource_imported -> _on_resource_imported`

### 13.4 UI-S1-002 实施注意事项

1. 在 `_init_ui()` 中以 `NEW_SHELL_ENABLED` 包裹新骨架构建函数：
   - 旧逻辑保持可用（默认）
   - 新逻辑并行挂载（灰度）
2. 保持对象名兼容（如 `self.widget_tree/self.property_panel/self.preview_panel`），避免后续信号断链。
3. 第一步只做“结构复用+封装”，不做视觉重绘，不改交互行为。
