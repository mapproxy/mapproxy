import scriptine
from scriptine import path
from scriptine.shell import backtick_, sh

PACKAGE_NAME = 'MapProxy'
REMOTE_DOC_LOCATION = 'mapproxy.org:/opt/www/mapproxy.org/docs'
REMOTE_REL_LOCATION = 'mapproxy.org:/opt/www/mapproxy.org/static/rel'

VERSION_FILES = [
    ('setup.py', 'version="###"'),
    ('doc/conf.py', "version = '##'"),
    ('doc/conf.py', "release = '###'"),
]

def version_command():
    print version()

def prepare_command(tag=""):
    sh('python setup.py egg_info -D -b "%s"' % tag)

def version():
    package_name = PACKAGE_NAME
    version = backtick_('grep Version: %(package_name)s.egg-info/PKG-INFO' % locals())
    version = version.split(':')[-1].strip()
    return version

def clean_all_command():
    path('build/').rmtree(ignore_errors=True)
    for pyc in path.cwd().walkfiles('*.pyc'):
        pyc.remove()

def bump_version_command(version):
    short_version = '.'.join(version.split('.')[:2])
    for filename, replace in VERSION_FILES:
        if '###' in replace:
            search_for = replace.replace('###', '[^\'"]+')
            replace_with = replace.replace('###', version)
        else:
            search_for = replace.replace('##', '[^\'"]+')
            replace_with = replace.replace('##', short_version)

        search_for = search_for.replace('"', '\\"')
        replace_with = replace_with.replace('"', '\\"')
        sh('''perl -p -i -e "s/%(search_for)s/%(replace_with)s/" %(filename)s ''' % locals())

    prepare_command()

def build_docs_command():
    sh('python setup.py build_sphinx')
    ver = version()
    package_name = PACKAGE_NAME
    sh("tar -c -v -z -C build/sphinx/ -f dist/%(package_name)s-docs-%(ver)s.tar.gz -s "
       "'/^html/%(package_name)s-docs-%(ver)s/' html"
        % locals())

def upload_docs_command():
    ver = version()
    remote_doc_location = REMOTE_DOC_LOCATION
    sh('rsync -a -v -P -z build/sphinx/html/ %(remote_doc_location)s/%(ver)s' % locals())

def build_sdist_command():
    sh('python setup.py egg_info -b "" -D sdist')

def build_wheel_command():
    sh('python setup.py egg_info -b "" -D bdist_wheel')

def upload_sdist_command():
    sh('python setup.py egg_info -b "" -D sdist')
    ver = version()
    remote_rel_location = REMOTE_REL_LOCATION
    sh('scp dist/MapProxy-%(ver)s.* %(remote_rel_location)s' % locals())

def upload_test_sdist_command():
    date = backtick_('date +%Y%m%d').strip()
    print('python setup.py egg_info -R -D -b ".dev%s" register -r testpypi sdist upload -r testpypi' % (date, ))

def check_uncommited():
    if sh('git diff-index --quiet HEAD --') != 0:
        print('ABORT: uncommited changes. please commit (and tag) release version number')
        sys.exit(1)

def upload_final_sdist_command():
    check_uncommited()
    build_sdist_command()
    ver = version()
    sh('twine upload dist/MapProxy-%(ver)s.tar.gz' % locals())

def upload_final_wheel_command():
    check_uncommited()
    build_wheel_command()
    ver = version()
    sh('twine upload dist/MapProxy-%(ver)s-py2.py3-none-any.whl' % locals())

def link_latest_command(ver=None):
    if ver is None:
        ver = version()
    host, path = REMOTE_DOC_LOCATION.split(':')
    sh('ssh %(host)s "cd %(path)s && rm latest && ln -s %(ver)s latest"' % locals())


def update_deb_command():
    import email.utils
    import time
    changelog_entry_template = """mapproxy (%(version)s) unstable; urgency=low

  * New upstream release.

 -- %(user)s <%(email)s>  %(time)s

"""
    with open('debian/changelog') as f:
        old_changelog = f.read()

    changelog = changelog_entry_template % {
        'version': version(),
        'user': backtick_('git config --get user.name').strip(),
        'email': backtick_('git config --get user.email').strip(),
        'time': email.utils.formatdate(time.time(), True),
    }
    changelog += old_changelog
    with open('debian/changelog', 'w') as f:
        f.write(changelog)

if __name__ == '__main__':
    scriptine.run()
