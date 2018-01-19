#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess

import os

import android_sdk
from enum import Enum, unique


@unique
class Mode(Enum):
    INSTALL = "Installation"
    UNINSTALL = "Uninstallation"


def _prepare_output(raw_output: bytes) -> list:
    output = []
    if raw_output:
        raw_output = raw_output.decode().split('\n')
        [output.append(line.strip()) for line in raw_output if line not in ('', '\r', '\n', '\t')]
    return output


def _execute_command(args: list) -> list:
    raw_output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return _prepare_output(raw_output.stdout)


def _get_device_descriptions(args: list) -> dict:
    res = {}
    for arg in args:
        pair = arg.split(':')
        res[pair[0]] = pair[1]
    return res


class AndroidAdb(object):
    def __init__(self, path: str, exceptions: bool=False) -> None:
        self.__adb = os.path.expandvars(path)
        self.__device = None
        self.__exceptions = exceptions

    def get_devices(self) -> list:
        output = _execute_command([self.__adb, 'devices', '-l'])
        devices = []
        for line in output:
            if not any([line.startswith('List of'), line.startswith('*')]):
                device_dict = {}

                serial_type_desc = line.split('   ')
                d_serial = serial_type_desc[0]
                d_type_desc = serial_type_desc[1].split(' ')
                d_type = d_type_desc[0]
                d_desc = _get_device_descriptions(d_type_desc[1:])
                device_dict['serial'] = d_serial
                device_dict['type'] = d_type
                device_dict['description'] = d_desc
                devices.append(device_dict)
        if not devices:
            if self.__exceptions:
                raise RuntimeError("Devices not found")
        return devices

    def set_device(self, serial: str) -> None:
        self.__device = serial

    def install(self, apk_file: str, serial: str=None, replace: bool=False, downgrade: bool=False,
                permissions: bool=False, auto_permissions: str=None, allow_test: bool=False,
                sdcard: bool=False) -> dict:
        command = ['install']
        if replace:
            command.append('-r')
        if downgrade:
            command.append('-d')
        if permissions:
            command.append('-g')
        if auto_permissions:
            pass
            # TODO: Добавить автоматический -g для Android 6+
        if allow_test:
            command.append('-t')
        if sdcard:
            command.append('-s')
        command.append(apk_file)

        output = self.__execute_adb_command(*command, serial=serial)
        return self.__check_install_remove(output, Mode.INSTALL)

    def uninstall(self, package: str) -> dict:
        output = self.__execute_adb_command('uninstall', package)
        return self.__check_install_remove(output, Mode.UNINSTALL)

    def __execute_adb_command(self, *args, **kwargs) -> list:
        command = [self.__adb]
        serial = kwargs.get('serial', self.__device)
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        return _execute_command(command)

    def __check_install_remove(self, output: list, command: Mode) -> dict:
        command_result = {"Message": output[-1].split(' ')[-1]}
        if output[-1] == 'Success':
            command_result["Success"] = True
        else:
            if self.__exceptions:
                raise RuntimeError("%s error: %s" % (command.value, command_result.get("Message")))
            command_result["Success"] = False
        return command_result


if __name__ == '__main__':
    sdk = android_sdk.AndroidSdk(path='%ANDROID_HOME%', auto_set=['adb'])
    adb = AndroidAdb(sdk.get_adb())
    device = adb.get_devices()[0].get('serial')
    print("Device:", device)
    adb.set_device(device)

    res = adb.install(r'D:\!\SDK_Android\KL_Mobile_SDK_Android_Example_5.2.0.601_Release.apk', replace=True)
    print("App is installed:", res)
    res = adb.install(r'D:\!\SDK_Android\KL_Mobile_SDK_Android_Example_5.2.0.601_Release.apk', replace=True)
    print("App is installed:", res)
    res = adb.uninstall('com.kavsdkexample')
    print("App is removed:", res)
    res = adb.install(r'D:\!\SDK_Android\KL_Mobile_SDK_Android_Example_5.2.0.601_Release.apk')
    print("App is installed:", res)
    res = adb.install(r'D:\!\SDK_Android\KL_Mobile_SDK_Android_Example_5.2.0.601_Release.apk')
    print("App is installed:", res)
    res = adb.uninstall('com.kavsdkexample')
    print("App is removed:", res)