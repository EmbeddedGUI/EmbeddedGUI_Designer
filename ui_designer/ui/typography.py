"""Typography roles and helpers (UIX-002, UI_UIX_REDESIGN_MASTER_PLAN).

Roles map to ``theme.py`` font-size and weight tokens. Prefer these helpers over
ad-hoc QLabel/QPushButton font tweaks so hierarchy stays consistent.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QApplication, QFormLayout, QLabel, QVBoxLayout, QWidget

from .theme import theme_tokens

# Role → (fs_key, fw_key) into theme_tokens()
_TYPO_ROLES = {
    "display": ("fs_display", "fw_semibold"),
    "heading": ("fs_h1", "fw_semibold"),
    "section": ("fs_h2", "fw_medium"),
    "panel_title": ("fs_panel_title", "fw_medium"),
    "body": ("fs_body", "fw_regular"),
    "meta": ("fs_body_sm", "fw_regular"),
    "caption": ("fs_caption", "fw_regular"),
}

# Control baseline map (UIX-002): make common control text rhythm explicit.
# Consumers can use this to keep label/control pairing stable.
_CONTROL_BASELINE_ROLES = {
    "panel_header": "panel_title",
    "field_label": "meta",
    "field_value": "body",
    "button_label": "meta",
    "chip_label": "caption",
    "hint_text": "caption",
}


def typography_role_keys(role: str) -> tuple[str, str] | None:
    """Return (font_size_key, font_weight_key) for a role, or None if unknown."""
    return _TYPO_ROLES.get(str(role or "").strip().lower())


def control_baseline_role(control_name: str) -> str | None:
    """Return the preferred typography role for a common control semantic name."""
    key = str(control_name or "").strip().lower()
    return _CONTROL_BASELINE_ROLES.get(key)


def _app_theme_mode() -> str:
    app = QApplication.instance()
    m = app.property("designer_theme_mode") if app is not None else None
    return m if m in ("dark", "light") else "dark"


def apply_typography_role(widget: QWidget, role: str, *, mode: str | None = None) -> bool:
    """Apply token-backed font size and weight to a widget. Returns False if role unknown."""
    spec = typography_role_keys(role)
    if spec is None or widget is None:
        return False
    fs_key, fw_key = spec
    app_mode = mode if mode in ("dark", "light") else _app_theme_mode()
    tokens = theme_tokens(app_mode)
    try:
        px = int(tokens.get(fs_key, 13))
        weight = int(tokens.get(fw_key, 400))
    except (TypeError, ValueError):
        px, weight = 13, 400
    font = widget.font()
    font.setPixelSize(max(px, 1))
    font.setWeight(weight)
    widget.setFont(font)
    return True


def build_typography_preview_widget(parent: QWidget | None = None) -> QWidget:
    """Dev-facing sample strip: one line per typography role (UIX-002 reference)."""
    root = QWidget(parent)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    intro = QLabel("Typography roles — use apply_typography_role() or stylesheet tokens.")
    intro.setWordWrap(True)
    apply_typography_role(intro, "meta")
    layout.addWidget(intro)
    form = QFormLayout()
    form.setSpacing(6)
    for role in ("display", "heading", "section", "panel_title", "body", "meta", "caption"):
        lab = QLabel(f"{role.replace('_', ' ').title()} — The quick brown fox 敏捷的棕色狐狸")
        apply_typography_role(lab, role)
        form.addRow(f"{role}:", lab)
    layout.addLayout(form)
    layout.addStretch()
    return root
