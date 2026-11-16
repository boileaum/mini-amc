"""Sphinx configuration for the mini-amc docs."""

from mini_amc import __version__

project = "mini-amc"
copyright = "2026, Matthieu Boileau"
author = "Matthieu Boileau"
release = __version__

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
    "sphinx_copybutton",
    "sphinxcontrib.programoutput",
    "sphinxcontrib.mermaid",
]

myst_enable_extensions = ["tasklist"]
myst_fence_as_directive = ["mermaid"]

# the pipeline diagram is tall: the extension's default CSS forces the SVG into
# a 500px-high box (mermaid_height), which shrinks it to unreadable — let the
# SVG keep its natural height, and enable pan/zoom on the big diagram
mermaid_height = "auto"
mermaid_d3_zoom = True
mermaid_init_config = {
    "themeVariables": {"fontSize": "24px"},
}

templates_path = ["_templates"]
# _autosummary (autosummary stubs) must stay readable: it is only gitignored
exclude_patterns = ["_build"]

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}

language = "en"

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
