"""Sphinx configuration for the mini-amc docs."""

from docutils import nodes

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

myst_enable_checkboxes = True
myst_fence_as_directive = ["mermaid"]

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


def _tasklist_to_checkboxes(app, doctree):
    # myst renders "- [ ] item" as a literal "[ ]" in docutils output; turn
    # task-list markers into real (disabled) HTML checkboxes
    for item in doctree.findall(nodes.list_item):
        if not item.children or not isinstance(item.children[0], nodes.paragraph):
            continue
        para = item.children[0]
        first = para.children[0] if para.children else None
        if not isinstance(first, nodes.Text):
            continue
        for marker, checked in (("[ ] ", False), ("[x] ", True), ("[X] ", True)):
            if first.astext().startswith(marker):
                para.children[0] = nodes.Text("", first.astext()[len(marker) :])
                raw = nodes.raw(
                    "",
                    f'<input type="checkbox" disabled{" checked" if checked else ""}> ',
                    format="html",
                )
                para.insert(0, raw)
                break


def setup(app):
    """Register the task-list to checkbox transform."""
    app.connect("doctree-read", _tasklist_to_checkboxes)
