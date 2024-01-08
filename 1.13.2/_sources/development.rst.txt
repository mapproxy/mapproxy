Development
===========

You want to improve MapProxy, found a bug and want to fix it? Great! This document points you to some helpful information.

.. .. contents::

Source
------

Releases are available from the `PyPI project page of MapProxy <http://pypi.python.org/pypi/MapProxy>`_. There is also `an archive of all releases <http://pypi.python.org/packages/source/M/MapProxy/>`_.

MapProxy uses `Git`_ as a source control management tool. If you are new to distributed SCMs or Git we recommend to read `Pro Git <http://git-scm.com/book>`_.

The main (authoritative) repository is hosted at http://github.com/mapproxy/mapproxy

To get a copy of the repository call::

  git clone https://github.com/mapproxy/mapproxy

If you want to contribute a patch, please consider `creating a "fork"`__ instead. This makes life easier for all of us.

.. _`Git`: http://git-scm.com/
.. _`fork`: http://help.github.com/fork-a-repo/

__ fork_

Documentation
-------------

This is the documentation you are reading right now. The raw files can be found in ``doc/``. The HTML version user documentation is build with `Sphinx`_. To rebuild this documentation install Sphinx with ``pip install sphinx sphinx-bootstrap-theme`` and call ``python setup.py build_sphinx``. The output appears in ``build/sphinx/html``. The latest documentation can be found at ``http://mapproxy.org/docs/lates/``.

.. _`Epydoc`: http://epydoc.sourceforge.net/
.. _`Sphinx`: http://sphinx.pocoo.org/


Issue Tracker
-------------

We are using `the issue tracker at GitHub <https://github.com/mapproxy/mapproxy/issues>`_ to manage all bug reports, enhancements and new feature requests for MapProxy. Go ahead and `create new tickets <https://github.com/mapproxy/mapproxy/issues/new>`_. Feel free to post to the `mailing list`_ first, if you are not sure if you really found a bug or if a feature request is in the scope of MapProxy.

Tests
-----

MapProxy contains lots of automatic tests. If you don't count in the ``mapproxy-seed``-tool and the WSGI application, the test coverage is around 95%. We want to keep this number high, so all new developments should include some tests.

MapProxy uses `pytest`_ as a test loader and runner.

  pip install pytest


To run the actual tests call::

  pytest

.. _`pytest`: https://pytest.org/

Available tests
"""""""""""""""

We distinguish between doctests, unit, system tests.

Doctests
^^^^^^^^
`Doctest <http://docs.python.org/library/doctest.html>`_ are embedded into the source documentation and are great for documenting small independent functions or methods. You will find lots of doctest in the ``mapproxy.core.srs`` module.

Unit tests
^^^^^^^^^^
Tests that are a little bit more complex, eg. that need some setup or state, are put into ``mapproxy.tests.unit``. To be recognized as a test all functions and classes should be prefixed with ``test_`` or ``Test``. Refer to the existing tests for examples.

System tests
^^^^^^^^^^^^
We have some tests that will start the whole MapProxy application, issues requests and does some assertions on the responses. All XML responses will be validated against the schemas in this tests. These test are located in ``mapproxy.tests.system``.


Communication
-------------
Mailing list
""""""""""""

The preferred medium for all MapProxy related discussions is our mailing list mapproxy@lists.osgeo.org You must `subscribe <http://lists.osgeo.org/mailman/listinfo/mapproxy>`_ to the list before you can write. The archive is `available here <http://lists.osgeo.org/pipermail/mapproxy/>`_.


Tips on development
-------------------

You are using `virtualenv` as described in :doc:`install`, right?

Before you start hacking on MapProxy you should install it in development-mode. In the root directory of MapProxy call ``pip install -e ./``. Instead of installing and thus copying MapProxy into your `virtualenv`, this will just link to your source directory. If you now start MapProxy, the source from your MapProxy directory will be used. Any change you do in the code will be available if you restart MapProxy. If you use the  ``mapproxy-util serve-develop`` command, any change in the source will issue a reload of the MapProxy server.


Coding Style Guide
------------------

MapProxy generally follows the `Style Guide for Python Code`_. With the only exception that we permit a line width of about 90 characters.
New files should be auto-formatted with `black <https://github.com/ambv/black>`_.

.. _`Style Guide for Python Code`: http://www.python.org/dev/peps/pep-0008/
