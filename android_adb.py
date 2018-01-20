#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import os
import android_sdk
from enum import Enum, unique


@unique
class Mode(Enum):
    INSTALL = "Installation"
    UNINSTALL = "Uninstalling"


def _prepare_output(raw_output: bytes) -> list:
    output = []
    if raw_output:
        raw_output = raw_output.decode().split('\n')
        [output.append(line.strip()) for line in raw_output if line not in ('', '\r', '\n', '\t')]
    return output


def _execute_command(args: list, output: bool = True) -> list:
    if output:
        raw_output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return _prepare_output(raw_output.stdout)
    else:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return []


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
        self.__logcat = None
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

        output = self.__execute_adb_run(*command, serial=serial)
        return self.__check_install_remove(output, Mode.INSTALL)

    def uninstall(self, package: str) -> dict:
        output = self.__execute_adb_run('uninstall', package)
        return self.__check_install_remove(output, Mode.UNINSTALL)

    def dump_logcat(self, log_format: str = 'threadtime') -> list:
        self.__check_logcat()
        command = ['logcat', '-d']
        if log_format:
            command.extend(['-v', log_format])
        return self.__execute_adb_run(*command)

    def clear_logcat(self) -> None:
        self.__check_logcat()
        self.__execute_adb_run('logcat', '-c', output=False)

    def start_logcat(self, clear: bool = True, log_format: str = 'threadtime') -> None:
        self.__check_logcat()
        if clear:
            self.__check_logcat()
        command = []
        if log_format:
            command.extend(['-v', log_format])
        return self.__execute_adb_popen('logcat', *command)

    def stop_logcat(self) -> None:
        if self.__logcat.poll is not None:
            self.__logcat.terminate()
        self.__logcat = None

    def read_logcat(self, timeout: int = 2) -> list:
        out = b''
        if self.__logcat is None:
            if self.__exceptions:
                raise RuntimeError('Unexpected reading logcat but it not works')
        try:
            out, err = self.__logcat.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.__logcat.terminate()
            out, err = self.__logcat.communicate()
        finally:
            if out:
                out = _prepare_output(out)
                return out
            else:
                return []
        # output = self.__logcat.stdout.read()
        # if output:
        #     output = _prepare_output(output)
        #     return output
        # else:
        #     return []

    def __execute_adb_popen(self, *args, **kwargs) -> None:
        command = [self.__adb]
        serial = kwargs.get('serial', self.__device)
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        self.__logcat = subprocess.Popen(command, stdout=subprocess.PIPE)

    def __execute_adb_run(self, *args, output: bool = True, **kwargs) -> list:
        command = [self.__adb]
        serial = kwargs.get('serial', self.__device)
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        return _execute_command(command, output=output)

    def __check_install_remove(self, output: list, command: Mode) -> dict:
        command_result = {"Message": output[-1].split(' ')[-1]}
        if output[-1] == 'Success':
            command_result["Success"] = True
        else:
            if self.__exceptions:
                raise RuntimeError("%s error: %s" % (command.value, command_result.get("Message")))
            command_result["Success"] = False
        return command_result

    def __check_logcat(self) -> None:
        if self.__logcat is not None:
            if self.__logcat.poll() is not None:
                if self.__exceptions:
                    raise RuntimeError('Previous logcat still working')
                else:
                    UserWarning('Previous logcat still working and will be stops')
                    self.__logcat.terminate()
            else:
                UserWarning('Unexpected self.__logcat condition')


if __name__ == '__main__':
    test_sdk_path = '/home/umnik/Android/Sdk'
    sdk = android_sdk.AndroidSdk(test_sdk_path, auto_set=['adb'])
    adb = AndroidAdb(sdk.get_adb())
    device = adb.get_devices()[0].get('serial')
    print("Device:", device)
    adb.set_device(device)

    adb.start_logcat()
    test_apk = r'/home/umnik/Documents/Work/Android/CLSDKExample/app/build/outputs/apk/app-debug.apk'
    test_package = 'com.kaspersky.clsdkexample'
    res = adb.install(test_apk, replace=True)
    print("App is installed:", res)
    res = adb.install(test_apk, replace=True)
    print("App is installed:", res)
    res = adb.uninstall(test_package)
    print("App is removed:", res)
    res = adb.install(test_apk)
    print("App is installed:", res)
    res = adb.install(test_apk)
    print("App is installed:", res)
    res = adb.uninstall(test_package)
    print("App is removed:", res)
    logcat = adb.read_logcat()
    for line in logcat:
        print(line)

    print('')
    print('=' * 10)
    adb.clear_logcat()
    res = adb.install(test_apk, replace=True)
    print("App is installed:", res)
    res = adb.install(test_apk, replace=True)
    print("App is installed:", res)
    res = adb.uninstall(test_package)
    print("App is removed:", res)
    res = adb.install(test_apk)
    print("App is installed:", res)
    res = adb.install(test_apk)
    print("App is installed:", res)
    res = adb.uninstall(test_package)
    print("App is removed:", res)
    logcat = adb.dump_logcat()
    for line in logcat:
        print(line)
