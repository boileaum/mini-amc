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

# Mermaid sizing, via the extension's own knobs (its inline <style> comes after
# html_css_files in the <head>, so custom.css cannot override it — use
# mermaid_width/mermaid_height instead): the defaults stretched every diagram
# to the full column (width 100%) in a 500px box, i.e. ~2.5x too zoomed.
# Render at 40% of the column, natural height, with pan/zoom.
mermaid_width = "40%"
mermaid_height = "auto"
mermaid_d3_zoom = True

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
