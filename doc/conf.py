# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'MapProxy Docs'
copyright = "2024"
author = 'MapProxy Community, <a href="http://mapproxy.org/about">Legal</a>'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '2.0'
# The full version, including alpha/beta/rc tags.
release = '2.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx_copybutton'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_book_theme'
html_static_path = ['_static']
html_css_files = ["mapproxy.css"]
html_logo = "_static/logo_title.png"
html_last_updated_fmt = ""
html_favicon = "_static/mapproxy-favicon.ico"
html_theme_options = {
    "path_to_docs": "./",
    "repository_url": "https://github.com/mapproxy/mapproxy",
    "repository_branch": "master",
    "show_navbar_depth": 2,
    "use_fullscreen_button": False,
    "use_download_button": False,
    "use_repository_button": True,
    "collapse_navbar": True,
    "toc_title": "",
    "navbar_start": ["versions.html"]
}
html_baseurl = "/mapproxy/"
html_context = {
    "docsBaseUrl": "https://mapproxy.github.io/mapproxy"
}
