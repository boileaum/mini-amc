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

# larger nodes/spacing so the pipeline diagram stays readable in the docs;
# useMaxWidth=False stops mermaid from shrinking the SVG to the container
# width (that is what made the diagram tiny)
mermaid_init_config = {
    "startOnLoad": False,
    "themeVariables": {"fontSize": "26px"},
    "flowchart": {
        "nodeSpacing": 90,
        "rankSpacing": 90,
        "useMaxWidth": False,
    },
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "_autosummary"]

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}

language = "en"

html_theme = "furo"
html_static_path = ["_static"]
