import platform

is_jython = platform.system() == 'Java'
is_cpython = not is_jython
