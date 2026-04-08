# 常见问题排查

这一篇按“现象 -> 优先检查项”的方式来写，便于直接查问题。

## 软件启动不了

优先检查：

1. `python --version`
2. `PyQt5` 是否可导入
3. 依赖是否用同一个 Python 安装
4. 是否在仓库根目录启动

推荐先执行：

```bash
python -c "import PyQt5; print('PyQt5 OK')"
```

## 欢迎页提示 SDK 无效

优先检查：

1. `sdk/EmbeddedGUI` 是否存在
2. 子模块是否完整
3. 是否错误地指向了别的目录
4. 该目录下是否有 `Makefile`、`src/`、`porting/designer/`

## 能编辑，但 Build EXE 失败

这通常说明：

- Python 侧能力是好的
- SDK 构建链路有问题

建议顺序：

1. 先 `Rebuild EGUI Project`
2. 再看 `Diagnostics` 和 `Debug Output`
3. 再看 `Repository Health`

## 资源加进去了，但控件里看不到

优先检查：

1. 资源是不是通过资源面板登记过
2. 控件是否真的绑定了这个资源
3. 是否执行了 `Generate Resources`
4. 当前页面或控件是不是还在用旧引用

## 改了 XML，但界面没更新

优先检查：

1. XML 是否存在语法错误
2. 当前是不是在错误页面上改
3. 改动是否属于被布局容器覆盖的字段

## Release History 是空的

通常意味着：

- 这个工程还没有真正做过 Release Build
- 输出根目录变了
- `history.json` 不在当前工程默认位置

先做一次：

```text
Build -> Release Build (EXE)...
```

## 不知道问题到底在工程、仓库还是 SDK

不要猜，直接看：

1. `Diagnostics`
2. `Debug Output`
3. `Build -> Repository Health...`
4. `python scripts/ui_designer/repo_doctor.py --summary`

继续阅读：[推荐使用习惯](25_best_practices.md)
