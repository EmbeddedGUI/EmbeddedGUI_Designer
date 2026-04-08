# 文档构建说明

本项目的 Sphinx 文档环境位于 `doc/` 目录。

当前文档主题是：

- `UI Designer` 使用手册

源码主入口位于：

- `doc/source/index.rst`
- `doc/source/ui_designer/index.rst`

## 安装依赖

```bash
python -m pip install -r doc/requirements.txt
```

## 构建 HTML

推荐命令：

```bash
python -m sphinx -b html doc/source doc/build/html
```

Windows 也可以用：

```bash
doc\make.bat html
```

## 输出目录

构建结果默认位于：

```text
doc/build/html/
```

主入口页面通常是：

```text
doc/build/html/index.html
```
