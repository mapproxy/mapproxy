from setuptools import setup, find_packages


install_requires = [
    'PyYAML>=3.0',
    'future',
    'pyproj>=2',
    'jsonschema>=4',
    'werkzeug<4',
    'Pillow>=8,!=8.3.0,!=8.3.1;python_version=="3.9"',
    'Pillow>=9;python_version=="3.10"',
    'Pillow>=10;python_version=="3.11"',
    'Pillow>=10.1;python_version=="3.12"',
    'Pillow>=11;python_version=="3.13"',
    'lxml>=6',
    'shapely>=2',
    'jinja2',
    'Babel',  # For jinja2
    'python-dateutil',  # For jinja2
    'requests'
]


def long_description(changelog_releases=10):
    import re
    import textwrap

    readme = open('README.md').read()
    changes = ['Changes\n-------\n']
    version_line_re = re.compile(r'^\d\.\d+\.\d+\S*\s20\d\d-\d\d-\d\d')
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
    version="6.0.1",
    description='An accelerating proxy for tile and web map services',
    long_description=long_description(7),
    long_description_content_type='text/x-rst',
    author='Oliver Tonnhofer',
    author_email='olt@omniscale.de',
    maintainer='terrestris GmbH & Co. KG',
    maintainer_email='info@terrestris.de',
    url='https://mapproxy.org',
    license='Apache Software License 2.0',
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'mapproxy-seed = mapproxy.seed.script:main',
            'mapproxy-util = mapproxy.script.util:main',
        ],
    },
    package_data={'': ['*.xml', '*.yaml', '*.ttf', '*.wsgi', '*.ini', '*.json']},
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    zip_safe=False
)
