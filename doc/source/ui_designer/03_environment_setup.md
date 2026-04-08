# 环境准备

要让 Designer 工作稳定，至少要同时满足 Python、依赖包和 SDK 三个条件。

## 基础要求

建议先确认下面几项：

- Python 可用
- `PyQt5` 已安装
- 仓库子模块已初始化
- `sdk/EmbeddedGUI` 目录存在并完整

## 安装依赖

在仓库根目录执行：

```bash
git submodule update --init --recursive
python -m pip install -r ui_designer/requirements-desktop.txt
```

如果你只想快速确认环境，可先检查：

```bash
python --version
python -c "import PyQt5; print('PyQt5 OK')"
```

## SDK 必须满足什么条件

Designer 会把一个目录视为有效 SDK 根目录，前提是该目录至少包含：

- `Makefile`
- `src/`
- `porting/designer/`

本仓库最推荐的 SDK 来源就是：

```text
sdk/EmbeddedGUI
```

## 什么时候需要 C/Make 工具链

分两种情况：

- 只做页面编辑、资源绑定、Python 预览时，重点是 Python 环境。
- 要做 EXE 预览、Rebuild、Release Build 时，需要 SDK 构建链路可用。

换句话说，Designer 能在部分场景下降级工作，但完整体验仍然依赖 SDK 的构建能力。

## 建议的环境自检命令

仓库自带一个很实用的健康检查脚本：

```bash
python scripts/ui_designer/repo_doctor.py --summary
```

如果你要更严格地看问题：

```bash
python scripts/ui_designer/repo_doctor.py --strict
```

## 常见准备错误

最常见的环境问题通常是：

- 子模块没拉下来，导致 `sdk/EmbeddedGUI` 不完整。
- Python 依赖装了，但 `PyQt5` 缺失或装到别的解释器里。
- SDK 路径存在，但不是有效的 SDK 根目录。
- 构建链没装好，导致只能用 Python 预览，不能跑 EXE 预览或 Release。

继续阅读：[SDK 绑定与查找规则](04_sdk_resolution.md)
