import sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from setuptools import find_packages


setup(
    name='MapProxy',
    version="0.8.0",
    description='MapProxy',
    author='Oliver Tonnhofer',
    author_email='tonnhofer@omniscale.de',
    url='http://mapproxy.org',
    namespace_packages = ['mapproxy'],
    packages=find_packages(),
    include_package_data=True,
    entry_points = {
        'console_scripts': [
            'proxy_seed = mapproxy.core.scripts.seed:main',
        ],
        'paste.app_factory': [
            'app = mapproxy.core.app:app_factory'
        ],
        'mapproxy.wms.request_parser': [
        ],
        'mapproxy.wms.client_request': [
        ],
        'paste.paster_create_template': [
            'mapproxy_conf=mapproxy.core.paster_templates:ConfigurationTemplate'
        ],
    },
    package_data = {'': ['*.xml', '*.yaml', '*.ttf']},
    install_requires=['PIL>=1.1.6,<1.2', 'pyproj>=1.8.5',
                      'PyYAML>=3.0,<4','Jinja2>=2.1,<2.2',
                      'flup>=1.0.1,<1.1', 'setuptools>=0.6c9',
                      'ConcurrentLogHandler>=0.8.3,<0.9'],
    zip_safe=False,
    test_suite='nose.collector',
)
