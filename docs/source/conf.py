"""Sphinx configuration for the mini-amc docs."""

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

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
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "_autosummary"]

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}

language = "fr"

html_theme = "furo"
html_static_path = ["_static"]
