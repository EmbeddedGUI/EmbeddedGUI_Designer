# Font Preview Demo

This sample renders a font preview PNG by reusing the same `ttf2c.py` glyph pipeline that resource generation uses.

## Run

```bash
python samples/font_preview_demo/render_font_preview_demo.py --sdk-root sdk/EmbeddedGUI
```

The command writes `samples/font_preview_demo/output/font_preview_demo.png`.

## Useful options

```bash
python samples/font_preview_demo/render_font_preview_demo.py \
    --sdk-root sdk/EmbeddedGUI \
    --font sdk/EmbeddedGUI/scripts/tools/build_in/Montserrat-Medium.ttf \
    --text-file samples/font_preview_demo/sample_text.txt \
    --pixelsize 20 \
    --fontbitsize 4 \
    --output temp/font_preview_demo.png
```
