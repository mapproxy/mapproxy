import platform
from setuptools import setup, find_packages

install_requires = [
    'PIL>=1.1.6,<1.2.99',
    'PyYAML>=3.0,<3.99',
]

if platform.python_version_tuple() < ('2', '6'):
    # for mapproxy-seed
    install_requires.append('multiprocessing>=2.6')

setup(
    name='MapProxy',
    version="1.1.2a",
    description='An accelerating proxy for web map services',
    long_description=open('README.txt').read(),
    author='Oliver Tonnhofer',
    author_email='olt@omniscale.de',
    url='http://mapproxy.org',
    license='Apache Software License 2.0',
    namespace_packages = ['mapproxy'],
    packages=find_packages(),
    include_package_data=True,
    entry_points = {
        'console_scripts': [
            'mapproxy-seed = mapproxy.seed.script:main',
            'mapproxy-util = mapproxy.script.util:main',
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
    package_data = {'': ['*.xml', '*.yaml', '*.ttf', '*.wsgi', '*.ini']},
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
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
)
