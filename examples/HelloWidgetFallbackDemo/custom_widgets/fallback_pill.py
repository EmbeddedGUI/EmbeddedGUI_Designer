"""Manual app-local descriptor for the fallback pill demo widget."""
from ui_designer.model.widget_registry import WidgetRegistry

WidgetRegistry.instance().register(
    type_name="fallback_pill",
    descriptor={
        "c_type": "egui_view_fallback_pill_t",
        "init_func": "egui_view_fallback_pill_init",
        "is_container": False,
        "add_child_func": None,
        "layout_func": None,
        "header_include": "widgets/egui_view_fallback_pill.h",
        "properties": {
            "text": {
                "type": "string",
                "default": "Fallback pill",
                "code_gen": {"kind": "text_setter", "func": "egui_view_fallback_pill_set_text"},
            },
            "emphasis": {
                "type": "bool",
                "default": False,
                "code_gen": {"kind": "setter", "func": "egui_view_fallback_pill_set_emphasis", "bool_to_int": True, "skip_default": True},
            },
        },
        "browser": {
            "category": "Custom",
            "keywords": ["fallback", "manual descriptor", "custom widget"],
            "browse_priority": 900,
        },
    },
    xml_tag="FallbackPill",
    display_name="FallbackPill",
)
