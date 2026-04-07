#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a local EmbeddedGUI Designer package with PyInstaller."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ui_designer.model.build_metadata import is_git_worktree_dirty, write_designer_build_metadata
from ui_designer.model.workspace import require_designer_sdk_root


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
SPEC_PATH = SCRIPT_DIR / "ui_designer" / "ui_designer.spec"
PREFLIGHT_SMOKE_SCRIPT_PATH = SCRIPT_DIR / "ui_designer_preview_smoke.py"
DIST_APP_NAME = "EmbeddedGUI-Designer"
EXAMPLES_BUNDLE_DIR_NAME = "examples"
SUPPRESSED_LOG_SNIPPETS = (
    "QFluentWidgets Pro is now released",
    "qfluentwidgets.com/pages/pro",
)
SDK_BUNDLE_DIR_NAME = "EmbeddedGUI"
SDK_BUNDLE_METADATA_NAME = ".designer_sdk_bundle.json"
SDK_BUNDLE_IGNORE_NAMES = {
    ".git",
    ".github",
    ".claude",
    ".pytest_cache",
    ".pytest-tmp",
    ".tmp",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".vscode",
    ".idea",
    "build",
    "build_cmake",
    "dist",
    "doc",
    "docs",
    "output",
    "runtime_check_output",
    "iteration_log",
    "runtime_check_images",
    "test_output",
    "coverage",
    "htmlcov",
    ".coverage",
    ".cache",
    ".venv",
    "venv",
    "node_modules",
}
SDK_BUNDLE_IGNORE_RELATIVE_PREFIXES = (
    "ui_designer/tests",
    "ui_designer/__pycache__",
    "__pycache__",
    "scripts/ui_designer/tests",
    "scripts/ui_designer/__pycache__",
    "scripts/__pycache__",
)


def compute_platform_tag(platform_name: str | None = None, machine_name: str | None = None) -> str:
    """Return a stable package platform tag."""
    platform_name = (platform_name or sys.platform).lower()
    detected_machine = machine_name
    if not detected_machine:
        detected_machine = os.environ.get("PROCESSOR_ARCHITECTURE", "")
    if not detected_machine and hasattr(os, "uname"):
        detected_machine = os.uname().machine
    machine_name = (detected_machine or "").lower()

    if any(token in machine_name for token in ("arm64", "aarch64")):
        arch = "arm64"
    else:
        arch = "x64"

    if platform_name.startswith("win"):
        return f"windows-{arch}"
    if platform_name == "darwin":
        return f"macos-{arch}"
    return f"linux-{arch}"


def sanitize_suffix(suffix: str) -> str:
    """Normalize an optional package suffix."""
    suffix = (suffix or "").strip()
    if not suffix:
        return ""
    suffix = suffix.replace(" ", "-")
    invalid_chars = set('/\\:*?"<>|')
    if any(ch in invalid_chars for ch in suffix):
        raise ValueError("package suffix contains invalid path characters")
    return suffix


def build_archive_base_name(platform_tag: str, package_suffix: str = "") -> str:
    """Return the base archive name without extension."""
    base = f"{DIST_APP_NAME}-{platform_tag}"
    suffix = sanitize_suffix(package_suffix)
    if suffix:
        base += f"-{suffix}"
    return base


def resolve_archive_format(archive_mode: str, platform_name: str | None = None) -> str | None:
    """Map CLI archive mode to shutil archive format."""
    archive_mode = (archive_mode or "auto").lower()
    if archive_mode == "none":
        return None
    if archive_mode == "zip":
        return "zip"
    if archive_mode == "tar.gz":
        return "gztar"
    if archive_mode == "auto":
        platform_name = (platform_name or sys.platform).lower()
        return "zip" if platform_name.startswith("win") else "gztar"
    raise ValueError(f"unsupported archive mode: {archive_mode}")


def build_pyinstaller_command(dist_dir: Path, work_dir: Path, clean: bool = True) -> list[str]:
    """Build the PyInstaller command."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_PATH),
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "-y",
    ]
    if clean:
        cmd.append("--clean")
    return cmd


def build_preflight_command(smoke_script: Path | None = None, sdk_root: str | Path | None = None) -> list[str]:
    """Build the live-preview preflight command."""
    script_path = Path(smoke_script or PREFLIGHT_SMOKE_SCRIPT_PATH).resolve()
    cmd = [sys.executable, str(script_path)]
    if sdk_root:
        cmd.extend(["--sdk-root", str(Path(sdk_root).resolve())])
    return cmd


def ensure_pyinstaller_available():
    """Raise with a clear message if PyInstaller is missing."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("PyInstaller is required. Run: python -m pip install pyinstaller") from exc


def looks_like_sdk_root(path: str | Path) -> bool:
    """Return True when *path* looks like a valid EmbeddedGUI SDK root."""
    root = Path(path).resolve()
    return (
        root.is_dir()
        and (root / "Makefile").is_file()
        and (root / "src").is_dir()
        and (root / "porting" / "designer").is_dir()
    )


def resolve_sdk_bundle_root(sdk_root: str | Path | None = None) -> Path:
    """Resolve the SDK root to bundle into the package."""
    resolved = require_designer_sdk_root(
        repo_root=str(PROJECT_ROOT),
        cli_sdk_root=str(sdk_root) if sdk_root else None,
        cli_flag="--sdk-root",
    )
    candidate = Path(resolved).resolve()
    if not looks_like_sdk_root(candidate):
        raise ValueError(f"invalid EmbeddedGUI SDK root: {candidate}")
    return candidate


def build_sdk_bundle_ignore(source_root: Path):
    """Build a copytree ignore callback for SDK bundling."""
    source_root = Path(source_root).resolve()

    def _ignore_sdk_bundle(current_dir: str, names: list[str]) -> set[str]:
        ignored = set()
        current_path = Path(current_dir).resolve()
        try:
            rel_dir = current_path.relative_to(source_root).as_posix()
        except ValueError:
            rel_dir = ""

        for name in names:
            if name in SDK_BUNDLE_IGNORE_NAMES or name.endswith((".pyc", ".pyo")):
                ignored.add(name)
                continue

            rel_path = f"{rel_dir}/{name}" if rel_dir else name
            rel_path = rel_path.strip("/")
            if any(rel_path == prefix or rel_path.startswith(prefix + "/") for prefix in SDK_BUNDLE_IGNORE_RELATIVE_PREFIXES):
                ignored.add(name)

        return ignored

    return _ignore_sdk_bundle


def copy_sdk_bundle(app_dir: Path, sdk_root: str | Path | None = None) -> Path:
    """Copy a local EmbeddedGUI SDK into ``app_dir/sdk/EmbeddedGUI``."""
    source_root = resolve_sdk_bundle_root(sdk_root)
    target_root = app_dir / "sdk" / SDK_BUNDLE_DIR_NAME
    target_root.parent.mkdir(parents=True, exist_ok=True)
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root, ignore=build_sdk_bundle_ignore(source_root))
    write_sdk_bundle_metadata(target_root, source_root)
    return target_root


def copy_designer_examples(app_dir: Path, examples_root: str | Path | None = None) -> Path:
    """Copy bundled Designer examples into ``app_dir/examples`` when present."""
    source_root = Path(examples_root or (PROJECT_ROOT / EXAMPLES_BUNDLE_DIR_NAME)).resolve()
    if not source_root.is_dir():
        return Path()

    target_root = app_dir / EXAMPLES_BUNDLE_DIR_NAME
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(
        source_root,
        target_root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return target_root


def summarize_directory_tree(root: str | Path) -> dict[str, int]:
    """Summarize the copied SDK tree for user-facing package output."""
    resolved_root = Path(root).resolve()
    file_count = 0
    total_size_bytes = 0

    for current_path in resolved_root.rglob("*"):
        if not current_path.is_file():
            continue
        file_count += 1
        try:
            total_size_bytes += current_path.stat().st_size
        except OSError:
            pass

    return {
        "file_count": file_count,
        "total_size_bytes": total_size_bytes,
    }


def write_sdk_bundle_metadata(bundle_root: str | Path, source_root: str | Path) -> Path:
    """Write a small manifest so the packaged Designer can identify bundled SDKs."""
    resolved_bundle_root = Path(bundle_root).resolve()
    resolved_bundle_root.mkdir(parents=True, exist_ok=True)
    resolved_source_root = Path(source_root).resolve()
    summary = summarize_directory_tree(resolved_bundle_root)
    metadata = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_count": summary["file_count"],
        "sdk_dir_name": SDK_BUNDLE_DIR_NAME,
        "source_root": str(resolved_source_root),
        "total_size_bytes": summary["total_size_bytes"],
    }
    metadata.update(collect_sdk_git_metadata(resolved_source_root))
    metadata["git_dirty"] = bool(collect_sdk_git_dirty_flag(resolved_source_root))
    metadata_path = resolved_bundle_root / SDK_BUNDLE_METADATA_NAME
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata_path


def load_sdk_bundle_metadata(bundle_root: str | Path) -> dict[str, object]:
    """Load bundled SDK metadata written by :func:`write_sdk_bundle_metadata`."""
    metadata_path = Path(bundle_root).resolve() / SDK_BUNDLE_METADATA_NAME
    if not metadata_path.is_file():
        return {}

    try:
        content = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

    if not isinstance(content, dict):
        return {}
    return content


def _run_git_text(repo_root: str | Path, *args: str) -> str:
    """Return stdout for a git command, or an empty string on failure."""
    resolved_repo_root = Path(repo_root).resolve()
    git_exe = shutil.which("git")
    if not git_exe or not resolved_repo_root.is_dir():
        return ""

    try:
        result = subprocess.run(
            [git_exe, "-c", f"safe.directory={resolved_repo_root}", "-C", str(resolved_repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def collect_sdk_git_metadata(source_root: str | Path) -> dict[str, object]:
    """Collect git revision metadata for a bundled SDK source tree."""
    resolved_source_root = Path(source_root).resolve()
    commit = _run_git_text(resolved_source_root, "rev-parse", "HEAD")
    if not commit:
        return {}

    metadata: dict[str, object] = {
        "git_commit": commit,
    }
    commit_short = _run_git_text(resolved_source_root, "rev-parse", "--short", "HEAD")
    if commit_short:
        metadata["git_commit_short"] = commit_short

    describe = _run_git_text(resolved_source_root, "describe", "--tags", "--always", "--dirty")
    if describe:
        metadata["git_describe"] = describe

    branch = _run_git_text(resolved_source_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        metadata["git_branch"] = branch

    remote_url = _run_git_text(resolved_source_root, "config", "--get", "remote.origin.url")
    if remote_url:
        metadata["git_remote_url"] = remote_url

    return metadata


def describe_sdk_git_revision(metadata: dict[str, object]) -> str:
    """Return the most useful SDK revision label from bundle metadata."""
    for key in ("git_describe", "git_commit_short", "git_commit"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def collect_sdk_git_dirty_flag(source_root: str | Path) -> bool:
    """Return True when the bundled SDK source tree has local modifications."""
    return bool(is_git_worktree_dirty(source_root))


def format_byte_count(size_bytes: int) -> str:
    """Return a compact human-readable size string."""
    size = max(int(size_bytes or 0), 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def should_suppress_build_output(line: str) -> bool:
    """Return True when a build log line is pure third-party promotion noise."""
    text = line or ""
    return any(snippet in text for snippet in SUPPRESSED_LOG_SNIPPETS)


def iter_filtered_build_output(lines):
    """Yield build output while stripping known third-party promotion lines."""
    suppress_blank_lines = False
    pending_blank_lines: list[str] = []
    for line in lines:
        if not line.strip():
            pending_blank_lines.append(line)
            continue
        if should_suppress_build_output(line):
            pending_blank_lines.clear()
            suppress_blank_lines = True
            continue
        if suppress_blank_lines:
            pending_blank_lines.clear()
        suppress_blank_lines = False
        if pending_blank_lines:
            for blank_line in pending_blank_lines:
                yield blank_line
            pending_blank_lines.clear()
        yield line


def run_pyinstaller(dist_dir: Path, work_dir: Path, clean: bool = True):
    """Execute the PyInstaller build."""
    cmd = build_pyinstaller_command(dist_dir, work_dir, clean=clean)
    process = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in iter_filtered_build_output(process.stdout):
        print(line, end="")

    returncode = process.wait()
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, cmd)


def run_preflight_check(smoke_script: Path | None = None, sdk_root: str | Path | None = None):
    """Run the live-preview smoke check before packaging."""
    resolved_sdk_root = resolve_sdk_bundle_root(sdk_root=sdk_root)
    cmd = build_preflight_command(smoke_script=smoke_script, sdk_root=resolved_sdk_root)
    print("[INFO] Running UI Designer live preview preflight...", flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"UI Designer live preview preflight failed with exit code {result.returncode}")


def create_archive(dist_dir: Path, archive_dir: Path, archive_format: str, base_name: str) -> Path:
    """Archive the built Designer directory."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_base = archive_dir / base_name
    archive_path = shutil.make_archive(
        str(archive_base),
        archive_format,
        root_dir=str(dist_dir),
        base_dir=DIST_APP_NAME,
    )
    return Path(archive_path)


def package_ui_designer(
    *,
    output_dir: str | Path | None = None,
    work_dir: str | Path | None = None,
    archive_mode: str = "auto",
    package_suffix: str = "",
    clean: bool = True,
    bundle_sdk: bool = True,
    sdk_root: str | Path | None = None,
    run_preflight: bool = True,
) -> dict[str, str | int]:
    """Build the Designer package and optionally archive it."""
    ensure_pyinstaller_available()
    if run_preflight:
        run_preflight_check(sdk_root=sdk_root)

    dist_dir = Path(output_dir or (PROJECT_ROOT / "dist")).resolve()
    build_dir = Path(work_dir or (PROJECT_ROOT / "build" / "pyinstaller")).resolve()

    run_pyinstaller(dist_dir, build_dir, clean=clean)

    app_dir = dist_dir / DIST_APP_NAME
    if not app_dir.is_dir():
        raise FileNotFoundError(f"PyInstaller output missing: {app_dir}")

    designer_metadata_path = write_designer_build_metadata(app_dir, PROJECT_ROOT)

    bundled_sdk_dir = None
    bundled_sdk_metadata = {}
    if bundle_sdk:
        bundled_sdk_dir = copy_sdk_bundle(app_dir, sdk_root=sdk_root)
        bundled_sdk_metadata = load_sdk_bundle_metadata(bundled_sdk_dir)
    bundled_examples_dir = copy_designer_examples(app_dir)

    archive_format = resolve_archive_format(archive_mode)
    archive_path = None
    if archive_format is not None:
        platform_tag = compute_platform_tag()
        base_name = build_archive_base_name(platform_tag, package_suffix=package_suffix)
        archive_path = create_archive(dist_dir, dist_dir, archive_format, base_name)

    return {
        "dist_dir": str(dist_dir),
        "app_dir": str(app_dir),
        "designer_metadata_path": designer_metadata_path,
        "archive_path": str(archive_path) if archive_path else "",
        "bundled_sdk_dir": str(bundled_sdk_dir) if bundled_sdk_dir else "",
        "bundled_sdk_file_count": int(bundled_sdk_metadata.get("file_count", 0)),
        "bundled_sdk_git_commit": str(bundled_sdk_metadata.get("git_commit", "")),
        "bundled_sdk_git_remote_url": str(bundled_sdk_metadata.get("git_remote_url", "")),
        "bundled_sdk_git_revision": describe_sdk_git_revision(bundled_sdk_metadata),
        "bundled_sdk_metadata_path": (
            str(Path(bundled_sdk_dir) / SDK_BUNDLE_METADATA_NAME) if bundled_sdk_dir else ""
        ),
        "bundled_sdk_source": str(bundled_sdk_metadata.get("source_root", "")),
        "bundled_sdk_total_size_bytes": int(bundled_sdk_metadata.get("total_size_bytes", 0)),
        "bundled_examples_dir": str(bundled_examples_dir) if bundled_examples_dir else "",
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Build a local EmbeddedGUI Designer package")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "dist"),
        help="PyInstaller dist output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--work-dir",
        default=str(PROJECT_ROOT / "build" / "pyinstaller"),
        help="PyInstaller work directory (default: %(default)s)",
    )
    parser.add_argument(
        "--archive",
        choices=["auto", "zip", "tar.gz", "none"],
        default="auto",
        help="Archive mode for the built package (default: %(default)s)",
    )
    parser.add_argument(
        "--package-suffix",
        default="",
        help="Optional suffix appended to the archive name, such as a version tag",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not pass --clean to PyInstaller",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the UI Designer live preview smoke check before packaging",
    )
    bundle_group = parser.add_mutually_exclusive_group()
    bundle_group.add_argument(
        "--bundle-sdk",
        dest="bundle_sdk",
        action="store_true",
        help="Copy an EmbeddedGUI SDK into the packaged app under sdk/EmbeddedGUI (default)",
    )
    bundle_group.add_argument(
        "--no-bundle-sdk",
        dest="bundle_sdk",
        action="store_false",
        help="Skip bundling the SDK into the packaged app",
    )
    parser.add_argument(
        "--sdk-root",
        default="",
        help="EmbeddedGUI SDK root (default: EMBEDDEDGUI_SDK_ROOT, sdk/EmbeddedGUI, or ../EmbeddedGUI beside this repo)",
    )
    parser.set_defaults(bundle_sdk=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = package_ui_designer(
            output_dir=args.output_dir,
            work_dir=args.work_dir,
            archive_mode=args.archive,
            package_suffix=args.package_suffix,
            clean=not args.no_clean,
            bundle_sdk=args.bundle_sdk,
            sdk_root=args.sdk_root,
            run_preflight=not args.skip_preflight,
        )
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(1)

    print(f"[OK] app_dir: {result['app_dir']}")
    if result["bundled_examples_dir"]:
        print(f"[OK] bundled_examples: {result['bundled_examples_dir']}")
    if result["bundled_sdk_dir"]:
        print(f"[OK] bundled_sdk: {result['bundled_sdk_dir']}")
        print(f"[OK] bundled_sdk_source: {result['bundled_sdk_source'] or 'unknown'}")
        if result["bundled_sdk_git_revision"]:
            print(f"[OK] bundled_sdk_revision: {result['bundled_sdk_git_revision']}")
        if result["bundled_sdk_git_commit"]:
            print(f"[OK] bundled_sdk_commit: {result['bundled_sdk_git_commit']}")
        if result["bundled_sdk_git_remote_url"]:
            print(f"[OK] bundled_sdk_remote: {result['bundled_sdk_git_remote_url']}")
        print(
            "[OK] bundled_sdk_summary: "
            f"{result['bundled_sdk_file_count']} files, "
            f"{format_byte_count(int(result['bundled_sdk_total_size_bytes']))}"
        )
        print(f"[OK] bundled_sdk_metadata: {result['bundled_sdk_metadata_path']}")
    if result["archive_path"]:
        print(f"[OK] archive: {result['archive_path']}")
    else:
        print("[OK] archive: skipped")


if __name__ == "__main__":
    main()






