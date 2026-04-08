# 工作区总览

主工作区是 Designer 的核心界面。你真正花时间的地方，基本都在这里。

![主工作区](images/02_main_workspace.png)

## 界面分区

从左到右、从上到下看，主界面可以分成五块：

1. 菜单栏和工具栏
2. 左侧工作区面板
3. 中央画布与编辑区
4. 右侧检查器
5. 底部工具区和状态栏

## 菜单栏应该怎么理解

### File

负责工程生命周期：

- New Project
- Open Example...
- Open Project...
- Save Project
- Export C Code...

### Edit

负责编辑动作：

- Undo / Redo
- Copy / Cut / Paste
- Duplicate / Delete

### Arrange

负责几何和层级调整：

- 对齐
- 分布
- 旋转
- 置顶/置底
- 锁定/隐藏

### Structure

负责容器与树结构操作，比如分组、提升层级、移动到容器等。

### Build

负责真正的工程输出：

- `Build EXE && Run`
- `Rebuild EGUI Project`
- `Auto Compile`
- `Release Build (EXE)...`
- `Generate Resources`

### View

负责工作区呈现方式：

- 左侧面板切换
- 检查器切换
- 底部工具切换
- Focus Canvas
- 网格、缩放、预览布局

## 左侧工作区面板

左侧一共有四个高频入口：

- `Project`
- `Structure`
- `Components`
- `Assets`

可以把它们理解成：

- Project：看页面和工程组织
- Structure：看当前页面里的控件树
- Components：找控件并插入
- Assets：管理图片、字体、文本等资源

## 中央编辑区

中央区域不是单一画布，而是一个带模式切换的编辑容器，支持：

- Design
- Split
- Code

日常布局调整主要在 Design，检查 XML 时切到 Code。

## 右侧检查器

右侧默认有三个主标签：

- Properties
- Animations
- Page

它们分别管控件属性、动画和页面级设置。

## 底部工具区

底部工具区默认可折叠，主要包括：

- Diagnostics
- History
- Debug Output

如果你遇到保存失败、构建失败、资源错误，这里通常是第一现场。

继续阅读：[页面管理](10_page_management.md)
