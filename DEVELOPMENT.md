Dev Setup
=========

* Create parent directory for source, applications and the virtual env
* Clone source into directory mapproxy: `git clone `
* Install dependencies: https://mapproxy.org/docs/latest/install.html#install-dependencies
* Create virtualenv: `python3.6 -m venv ./venv`
* Activate virtualenv: `source venv/bin/activate`
* Install mapproxy: `pip install -e mapproxy/`
* Install dev dependencies: `pip install -r mapproxy/requirements-tests.txt`
* Run tests:
    * `cd mapproxy`
    * `pytest mapproxy`
    * Run single test: `pytest mapproxy/test/unit/test_grid.py -v`
* Create an application: `mapproxy-util create -t base-config apps/base`

* Start a dev server in debug mode: `mapproxy-util serve-develop apps/base/mapproxy.yaml --debug`


Coding Style
------------

PEP8: https://www.python.org/dev/peps/pep-0008/


Debugging
---------

With PyCharm: Attach to dev server with https://www.jetbrains.com/help/pycharm/attaching-to-local-process.html

With ipython:
* `pip install ipython ipdb`


Some more details in the documentation
--------------------------------------

See https://mapproxy.org/docs/latest/development.html


Some incomplete notes about the structure of the software
---------------------------------------------------------

A mapproxy app decides on the request-URL which handler it starts. There exist different handlers for WMS, WMTS.

Incoming http requests are transformed into own request objects (for example `WMSRequest`).

The class `TileManager` decides if tiles are served from cache or from a source.

All caches need to implement the interface `TileCacheBase`.

The code in `config/` builds mapproxy out of a configuration. `config/spec.py` validates the config.

The sources live in `source/` which in turn use low-level functions from `client/` to request the data.

The file `layer.py` merges/clips/transforms tiles.

The whole of MapProxy is stateless apart from the chache which uses locks on file system level.
