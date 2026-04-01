# EmbeddedGUI Designer — UI 视觉与交互重构推进计划（VNext）

> **目标**：解决“页面丑、图标丑、交互重、渲染冗余、发布流程不聚焦”的核心问题，形成可落地、可验收、可分阶段推进的执行方案。  
> **方向**：默认走 **EXE 编译发布**，Python 仅作为兜底调试路径；清理 V2 遗留，聚焦单一主路径体验。

---

## 1. 本次重构的明确结论（先定原则）

1. **视觉层面**
   - 当前 UI 观感不达标，需整体提升为“轻量、克制、统一”。
   - **图标体系统一为 Material Symbols（字体图标）**，不再混用多套风格。

2. **交互层面**
   - 当前“widget 存在感过重”，需要降噪：减少无意义面板、描边、标签和重复控件。
   - 优先保证“编辑主路径”流畅（选中 → 修改属性 → 预览/编译）。

3. **渲染层面**
   - 去除冗余刷新与重复渲染；建立“按需刷新 + 脏区触发”机制。

4. **发布与运行策略**
   - **默认编译 EXE**（主推荐路径）。
   - Python 运行仅保留为“失败兜底/开发调试”路径，不作为主入口。

5. **版本治理**
   - **V2 相关功能/入口/文案/分支全部清理**，避免双轨维护成本。

---

## 2. 改造范围（Scope）

### 2.1 必做（P0）
- 全局图标替换为 Material Symbols。
- 主界面视觉层级重做：顶部工具栏、左侧导航、中央工作区、右侧属性区、底部信息区。
- 交互降重：减少 widget 视觉重量与结构重量。
- 渲染链路梳理并削减冗余刷新。
- 构建路径改为“默认 EXE，Python 兜底”。
- V2 清理（代码、配置、入口、文档、测试）。

### 2.2 应做（P1）
- 关键流程的微交互优化（加载、空状态、错误提示、成功反馈）。
- 用户偏好持久化（布局、最近操作、常用面板显示状态）。

### 2.3 暂不做（P2）
- 大规模动画系统。
- 全量历史页面一次性重绘。
- 跨平台像素级一致性。

---

## 3. 诊断问题清单（现阶段共识）

1. **视觉问题**
   - 图标风格混乱、辨识度不一致。
   - 组件描边/阴影/块感过强，页面显“重”“挤”“乱”。
   - 字号层级不清，信息主次不明显。

2. **交互问题**
   - 同一动作入口分散（例如状态、构建、诊断信息分散在多个区域）。
   - 编辑/属性调整路径存在多余跳转和重复操作。

3. **性能与渲染问题**
   - 局部变更触发整块刷新，存在过度渲染。
   - 面板切换、列表更新可能存在重复绘制。

4. **工程治理问题**
   - V2 遗留导致分支逻辑复杂。
   - 发布路径不收敛（EXE/Python 权重不明确）。

---

## 4. 目标体验（重构完成后）

- 首屏观感：简洁、清晰、轻量，不再“工具堆叠感”。
- 图标观感：统一 Material Symbols，语义一致，尺寸/描边一致。
- 操作效率：高频动作一步可达；低频功能收纳但可发现。
- 渲染表现：响应快、切换稳、无明显闪烁和冗余重绘。
- 发布体验：一键默认 EXE，失败时自动提示 Python 兜底方案。
- 代码状态：V2 删除后结构更清晰，维护成本下降。

---

## 5. 分阶段执行计划（可直接排期）

## 阶段 A：视觉统一与图标替换（1~2 周）

### A1. 建立视觉 Token（颜色/字号/间距/圆角/阴影）
- 统一 token 来源，禁止散落硬编码。
- 清理历史样式冲突点。

### A2. Material Symbols 落地
- 引入字体资源（Outlined/Rounded 选定一种主风格）。
- 建立图标映射表（功能语义 -> icon name）。
- 统一 icon 尺寸、基线、按钮内边距与状态色。

### A3. 主框架降重
- 左/右栏背景与边界弱化，减少重边框。
- 顶部工具栏分组并降低视觉噪声。
- 列表与属性区统一密度与间距。

**阶段验收**
- 图标统一率 ≥ 95%。
- 主界面不存在混搭图标。
- 视觉回归截图通过评审（首页、编辑页、属性页、构建页）。

---

## 阶段 B：交互降重与流程重排（1~2 周）

### B1. “widget 过重”专项
- 删除非必要卡片化包装。
- 将低频信息折叠/二级展开。
- 合并重复按钮与重复状态提示。

### B2. 高频路径优化
- 主路径：选中组件 -> 编辑属性 -> 实时反馈（减少跳转）。
- 状态信息单一主入口（其余仅作为跳转锚点）。

### B3. 微交互优化
- 空状态、加载中、失败重试、成功确认文案统一。
- 减少打断式弹窗，更多使用就地反馈。

**阶段验收**
- 核心任务操作步数下降（对比基线减少 20%+）。
- 用户主观反馈：页面“更轻”“更顺”。

---

## 阶段 C：渲染优化（1 周）

### C1. 渲染链路梳理
- 标记刷新触发点（属性变更、树更新、面板切换、预览刷新）。
- 区分“必须全量刷新”与“局部刷新”。

### C2. 去冗余策略
- 去除重复信号触发与重复 repaint。
- 引入防抖/节流（适用于快速连续输入场景）。
- 列表/树控件采用增量更新策略。

### C3. 监控与回归
- 增加基本性能观测点（切换耗时、刷新次数）。
- 对关键页面做对比验证。

**阶段验收**
- 关键交互帧时间下降，卡顿与闪烁明显减少。
- 高频操作不出现可感知的重复渲染。

---

## 阶段 D：发布路径收敛 + V2 清理（1 周）

### D1. 默认 EXE 发布
- 构建入口默认指向 EXE 编译。
- UI 文案、按钮顺序、帮助提示均以 EXE 为主。

### D2. Python 兜底机制
- 编译失败后提供清晰 fallback 提示：可切 Python 运行调试。
- 兜底路径仅在失败或开发模式暴露。

### D3. V2 清理
- 删除 V2 代码目录、功能开关、菜单入口、文档描述。
- 清理测试与 CI 中 V2 相关项。
- 执行死代码扫描与引用检查，确保无残留引用。

**阶段验收**
- 用户默认流程只看到 EXE 路径。
- 仓库内无 V2 可见入口与主路径依赖。

---

## 6. 任务拆分（任务 ID）

| ID | 任务 | 优先级 | 依赖 |
|---|---|---|---|
| UX-001 | 建立全局视觉 token 并收敛样式入口 | P0 | - |
| UX-002 | 引入 Material Symbols 字体与渲染工具 | P0 | UX-001 |
| UX-003 | 完成图标语义映射表并替换主界面图标 | P0 | UX-002 |
| UX-004 | 顶栏/侧栏/属性栏降重改造 | P0 | UX-001 |
| UX-005 | widget 降重（去冗余容器、减标签噪音） | P0 | UX-004 |
| UX-006 | 主路径交互重排（编辑-反馈闭环） | P0 | UX-005 |
| PERF-001 | 梳理渲染触发链路并定位冗余点 | P0 | - |
| PERF-002 | 实施局部刷新与防抖节流 | P0 | PERF-001 |
| PERF-003 | 建立性能回归样例与阈值 | P1 | PERF-002 |
| REL-001 | 默认 EXE 构建入口与文案改造 | P0 | - |
| REL-002 | Python fallback 机制与提示策略 | P0 | REL-001 |
| CLEAN-001 | V2 代码与入口清理 | P0 | - |
| CLEAN-002 | V2 文档/测试/配置清理 | P0 | CLEAN-001 |
| CLEAN-003 | 全量引用检查与回归 | P0 | CLEAN-002 |

---

## 7. 验收标准（DoD）

1. **视觉**
   - 主页面视觉一致，图标风格统一为 Material。
   - 无明显“重组件堆叠感”。

2. **交互**
   - 核心链路更短、反馈更快、入口更明确。
   - 重复入口与重复提示显著减少。

3. **性能**
   - 关键页面冗余渲染下降。
   - 高频操作无明显卡顿。

4. **发布与治理**
   - 默认 EXE，Python 仅兜底。
   - V2 清理完成，无残留主路径引用。

---

## 8. 风险与应对

- **风险：一次性改动过大引发回归**  
  应对：按阶段提交，小步快跑，每阶段都可回滚。

- **风险：图标替换影响布局**  
  应对：先替换高频区域，再全量替换；保留映射兼容层一周。

- **风险：渲染优化引入状态不同步**  
  应对：先加观测点，再做优化；每次改动配套回归用例。

- **风险：V2 删除影响隐性依赖**  
  应对：删除前做引用清单，删除后执行专项回归。

---

## 9. 里程碑建议（供排期）

- **M1（第 1 周末）**：图标体系 + 基础视觉统一完成（UX-001~004）。
- **M2（第 2 周末）**：交互降重与主路径优化完成（UX-005~006）。
- **M3（第 3 周中）**：渲染优化完成并通过性能回归（PERF-001~003）。
- **M4（第 3 周末）**：默认 EXE + V2 清理完成（REL-001~002, CLEAN-001~003）。

---

## 10. 执行跟踪区（每次推进后更新）

```yaml
last_update: 2026-04-01
phase: phase_b_in_progress
in_progress:
  - UX-005
  - UX-006
  - PERF-002
completed:
  - CLEAN-001
  - CLEAN-002
  - CLEAN-003
  - PERF-001
  - UX-001
  - UX-002
  - UX-003
  - UX-004
  - REL-001
  - REL-002
blocked: []
next_recommended:
  - UX-005
notes:
  - `UX-005` updated: status center now hides the diagnostic summary line while diagnostics are clear, only surfacing that extra copy when errors, warnings, or info items exist.
  - `UX-005` updated: status center runtime detail copy now stays hidden while runtime is clear, only expanding to show text when there is an actual runtime issue.
  - `UX-005` updated: status center repeat action control now uses a plain button for the single-action state, only showing the split menu chrome when older history exists.
  - `UX-005` updated: status center now hides the last-action label for the single-action state, leaving only the repeat button until there is richer history to summarize.
  - `UX-005` updated: widget browser now hides the insert-target chip while it is still on the default page root, reducing header noise until a more specific target is active.
  - `PERF-002` updated: widget browser now ignores redundant clicks on the already-active sort and complexity organizers, avoiding no-op result rebuilds.
  - `UX-005` updated: mixed-state callback code buttons in the property panel now stay hidden until the selection shares one callback target, reducing disabled inspector chrome.
  - `UX-005` updated: status center first-error / first-warning jump actions now stay hidden until those diagnostics exist, removing two idle disabled buttons.
  - `UX-005` updated: widget browser empty-state hint copy is now contextual, matching the specific active filter state instead of a fixed generic sentence.
  - `UX-005` updated: property panel search now hides until there is an active selection, reducing idle inspector chrome.
  - `UX-005` updated: property panel search filters now reapply after inspector rebuilds, keeping the filtered view stable while changing the current selection.
  - `UX-005` updated: status center now hides the last-action repeat row until there is actionable history, removing idle-state repeat chrome.
  - `UX-005` updated: widget browser empty-state actions are now contextual, showing only the reset controls relevant to the active filters instead of a fixed full button row.
  - `PERF-002` updated: widget browser explicit reset actions now bypass the search debounce and collapse multi-control resets into a single immediate refresh.
  - `PERF-002` updated: clearing widget browser tags now relies on the normal refresh path, avoiding a second immediate metadata sync on the same click.
  - `PERF-002` started: widget browser search input now uses a short debounce before rebuilding results, while explicit refresh paths still apply immediately.
  - `UX-005` updated: widget browser tag reset now appears only when filters are active, removing an idle-state control from the bottom filter rail.
  - `UX-005` updated: status center suggested-action chrome now relies on the action button and guidance copy, with the redundant visible prefix label removed from the layout.
  - `UX-005` updated: status center metrics/actions outer wrappers were flattened, and metric cards now keep their border emphasis for hover/focus instead of the resting state.
  - `UX-005` updated: status center now hides the recent-actions summary until there is older history to replay, and keeps the Quick Actions title quiet for the single-action state.
  - `UX-005` updated: widget browser header stats were collapsed from three separate count labels into one compact summary line to cut top-of-panel noise.
  - `UX-006` expanded: widget browser insert/reveal and diagnostics target navigation also auto-focus the Properties inspector after selecting a widget.
  - `UX-006` started: tree/preview selection entry points now auto-focus the Properties inspector to shorten the select -> edit loop, with targeted MainWindow file-flow coverage.
  - 已清理 V2 预览代码与测试残留：删除 `renderer/v2_renderer_qml.py` 与 `tests/renderer/test_v2_renderer.py`。
  - 已在 iconography 中增加 Material Symbols 映射与字体渲染回退机制。
  - Build 菜单与失败提示已改为 EXE 优先 + Python fallback 明确提示。
  - 已完成主题 token 收敛首批调整（左栏/命令栏/导航与状态芯片降重）。
  - 已完成主界面 Build 流程相关菜单图标映射与替换联调。
  - 已完成主壳层间距降重一批（workspace/editor/inspector/bottom 区域 spacing 与 margin 下调）。
  - 已完成 PERF-001 首批治理：canvas move/resize 改为拖拽中轻量刷新、拖拽结束后统一补做 overlay/XML/资源面板同步。
  - 已为 PropertyPanel 几何同步与 MainWindow 拖拽刷新节流补充定向回归用例。
  - 已完成 CLEAN-003：删除 `settings/preview_settings.py`、对应测试与旧版 V1/V2 扩展计划文档，主代码/测试中不再保留 V2 入口引用。
  - 已执行残留引用扫描与预览相关回归：`test_preview_workspace.py`、`test_main_window_file_flow.py -k canvas_move|preview_failure|preview_engine_invalid_name` 通过。
  - UX-005 首批已落地到 PropertyPanel：多选摘要改为轻量 header，Interaction Notes 改为就地提示条，多选分组统一到 collapsible inspector 组。
  - 已补充并通过 PropertyPanel 多选摘要/提示条/混合态定向回归。
```

---

## 11. 下一步执行建议（马上可做）

1. 先做 **UX-001 + UX-002**（当天可以开始）。
2. 同步建立 icon 映射表，直接推动 **UX-003**。
3. 并行启动 **REL-001**（默认 EXE 路径文案与入口）。
4. 一旦视觉基线稳定，立即进入 **PERF-001** 进行渲染触发点梳理。

> 本文档即后续迭代的唯一推进基线。
