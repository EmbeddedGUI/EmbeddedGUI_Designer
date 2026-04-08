# 五分钟快速上手

这一篇只给你一条最短路径，不展开讲概念。

## 第一步：准备仓库

在仓库根目录执行：

```bash
git submodule update --init --recursive
python -m pip install -r ui_designer/requirements-desktop.txt
```

## 第二步：启动 Designer

推荐直接指定 SDK 路径：

```bash
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

如果你要直接打开一个工程：

```bash
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI --project examples/DesignerSandbox/DesignerSandbox.egui
```

## 第三步：打开示例工程

启动后有两种最快的方式：

1. 在欢迎页点击 `Open Example...`
2. 直接用上面的 `--project` 参数打开 `examples/DesignerSandbox`

建议第一次先打开：

- `examples/DesignerSandbox`
- `examples/HelloSimpleDemo`

## 第四步：修改界面

最简单的试用路径是：

1. 在左侧切到 `Components`
2. 选一个控件插入画布
3. 在右侧 `Properties` 修改 `text`、位置和尺寸
4. 按 `Ctrl+S` 保存

## 第五步：验证结果

常用入口都在 `Build` 菜单：

- `Build EXE && Run`
- `Rebuild EGUI Project`
- `Generate Resources`
- `Release Build (EXE)...`

如果只是想导出代码：

- `File -> Export C Code...`

## 第六步：看生成结果

一个典型工程会得到这些内容：

- `.egui`：工程主文件
- `.eguiproject/layout/*.xml`：页面布局
- `resource/`：资源相关输出
- `{page}_layout.c`、`{page}.h`、`{page}.c`：页面代码

## 下一步读什么

- 想先把环境搭稳：看 [环境准备](03_environment_setup.md)
- 想理解 SDK 是怎么绑定的：看 [SDK 绑定与查找规则](04_sdk_resolution.md)
- 想了解欢迎页和入口：看 [首次启动与欢迎页](05_first_launch.md)
