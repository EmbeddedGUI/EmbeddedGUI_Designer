# IDE 风格视觉改版设计（EmbeddedGUI Designer）

- **状态**: Implemented
- **日期**: 2026-04-21
- **所有者**: UI/UX
- **相关**: `ref/UI Editor Design/`（Figma 源码）、[ui_designer/ui/theme.py](../../../ui_designer/ui/theme.py)、[ui_designer/ui/typography.py](../../../ui_designer/ui/typography.py)、[ui_designer/ui/iconography.py](../../../ui_designer/ui/iconography.py)

---

## 1. 背景与目标

### 现状

- `EmbeddedGUI Designer` 是 PyQt5 桌面应用，功能完备但观感"偏糊"：蓝黑底色、控件偏大、圆角偏圆、图标风格不统一（自绘 + qtawesome + qfluentwidgets 混杂）。
- 设计部门已在 Figma 里出了一套 Android Studio 风格的参考方案，源码在 `ref/UI Editor Design/`（React + Tailwind，Tailwind 默认 zinc 色阶 + `blue-500` 强调色）。

### 目标

在 **不改任何面板的位置、Dock 结构、tab 组织、交互流程** 的前提下，让 Designer 的视觉风格（配色 / 字号 / 密度 / 圆角 / 激活态 / 图标）严格向参考对齐，达到 **与参考截图肉眼一致** 的程度。

### 非目标

- ❌ 不调整主窗口 Dock 布局
- ❌ 不改左侧 `Pages/Tree/Add/Assets` 四 tab 合并为双 tab
- ❌ 不改右侧属性/动画/页面 tab 结构
- ❌ 不改浅色主题（`_TOKENS["light"]` 保持现状）
- ❌ 本轮不改任何业务逻辑 / 功能

---

## 2. 决策摘要（已与负责人对齐）

| 维度 | 决策 |
|---|---|
| 范围 | A. 纯视觉改版 |
| 配色方向 | A. 完全对齐参考（Tailwind zinc + blue-500） |
| 主题覆盖 | D2. 仅 dark，不动 light |
| 字号/密度 | A. 严格紧凑 IDE 密度 |
| 细节风格 | C. 激进到底，含 lucide 图标替换 |
| 选中态色 | S1. RGBA 动态透明度 |
| 交付路径 | 路径 3：阶段 1（色板 + 字号 + 圆角 + 激活态） + 阶段 2（lucide 图标） |

---

## 3. Token 新旧对照（`theme.py` → `_TOKENS["dark"]`）

### 3.1 色彩 token

| Key | 旧值 | 新值 | 说明 |
|---|---|---|---|
| `bg` | `#12161B` | `#09090B` | `zinc-950` 窗口底 |
| `shell_bg` | `#12161B` | `#09090B` | 同 `bg` |
| `sidebar_bg` | `#161B21` | `#27272A` | `zinc-800` 侧栏 |
| `panel` | `#1C232C` | `#18181B` | `zinc-900` 面板 |
| `panel_alt` | `#202833` | `#27272A` | `zinc-800` 替代面板 |
| `panel_soft` | `#283241` | `#3F3F46` | `zinc-700` 柔面板 |
| `panel_raised` | `#242E3A` | `#27272A` | 对齐 `panel_alt` |
| `surface` | `#2D3947` | `#3F3F46` | `zinc-700` |
| `surface_hover` | `#364453` | `#52525B` | `zinc-600` |
| `surface_pressed` | `#3F4E60` | `#71717A` | `zinc-500` |
| `canvas_bg` | `#101418` | `#09090B` | 与 `bg` 同 |
| `canvas_stage` | `#0D1116` | `#09090B` | 同 `bg` |
| `border` | `#344150` | `#3F3F46` | `zinc-700` |
| `border_strong` | `#425164` | `#52525B` | `zinc-600` |
| `focus_ring` | `#4B9DFF` | `#3B82F6` | `blue-500` |
| `text` | `#F3F6FA` | `#D4D4D8` | `zinc-300`（参考 body 文字） |
| `text_muted` | `#BCC7D4` | `#A1A1AA` | `zinc-400` |
| `text_soft` | `#93A1B2` | `#71717A` | `zinc-500` |
| `accent` | `#4B9DFF` | `#3B82F6` | `blue-500` |
| `accent_hover` | `#78B5FF` | `#60A5FA` | `blue-400` |
| `accent_soft` | `#163451` | `rgba(59,130,246,0.15)` | 动态透明（选中态用） |
| `danger` | `#FF6B5F` | `#EF4444` | `red-500` |
| `success` | `#46C98B` | `#22C55E` | `green-500` |
| `warning` | `#FFB84D` | `#EAB308` | `yellow-500` |
| `selection` | `#2B5F98` | `rgba(59,130,246,0.40)` | **S1 方案**，半透明蓝 |
| `selection_soft` | `#1B2E46` | `rgba(59,130,246,0.15)` | hover/弱选中 |

> ⚠️ RGBA 值在 QSS 里写成 `rgba(59, 130, 246, 0.40)`；在需要 hex 的 API 里保留 fallback 常量 `#1E3A5F` / `#1E2A45`。

### 3.2 字号 token（全部 px）

| Key | 旧值 | 新值 | 对应参考类名 |
|---|---|---|---|
| `fs_display` | 20 | 18 | - |
| `fs_h1` | 14 | 13 | MenuBar `text-[13px]` |
| `fs_h2` | 13 | 12 | 分区标题（semibold） |
| `fs_panel_title` | 13 | 12 | panel header |
| `fs_body` | 13 | 12 | 属性行、树条目（`text-xs`） |
| `fs_body_sm` | 12 | 11 | toolbar 小按钮 |
| `fs_caption` | 12 | 10 | 类别小标题 `text-[10px]` uppercase |
| `fs_micro` | 11 | 10 | 同上 |

### 3.3 间距与圆角

| Key | 旧值 | 新值 | 说明 |
|---|---|---|---|
| `pad_btn_v` | 3 | 2 | 按钮紧凑 |
| `pad_btn_h` | 10 | 8 | |
| `pad_input_v` | 3 | 2 | 输入框紧凑 |
| `pad_input_h` | 10 | 6 | |
| `h_tab_min` | 24 | 24 | 不变 |
| `r_sm` | 4 | 4 | 保留（按钮/输入） |
| `r_md` | 6 | 4 | 下调 |
| `r_lg` | 8 | 4 | 下调 |
| `r_xl` | 8 | 6 | 仅对话框 / 悬浮卡用 |
| `r_2xl` | 12 | 8 | |
| `r_3xl` | 14 | 8 | |

> `space_*` / `icon_*` 系列保持不变。

### 3.4 图标尺寸（保持）

- `icon_xs=14, icon_sm=16, icon_md=18, icon_lg=20` 与参考一致，不改。

---

## 4. QSS 模板改动清单（`theme.py`）

阶段 1 需要把下列 QSS 常量中硬编码的圆角 `0px` / `px` 字号值重新校准：

| 常量 | 改动 |
|---|---|
| `_FLUENT_BUTTON_RADIUS_QSS` | `border-radius: 0px` → `4px`；`font-size: 13px` → `12px` |
| `_FLUENT_PROPERTY_PANEL_BUTTON_QSS` | `border-radius: 0px` → `4px`；`min-height: 22px` → `22px`（不变） |
| `_FLUENT_LINE_EDIT_RADIUS_QSS` | `border-radius: 0px` → `4px`；`font-size: 13px` → `12px`；`padding: 0 8px` → `0 6px` |
| `_FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS` | `border-radius: 0px` → `4px` |
| `_FLUENT_COMBO_BOX_RADIUS_QSS` | 同上字号/圆角 |
| `_FLUENT_SPIN_BOX_RADIUS_QSS` | 同上 |

`_PROPERTY_PANEL_SPIN_BUTTON_WIDTH/HEIGHT` 保持 `20x20`（与参考 tab 切换按钮尺寸一致）。

额外需新增的 QSS 片段（加入 `_build_global_stylesheet` 输出，如尚不存在）：

1. **Tab 激活态 = 顶部 2px 蓝条**
   ```qss
   QTabBar::tab:selected {
       border-top: 2px solid {accent};
       background: {panel};
       color: {text};
   }
   QTabBar::tab {
       border-top: 2px solid transparent;
       background: {sidebar_bg};
       color: {text_soft};
       padding: 4px 12px;
   }
   ```
2. **Tree/List 选中行 = 半透明蓝 + 亮蓝文字**
   ```qss
   QTreeView::item:selected, QListView::item:selected {
       background: rgba(59, 130, 246, 0.25);
       color: #BFDBFE;  /* blue-200 */
   }
   ```
3. **hover 态克制**：只加 1 档灰，不改文字色
   ```qss
   QPushButton:hover, QToolButton:hover { background: {surface_hover}; }
   ```

---

## 5. 受影响的文件（阶段 1）

| 文件 | 改动内容 | 预估行数 |
|---|---|---|
| `ui_designer/ui/theme.py` | `_TOKENS["dark"]` 全部替换；QSS 常量字符串微调 | ~80 行 |
| `ui_designer/ui/typography.py` | 无改动（它读 tokens） | 0 |
| `ui_designer/ui/iconography.py` | 阶段 1 不改；阶段 2 重写图标加载层 | 阶段 2 ~150 行 |
| `ui_designer/ui/main_window.py` | 可能有硬编码色值 → grep 替换 | ≤ 20 行 |
| `ui_designer/ui/*panel.py` | 同上；若有就地 QSS `setStyleSheet(...)` 需核查 | ≤ 30 行 |

**强约束**：所有硬编码颜色/字号必须走 `theme_tokens(mode)` 取值。本次改版会 `grep -E '#[0-9A-Fa-f]{6}'` 巡检一轮，发现的绕过都列入工单修正。

---

## 6. 阶段 2：lucide 图标替换

### 资源组织

```
ui_designer/assets/icons/lucide/
    play.svg
    pause.svg
    square.svg
    ...（按需提取 ~60 个）
```

下载方式：从 https://lucide.dev/icons/ 单独下载所需 SVG，或用 `npm i lucide-static` 一次性拉全集后挑选。**不引入 npm 运行时依赖**，只当资源用。

### 图标映射（参考 → 项目语义）

| 参考 lucide 名 | 项目 `iconography.py` 现有 key | 用途 |
|---|---|---|
| `play` | `run` / toolbar-run | Build EXE & Run |
| `square` | `stop` | Stop Exe |
| `bug` | `debug` | Debug |
| `rotate-cw` | `refresh` | Apply Changes |
| `folder-tree` | `project` | Pages/Project |
| `component` | `palette` | Widget browser |
| `search` | `search` | 搜索栏 |
| `type` | `widget:text` / `widget:label` | TextView |
| `image` | `widget:image` | ImageView |
| `box-select` | `widget:group` | 容器 |
| `columns` | `widget:linearlayout` | LinearLayout |
| `grid-3x3` | `widget:gridlayout` | GridLayout |
| `check-square` | `widget:checkbox` | CheckBox |
| `settings-2` | `widget:switch` / config | Switch |
| `sliders-horizontal` | `widget:slider` | Slider |
| `minus-square` | `widget:button` | Button |
| `list` | `widget:list` | List |
| `crosshair` | `attr_target` | 属性面板定位 |
| `help-circle` | `help` | 帮助 |
| `chevron-up/down` | collapse | 折叠 |
| `terminal` | `debug_output` | Debug Output tab |
| `x` | `close` | 关闭按钮 |
| `plus` / `minus` | `expand`/`collapse` | 组件树 |

> 完整映射表在实施计划阶段补齐（目标覆盖 `_WIDGET_ICON_KEYS` 全部 70+ 键 + toolbar/nav/state 语义键共约 100 项）。

### 加载层改造

`iconography.py` 新增：

```python
def load_lucide_icon(name: str, color: str, size: int = 16) -> QIcon:
    """从 assets/icons/lucide/{name}.svg 加载并按 color 着色返回 QIcon。"""
```

- 用 `QSvgRenderer` 渲染到 `QPixmap`
- 用 `QPainter` + `CompositionMode_SourceIn` 把描边染成目标色
- 按 token 取色：`theme_tokens()["text_soft"]` 作为默认，hover/active 用 `text`/`accent`
- 带 LRU 缓存（`functools.lru_cache`）避免每次重渲

原有自绘/qtawesome 分支保留作为 fallback，确保阶段 2 翻车时能回滚到阶段 1 成果。

---

## 7. 分阶段交付计划

### 阶段 1：色板 + 字号 + 密度 + 圆角 + 激活态（单 PR）

**步骤**

1. 更新 `_TOKENS["dark"]` 全量色板与字号
2. 更新 `_FLUENT_*_QSS` 常量圆角/字号
3. 新增 tab/tree 选中态 QSS 片段，注入 `_build_global_stylesheet`
4. `grep` 巡检硬编码颜色，替换为 `theme_tokens()` 读取
5. 本地启动 `python ui_designer/main.py --sdk-root sdk/EmbeddedGUI` 肉眼对比参考 5 张截图
6. 跑一次 `python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v`
7. 在 PR 描述里贴新旧对比截图

**验收标准**（肉眼）

- [ ] 打开主窗口，窗口底色接近 `#09090B`（纯黑而非蓝黑）
- [ ] 侧栏、面板层级三档灰（`#27272A` / `#18181B` / `#09090B`）清晰
- [ ] 属性行、树条目字号从 13px 降到 12px，caption 到 10px
- [ ] 按钮/输入圆角 4px，视觉上不再"糯"
- [ ] Tab 激活态显示顶部 2px 蓝条
- [ ] Tree/List 选中行呈半透明蓝 + 亮蓝文字
- [ ] 浅色主题打开没有视觉回归（验证 D2 决策）

### 阶段 2：lucide 图标替换（单 PR）

**步骤**

1. 在 `ui_designer/assets/icons/lucide/` 落地所需 SVG（约 60–100 个）
2. 在 `iconography.py` 新增 `load_lucide_icon()`
3. 把 `_ICON_DEFINITIONS` / `_WIDGET_ICON_KEYS` 映射到新的 lucide key
4. 保留旧实现作为 `LEGACY_ICON_MODE` 开关（env var 或 `QApplication.setProperty`），便于回滚
5. 本地验收 + 跑 pytest
6. PR 贴图标栅格对比图

**验收标准**

- [ ] 工具条、侧栏、组件树、属性面板所有图标呈 stroke-based lucide 风格
- [ ] 图标颜色跟随 `text_soft`/`text`/`accent` token，hover/active 有区分
- [ ] 主题切换后图标自动 re-tint
- [ ] 无图标缺失（fallback 到默认占位）

---

## 8. 验收方式

两阶段都通过 **人工肉眼对比** + **pytest 全绿** 验收，不引入基于 SSIM 的回归（现有 `figmamake` 模块有 SSIM，但那是针对 C 运行时画面的，不适用 Qt 桌面 UI）。

每阶段交付时，在 PR 里提供：
- 主窗口截图（对比参考 `ScreenShot_2026-04-19_141229_121.png` 到 `141849_027.png` 五张）
- New Project 对话框截图（对比 `141229`）
- Assets tab + Font Charset 弹窗截图（对比 `141849`）

---

## 9. 风险与回滚

| 风险 | 缓解 |
|---|---|
| QSS 模板改动影响所有控件，可能出现意料外的视觉回归 | 阶段 1 前跑一遍 GUI 冒烟测试 `scripts/ui_designer/run_gui_pytest.py`，记录基线 |
| qfluentwidgets 组件自带样式覆盖 | `_apply_fluent_engineering_style` 已有机制，按控件类型分派 QSS，保持 |
| lucide 图标数量过多导致包体积增大 | 只提取用到的 key 对应的 SVG，不全量打包 |
| 某些 dialog 硬编码 13px/14px 字号绕过 token | `grep -nE '(font-size|setPixelSize|setPointSize).*(1[2-6])'` 巡检 |
| 阶段 2 图标改动翻车 | 保留 `LEGACY_ICON_MODE` 开关；不动 `_ICON_DEFINITIONS` 老数据，新加一层 lucide 层，运行时按 flag 选择 |

**回滚策略**：每阶段独立 commit，回滚即 `git revert`；Token 改动是声明式的，即使整个阶段 1 被 revert 也只是回到改版前状态，功能零影响。

---

## 10. 后续（超出本轮范围）

这些在 B/C 范围内，不在本次实施，仅记录：

- 左侧栏 `Pages/Tree/Add/Assets` 四 tab 合并为 `Project/Palette` 双 tab
- 右侧栏改为上下分栏（组件树 / 属性）
- 顶部工具条按参考重排
- 底部日志栏改为 Run/Build/Debug/Logcat 四 tab + 折叠

后续如需推进，在本文档上开新版本或另起设计文档即可。
