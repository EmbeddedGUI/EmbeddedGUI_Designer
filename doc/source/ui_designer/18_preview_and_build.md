# 预览与构建

Designer 既支持设计态预览，也支持真实构建后的 EXE 预览。

## 两种预览思路

### Python Preview

这是 Designer 自己的设计态预览能力，优点是：

- 速度快
- 对临时编辑友好
- 即使构建条件不完美，也能继续工作

### EXE 预览

这是通过 `Build` 菜单触发的真实构建预览，更接近运行时结果。

## Build 菜单的核心入口

当前版本最重要的几个动作是：

- `Build EXE && Run`
- `Rebuild EGUI Project`
- `Auto Compile`
- `Stop Exe`
- `Generate Resources`
- `Resource Generator...`

## 什么时候用 Build EXE && Run

适合：

- 你已经完成一轮布局调整
- 想看更接近真实结果的运行效果
- 想验证构建链路是否正常

快捷键是：

```text
F5
```

## 什么时候用 Rebuild

当你怀疑构建缓存脏了、资源状态不一致、预览异常时，优先使用：

```text
Ctrl+F5
```

对应菜单项：

```text
Build -> Rebuild EGUI Project
```

## Auto Compile 适合谁

适合小步快改的日常工作，但不适合每个人都默认打开。因为：

- 改动频繁时会不断触发编译
- 大工程下会打断节奏

建议在工程还小、你正在持续试布局时打开。

## Generate Resources 什么时候必须跑

下面这些变化之后，建议立刻生成资源：

- 新增图片
- 新增字体
- 改了字符集
- 改了资源配置

## Resource Generator... 什么时候用

`Build -> Resource Generator...` 适合下面这些场景：

- 你还没有打开 `.egui` 工程，但需要先整理或生成 `app_resource_config.json`
- 你想单独维护资源配置，而不是先进入页面编辑流
- 你需要在图形化表单和原始 JSON 之间切换编辑
- 你要检查用户配置和 `.designer/app_resource_config_designer.json` 合并后的实际结果

这个窗口和项目内的 `Generate Resources` 不是同一个入口：

- `Generate Resources`
  - 面向当前已打开工程
  - 直接使用工程自己的 `resource/` 目录
- `Resource Generator...`
  - 可以脱离工程单独工作
  - 需要你明确给出 `Config`、`Source Dir`、`Workspace`、`Bin Output`
  - 适合导入现有配置或新建一个新的 `app_resource_config.json`

## 构建失败后的 Designer 行为

构建失败时，Designer 通常会尽量退回 Python 侧能力，而不是直接让整个工作流中断。

但这只适合临时继续编辑，不适合当成“构建已通过”。

继续阅读：[导出 C 代码](19_export_c_code.md)
