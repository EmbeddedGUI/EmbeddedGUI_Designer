# 从零到 Release 的完整流程

这一篇不是按功能讲，而是按一次真实交付的顺序讲。

## 阶段 1：准备环境

先在仓库根目录完成：

```bash
git submodule update --init --recursive
python -m pip install -r ui_designer/requirements-desktop.txt
```

然后建议执行一次：

```bash
python scripts/ui_designer/repo_doctor.py --summary
```

## 阶段 2：启动 Designer

推荐命令：

```bash
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

## 阶段 3：创建或打开工程

你有两种路径：

1. 新项目：`New Project...`
2. 参考项目：`Open Example...`

如果是第一次做完整流程，建议先用：

- `examples/DesignerSandbox`

## 阶段 4：完成页面基本搭建

先不要一上来堆满所有内容，建议只做一个最小页面闭环：

1. 插入几个基础控件
2. 调整结构和属性
3. 保存
4. 确认页面 XML 和资源状态正常

## 阶段 5：补资源

如果页面里用到了：

- 图片
- 字体
- 中文字符
- 特殊符号

就进入 `Assets` 面板处理，并在需要时使用 `Generate Charset...`。

## 阶段 6：做一次本地预览验证

建议顺序是：

1. 先保存
2. 必要时 `Generate Resources`
3. `Build EXE && Run`
4. 如果状态不稳，再 `Rebuild EGUI Project`

## 阶段 7：导出代码

如果你的目标是把页面集成到别的 SDK 工程，可以先：

```text
File -> Export C Code...
```

## 阶段 8：正式做 Release

当你确认工程已经稳定后，执行：

```text
Build -> Release Build (EXE)...
```

建议同时确认：

- Profile 是否正确
- SDK 路径是否正确
- 是否需要 zip 包

## 阶段 9：检查发布结果

发布结束后，至少检查三项：

1. `dist/` 是否完整
2. `release-manifest.json` 是否存在
3. `Release History` 里是否能看到这次记录

## 阶段 10：保留可追溯信息

如果这是正式交付，建议把下面这些一起留档：

- build id
- SDK revision
- manifest
- log
- package

## 一句话总结

最稳的交付顺序是：

先把页面和资源闭环做小，再做 EXE 验证，最后做 Release，不要把 Release 当日常调试入口。
