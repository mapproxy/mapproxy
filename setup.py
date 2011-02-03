import os
import sys
import platform
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

install_requires = [
    'setuptools>=0.6c9',
    'Paste>=1.7.2,<1.7.99',
    'PasteDeploy>=1.3.3,<1.3.99',
    'PasteScript>=1.7.3,<1.7.99',
]

if platform.system() != "Java":
    if platform.python_version_tuple() < ('2', '6'):
        install_requires.append('multiprocessing>=2.6')
    install_requires.extend([
        'PIL>=1.1.6,<1.2.99',
        'PyYAML>=3.0,<3.99',
    ])

setup(
    name='MapProxy',
    version="1.0.0",
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
            'mapproxy-seed = mapproxy.seed.script:main',
            'mapproxy-cleanup = mapproxy.seed.script:cleanup_main',
        ],
        'paste.app_factory': [
            'app = mapproxy.wsgiapp:app_factory',
            'multiapp = mapproxy.multiapp:app_factory'
        ],
        'paste.paster_create_template': [
            'mapproxy_conf=mapproxy.config_template:PasterConfigurationTemplate'
        ],
        'paste.filter_factory': [
            'lighttpd_root_fix = mapproxy.util.wsgi:lighttpd_root_fix_filter_factory',
        ],
    },
    package_data = {'': ['*.xml', '*.yaml', '*.ttf']},
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    zip_safe=False,
    test_suite='nose.collector',
    cmdclass={'build_api': build_api},
)
