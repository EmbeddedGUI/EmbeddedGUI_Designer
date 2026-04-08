# HelloWidgetFallbackDemo

This bundled Designer example covers the app-local custom widget fallback path.

- `widgets/egui_view_fallback_pill.h` intentionally does **not** use the SDK parser's preferred header pattern.
- `custom_widgets/fallback_pill.py` provides the manual widget descriptor that the Designer loads from the app root.
- Opening the project demonstrates that app-local Python descriptors can recover when header parsing is insufficient.
