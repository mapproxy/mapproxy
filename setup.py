import platform
from setuptools import setup, find_packages

install_requires = [
    'PIL>=1.1.6,<1.2.99',
    'PyYAML>=3.0,<3.99',
]

if platform.python_version_tuple() < ('2', '6'):
    # for mapproxy-seed
    install_requires.append('multiprocessing>=2.6')

def long_description(changelog_releases=10):
    import re
    import textwrap

    readme = open('README.txt').read()
    changes = ['Changes\n-------\n']
    version_line_re = re.compile('^\d\.\d+\.\d+\S*\s20\d\d-\d\d-\d\d')
    for line in open('CHANGES.txt'):
        if version_line_re.match(line):
            if changelog_releases == 0:
                break
            changelog_releases -= 1
        changes.append(line)
    
    changes.append(textwrap.dedent('''
        Older changes
        -------------
        See https://bitbucket.org/olt/mapproxy/src/default/CHANGES.txt
        '''))
    return readme + ''.join(changes)

setup(
    name='MapProxy',
    version="1.1.3a",
    description='An accelerating proxy for web map services',
    long_description=long_description(7),
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
