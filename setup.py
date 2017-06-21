import platform
from setuptools import setup, find_packages
import pkg_resources


install_requires = [
    'PyYAML>=3.0,<3.99',
]

def package_installed(pkg):
    """Check if package is installed"""
    req = pkg_resources.Requirement.parse(pkg)
    try:
        pkg_resources.get_provider(req)
    except pkg_resources.DistributionNotFound:
        return False
    else:
        return True

# depend in Pillow if it is installed, otherwise
# depend on PIL if it is installed, otherwise
# require Pillow
if package_installed('Pillow'):
    install_requires.append('Pillow !=2.4.0')
elif package_installed('PIL'):
    install_requires.append('PIL>=1.1.6,<1.2.99')
else:
    install_requires.append('Pillow !=2.4.0')

if platform.python_version_tuple() < ('2', '6'):
    # for mapproxy-seed
    install_requires.append('multiprocessing>=2.6')

def long_description(changelog_releases=10):
    import re
    import textwrap

    readme = open('README.rst').read()
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
        See https://raw.github.com/mapproxy/mapproxy/master/CHANGES.txt
        '''))
    return readme + ''.join(changes)

setup(
    name='MapProxy',
    version="1.10.2",
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
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    zip_safe=False,
    test_suite='nose.collector',
)
