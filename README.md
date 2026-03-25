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
- Run a real release smoke on the sample project:
  `python scripts/ui_designer/release_project.py --project samples/release_smoke/ReleaseSmokeApp --sdk-root sdk/EmbeddedGUI --output-dir build/release-smoke --json`
- Inspect local repo health:
  `python scripts/ui_designer/repo_doctor.py`
  `python scripts/ui_designer/repo_doctor.py --strict`
  `python scripts/ui_designer/repo_doctor.py --critical-only`
  `python scripts/ui_designer/repo_doctor.py --blocked-only`
  `python scripts/ui_designer/repo_doctor.py --summary`

## Release workflow

### From the GUI

Use `Build -> Release Build...` to create a reproducible release for the current project.
Use `Build -> Release Profiles...` to maintain project-local release profiles in `.eguiproject/release.json`.
Use `Build -> Release History...` to inspect, time-filter, artifact-filter, diagnostics-filter, sort, refresh, copy, or export prior release summaries as text or JSON, copy or export the currently selected entry JSON, reset back to the default history view, switch between auto, manifest, version, or log previews directly inside the Designer, reopen release roots, dist folders, tracked artifacts, or the raw `history.json` ledger, and reopen with the last-used filters still applied per project.
Use `Build -> Repository Health...` to inspect SDK submodule state, release smoke sample presence, stale workspace temp directories, filter to critical issues or blocked stale directories, reset back to the default view, switch between text or JSON reports with embedded summary/count metadata, copy short summaries, JSON reports, or the selected stale directory path for issue reports, choose and open the currently filtered stale temp directory directly, export text or JSON report snapshots, and reopen with the previous view settings intact.
The latest successful build can be reopened from `Build -> Open Last Release Folder`, `Build -> Open Last Release Dist`, `Build -> Open Last Release Manifest`, `Build -> Open Last Release Version`, `Build -> Open Last Release Package`, or `Build -> Open Last Release Log`.
The project-wide release history ledger can be reopened from `Build -> Open Release History File`.

### From the CLI

- Create a release package for a project:
  `python scripts/ui_designer/release_project.py --project path/to/Demo.egui --sdk-root sdk/EmbeddedGUI`
- Emit release result as JSON for CI or wrappers:
  `python scripts/ui_designer/release_project.py --project path/to/Demo.egui --sdk-root sdk/EmbeddedGUI --json`
- Inspect a release root, manifest, packaged app, or bundled SDK directory:
  `python scripts/ui_designer/inspect_release.py path/to/output/ui_designer_release/windows-pc/<build_id>`
  `python scripts/ui_designer/inspect_release.py dist/EmbeddedGUI-Designer --json`

### Release output

A project release is written under `output/ui_designer_release/<profile>/<build_id>/` and includes:

- `release-manifest.json`: build result, Designer revision, SDK revision, warnings/errors, artifacts.
- `VERSION.txt`: compact human-readable version stamp.
- `logs/build.log`: resource generation and build output.
- `dist/`: copied executable, resources, `VERSION.txt`, and a manifest copy.
- `history.json`: rolling release history for the project, including SDK/Designer revisions, diagnostics counts, and artifact paths.

Packaged Designer builds also include:

- `.designer_build_info.json` in the app root.
- `sdk/EmbeddedGUI/.designer_sdk_bundle.json` when SDK bundling is enabled.
- CI package builds also upload `dist/designer-package-metadata.json` for quick SDK/version inspection.
- CI release smoke builds also upload `build/release-smoke/` plus JSON summaries for manifest and SDK traceability.
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

## Updating the SDK pin

- Move the submodule to the SDK revision you want to verify:
  `git submodule update --remote sdk/EmbeddedGUI`
- Re-run Designer verification against that SDK revision.
- Commit both `.gitmodules` and the updated `sdk/EmbeddedGUI` gitlink.
