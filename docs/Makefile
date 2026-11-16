SPHINXOPTS = -b html
SOURCEDIR = source
BUILDDIR = build
AUTOSUMMARY = $(SOURCEDIR)/_autosummary

html:
	sphinx-build -b html $(SOURCEDIR) $(BUILDDIR)/html

clean:
	rm -rf $(BUILDDIR) $(AUTOSUMMARY)
