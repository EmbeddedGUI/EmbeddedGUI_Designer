# EmbeddedGUI Designer

Standalone repository for `ui_designer`.

## Local setup

1. Keep the SDK repo beside this repo as `../EmbeddedGUI`, or set `EMBEDDEDGUI_SDK_ROOT`, or pass `--sdk-root` explicitly.
2. Install Python dependencies:
   `python -m pip install -r ui_designer/requirements-desktop.txt`

## Common commands

- Run tests:
  `python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v --tb=short`
- Run preview smoke:
  `python ui_designer_preview_smoke.py --sdk-root ../EmbeddedGUI`
- Build package:
  `python package_ui_designer.py --sdk-root ../EmbeddedGUI`
