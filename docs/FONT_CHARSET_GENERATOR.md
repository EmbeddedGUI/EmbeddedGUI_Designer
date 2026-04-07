# Font Charset Generator

资源面板中的 `Fonts -> Generate Charset...` 用来生成字体 `text` 资源文件，目标是让常见字符集不再靠手工拷贝维护。

## 适用场景

- 需要快速生成 ASCII、GB2312、GBK 的完整或子集字符表
- 需要给中文字体补固定字符集，而不是只依赖源码抽字
- 需要把生成结果直接绑定到当前控件的 `font_text_file`

## 使用入口

1. 打开一个已保存项目
2. 进入左侧资源面板 `Fonts` 页
3. 点击 `Generate Charset...`

## 当前内置预设

- `ASCII 可显示字符`：95 个
- `GB2312 全角符号`：682 个
- `GB2312 一级汉字`：3755 个
- `GB2312 二级汉字`：3008 个
- `GB2312 全部字符`：7540 个，包含 ASCII
- `GBK 全部字符`：21886 个，包含 ASCII

这些预设可以组合使用，生成器会按选择顺序去重合并。

## 输出规则

- 输出位置：`.eguiproject/resources/<filename>.txt`
- 输出编码：UTF-8
- 输出格式：每个字符一行
- ASCII 可见字符直接写字面量
- 空格和非 ASCII 字符写成 `&#xHHHH;`

这样做的目的：

- `space` 不会因为空白行而丢失
- 罕见字符和 GBK 扩展字符在 diff 中更稳定
- 兼容现有 `ttf2c.py` / `app_resource_generate.py` 解析逻辑

## 保存行为

- `Save`
  - 只生成或覆盖 `.txt` 资源
  - 自动刷新资源面板并切换到 `Text` 页选中新文件
- `Save and Bind Current Widget`
  - 在 `Save` 基础上，把当前文件写入当前选中控件的 `font_text_file`

如果目标文件已经存在，会先显示旧字符数、新字符数、新增数、删除数，再确认是否覆盖。

## 和现有资源链路的关系

- 生成器只负责写设计期资源：`.eguiproject/resources/*.txt`
- 项目保存或资源刷新后，现有同步链路会把这些文件复制到 `resource/src/`
- `ResourceConfigGenerator` 会把控件上的 `font_text_file` 合并进 `app_resource_config.json`
- SDK 侧仍然使用原有 `app_resource_generate.py` 和 `ttf2c.py`

## 当前限制

- 只提供内置预设，不支持自定义命名预设库
- 不做字体体积估算
- 不替代源码抽字；如果项目文本来自运行时动态数据，仍需要你主动补字符集
