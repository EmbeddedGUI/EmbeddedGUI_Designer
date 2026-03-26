# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
git submodule update --init --recursive
python -m pip install -r ui_designer/requirements-desktop.txt
```

The SDK submodule lives at `sdk/EmbeddedGUI`. Alternatively, set `EMBEDDEDGUI_SDK_ROOT` or place a checkout at sibling `../EmbeddedGUI`.

## Commands

```bash
# Run tests
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v --tb=short

# Run a single test file
python -m pytest -c ui_designer/pyproject.toml ui_designer/tests/test_html_parsing.py -v

# Launch the Designer GUI
python ui_designer/main.py --sdk-root sdk/EmbeddedGUI

# Preview smoke test
python ui_designer_preview_smoke.py --sdk-root sdk/EmbeddedGUI

# Build release package
python package_ui_designer.py --sdk-root sdk/EmbeddedGUI
```

## Architecture

This repo is the standalone distribution of the **EmbeddedGUI Visual UI Designer** — a PyQt5 desktop app that lets you design LVGL-style UIs visually and generate C code for embedded targets.

### Core layers

**`ui_designer/model/`** — Data layer (no Qt dependencies):
- `project.py` + `page.py` — Project/page serialization to XML (`.egui` files in `example/<AppName>/`)
- `widget_model.py` + `widget_registry.py` — Widget definitions and type registry
- `workspace.py` — SDK root resolution logic (env var → submodule → sibling dir)
- `resource_catalog.py`, `string_resource.py` — Resource and i18n management
- `undo_manager.py` — Undo/redo stack

**`ui_designer/engine/`** — Build and rendering:
- `compiler.py` — Drives `make` to compile the C project; parses gcc commands via `make V=1 --dry-run`
- `layout_engine.py` — Pure-Python replication of the C-side LinearLayout algorithm to position overlay widgets in the preview
- `designer_bridge.py` — Runtime bridge between the running EmbeddedGUI executable and the Designer
- `python_renderer.py` — Software renderer for design-time preview without building

**`ui_designer/generator/`** — C code generation:
- `code_generator.py` — Produces MFC-style multi-file output per page: `{page}_layout.c` (always overwritten), `{page}.h` (struct + USER CODE regions), `{page}.c` (created once, never overwritten)
- `resource_config_generator.py`, `string_resource_generator.py` — Resource and i18n C/header generation
- `user_code_preserver.py` — Extracts and re-injects `/* USER CODE */` regions so user code survives regeneration

**`ui_designer/ui/`** — PyQt5 UI panels:
- `main_window.py` — Top-level window, panel orchestration
- `preview_panel.py` — Live preview (runs the compiled exe via `designer_bridge`)
- `property_panel.py` — Widget property editor
- `widget_tree.py` — Hierarchical widget tree view

**`ui_designer/custom_widgets/`** — One Python file per supported EmbeddedGUI widget type, each declaring its properties and code-gen snippets.

### Design-conversion toolchain

**`html2egui_helper.py`** — Multi-subcommand script for HTML/JSX → EGUI conversion: `scaffold`, `extract-layout`, `generate-code`, `gen-resource`, `export-icons`, `figma2xml`.

**`figmamake/`** — Figma Make → EGUI pipeline (4 stages): Playwright capture → TSX parse/convert → compile + run → SSIM regression verify.

### Project file layout on disk

```
example/<AppName>/
    <AppName>.egui              # project metadata (XML)
    .eguiproject/
        layout/<page>.xml       # one XML per page
        resources/
            resources.xml
            images/
            values/strings.xml  # default locale
            values-zh/strings.xml
    resource/                   # generated output (don't hand-edit)
```

### SDK validity check

`workspace.is_valid_sdk_root()` confirms an SDK root by checking for `Makefile`, `src/`, and `porting/designer/` subdirectories.
