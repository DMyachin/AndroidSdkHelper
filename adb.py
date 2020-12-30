#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
from typing import List

import android_sdk

if android_sdk.get_module_version() < 1:
    raise ImportError("SDK module version too low")

list_str = List[str]

__version = 1


def get_module_version() -> int:
    return __version


def _get_adb(sdk_path: str) -> str:
    adb = android_sdk.AndroidSdk(sdk_path).get_adb()
    android_sdk.check_util_exists(adb)
    return adb


def _prepare_output(output: bytes) -> list_str:
    result = []
    output = output.decode(encoding="utf-8", errors="replace").split('\n')
    [result.append(line.strip()) for line in output if line not in ('', '\r', '\n', '\t')]
    return output


class Adb:
    def __init__(self, custom_sdk_path: str = None):
        self._adb = _get_adb(custom_sdk_path)
        self._device = None
        self._shell = None

    def _execute_shell_command(self, *args) -> list_str:
        cmd = subprocess.run((*self.get_shell(), *args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return _prepare_output(cmd.stdout)

    def set_device(self, serial: str):
        self._device = serial

    def get_shell(self) -> list_str:
        if self._shell is None:
            self._shell = [self._adb]
            if self._device:
                self._shell.extend(["-s", self._device])
            self._shell.append("shell")
        return self._shell

    def get_properties(self, prop: str) -> str:
        return self._execute_shell_command("getprop", prop)[0]
