# 独立资源生成器

`Build -> Resource Generator...` 是一个独立于项目页面编辑流的资源配置与生成入口。

它适合处理 `app_resource_config.json`，而不要求你先打开一个 `.egui` 工程。

## 什么时候用它

- 你手上已经有一份 `app_resource_config.json`，想直接导入并编辑
- 你要新建一份资源配置，但还没开始搭 UI 工程
- 你要核对用户配置和 Designer 自动生成 overlay 合并后的最终结果
- 你要先把资源生成链路跑通，再回到页面设计

## 入口

```text
Build -> Resource Generator...
```

这个窗口可以在没有打开任何工程时直接使用。

## 它和 Generate Resources 的区别

### Generate Resources

- 面向当前已经打开的工程
- 默认使用工程自己的 `resource/` 目录
- 更像是“对当前工程执行一次资源生成”

### Resource Generator...

- 可以脱离工程独立工作
- 同时负责配置编辑、预览和生成
- 更像是“单独维护和验证 app_resource_config.json”

如果你只是改了当前工程里的资源，并且项目已经打开，通常继续用 `Generate Resources` 就够了。

如果你需要导入一个外部配置文件，或想新建独立资源配置，优先用 `Resource Generator...`。

## 窗口里能做什么

- `New`
  - 新建空白资源配置
- `Open...`
  - 打开已有 `app_resource_config.json`
- `Save`
  - 保存当前配置
- `Save As...`
  - 另存为新的配置文件
- `Generate`
  - 直接调用 SDK 资源生成脚本

底部还有三个辅助标签页：

- `Raw JSON`
  - 直接编辑原始 JSON
- `Merged Preview`
  - 查看用户配置和 Designer overlay 合并后的结果
- `Generation Log`
  - 查看校验、命令和生成日志

## 当前支持的结构化 section

窗口目前为这些常见 section 提供了图形化编辑器：

- `img`
- `font`
- `mp4`

未知字段不会被直接丢掉。它们仍然可以通过 `Raw JSON` 编辑和保留。

## 路径模型要怎么理解

这个窗口把资源生成拆成四个明确路径：

- `Config`
  - 当前要编辑的用户配置文件
- `Source Dir`
  - 图片、字体、字符集文本等源文件目录
- `Workspace`
  - 资源生成工作目录
- `Bin Output`
  - 合并资源 bin 的输出目录

如果你先指定 `Config`，窗口会按常见目录结构自动推断其余路径；你也可以手动覆盖。

## Overlay 规则

如果 `Source Dir` 下存在：

```text
.designer/app_resource_config_designer.json
```

Designer 会把它看成自动维护的 overlay：

- 你编辑的是用户侧 `app_resource_config.json`
- `Merged Preview` 里看到的是最终合并结果
- 不会直接改写 `.designer/app_resource_config_designer.json`
- 生成时如果需要临时合并配置，会在当前 `Workspace/src/.designer/` 下短暂使用 `.app_resource_config_merged.json`，生成结束后自动清理，不属于需要手工维护的项目文件

这样可以把用户手工配置和 Designer 自动元数据分开。

## 生成前建议检查什么

- SDK 根目录有效
- `Source Dir` 存在
- `Workspace` 和 `Source Dir` 不是同一个目录
- 图片、字体、文本文件路径都能解析到真实文件
- `font.text` 引用的文本文件存在

如果配置里包含 `mp4` 条目，还要求系统里能找到 `ffmpeg`。

## 当前限制

- 结构化表单目前只覆盖 `img`、`font`、`mp4`
- 更复杂或未知字段仍然建议在 `Raw JSON` 中处理
- 它不替代左侧资源面板，后者仍负责项目设计期资源管理

继续阅读：[预览与构建](18_preview_and_build.md)
