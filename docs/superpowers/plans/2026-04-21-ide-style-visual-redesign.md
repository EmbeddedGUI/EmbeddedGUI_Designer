# IDE 风格视觉改版 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `EmbeddedGUI Designer` 的 dark 主题严格对齐参考 Figma（Android Studio 风格：zinc 色板 + blue-500 强调 + 紧凑 IDE 密度 + 4px 圆角 + 顶部 2px 蓝条激活态 + lucide 图标）。

**Architecture:** 改动集中在 token 层（`theme.py` 的 `_TOKENS["dark"]` 与 `_FLUENT_*_QSS` 常量）以及图标层（`iconography.py`）。不触碰任何面板布局、Dock 结构或业务逻辑。分两阶段：阶段 1 = 色板/字号/圆角/激活态；阶段 2 = lucide 图标替换。每阶段独立 commit 便于回滚。

**Tech Stack:** PyQt5, qfluentwidgets, `QSvgRenderer`（阶段 2），pytest（覆盖 token 断言与 QSS 片段断言）。

**Spec:** [docs/superpowers/specs/2026-04-21-ide-style-visual-redesign-design.md](../specs/2026-04-21-ide-style-visual-redesign-design.md)

---

## File Structure

### 阶段 1（不新建文件，全部在现有文件内改）

- 修改：[ui_designer/ui/theme.py](../../../ui_designer/ui/theme.py) — `_TOKENS["dark"]` 全量替换；`_FLUENT_*_QSS` 常量里硬编码 `0px` 圆角与 `13px` 字号的字符串微调；`_build_stylesheet()` 内新增 tab 激活态 / tree 选中态 / 克制 hover QSS 片段
- 修改：[ui_designer/tests/ui/test_theme.py](../../../ui_designer/tests/ui/test_theme.py) — 追加 token 值断言
- 新增：[ui_designer/tests/ui/test_theme_ide_style.py](../../../ui_designer/tests/ui/test_theme_ide_style.py) — 本次专用的 token/QSS 断言集（保持新老分离，方便回滚）

### 阶段 2（新增资源目录 + 图标加载层）

- 新建：`ui_designer/assets/icons/lucide/*.svg` — 所需 lucide SVG（~60–100 个）
- 修改：[ui_designer/ui/iconography.py](../../../ui_designer/ui/iconography.py) — 新增 `load_lucide_icon()` + 在 `_ICON_DEFINITIONS` / `_WIDGET_ICON_KEYS` 映射路由到 lucide 加载层；保留 `LEGACY_ICON_MODE` 开关
- 新增：`ui_designer/tests/ui/test_iconography_lucide.py` — 加载与着色测试

---

## Chunk 1: 阶段 1 — Token 表替换（色板 + 字号 + 间距 + 圆角）

### Task 1.1: 写 token 值断言测试

**Files:**
- Create: `ui_designer/tests/ui/test_theme_ide_style.py`

- [x] **Step 1: 新建失败测试**

```python
"""IDE-style redesign token assertions (dark only).

Locks in the exact token values defined in the 2026-04-21 design spec so that
any regression is caught by pytest before it ships.
"""

from ui_designer.ui.theme import theme_tokens


def test_dark_palette_uses_zinc_and_blue500():
    t = theme_tokens("dark")
    # zinc scale
    assert t["bg"] == "#09090B"
    assert t["shell_bg"] == "#09090B"
    assert t["sidebar_bg"] == "#27272A"
    assert t["panel"] == "#18181B"
    assert t["panel_alt"] == "#27272A"
    assert t["panel_soft"] == "#3F3F46"
    assert t["panel_raised"] == "#27272A"
    assert t["surface"] == "#3F3F46"
    assert t["surface_hover"] == "#52525B"
    assert t["surface_pressed"] == "#71717A"
    assert t["canvas_bg"] == "#09090B"
    assert t["canvas_stage"] == "#09090B"
    assert t["border"] == "#3F3F46"
    assert t["border_strong"] == "#52525B"
    # blue-500 accent
    assert t["focus_ring"] == "#3B82F6"
    assert t["accent"] == "#3B82F6"
    assert t["accent_hover"] == "#60A5FA"
    # text
    assert t["text"] == "#D4D4D8"
    assert t["text_muted"] == "#A1A1AA"
    assert t["text_soft"] == "#71717A"
    # status colors
    assert t["danger"] == "#EF4444"
    assert t["success"] == "#22C55E"
    assert t["warning"] == "#EAB308"


def test_dark_selection_uses_rgba_blue500():
    t = theme_tokens("dark")
    assert t["selection"] == "rgba(59, 130, 246, 0.40)"
    assert t["selection_soft"] == "rgba(59, 130, 246, 0.15)"
    assert t["accent_soft"] == "rgba(59, 130, 246, 0.15)"


def test_dark_typography_uses_compact_ide_scale():
    t = theme_tokens("dark")
    assert t["fs_display"] == 18
    assert t["fs_h1"] == 13
    assert t["fs_h2"] == 12
    assert t["fs_panel_title"] == 12
    assert t["fs_body"] == 12
    assert t["fs_body_sm"] == 11
    assert t["fs_caption"] == 10
    assert t["fs_micro"] == 10


def test_dark_spacing_and_radii_tightened():
    t = theme_tokens("dark")
    assert t["pad_btn_v"] == 2
    assert t["pad_btn_h"] == 8
    assert t["pad_input_v"] == 2
    assert t["pad_input_h"] == 6
    assert t["r_sm"] == 4
    assert t["r_md"] == 4
    assert t["r_lg"] == 4
    assert t["r_xl"] == 6
    assert t["r_2xl"] == 8
    assert t["r_3xl"] == 8


def test_light_palette_unchanged():
    """D2 decision: light theme must NOT be touched in this pass."""
    t = theme_tokens("light")
    assert t["bg"] == "#EEF2F6"
    assert t["accent"] == "#287DDA"
    assert t["fs_body"] == 13
```

- [x] **Step 2: 跑测试确认失败**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme_ide_style.py -v
```

Expected: 4 个新 dark 测试 FAIL（因为旧值还没改），1 个 light 测试 PASS。

- [x] **Step 3: Commit 测试骨架**

```
git add ui_designer/tests/ui/test_theme_ide_style.py
git commit -m "test(theme): add IDE-style redesign dark-mode token assertions (RED)"
```

---

### Task 1.2: 更新 `_TOKENS["dark"]` 全量替换

**Files:**
- Modify: `ui_designer/ui/theme.py` — `_TOKENS["dark"]` 整个 dict（行号以实际文件为准，约 L248–L299）

- [x] **Step 1: 替换 dark token 字典**

定位 `_TOKENS = { "dark": { ... }, "light": { ... } }`，把 `dark` 分支完整替换为：

```python
    "dark": {
        "bg": "#09090B",
        "shell_bg": "#09090B",
        "sidebar_bg": "#27272A",
        "panel": "#18181B",
        "panel_alt": "#27272A",
        "panel_soft": "#3F3F46",
        "panel_raised": "#27272A",
        "surface": "#3F3F46",
        "surface_hover": "#52525B",
        "surface_pressed": "#71717A",
        "canvas_bg": "#09090B",
        "canvas_stage": "#09090B",
        "border": "#3F3F46",
        "border_strong": "#52525B",
        "focus_ring": "#3B82F6",
        "text": "#D4D4D8",
        "text_muted": "#A1A1AA",
        "text_soft": "#71717A",
        "accent": "#3B82F6",
        "accent_hover": "#60A5FA",
        "accent_soft": "rgba(59, 130, 246, 0.15)",
        "danger": "#EF4444",
        "success": "#22C55E",
        "warning": "#EAB308",
        "selection": "rgba(59, 130, 246, 0.40)",
        "selection_soft": "rgba(59, 130, 246, 0.15)",
        "r_sm": 4,
        "r_md": 4,
        "r_lg": 4,
        "r_xl": 6,
        "r_2xl": 8,
        "r_3xl": 8,
        "space_xxs": 4,
        "space_xs": 4,
        "space_sm": 8,
        "space_md": 12,
        "space_lg": 16,
        "space_xl": 20,
        "space_2xl": 24,
        "pad_btn_v": 2,
        "pad_btn_h": 8,
        "pad_input_v": 2,
        "pad_input_h": 6,
        "h_tab_min": 24,
        "fs_display": 18,
        "fs_h1": 13,
        "fs_h2": 12,
        "fs_panel_title": 12,
        "fs_body": 12,
        "fs_body_sm": 11,
        "fs_caption": 10,
        "fs_micro": 10,
        "fw_regular": 400,
        "fw_medium": 500,
        "fw_semibold": 600,
        "fw_bold": 700,
        "icon_xs": 14,
        "icon_sm": 16,
        "icon_md": 18,
        "icon_lg": 20,
    },
```

- [x] **Step 2: 跑 1.1 的测试，验证 RED → GREEN**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme_ide_style.py -v
```

Expected: 全部 PASS。

- [x] **Step 3: 跑整个 theme 测试套件，检查回归**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme.py -v
```

Expected: 可能出现少量失败（老测试可能断言了旧颜色值，如 `#12161B`、`#4B9DFF`）。**逐个评估**：
- 如果老测试断言的是"token 存在且非空"→ 仍 PASS，无需改
- 如果老测试断言了具体 hex 值 → 更新为新值
- 如果老测试断言了 `selection` 是 hex（现在是 rgba）→ 改为断言 rgba 字符串

**⚠️ 不得删除老测试以让它通过，必须更新断言到与新 spec 一致的期望值。** 任何语义变化（例如 token 用途变了）才可以重写。

- [x] **Step 4: Commit token 替换**

```
git add ui_designer/ui/theme.py ui_designer/tests/ui/test_theme.py
git commit -m "feat(theme): align dark-mode tokens with IDE-style zinc + blue-500 palette"
```

---

### Task 1.3: 更新 QSS 模板常量的圆角与字号

**Files:**
- Modify: `ui_designer/ui/theme.py` — `_FLUENT_*_QSS` 系列常量（行号以实际文件为准，约 L75–L200）

- [x] **Step 1: 写失败断言**

在 `ui_designer/tests/ui/test_theme_ide_style.py` 追加：

```python
from ui_designer.ui import theme as _theme_mod


def test_fluent_qss_templates_use_4px_radius_and_12px_font():
    """Buttons/inputs/combos must have 4px radius and 12px font (IDE density)."""
    fragments = [
        _theme_mod._FLUENT_BUTTON_RADIUS_QSS,
        _theme_mod._FLUENT_LINE_EDIT_RADIUS_QSS,
        _theme_mod._FLUENT_COMBO_BOX_RADIUS_QSS,
        _theme_mod._FLUENT_SPIN_BOX_RADIUS_QSS,
    ]
    for qss in fragments:
        assert "border-radius: 4px" in qss, f"missing 4px radius: {qss[:80]}"
        assert "font-size: 12px" in qss, f"missing 12px font: {qss[:80]}"
        assert "border-radius: 0px" not in qss


def test_property_panel_qss_templates_use_4px_radius():
    fragments = [
        _theme_mod._FLUENT_PROPERTY_PANEL_BUTTON_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_LINE_EDIT_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_COMBO_BOX_QSS,
        _theme_mod._FLUENT_PROPERTY_PANEL_SPIN_BOX_QSS,
    ]
    for qss in fragments:
        assert "border-radius: 4px" in qss
        assert "border-radius: 0px" not in qss
```

- [x] **Step 2: 跑测试确认 RED**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme_ide_style.py::test_fluent_qss_templates_use_4px_radius_and_12px_font ui_designer/tests/ui/test_theme_ide_style.py::test_property_panel_qss_templates_use_4px_radius -v
```

Expected: FAIL。

- [x] **Step 3: 改 `_FLUENT_*_QSS` 常量**

在 `theme.py` 的全部 8 个 QSS 模板（4 个全局 + 4 个 property-panel）里，用文本替换：

- `border-radius: 0px;` → `border-radius: 4px;`
- `font-size: 13px;` → `font-size: 12px;`

其余字段（`min-height`, `padding`, `min-width`）保持现状。

- [x] **Step 4: 跑测试 → GREEN**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme_ide_style.py -v
```

- [x] **Step 5: Commit**

```
git add ui_designer/ui/theme.py ui_designer/tests/ui/test_theme_ide_style.py
git commit -m "feat(theme): round buttons/inputs to 4px and tighten font to 12px in dark QSS"
```

---

### Task 1.4: 新增 tab 激活态 / tree 选中态 / 克制 hover QSS 片段

**Files:**
- Modify: `ui_designer/ui/theme.py` — `_build_stylesheet()` 函数体内追加 QSS

- [x] **Step 1: 写失败断言**

在 `ui_designer/tests/ui/test_theme_ide_style.py` 追加：

```python
def test_dark_stylesheet_includes_ide_accent_features():
    css = _theme_mod._build_stylesheet("dark")
    # 顶部 2px 蓝条激活态
    assert "QTabBar::tab:selected" in css
    assert "border-top: 2px solid #3B82F6" in css or "border-top: 2px solid rgb(59, 130, 246)" in css
    # 半透明蓝选中
    assert "rgba(59, 130, 246, 0.25)" in css or "rgba(59, 130, 246, 0.40)" in css
    # 亮蓝文字（blue-200 #BFDBFE）
    assert "#BFDBFE" in css
```

- [x] **Step 2: 跑测试确认 RED**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme_ide_style.py::test_dark_stylesheet_includes_ide_accent_features -v
```

Expected: FAIL。

- [x] **Step 3: 读 `_build_stylesheet()` 找到 QTabBar 相关 QSS 的输出位置**

```
python - <<'PY'
from ui_designer.ui.theme import _build_stylesheet
css = _build_stylesheet("dark")
for i, line in enumerate(css.splitlines()):
    if "QTabBar" in line or "QTreeView::item:selected" in line:
        print(i, line)
PY
```

记录现有 QTabBar/QTreeView 规则所在行数，准备在其附近插入新规则。

- [x] **Step 4: 追加新规则**

在 `_build_stylesheet()` 返回字符串的末尾（或现有 QTabBar 规则之后）追加：

```python
# Append to the returned stylesheet f-string (use token values, not literals)
css_ide_accents = f"""
/* IDE-style tab activation: 2px accent bar on top */
QTabBar::tab {{
    border-top: 2px solid transparent;
    padding: 4px 12px;
    background: {t["sidebar_bg"]};
    color: {t["text_soft"]};
}}
QTabBar::tab:selected {{
    border-top: 2px solid {t["accent"]};
    background: {t["panel"]};
    color: {t["text"]};
}}
QTabBar::tab:hover:!selected {{
    background: {t["surface_hover"]};
    color: {t["text_muted"]};
}}

/* IDE-style tree/list selection: translucent blue + light blue text */
QTreeView::item:selected,
QTreeView::item:selected:active,
QListView::item:selected,
QListView::item:selected:active,
QListWidget::item:selected {{
    background: rgba(59, 130, 246, 0.25);
    color: #BFDBFE;
}}
QTreeView::item:hover,
QListView::item:hover,
QListWidget::item:hover {{
    background: rgba(59, 130, 246, 0.10);
}}

/* Restrained hover for buttons/toolbuttons */
QPushButton:hover, QToolButton:hover {{
    background: {t["surface_hover"]};
}}
"""
# Then concatenate into the main return
```

**实现提示**：`_build_stylesheet` 目前返回单个 f-string，需要把这段 `css_ide_accents` 通过字符串拼接加到末尾。`t` 是 `theme_tokens(mode, ...)` 的返回值（已在函数顶部计算）。

- [x] **Step 5: 跑测试 → GREEN**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme_ide_style.py -v
```

- [x] **Step 6: 跑全量 theme 测试，修任何回归**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_theme.py -v
```

- [x] **Step 7: Commit**

```
git add ui_designer/ui/theme.py ui_designer/tests/ui/test_theme_ide_style.py
git commit -m "feat(theme): add IDE-style tab activation bar, translucent selection, restrained hover"
```

---

### Task 1.5: 巡检硬编码颜色

**Files:**
- Scan: `ui_designer/ui/**/*.py`

- [x] **Step 1: 列出硬编码 hex 颜色**

```
python - <<'PY'
import re, pathlib
pat = re.compile(r"#[0-9A-Fa-f]{6}")
old_palette = {"#12161B","#161B21","#1C232C","#202833","#283241","#242E3A","#2D3947","#364453","#3F4E60","#101418","#0D1116","#344150","#425164","#4B9DFF","#F3F6FA","#BCC7D4","#93A1B2","#78B5FF","#163451","#FF6B5F","#46C98B","#FFB84D","#2B5F98","#1B2E46"}
for p in pathlib.Path("ui_designer/ui").rglob("*.py"):
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        for m in pat.findall(line):
            if m.upper() in old_palette:
                print(f"{p}:{n}: {m}  {line.strip()[:100]}")
PY
```

Expected: 输出一份候选列表。

- [x] **Step 2: 逐个替换为 token 读取**

对每个命中：
- 确认该色在 `_TOKENS["dark"]` 中的角色（查对照表）
- 改为 `theme_tokens(mode)["<key>"]` 或 `app_theme_tokens(app)["<key>"]`
- 若在 QSS f-string 内，用 `f"color: {tokens['text']}"` 风格

- [x] **Step 3: 跑 pytest 套件**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v --tb=short
```

- [x] **Step 4: Commit**

```
git add -u ui_designer/ui
git commit -m "refactor(ui): replace hard-coded legacy hex colors with theme tokens"
```

---

### Task 1.6: 肉眼冒烟验收

**Files:** 无代码改动，仅人工验证。

- [x] **Step 1: 启动 Designer 做短启动检查（非阻塞）**

```
python ui_designer_preview_smoke.py --sdk-root sdk/EmbeddedGUI
```

Expected: 程序能启动并在 ~5 秒内进入主窗口；无 Python 异常。

- [ ] **Step 2: 截图对比**

补充：已完成 welcome screen 的短启动窗口截图和主窗口纯黑底/紧凑按钮样式核对；加载项目后的 tab 激活态、tree 选中态和完整侧栏层级截图仍待补全。

启动 `python ui_designer/main.py --sdk-root sdk/EmbeddedGUI`（后台模式），截图：
- 主窗口（对比 `ref/UI Editor Design/src/imports/ScreenShot_2026-04-19_141404_066.png`）
- New Project 对话框（对比 `141229`）
- Assets 面板（对比 `141615`）

核对清单：
- [ ] 窗口底色是纯黑 `#09090B` 而非蓝黑
- [ ] 侧栏 / 面板 / 背景形成三档灰阶
- [ ] 按钮、输入框圆角 4px（不再直角，也不再 6px）
- [ ] Tab 激活态有顶部蓝条
- [ ] 树选中行半透明蓝 + 亮蓝文字
- [ ] 文字整体变小了一档（body 12px / caption 10px）

- [ ] **Step 3: 如果有肉眼回归，逐条修到满意再进入 Chunk 2**

---

## Chunk 2: 阶段 2 — lucide 图标替换

### Task 2.1: 准备 lucide SVG 资源与映射表

**Files:**
- Create: `ui_designer/assets/icons/lucide/*.svg`（资源文件）
- Create: `ui_designer/assets/icons/lucide/MAPPING.md` — 本地文档记录「项目 key → lucide name」

- [x] **Step 1: 归纳所需 icon key 清单**

```
python - <<'PY'
from ui_designer.ui.iconography import _WIDGET_ICON_KEYS
keys = sorted(set(_WIDGET_ICON_KEYS.values()))
print("semantic keys (targets):")
for k in keys: print(" -", k)
PY
```

对照 Spec 第 6 节补齐 toolbar/nav/state 语义键（约 40 项）与 widget 键（70+ 项）。

- [x] **Step 2: 拉取 lucide SVG**

方式 A（零依赖）：从 https://lucide.dev/icons/ 单独下载所需 SVG，放入 `ui_designer/assets/icons/lucide/`。

方式 B（开发期便利）：`npm i lucide-static`（一次性，不加入 requirements），`cp node_modules/lucide-static/icons/<name>.svg` 到资源目录后卸载 node_modules。

确保 SVG viewBox 为 `0 0 24 24`、`stroke="currentColor"`、`stroke-width="2"`、`fill="none"` 的 lucide 标准格式。

- [x] **Step 3: 写映射表 MAPPING.md**

```markdown
# Lucide Icon Mapping

| Project key | lucide name | SVG file |
|---|---|---|
| run | play | play.svg |
| stop | square | square.svg |
| debug | bug | bug.svg |
| refresh | rotate-cw | rotate-cw.svg |
| project | folder-tree | folder-tree.svg |
| palette | component | component.svg |
| widget:button | minus-square | minus-square.svg |
| widget:text | type | type.svg |
| widget:image | image | image.svg |
| widget:checkbox | check-square | check-square.svg |
| widget:switch | settings-2 | settings-2.svg |
| widget:slider | sliders-horizontal | sliders-horizontal.svg |
| widget:linearlayout | columns | columns.svg |
| widget:gridlayout | grid-3x3 | grid-3x3.svg |
| ... | ... | ... |
```

（完整表格由执行时按 widget 清单填充；最终应覆盖所有 `_ICON_DEFINITIONS` + `_WIDGET_ICON_KEYS` 值）

- [x] **Step 4: Commit 资源**

```
git add ui_designer/assets/icons/lucide
git commit -m "assets(icons): add lucide SVG icon set for IDE-style redesign"
```

---

### Task 2.2: 实现 `load_lucide_icon()` 加载层

**Files:**
- Create: `ui_designer/tests/ui/test_iconography_lucide.py`
- Modify: `ui_designer/ui/iconography.py`

- [x] **Step 1: 写失败测试**

```python
"""Lucide icon loader tests."""
import pytest
from PyQt5.QtGui import QIcon

from ui_designer.ui.iconography import load_lucide_icon


def test_load_lucide_icon_returns_valid_qicon(qapp):
    icon = load_lucide_icon("play", color="#D4D4D8", size=16)
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_load_lucide_icon_caches_by_key(qapp):
    a = load_lucide_icon("play", color="#D4D4D8", size=16)
    b = load_lucide_icon("play", color="#D4D4D8", size=16)
    assert a is b  # cached


def test_load_lucide_icon_recolors_via_stroke(qapp):
    a = load_lucide_icon("play", color="#D4D4D8", size=16)
    b = load_lucide_icon("play", color="#3B82F6", size=16)
    assert a is not b


def test_load_lucide_icon_missing_returns_fallback(qapp):
    icon = load_lucide_icon("definitely_not_a_real_lucide_name", color="#fff", size=16)
    assert isinstance(icon, QIcon)
    # fallback may be empty QIcon or a placeholder; just ensure no crash
```

（`qapp` fixture 可能已存在于 conftest，否则用 `pytest-qt` 提供。）

- [x] **Step 2: 跑测试确认 RED**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_iconography_lucide.py -v
```

Expected: FAIL（`load_lucide_icon` 不存在）。

- [x] **Step 3: 实现 `load_lucide_icon`**

在 `iconography.py` 顶部追加：

```python
from functools import lru_cache
from pathlib import Path
from PyQt5.QtCore import QByteArray, Qt
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

_LUCIDE_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons" / "lucide"


@lru_cache(maxsize=512)
def _load_lucide_icon_cached(name: str, color: str, size: int) -> QIcon:
    svg_path = _LUCIDE_DIR / f"{name}.svg"
    if not svg_path.is_file():
        return QIcon()
    svg = svg_path.read_text(encoding="utf-8")
    # Replace stroke color
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pm)


def load_lucide_icon(name: str, color: str = None, size: int = 16) -> QIcon:
    """Load a lucide icon by name, recolored to `color`.

    Returns an empty QIcon if the SVG is missing.
    """
    if color is None:
        from .theme import app_theme_tokens
        color = app_theme_tokens().get("text_soft", "#71717A")
    return _load_lucide_icon_cached(str(name), str(color), int(size))
```

- [x] **Step 4: 跑测试 → GREEN**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_iconography_lucide.py -v
```

- [x] **Step 5: Commit**

```
git add ui_designer/ui/iconography.py ui_designer/tests/ui/test_iconography_lucide.py
git commit -m "feat(icons): add load_lucide_icon SVG loader with recoloring and caching"
```

---

### Task 2.3: 路由 `_ICON_DEFINITIONS` 到 lucide 加载层 + 保留 LEGACY 开关

**Files:**
- Modify: `ui_designer/ui/iconography.py`

- [x] **Step 1: 加 LEGACY 开关**

```python
import os

_LEGACY_ICON_MODE = os.environ.get("EMBEDDEDGUI_LEGACY_ICONS", "0") == "1"
```

- [x] **Step 2: 在现有图标解析入口（例如 `icon_for_widget(key)` / `icon_for_semantic(key)` — 以实际函数名为准）新增 lucide 分支**

伪代码：

```python
def icon_for_widget(widget_key: str, *, color=None, size=16) -> QIcon:
    if _LEGACY_ICON_MODE:
        return _legacy_icon_for_widget(widget_key, color=color, size=size)
    semantic = _WIDGET_ICON_KEYS.get(widget_key)
    lucide_name = _LUCIDE_KEY_MAP.get(semantic) or _LUCIDE_KEY_MAP.get(widget_key)
    if lucide_name:
        icon = load_lucide_icon(lucide_name, color=color, size=size)
        if not icon.isNull():
            return icon
    return _legacy_icon_for_widget(widget_key, color=color, size=size)
```

`_LUCIDE_KEY_MAP` 是一个顶层字典，把项目 key 映射到 lucide 文件名（来自 Task 2.1 的 MAPPING.md）：

```python
_LUCIDE_KEY_MAP = {
    # toolbar / nav
    "run": "play",
    "stop": "square",
    "debug": "bug",
    "refresh": "rotate-cw",
    # palette semantics
    "text": "type",
    "image": "image",
    "button": "minus-square",
    "toggle": "check-square",
    "input": "type",
    "layout": "columns",
    "grid": "grid-3x3",
    # ... 完整表见 Task 2.1 MAPPING.md
}
```

- [x] **Step 3: 写集成测试**

`ui_designer/tests/ui/test_iconography_lucide.py` 追加：

```python
def test_icon_for_widget_uses_lucide_by_default(qapp):
    from ui_designer.ui.iconography import icon_for_widget  # or actual fn name
    icon = icon_for_widget("button")
    assert not icon.isNull()


def test_legacy_icon_mode_falls_back(qapp, monkeypatch):
    monkeypatch.setenv("EMBEDDEDGUI_LEGACY_ICONS", "1")
    # re-import module to pick up env var
    import importlib, ui_designer.ui.iconography as ico
    importlib.reload(ico)
    icon = ico.icon_for_widget("button")
    assert not icon.isNull()  # legacy path still works
```

- [x] **Step 4: 跑测试 + GUI 冒烟**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_iconography_lucide.py -v
python ui_designer_preview_smoke.py --sdk-root sdk/EmbeddedGUI
```

- [x] **Step 5: Commit**

```
git add ui_designer/ui/iconography.py ui_designer/tests/ui/test_iconography_lucide.py
git commit -m "feat(icons): route widget/semantic icons through lucide loader with LEGACY fallback"
```

---

### Task 2.4: 主题变更时刷新图标缓存

**Files:**
- Modify: `ui_designer/ui/iconography.py` 或 `ui_designer/ui/theme.py`

- [x] **Step 1: 在 `apply_theme()` 末尾清空 lucide LRU 缓存**

在 `theme.py` 的 `apply_theme(app, mode, density)` 末尾添加：

```python
try:
    from .iconography import _load_lucide_icon_cached
    _load_lucide_icon_cached.cache_clear()
except ImportError:
    pass
```

- [x] **Step 2: 写断言**

```python
def test_theme_switch_clears_lucide_cache(qapp):
    from ui_designer.ui.iconography import load_lucide_icon, _load_lucide_icon_cached
    from ui_designer.ui.theme import apply_theme
    load_lucide_icon("play")
    assert _load_lucide_icon_cached.cache_info().currsize >= 1
    apply_theme(qapp, mode="dark")
    assert _load_lucide_icon_cached.cache_info().currsize == 0
```

- [x] **Step 3: 跑测试**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/ui/test_iconography_lucide.py -v
```

- [x] **Step 4: Commit**

```
git add -u
git commit -m "fix(icons): invalidate lucide cache on theme change for proper recolor"
```

---

### Task 2.5: 最终肉眼验收

- [ ] **Step 1: 启动并对比**

补充：已完成 modern/legacy 两条路径的 Qt 级别短启动可见性检查；工具条和项目加载态的图标肉眼对比仍待补充截图。

```
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

核对：
- [ ] 工具条运行/停止/调试按钮是 lucide 的 stroke 风格
- [ ] 侧栏 palette 分类图标都是 lucide
- [ ] Component Tree 每种 widget 的图标已切换
- [ ] 图标颜色跟随 `text_soft`，hover/active 时变亮
- [ ] 切换主题（若可切）后图标 re-tint

- [ ] **Step 2: 验证 LEGACY 回滚**

```
$env:EMBEDDEDGUI_LEGACY_ICONS="1"
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI
```

确认能回退到老图标，证明回滚路径可用。

- [x] **Step 3: 跑全量 pytest**

```
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v --tb=short
```

Expected: 全绿。

- [x] **Step 4: 更新 Spec 状态为 Done**

在 spec 文件顶部改 `Status: Draft` → `Status: Implemented`。

```
git add docs/superpowers/specs/2026-04-21-ide-style-visual-redesign-design.md
git commit -m "docs(spec): mark IDE-style visual redesign as implemented"
```

---

## Remember

- 每阶段独立 commit、独立可回滚
- Token 变更前后都跑 `test_theme.py`，不要让老断言静默失败
- GUI 验收用 `ui_designer_preview_smoke.py` 短启动，**不要** 用阻塞式 `python ui_designer/main.py` 跑到你中断
- 任何硬编码色值发现了都要换成 token，不要绕过
- LEGACY 开关是最后的保险，阶段 2 翻车直接 `EMBEDDEDGUI_LEGACY_ICONS=1` 止血
