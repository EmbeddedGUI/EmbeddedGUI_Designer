# FAQ

这一篇只回答高频问题，尽量短。

## 1. Designer 和 `sdk/EmbeddedGUI` 是什么关系

Designer 是上层桌面工具，`sdk/EmbeddedGUI` 是底层 SDK 和运行时。

## 2. 不指定 `--sdk-root` 能不能用

能，但不建议。最稳妥的启动方式仍然是：

```bash
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

## 3. 为什么我能编辑页面，但不能跑 EXE 预览

通常是 Python 侧可用，但 SDK 构建链路不可用。

## 4. `Build EXE && Run` 和 `Release Build` 有什么区别

- `Build EXE && Run`：偏本地验证
- `Release Build`：偏正式产物输出和记录归档

## 5. 改完资源后为什么界面没变化

大概率还缺一步：

- `Build -> Generate Resources`

## 6. 哪些文件可以手改，哪些不建议手改

原则上：

- 源信息可以改
- 纯生成文件不建议作为主编辑入口

尤其不要长期手改 `*_layout.c`。

## 7. 为什么 Code 模式改了 XML，但界面没更新

优先怀疑 XML 解析失败，或者你改的是会被结构/布局关系覆盖的字段。

## 8. Release 产物在哪

通常在：

```text
output/ui_designer_release/<profile>/<build_id>/
```

## 9. Release History 为什么是空的

通常因为这个工程还没有真正做过一次 Release Build，或者当前工程指向了不同的输出根目录。

## 10. 怎么最快确认仓库状态有没有问题

图形界面：

- `Build -> Repository Health...`

命令行：

```bash
python scripts/ui_designer/repo_doctor.py --summary
```

## 11. 第一次最适合打开哪个工程

优先建议：

- `examples/DesignerSandbox`
- `examples/HelloSimpleDemo`

## 12. 要不要直接在示例工程上做正式项目

不建议。示例工程更适合学习，正式项目最好尽快用自己的目录和命名规范。
