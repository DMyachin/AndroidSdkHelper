#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os


def _path_checker(path: str, obj_type: str, raise_exception=True) -> bool:
    if not isinstance(raise_exception, bool):
        raise AttributeError('Parameter "raise_exception" must be bool')

    if os.path.exists(path):
        if obj_type == "dir":
            if os.path.isdir(path):
                return True
            else:
                if raise_exception:
                    raise IsADirectoryError(f'"{path}" is not a directory')
                else:
                    return False
        elif obj_type == "file":
            if os.path.isfile(path):
                return True
            else:
                if raise_exception:
                    raise FileNotFoundError(f'"{path}" is not file')
                else:
                    return False
        else:
            raise AttributeError(f'Unknown parameter "{obj_type}"')
    else:
        if raise_exception:
            raise OSError(f'Path {path} not exist')
        else:
            return False


class AndroidSdk(object):
    def __init__(self, path=None, auto_set=None, select_last=True):
        self.__util_name = {'adb': 'adb', 'aapt': 'aapt', 'zipalign': 'zipalign', 'emulator': 'emulator'}
        if os.name == 'nt':
            for key in self.__util_name:
                self.__util_name[key] = self.__util_name.get(key) + '.exe'

        self.__sdk = None
        self.__adb = None
        self.__aapt = None
        self.__zipalign = None
        self.__emulator = None
        self.__select_last = select_last

        if path:
            if auto_set is None:
                auto_set = []
            if isinstance(auto_set, list):
                self.set_sdk(path, auto_set)
            else:
                raise AttributeError('Auto_set must be list type')

    def set_sdk(self, path: str, auto_set: list) -> None:
        if _path_checker(path, "dir"):
            self.__sdk = path
            if auto_set:
                self.__auto_set(auto_set)

    def __get_build_tools_dir(self) -> str:
        expected_build_tools = os.path.join(self.__sdk, 'build-tools')
        if _path_checker(expected_build_tools, "dir"):
            internal_dirs = sorted(os.listdir(expected_build_tools))
            if not internal_dirs:
                raise OSError("Build tools not installed")
            elif len(internal_dirs) == 1:
                return os.path.join(expected_build_tools, internal_dirs)
            else:
                if self.__select_last:
                    return os.path.join(expected_build_tools, internal_dirs[-1])
                else:
                    raise ValueError("Build tools has different versions")

    def get_sdk(self) -> str:
        return self.__sdk

    def set_adb(self, path=None) -> None:
        if path:
            if _path_checker(path, "file"):
                self.__adb = path
        else:
            expected_adb_path = os.path.join(self.__sdk, 'platform-tools', self.__util_name.get('adb'))
            if _path_checker(expected_adb_path, "file"):
                self.__adb = expected_adb_path

    def get_adb(self) -> str:
        return self.__adb

    def set_aapt(self, path=None) -> None:
        if path:
            if _path_checker(path, 'file'):
                self.__aapt = path
        else:
            build_tools = self.__get_build_tools_dir()
            expected_aapt = os.path.join(build_tools, self.__util_name.get('aapt'))
            if _path_checker(expected_aapt, 'file'):
                self.__aapt = expected_aapt

    def get_aapt(self) -> str:
        return self.__aapt

    def set_zipalign(self, path=None) -> None:
        if path:
            if _path_checker(path, "file"):
                self.__zipalign = path
        else:
            build_tools = self.__get_build_tools_dir()
            expected_path = os.path.join(build_tools, self.__util_name.get('zipalign'))
            if _path_checker(expected_path, 'file'):
                self.__zipalign = expected_path

    def get_zipalign(self) -> str:
        return self.__zipalign

    def set_emulator(self, path=None) -> None:
        if path:
            if _path_checker(path, 'file'):
                self.__emulator = path
        else:
            expected_path = os.path.join(self.__sdk, 'tools', self.__util_name.get('emulator'))
            if _path_checker(expected_path, 'file'):
                self.__emulator = expected_path

    def get_emulator(self) -> str:
        return self.__emulator

    def __auto_set(self, set_list) -> None:
        for name in set_list:
            if name == 'adb':
                self.set_adb()
            elif name == 'aapt':
                self.set_aapt()
            elif name == 'zipalign':
                self.set_zipalign()
            elif name == 'emulator':
                self.set_emulator()
            else:
                raise AttributeError('Unknown parameter: %s' % name)


if __name__ == '__main__':
    sdk = AndroidSdk("/home/umnik/Android/Sdk", auto_set=['adb'])
    adb = sdk.get_adb()
