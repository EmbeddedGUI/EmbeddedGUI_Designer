"""Render a preview PNG using the SDK font-generation glyph pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui_designer.utils.font_preview_renderer import render_font_preview_image


def _default_sdk_root() -> Path:
    return REPO_ROOT / "sdk" / "EmbeddedGUI"


def _default_font_path(sdk_root: Path) -> Path:
    candidates = (
        sdk_root / "scripts" / "tools" / "build_in" / "NotoSansSC-VF.ttf",
        sdk_root / "scripts" / "tools" / "build_in" / "Montserrat-Medium.ttf",
        sdk_root / "scripts" / "tools" / "build_in" / "DejaVuSans.ttf",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No built-in demo font was found under sdk/EmbeddedGUI/scripts/tools/build_in/.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a font preview PNG using the EmbeddedGUI SDK glyph pipeline.")
    parser.add_argument("--sdk-root", default=str(_default_sdk_root()), help="EmbeddedGUI SDK root")
    parser.add_argument("--font", default="", help="Path to the font file to preview")
    parser.add_argument(
        "--text-file",
        default=str(Path(__file__).with_name("sample_text.txt")),
        help="UTF-8 sample text file. Supports the same &#xNNNN; entities as ttf2c.py.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).with_name("output") / "font_preview_demo.png"),
        help="Output PNG path",
    )
    parser.add_argument("--pixelsize", type=int, default=20, help="Preview font pixel size")
    parser.add_argument("--fontbitsize", type=int, default=4, choices=(1, 2, 4, 8), help="Glyph bit depth")
    parser.add_argument("--weight", type=int, default=None, help="Optional variable-font weight")
    args = parser.parse_args()

    sdk_root = Path(args.sdk_root).resolve()
    font_path = Path(args.font).resolve() if args.font else _default_font_path(sdk_root).resolve()
    text_file = Path(args.text_file).resolve()
    output_path = Path(args.output).resolve()

    if not sdk_root.is_dir():
        raise SystemExit(f"SDK root does not exist: {sdk_root}")
    if not font_path.is_file():
        raise SystemExit(f"Font file does not exist: {font_path}")
    if not text_file.is_file():
        raise SystemExit(f"Sample text file does not exist: {text_file}")

    sample_text = text_file.read_text(encoding="utf-8")
    image = render_font_preview_image(
        sdk_root=str(sdk_root),
        font_path=str(font_path),
        sample_text=sample_text,
        pixel_size=max(int(args.pixelsize), 4),
        font_bit_size=int(args.fontbitsize),
        weight=args.weight,
    )
    if image is None:
        raise SystemExit("Failed to render preview image. Check Pillow/freetype dependencies and the SDK toolchain.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PNG")
    print(f"Saved preview to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
