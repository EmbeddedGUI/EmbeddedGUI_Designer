# 工程目录结构

理解工程目录结构，能帮你避免很多“文件改了又被覆盖”的问题。

## 一个典型工程长什么样

以当前仓库的 Designer 工程为例，结构通常类似：

```text
<AppName>/
    <AppName>.egui
    .designer/
        main_page.h
        main_page_layout.c
        uicode.h
        uicode.c
        build_designer.mk
        app_egui_config_designer.h
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
    main_page.c
    main_page_ext.h
    app_egui_config.h
    build.mk
```

## 哪些是源文件

通常把这些看成“你要长期维护”的源信息更合适：

- `<AppName>.egui`
- `.designer/` 之外的根目录用户文件，如 `main_page.c`、`main_page_ext.h`
- `.eguiproject/layout/*.xml`
- `.eguiproject/resources/*`
- `resource/src/app_resource_config.json`

## 哪些是生成结果

下面这些文件通常是从工程状态推导出来的，不应该当成主编辑入口：

- `.designer/{page}.h`
- `.designer/{page}_layout.c`
- `.designer/uicode.h`
- `.designer/uicode.c`
- `.designer/build_designer.mk`
- `.designer/app_egui_config_designer.h`
- `resource/src/.designer/app_resource_config_designer.json`
- 资源生成后的 `resource` 输出文件
- 导出目录里的 C 文件副本

## 页面代码覆盖规则

当前仓库的生成策略可以概括成三句话：

1. `.designer/{page}.h` 和 `.designer/{page}_layout.c` 会反复覆盖。
2. `{page}.c` 和 `{page}_ext.h` 属于用户业务代码，Designer 只在缺失时创建骨架。
3. `build.mk`、`app_egui_config.h`、`resource/src/app_resource_config.json` 是用户覆盖层，Designer 文件走独立 include / overlay。

这意味着：

- 页面布局逻辑不要手改到 `.designer/` 里的生成文件
- 自定义业务逻辑优先放进根目录 `{page}.c`、`{page}_ext.h`
- 不要把“只改生成结果、不改源信息”当成正常工作流

## 资源目录要怎么看

资源相关最常见的是两层：

- `.eguiproject/resources/`：Designer 工程侧资源元数据
- `resource/src/`：工程侧覆盖配置与生成入口
- `resource/src/.designer/`：Designer 自动生成的资源元数据

当你用资源面板工作时，重点看的是资源是否被正确登记，而不是只看磁盘上有没有某个文件。

继续阅读：[工作区总览](09_workspace_overview.md)
