# EmbeddedGUI Designer 使用手册

本目录参考 `sdk/EmbeddedGUI/doc` 的章节化写法，为当前仓库补齐一套面向实际使用者的中文文档。

文档目标有三件事：

1. 解释本项目到底能做什么，以及它和 `sdk/EmbeddedGUI` 的关系。
2. 按真实操作顺序说明 Designer 的常见工作流。
3. 用本仓库实际运行后截取的界面截图，降低上手成本。

## 建议阅读顺序

如果你第一次使用本软件，建议按下面顺序阅读：

1. [项目概览](01_overview.md)
2. [五分钟快速上手](02_quick_start.md)
3. [环境准备](03_environment_setup.md)
4. [SDK 绑定与查找规则](04_sdk_resolution.md)
5. [首次启动与欢迎页](05_first_launch.md)
6. [新建工程](06_new_project.md)
7. [打开示例与已有工程](07_open_example_and_project.md)
8. [工作区总览](09_workspace_overview.md)

如果你已经能正常打开工程，建议继续阅读：

1. [页面管理](10_page_management.md)
2. [组件面板](11_widget_browser.md)
3. [画布编辑](12_canvas_editing.md)
4. [结构面板](13_structure_panel.md)
5. [属性面板](14_property_panel.md)
6. [资源面板](15_resource_panel.md)
7. [字符集生成器](16_font_charset_generator.md)
8. [Code/XML 模式](17_code_mode_and_xml.md)

如果你准备进入生成、发布和排障阶段，建议阅读：

1. [预览与构建](18_preview_and_build.md)
2. [导出 C 代码](19_export_c_code.md)
3. [Release Build](20_release_build.md)
4. [Release Profiles](21_release_profiles.md)
5. [Release History](22_release_history.md)
6. [Repository Health](23_repository_health.md)
7. [常见问题排查](24_troubleshooting.md)
8. [推荐使用习惯](25_best_practices.md)

## 文档清单

| 序号 | 文档 | 说明 |
| --- | --- | --- |
| 01 | [项目概览](01_overview.md) | 产品定位、能力边界、典型流程 |
| 02 | [五分钟快速上手](02_quick_start.md) | 从安装到导出的一条最短路径 |
| 03 | [环境准备](03_environment_setup.md) | Python、依赖、子模块、工具链 |
| 04 | [SDK 绑定与查找规则](04_sdk_resolution.md) | `--sdk-root`、环境变量、默认路径 |
| 05 | [首次启动与欢迎页](05_first_launch.md) | 欢迎页按钮、最近工程、首次配置 |
| 06 | [新建工程](06_new_project.md) | 新建工程对话框、命名和目录规则 |
| 07 | [打开示例与已有工程](07_open_example_and_project.md) | Open Example、Open Project、Recent |
| 08 | [工程目录结构](08_project_structure.md) | `.egui`、`.eguiproject`、生成代码与资源 |
| 09 | [工作区总览](09_workspace_overview.md) | 菜单栏、左栏、画布、检查器、底部工具 |
| 10 | [页面管理](10_page_management.md) | 页面新增、复制、删除、启动页设置 |
| 11 | [组件面板](11_widget_browser.md) | 插件式组件浏览、搜索、收藏、插入 |
| 12 | [画布编辑](12_canvas_editing.md) | 选中、拖拽、缩放、对齐、网格、背景图 |
| 13 | [结构面板](13_structure_panel.md) | 树结构、分组、层级调整、容器移动 |
| 14 | [属性面板](14_property_panel.md) | 单选/多选属性编辑、校验与批量修改 |
| 15 | [资源面板](15_resource_panel.md) | 图片、字体、文本资源管理 |
| 16 | [字符集生成器](16_font_charset_generator.md) | `Generate Charset...` 的使用方式 |
| 17 | [Code/XML 模式](17_code_mode_and_xml.md) | Design/Split/Code 三种编辑方式 |
| 18 | [预览与构建](18_preview_and_build.md) | Python Preview、EXE 预览、资源生成 |
| 19 | [导出 C 代码](19_export_c_code.md) | 代码导出规则和 USER CODE 保留策略 |
| 20 | [Release Build](20_release_build.md) | 打包入口、输出目录和产物说明 |
| 21 | [Release Profiles](21_release_profiles.md) | 发布配置的增删改查 |
| 22 | [Release History](22_release_history.md) | 发布记录筛选、预览、导出与回溯 |
| 23 | [Repository Health](23_repository_health.md) | 仓库健康检查、路径跳转和报告导出 |
| 24 | [常见问题排查](24_troubleshooting.md) | 启动、SDK、资源、构建、发布问题 |
| 25 | [推荐使用习惯](25_best_practices.md) | 命名、目录、保存、发布前检查清单 |
| 26 | [从零到 Release 的完整流程](26_zero_to_release_workflow.md) | 按实际交付顺序串起完整流程 |
| 27 | [日常迭代工作流](27_daily_iteration_workflow.md) | 面向持续开发的高频使用节奏 |
| 28 | [快捷键与菜单速查](28_shortcuts_and_menu_map.md) | 快捷键、菜单入口和高频动作速查 |
| 29 | [FAQ](29_faq.md) | 高频问题和快速回答 |

## 截图说明

本目录中的截图均来自当前仓库在本机实际运行后的界面采集，主要基于：

- `examples/DesignerSandbox`
- `sdk/EmbeddedGUI`
- 本仓库内置的 Release、History、Repository Health 等真实功能

截图文件位于 `images/` 目录。

## 入口建议

只想立刻跑起来，请读 [五分钟快速上手](02_quick_start.md)。

想系统学习，请从 [项目概览](01_overview.md) 开始。

如果后续准备挂到类似 `sdk/EmbeddedGUI/doc` 的章节体系，也可以直接从 [index.rst](index.rst) 作为 toctree 入口。
