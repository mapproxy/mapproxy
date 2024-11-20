import os

from mapproxy.test.helper import TempDir, assert_files_in_dir, ChangeWorkingDir, assert_permissions
from mapproxy.util.fs import ensure_directory


class TestFs:
    def test_ensure_directory_absolute(self):
        with TempDir() as dir_name:
            file_path = os.path.join(dir_name, 'a/b/c')
            ensure_directory(file_path)
            assert_files_in_dir(dir_name, ['a'])
            assert_files_in_dir(os.path.join(dir_name, 'a'), ['b'])
            assert_files_in_dir(os.path.join(dir_name, 'a/b'), [])

    def test_ensure_directory_relative(self):
        with TempDir() as dir_name:
            with ChangeWorkingDir(dir_name):
                ensure_directory('./a/b/c')
                assert_files_in_dir(dir_name, ['a'])
                assert_files_in_dir(os.path.join(dir_name, 'a'), ['b'])
                assert_files_in_dir(os.path.join(dir_name, 'a/b'), [])

    def test_ensure_directory_permissions(self):
        with TempDir() as dir_name:
            file_path = os.path.join(dir_name, 'a/b')
            desired_permissions = '700'
            ensure_directory(file_path, directory_permissions=desired_permissions)
            assert_files_in_dir(dir_name, ['a'])
            assert_permissions(os.path.join(dir_name, 'a'), desired_permissions)
