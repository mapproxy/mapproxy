import os
import sys
from setuptools import setup, find_packages
from distutils.cmd import Command

class build_api(Command):
    description = 'Build API documentation'
    user_options = [('verbose', 'v', 'verbose output')]

    def initialize_options(self): pass
    def finalize_options(self): pass

    def run(self):
        conf = os.path.join('doc', 'epydoc.ini')
        argv_ = sys.argv[1:]
        try:
            from epydoc import cli
            sys.argv[1:] = [
                '--config=%s' % conf,
            ]
            if self.verbose:
                sys.argv.append('-v')
            cli.cli()
        except ImportError:
            print 'install epydoc to create the API documentation'
        finally:
            sys.argv[1:] = argv_

setup(
    name='MapProxy',
    version="0.8.0",
    description='An accelerating proxy for web map services',
    long_description=open('README.txt').read(),
    author='Oliver Tonnhofer',
    author_email='olt@omniscale.de',
    url='http://mapproxy.org',
    license='GNU Affero General Public License v3 (AGPLv3)',
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
    install_requires=['PIL>=1.1.6,<1.1.99', 'pyproj>=1.8.5,<1.8.99',
                      'PyYAML>=3.0,<3.99','Jinja2>=2.1,<2.1.99',
                      'flup>1.0.2,<1.0.99', 'setuptools>=0.6c9',
                      'Paste>=1.7.2,<1.7.99', 'PasteDeploy>=1.3.3,<1.3.99',
                      'PasteScript>=1.7.3,<1.7.99',
                      'ConcurrentLogHandler>=0.8.3,<0.8.99'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    zip_safe=False,
    test_suite='nose.collector',
    cmdclass={'build_api': build_api},
)
