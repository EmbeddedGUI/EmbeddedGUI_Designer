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
  `python -m pytest -c ui_designer/pyproject.toml ui_designer/tests -v --tb=short`
- Run preview smoke:
  `python ui_designer_preview_smoke.py --sdk-root sdk/EmbeddedGUI`
- Build package:
  `python package_ui_designer.py --sdk-root sdk/EmbeddedGUI`

## Updating the SDK pin

- Move the submodule to the SDK revision you want to verify:
  `git submodule update --remote sdk/EmbeddedGUI`
- Re-run Designer verification against that SDK revision.
- Commit both `.gitmodules` and the updated `sdk/EmbeddedGUI` gitlink.
