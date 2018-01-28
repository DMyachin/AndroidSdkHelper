#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os


def _path_checker(path: str, obj_type: str) -> bool:
    """
    Проверяем переданные пути к фалам и папкам

    :param path: сам путь к файлу или папке. Переменные окружения разрешены
    :param obj_type: что передали то — файл или папку?
    :return:
    """
    path = os.path.expandvars(path)
    if os.path.exists(path):
        if obj_type == "dir":
            if os.path.isdir(path):
                return True
            else:
                raise IsADirectoryError(f'"{path}" is not a directory')
        elif obj_type == "file":
            if os.path.isfile(path):
                return True
            else:
                raise FileNotFoundError(f'"{path}" is not file')
        else:
            raise AttributeError(f'Unknown parameter "{obj_type}"')
    else:
        raise OSError(f'Path {path} not exist')


class AndroidSdk(object):
    def __init__(self, path: str = None, auto_set: list = None, select_last: bool = True) -> None:
        """
        Конструктор, чё тут ещё сказать

        :param path: путь к SDK. Переменные окружения разрешены. Если путь не передать, то его потом можно установить
         специальным методом класса
        :param auto_set: список утилит, которые нужно автоматически найти (адб, аапт, вот это всё)
        :param select_last: если установлено несколько версий утилит, брать последнюю. Актуально для build-tools
        """
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
                self.set_sdk(os.path.expandvars(path), auto_set)
            else:
                raise AttributeError('Auto_set must be list type')

    def set_sdk(self, path: str, auto_set: list) -> None:
        """
        Задать путь к SDK

        :param path: путь к SDK. Переменные окружения разрешены
        :param auto_set: список утилит, которые нужно автоматически найти (адб, аапт, вот это всё)
        """
        if _path_checker(path, "dir"):
            self.__sdk = path
            if auto_set:
                self.__auto_set(auto_set)

    def __get_build_tools_dir(self) -> str:
        """
        Попытаться найти build-tools, если они нужны

        :return: путь к build-tools/version/
        Где /version/ — вложенная директория
        """
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
        """
        Вспомнить путь к SDK, если вдруг забыли

        :return: путь к SDK
        """
        return self.__sdk

    def set_adb(self, path: str = None) -> None:
        """
        Задать путь к adb, если заранее не делали auto_set=['adb'], хотя вам и предлагали. Ну или если хотите
         его заменить на другой

        :param path: путь к утилите adb, включая её саму
        """
        if path:
            if _path_checker(path, "file"):
                self.__adb = path
        else:
            expected_adb_path = os.path.join(self.__sdk, 'platform-tools', self.__util_name.get('adb'))
            if _path_checker(expected_adb_path, "file"):
                self.__adb = expected_adb_path

    def get_adb(self) -> str:
        """
        Вспомнить da way к adb, если вдруг забыли. Ну или узнать, если он был установлен автоматически

        :return: путь к adb
        """
        return self.__adb

    def set_aapt(self, path: str = None) -> None:
        """
        Задать путь к aapt, если заране не сделали auto_set=['aapt'], хотя вам и предлагали. Ну, либо вы хотите заменить
         его на другой

        :param path: путь к утилите appt, включая её саму
        """
        if path:
            if _path_checker(path, 'file'):
                self.__aapt = path
        else:
            build_tools = self.__get_build_tools_dir()
            expected_aapt = os.path.join(build_tools, self.__util_name.get('aapt'))
            if _path_checker(expected_aapt, 'file'):
                self.__aapt = expected_aapt

    def get_aapt(self) -> str:
        """
        Получить путь к aapt

        :return: путь к aapt
        """
        return self.__aapt

    def set_zipalign(self, path: str = None) -> None:
        """
        Задать путь к утилите zipalign, либо заменить на новый

        :param path: путь к утилите, включая её саму
        """
        if path:
            if _path_checker(path, "file"):
                self.__zipalign = path
        else:
            build_tools = self.__get_build_tools_dir()
            expected_path = os.path.join(build_tools, self.__util_name.get('zipalign'))
            if _path_checker(expected_path, 'file'):
                self.__zipalign = expected_path

    def get_zipalign(self) -> str:
        """
        Получить путь к утилите zipalign

        :return: путь к утилите zipalign
        """
        return self.__zipalign

    def set_emulator(self, path: str = None) -> None:
        """
        Задать путь к утилите emulator

        :param path: путь к утилите, включая сам файл emulator
        """
        if path:
            if _path_checker(path, 'file'):
                self.__emulator = path
        else:
            expected_path = os.path.join(self.__sdk, 'tools', self.__util_name.get('emulator'))
            if _path_checker(expected_path, 'file'):
                self.__emulator = expected_path

    def get_emulator(self) -> str:
        """
        Получить путь к утилите emulator

        :return: путь к утилите emulator
        """
        return self.__emulator

    def __auto_set(self, set_list: list) -> None:
        """
        Попытаться автоматически найти утилиты, названия которых переданы в списке

        :param set_list: названия утилит без расширений в виде списка
        """
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
    sdk = AndroidSdk("/home/umnik/Android/Sdk", auto_set=['adb', 'aapt'])
    adb = sdk.get_adb()
    print(adb)
    aapt = sdk.get_aapt()
    print(aapt)
