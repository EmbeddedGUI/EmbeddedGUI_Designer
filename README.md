# EmbeddedGUI Designer

Standalone repository for `ui_designer`.

## SDK dependency model

This repository tracks the EmbeddedGUI SDK as a pinned submodule at `sdk/EmbeddedGUI`.
The default SDK resolution order is:

1. `--sdk-root`
2. `EMBEDDEDGUI_SDK_ROOT`
3. `sdk/EmbeddedGUI`
4. sibling `../EmbeddedGUI`

Release packaging bundles the resolved SDK into the app and writes source-path plus git revision metadata to `sdk/EmbeddedGUI/.designer_sdk_bundle.json` inside the packaged output. The packaged UI also shows the bundled SDK revision so users can see which SDK commit a verified executable was built against.

## Local setup

1. Initialize or update the SDK submodule:
   `git submodule update --init --recursive`
2. Install Python dependencies:
   `python -m pip install -r ui_designer/requirements-desktop.txt`

If you do not want to use the submodule checkout locally, `EMBEDDEDGUI_SDK_ROOT` or a sibling `../EmbeddedGUI` checkout still works.

## Common commands

- Run tests:
  `python scripts/ui_designer/run_pytest.py`
- Run preview smoke:
  `python ui_designer_preview_smoke.py --sdk-root sdk/EmbeddedGUI`
- Build package:
  `python package_ui_designer.py --sdk-root sdk/EmbeddedGUI`
- Inspect local repo health:
  `python scripts/ui_designer/repo_doctor.py`
  `python scripts/ui_designer/repo_doctor.py --strict`
  `python scripts/ui_designer/repo_doctor.py --critical-only`
  `python scripts/ui_designer/repo_doctor.py --blocked-only`
  `python scripts/ui_designer/repo_doctor.py --summary`

## Documentation

Detailed Chinese usage guide with real UI screenshots:

- `doc/README.md`
- `doc/source/ui_designer/README.md`

## Release workflow

### GitHub release tags

Repository distribution releases are handled outside the Designer UI through GitHub Actions.
Push a version tag such as `v0.1.0`, and the `Designer Release` workflow will:

- build the Windows package on `windows-latest`
- run package preflight checks and build `dist/EmbeddedGUI-Designer/EmbeddedGUI-Designer.exe`
- archive the full runtime folder as `EmbeddedGUI-Designer-windows-x64-<tag>.zip`
- create or reuse the matching GitHub Release and upload the zip, `designer-package-metadata.json`, `repo-health.json`, and `SHA256SUMS.txt`

The published asset is a zip package that contains the runnable `EmbeddedGUI-Designer.exe` together with its required runtime files and bundled SDK.

### From the CLI

- Inspect a packaged app or bundled SDK directory:
  `python scripts/ui_designer/inspect_release.py dist/EmbeddedGUI-Designer --json`

### Release output

Packaged Designer builds also include:

- `.designer_build_info.json` in the app root.
- `sdk/EmbeddedGUI/.designer_sdk_bundle.json` when SDK bundling is enabled.
- CI package builds also upload `dist/designer-package-metadata.json` for quick SDK/version inspection.
- CI jobs also upload `build/repo-health.json` so submodule and workspace health are inspectable from artifacts.

## Figma and HTML conversion tools

This repository is now the maintenance home for the design-conversion toolchain.
Run these commands from the repository root:

- HTML or JSX layout analysis:
  `python html2egui_helper.py extract-layout --input design.html`
- Create a Designer project:
  `python html2egui_helper.py scaffold --app MyApp --width 320 --height 480`
- Generate code and resources:
  `python html2egui_helper.py generate-code --app MyApp`
  `python html2egui_helper.py gen-resource --app MyApp`
- End-to-end Figma Make pipeline:
  `python figmamake/figmamake2egui.py --project-dir figma_make_project --app MyApp`

The SDK is resolved from `--sdk-root`, `EMBEDDEDGUI_SDK_ROOT`, the bundled `sdk/EmbeddedGUI` submodule, or a sibling `../EmbeddedGUI` checkout.

## Font charset resources

The resource panel now includes `Fonts -> Generate Charset...` for creating project-local font text resources without hand-maintaining `.txt` files.

- Built-in presets include printable ASCII, `GB2312` symbol/level-1/level-2 sets, full `GB2312`, and full `GBK`.
- Generated files are written to `.eguiproject/resources/*.txt`, then flow through the existing resource sync and `app_resource_config.json` generation path.
- `Save and Bind Current Widget` also assigns the generated text file to the selected widget's `font_text_file`.

More detail: [`docs/FONT_CHARSET_GENERATOR.md`](docs/FONT_CHARSET_GENERATOR.md)

## Standalone resource generator

The `Build -> Resource Generator...` entry opens a standalone editor for `app_resource_config.json`.

- It can be used without opening an `.egui` project first.
- It supports `New`, `Open`, `Save`, `Save As`, merged preview, and direct resource generation.
- It now provides `Simple` and `Professional` modes so quick asset setup and detailed config editing can coexist in the same window.
- Known sections currently have structured editors for `img`, `font`, and `mp4`.
- `Simple` mode groups actions into `Import & Setup`, `Batch Fixes`, `Preview & Open`, `Image Tools`, and `Selection` panels for a more guided workflow.
- `Simple` mode adds quick helpers for importing individual images/fonts/videos, scanning an asset folder, packing external assets into `Source Dir`, renaming asset names from filenames, auto-creating missing font text files, refreshing font text links and video metadata from files, sorting, deduplicating, and cleaning missing assets, auto-filling missing names and metadata, generating font text files, and opening or creating linked font text resources.
- `Simple` mode also previews the selected asset, opens or exports a preview board for all imported assets, renders font samples directly in the window, auto-detects video fps and size, and can open asset folders plus duplicate, remove, open, resize, rotate, flip, or crop images for quick touch-up.
- Generation uses an explicit path model: `Config`, `Source Dir`, `Workspace`, and `Bin Output`.
- When `resource/src/.designer/app_resource_config_designer.json` exists next to the config, the window shows the merged effective view without modifying the designer-owned overlay.

More detail: [`docs/RESOURCE_GENERATOR.md`](docs/RESOURCE_GENERATOR.md)

## Updating the SDK pin

- Move the submodule to the SDK revision you want to verify:
  `git submodule update --remote sdk/EmbeddedGUI`
- Re-run Designer verification against that SDK revision.
- Commit both `.gitmodules` and the updated `sdk/EmbeddedGUI` gitlink.
