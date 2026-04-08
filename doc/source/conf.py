# Configuration file for the Sphinx documentation builder.

project = "EmbeddedGUI Designer"
copyright = "2026, EmbeddedGUI Designer"
author = "EmbeddedGUI Designer"
release = "1.0"

extensions = ["myst_parser"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build"]

language = "zh"

html_theme = "furo"
html_static_path = ["_static"]

html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#2f6fed",
        "color-brand-content": "#2f6fed",
    },
    "dark_css_variables": {
        "color-brand-primary": "#7db2ff",
        "color-brand-content": "#7db2ff",
    },
}
