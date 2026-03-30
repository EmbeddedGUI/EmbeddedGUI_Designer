# UI 样式入口盘点（MAC-A-001）

> 自动生成辅助；随改版更新。约定：`theme.py` 为全局 QSS 主入口；`setObjectName` 供 QSS 选择器；散落 `setStyleSheet` 逐步收敛。

## `setStyleSheet(`

| 文件 | 说明 | 收敛建议 |
|------|------|----------|
| `ui/theme.py` | `app.setStyleSheet(_build_stylesheet(...))` | 保持 |
| `ui/main_window.py` | 工具栏局部 QSS；`_set_font_sizes` 动态追加 `* { font-size }` | 工具栏可迁入 `#main_toolbar` 规则；字体覆盖保留代码 |
| `ui/preview_panel.py` | 多处灰阶、等宽标签、缩放按钮 | 迁移到 `theme.py`（objectName 或 token） |
| `ui/widgets/page_navigator.py` | 边框、`#2a2a2a` / `#ccc` | token |
| `ui/new_project_dialog.py` | `#888` 提示 | token |
| `ui/app_selector.py` | 多色状态提示 | 语义色 token |
| `ui/editor_tabs.py` | 分段按钮、`#0078D4` | token / objectName |
| `ui/widget_tree.py` | `_DRAG_TARGET_LABEL_STYLES` 字典驱动 | 可与 token 对齐或保持数据驱动 |
| `ui/widgets/font_selector.py` | 预览字号 | 保持内联 |

## `setObjectName` / 属性（workspace / 主题钩子）

- **`main_window.py`**：`workspace_shell`、`workspace_command_bar`、`workspace_nav_rail`、`workspace_left_shell`、`workspace_center_shell`、`workspace_inspector_tabs`、`workspace_bottom_*`、`main_toolbar`、`workspace_status_chip` 等 — 样式应在 **`theme.py`** 针对这些选择器维护。
- **各 panel**（`property_panel`、`widget_browser`、`project_workspace`、`status_center_panel`、`welcome_page`、`resource_panel`、`history_panel` 等）：`workspace_section_title`、`workspace_panel_header`、`workspace_status_chip` 等 — 同上。

## 小结

- 内联样式 **`setStyleSheet` 优先迁到 `theme.py`**，例外：运行时字体覆盖、字体预览、强状态临时样式。
 **`workspace_*` objectName 已是正确方向**，后续 MAC-B 任务应扩展 token 而非新增散落颜色。
