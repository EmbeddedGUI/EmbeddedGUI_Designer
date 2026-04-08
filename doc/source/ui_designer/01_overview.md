# 项目概览

`EmbeddedGUI Designer` 是一个基于 PyQt5 的桌面端 UI 设计器，用来为 `EmbeddedGUI` SDK 生成页面布局、资源配置和 C 代码。

它不是独立的运行时框架，而是 `sdk/EmbeddedGUI` 的上层生产工具。可以把它理解成：

- `sdk/EmbeddedGUI` 负责控件、渲染、移植、示例与运行时。
- `EmbeddedGUI_Designer` 负责工程组织、可视化编辑、预览、资源绑定、代码导出与发布打包。

## 你可以用它做什么

本项目主要解决下面几类工作：

- 新建一个符合 `EmbeddedGUI` 目录规范的应用工程。
- 可视化编辑页面和控件树，而不是只手写 XML 或 C。
- 管理图片、字体、文本资源，并生成资源配置文件。
- 在 Design、Split、Code 三种视图之间切换。
- 导出页面对应的 C 文件，并保留用户代码区。
- 直接对当前工程做 Release Build，生成可交付的 EXE 包。

## 它不负责什么

有几个边界要提前明确：

- 它不替代 `sdk/EmbeddedGUI` 本身，SDK 仍然是编译和运行的基础。
- 它不直接替代底层移植工作，板级、驱动和平台适配仍在 SDK 中完成。
- 它不是纯图像设计工具，重点是工程化的 UI 生产链路。

## 典型工作流

一个完整的 Designer 工作流通常是：

1. 准备好 SDK 和 Python 环境。
2. 启动 Designer，绑定 `sdk/EmbeddedGUI`。
3. 新建工程，或打开示例/已有 `.egui` 工程。
4. 在左侧切换 Project、Structure、Components、Assets 面板。
5. 在中间画布编辑页面，在右侧属性区修改参数。
6. 保存工程，必要时切换到 Code 模式检查 XML。
7. 执行 Build、Generate Resources、Export C Code 或 Release Build。

## 建议怎么阅读后续文档

- 如果你是第一次接触本软件，先看 [五分钟快速上手](02_quick_start.md)。
- 如果你已经能打开工程，建议继续看 [工作区总览](09_workspace_overview.md)。
- 如果你重点关心交付，直接阅读 [Release Build](20_release_build.md) 和 [Release History](22_release_history.md)。

继续阅读：[五分钟快速上手](02_quick_start.md)
