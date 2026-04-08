# SDK 绑定与查找规则

Designer 的大部分能力都依赖一个可用的 `EmbeddedGUI` SDK 根目录，所以先理解它怎么找 SDK 很重要。

## 默认查找顺序

本项目当前的默认查找顺序是：

1. 命令行参数 `--sdk-root`
2. 环境变量 `EMBEDDEDGUI_SDK_ROOT`
3. 仓库内置子模块 `sdk/EmbeddedGUI`
4. 同级目录 `../EmbeddedGUI`

如果你追求确定性，最稳妥的做法永远是显式传：

```bash
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

## 为什么推荐显式传参

因为它能避免下面几类误判：

- 你本机还有另一个 `EmbeddedGUI` 副本
- 最近一次配置缓存了旧路径
- 你在不同仓库之间切换
- 你在 CI 或打包环境里运行 Designer

## 界面内怎么改 SDK

如果你已经打开了 Designer，可以在：

- `File -> Set SDK...`
- 欢迎页里的 SDK 相关入口

手动指定一个 SDK 根目录。

## 什么情况下可以不手动设置

如果你就是在当前仓库里工作，并且子模块已拉全，通常下面这个路径就够用了：

```text
sdk/EmbeddedGUI
```

也就是说，大多数仓库内开发不需要再单独配置别的 SDK。

## 如何判断当前绑定是否正确

你可以从几个地方确认：

- 启动参数是否传了 `--sdk-root`
- 欢迎页或状态栏里是否显示 SDK ready/valid
- `Build EXE && Run` 是否可用
- `Repository Health...` 里 SDK 路径是否正常

## 什么时候必须处理 SDK 问题

下面这些功能对 SDK 更敏感：

- EXE 预览
- Rebuild
- 资源生成
- Release Build
- 打开 SDK 示例工程

如果只是临时做 XML 或页面层编辑，Designer 有时可以退回 Python 预览，但这不代表 SDK 问题可以长期忽略。

继续阅读：[首次启动与欢迎页](05_first_launch.md)
