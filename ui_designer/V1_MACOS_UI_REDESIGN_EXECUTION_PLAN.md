# UI Designer V1 macOS 风格重构执行文档（AI 跟进版）

## 0. 文档目的

本文件用于指导后续 AI/开发者持续推进 `ui_designer` 的 macOS 风格重构，重点解决：

- 界面“丑、乱、信息密度失衡”
- 功能变多后缺乏视觉层级
- 面板交互不统一、状态反馈不一致

目标是：**可分阶段执行、可追踪、可回滚、可由 AI 按任务 ID 续做**。

---

## 1. 目标与范围

## 1.1 V1 目标（必须完成）

1. 建立统一 macOS 风格设计令牌（颜色/圆角/间距/阴影/字体层级）
2. 重排主工作区视觉层级（左侧栏/中间画布/右侧检查器/顶部工具栏）
3. 统一高频控件视觉与交互状态（按钮/输入框/Tab/列表项/分组）
4. 完成属性面板分组视觉优化（可折叠、分组标题、字段密度）
5. 增加轻量动画与状态反馈（hover/active/focus/selected/disabled）

## 1.2 V1 不做（避免失控）

- 全量重写业务逻辑
- 引入大型主题框架替换现有机制
- 动效系统全面重构
- 全部低频页面一次性改完

---

## 2. 设计原则（macOS 风）

1. **留白优先**：统一 8/12/16 间距节奏，去掉无意义挤压。
2. **弱边框分层**：少用硬边框，多用中性背景层区分区域。
3. **圆角一致**：面板、控件、浮层圆角统一。
4. **低饱和中性色**：强调色只用于关键操作与选中态。
5. **状态明确**：hover/active/focus/selected/disabled 可感知。
6. **信息层级清晰**：标题 > 分组标题 > 标签 > 辅助文本。

---

## 3. 影响文件（首批）

- `ui_designer/ui/theme.py`（主题令牌与样式入口）
- `ui_designer/ui/main_window.py`（整体布局与容器样式）
- `ui_designer/ui/panels/*`（侧栏/检查器/底部面板）
- `ui_designer/ui/widgets/*`（复用控件样式）
- `ui_designer/model/config.py`（主题偏好持久化，若需要）

---

## 4. 任务拆分（AI 可执行）

> 状态：`todo | doing | blocked | done`

```yaml
- id: MACOS-S1-001
  title: 盘点当前样式入口与硬编码颜色
  status: todo
  deps: []
  output:
    - 样式来源清单（QSS/代码内 setStyleSheet/常量）
    - 硬编码颜色与半径清单
  acceptance:
    - 明确统一收口点（theme.py 或 token 模块）

- id: MACOS-S1-002
  title: 建立 macOS 主题令牌（色彩/圆角/间距/阴影/字体层级）
  status: todo
  deps: [MACOS-S1-001]
  output:
    - 主题 token 常量
    - 亮色模式下基础调色板
  acceptance:
    - 高优先级控件不再直接依赖硬编码颜色

- id: MACOS-S1-003
  title: 统一基础控件样式（按钮/输入框/下拉/Tab）
  status: todo
  deps: [MACOS-S1-002]
  output:
    - 可复用基础控件样式规则
  acceptance:
    - 同类控件视觉一致，focus/hover 状态可见

- id: MACOS-S2-001
  title: 主窗口三栏与工具栏视觉重整
  status: todo
  deps: [MACOS-S1-003]
  output:
    - 顶部工具栏、左右面板、画布容器分层优化
  acceptance:
    - 首屏视觉层级清晰，边界与留白统一

- id: MACOS-S2-002
  title: 左侧 Library/Tree 列表项样式统一
  status: todo
  deps: [MACOS-S2-001]
  output:
    - 列表项高度、图标对齐、选中态/悬停态统一
  acceptance:
    - 长列表阅读与点击辨识度提升

- id: MACOS-S2-003
  title: 右侧 Inspector 分组视觉优化
  status: todo
  deps: [MACOS-S2-001]
  output:
    - 分组标题层级、折叠区域、字段间距规范
  acceptance:
    - 属性编辑区不再拥挤，分组扫描成本下降

- id: MACOS-S3-001
  title: 状态反馈与微动效统一
  status: todo
  deps: [MACOS-S2-002, MACOS-S2-003]
  output:
    - hover/pressed/focus/selected/disabled 状态规则
    - 轻量过渡时长规范（如 120ms/180ms）
  acceptance:
    - 交互反馈一致，不突兀、不延迟

- id: MACOS-S3-002
  title: 主题配置与回退策略接入
  status: todo
  deps: [MACOS-S3-001]
  output:
    - 配置项开关（例如 MACOS_THEME_ENABLED）
    - 一键回退到旧主题能力
  acceptance:
    - 出现兼容问题可快速回退

- id: MACOS-S3-003
  title: 全链路验收与文档回填
  status: todo
  deps: [MACOS-S3-002]
  output:
    - 验收记录
    - 本文档状态区更新
  acceptance:
    - AI 可基于文档继续推进，无上下文丢失
```

---

## 5. 每次 AI 执行 SOP（固定模板）

```text
请按 V1_MACOS_UI_REDESIGN_EXECUTION_PLAN.md 执行：
1) 选择所有 deps 已满足且 status=todo 的任务。
2) 每次只做 1~2 个任务，完成后更新状态为 done。
3) 优先最小改动；避免改动无关业务逻辑。
4) 改动后做最小可行验证（启动/界面操作/关键路径）。
5) 输出：
   - 完成任务ID
   - 修改文件列表
   - 验证结果
   - 风险与阻塞
   - 下一建议任务ID
```

---

## 6. 验收标准（Definition of Done）

1. 样式一致：同类控件视觉/状态统一。
2. 结构清晰：主界面阅读路径明确（左导航-中画布-右属性）。
3. 可回退：主题切换异常不影响编辑功能。
4. 可维护：样式令牌集中管理，减少散落硬编码。
5. 可续做：文档状态区保持最新。

---

## 7. 风险与应对

- 风险：QSS 覆盖顺序冲突导致局部样式失效  
  应对：统一样式注入入口，减少局部 setStyleSheet。

- 风险：改样式影响控件尺寸与布局抖动  
  应对：先在高频页面灰度验证，再扩展到全局。

- 风险：现有用户习惯变化过大  
  应对：提供主题开关与回退策略。

---

## 8. 回滚策略

- 通过 `MACOS_THEME_ENABLED` 快速关闭新主题。
- 样式改动按任务粒度提交，支持逐步回滚。
- 保持旧主题实现直到 V1 验收完成。

---

## 9. 执行状态跟踪区（持续更新）

```yaml
last_update: 2026-03-30
current_phase: S1
completed: []
in_progress: []
blocked: []
next_recommended:
  - MACOS-S1-001
notes:
  - 初始化 macOS 风格重构计划文档。
  - 下一步先盘点样式入口与硬编码颜色，再落地主题 token。
```

---

## 10. 建议起步顺序（马上可做）

1. `MACOS-S1-001`：盘点主题入口与硬编码样式
2. `MACOS-S1-002`：在 `theme.py` 建立统一 token
3. `MACOS-S1-003`：先统一按钮/输入框/Tab 三类高频控件
