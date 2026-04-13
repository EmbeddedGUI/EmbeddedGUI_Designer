# Resource Generator

`Build -> Resource Generator...` 是一个独立的资源配置与生成入口，目标是让 `app_resource_config.json` 不再只能依赖已打开的 Designer 工程来维护。

## 适用场景

- 还没有打开 `.egui` 工程，但要先整理资源配置
- 已经有一个现成的 `app_resource_config.json`，想导入并图形化编辑
- 想新建一份资源配置，再逐步补图片、字体、视频条目
- 想先看用户配置和 Designer 自动元数据合并后的实际效果

## 使用入口

1. 打开 Designer
2. 进入 `Build`
3. 点击 `Resource Generator...`

这个窗口可以在没有打开任何项目时直接使用。

## 当前支持的编辑方式

- `New`
  - 新建一个空的资源配置
- `Open...`
  - 导入已有 `app_resource_config.json`
- `Save`
  - 保存到当前配置路径
- `Save As...`
  - 另存为新的配置文件
- `Generate`
  - 直接调用 SDK 的资源生成脚本

窗口底部还提供三个辅助视图：

- `Raw JSON`
  - 直接编辑原始配置文本
- `Merged Preview`
  - 查看用户配置和 Designer 侧 `.designer/app_resource_config_designer.json` 合并后的结果
- `Generation Log`
  - 查看校验、命令行和生成日志

## 当前支持的结构化 section

目前内置了三个常见 section 的结构化编辑器：

- `img`
- `font`
- `mp4`

这些 section 可以直接通过表格和表单编辑。其余未知字段仍然会在 `Raw JSON` 中保留，不会被静默丢弃。

## 路径模型

独立资源生成不是只靠一个配置文件路径完成的，它显式区分四个路径：

- `Config`
  - 要编辑的用户配置文件，一般是 `app_resource_config.json`
- `Source Dir`
  - 存放图片、字体、字符集文本等源文件的目录
- `Workspace`
  - 生成时使用的资源工作目录
- `Bin Output`
  - 合并资源 bin 的输出目录

如果你先指定 `Config`，窗口会优先按常见资源目录结构自动推断另外三个路径；你也可以手动覆盖。

## 和项目内 Generate Resources 的区别

- `Generate Resources`
  - 面向当前已打开工程
  - 默认直接使用工程自己的 `resource/` 布局
- `Resource Generator...`
  - 可以脱离工程独立工作
  - 更适合编辑、迁移、验证单独的 `app_resource_config.json`

如果你只是改了当前工程里的资源并且项目已经打开，通常继续用原来的 `Generate Resources` 就够了。

如果你要处理独立配置文件、临时资源目录或新建配置，优先用 `Resource Generator...`。

## Overlay 规则

当 `Source Dir` 下存在：

```text
.designer/app_resource_config_designer.json
```

窗口会把它当成 Designer 自动维护的 overlay：

- 编辑时只修改用户侧 `app_resource_config.json`
- `Merged Preview` 展示合并后的实际结果
- 不会直接改写 `.designer/app_resource_config_designer.json`

这能避免把 Designer 自动生成的元数据和用户手工配置混在一起。

## 生成前的常见检查

在点击 `Generate` 之前，通常要确认：

- SDK 根目录有效
- `Source Dir` 存在
- `Workspace` 和 `Source Dir` 不是同一个目录
- `font.text` 指向的文本文件存在
- `img` / `mp4` 的源文件能在 `Source Dir` 下找到

如果配置里含有 `mp4` 条目，系统还要求 `ffmpeg` 可用。

## 当前限制

- 结构化表单目前只覆盖 `img` / `font` / `mp4`
- 复杂或未知字段仍然建议在 `Raw JSON` 里处理
- 这是资源配置与生成入口，不替代左侧资源面板的设计期资源管理
