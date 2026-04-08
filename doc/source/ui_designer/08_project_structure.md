# 工程目录结构

理解工程目录结构，能帮你避免很多“文件改了又被覆盖”的问题。

## 一个典型工程长什么样

以当前仓库的 Designer 工程为例，结构通常类似：

```text
<AppName>/
    <AppName>.egui
    .eguiproject/
        layout/
            main_page.xml
        resources/
            resources.xml
            app_resource_config.json
            images/
    resource/
        src/
            resources.xml
            app_resource_config.json
    main_page_layout.c
    main_page.h
    main_page.c
    uicode.c
    uicode.h
    app_egui_config.h
    build.mk
```

## 哪些是源文件

通常把这些看成“你要长期维护”的源信息更合适：

- `<AppName>.egui`
- `.eguiproject/layout/*.xml`
- `.eguiproject/resources/*`
- `resource/src/*`
- `main_page.c`、`main_page.h` 里的用户代码区

## 哪些是生成结果

下面这些文件通常是从工程状态推导出来的，不应该当成主编辑入口：

- `{page}_layout.c`
- 资源生成后的 `resource` 输出文件
- 导出目录里的 C 文件副本

## 页面代码覆盖规则

当前仓库的生成策略可以概括成三句话：

1. `{page}_layout.c` 会反复覆盖。
2. `{page}.h` 会更新，但会保留 `USER CODE` 区域。
3. `{page}.c` 一般创建一次后不再强制覆盖。

这意味着：

- 页面布局逻辑不要手改到 `*_layout.c`
- 自定义业务逻辑优先放进 `USER CODE`
- 不要把“只改生成结果、不改源信息”当成正常工作流

## 资源目录要怎么看

资源相关最常见的是两层：

- `.eguiproject/resources/`：Designer 工程侧资源元数据
- `resource/src/`：资源生成输入或同步后的工程侧目录

当你用资源面板工作时，重点看的是资源是否被正确登记，而不是只看磁盘上有没有某个文件。

继续阅读：[工作区总览](09_workspace_overview.md)
