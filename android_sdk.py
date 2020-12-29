#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import platform

__version = 1


def get_module_version() -> int:
    return __version


def _check_dir_exist(dir_path: str):
    if not os.path.isdir(dir_path):
        raise NotADirectoryError(f"Directory '{dir_path}' does not exist")


def resolve_sdk_path(custom_path: str = None) -> str:
    if custom_path is None:
        for env in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):  # https://developer.android.com/studio/command-line/variables
            if os.getenv(env) is not None:
                custom_path = env
                break
        if custom_path is None:
            raise ValueError("Environment variable 'ANDROID_SDK_ROOT' does not set. Cannot find Android SDK directory")

    custom_path = os.path.expanduser(os.path.expandvars(custom_path))
    _check_dir_exist(custom_path)
    return custom_path


def _get_bin_name(file_name: str) -> str:
    return file_name + '.exe' if platform.system() == "Windows" else file_name


class AndroidSdk:
    def __init__(self, custom_path: str = None):
        self._sdk_path = resolve_sdk_path(custom_path)

    def get_sdk_dir(self) -> str:
        return self._sdk_path

    def get_build_tools(self) -> str:
        build_tools_dir = os.path.join(self._sdk_path, "build-tools")
        _check_dir_exist(build_tools_dir)
        versions = os.listdir(build_tools_dir)
        sorted(versions, reverse=True)  # from new to old
        for version in versions:
            path = os.path.join(build_tools_dir, version)
            if os.listdir(path):
                return path
        raise FileNotFoundError(f"No any files found in subdirectories under {build_tools_dir}")

    def get_adb(self) -> str:
        return os.path.join(self.get_sdk_dir(), "platform-tools", _get_bin_name("adb"))

    def get_aapt(self) -> str:
        return os.path.join(self.get_build_tools(), _get_bin_name("aapt"))

    def get_apksigner(self) -> str:
        return os.path.join(self.get_build_tools(), _get_bin_name("apksigner"))

    def get_zipalign(self) -> str:
        return os.path.join(self.get_build_tools(), _get_bin_name("zipalign"))
