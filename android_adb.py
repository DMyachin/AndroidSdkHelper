#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import os
from signal import SIGTERM

import android_sdk
from enum import Enum, unique


@unique
class Mode(Enum):
    INSTALL = "Installation"
    UNINSTALL = "Uninstalling"


def _prepare_output(raw_output: bytes) -> list:
    """
    Сделать из байтов читабельный текст. Будет проведено декодирование, затем разделение строк, затем каждрая строка
    будет проверена на вменяемость. Если проверку проходит — добавляется в список строк, которые будут отданы наружу.
    Перед помещением строки в список у неё откусываются символы перевода строки.

    :param raw_output: типичный выхлоп subprocess.run()/.Popen() без предварительной подготовки
    :return: список читабельных строк без лишнего мусора
    """
    output = []
    if raw_output:
        raw_output = raw_output.decode().split('\n')
        [output.append(line.strip()) for line in raw_output if line not in ('', '\r', '\n', '\t')]
    return output


def _execute_command(args: list, output: bool = True) -> list:
    """
    Выполняет переданную команду и возвращает список строк, которые предварительно были очищены от мусора

    :param args: список аргументов, которые будут переданы subprocess.run()
    :param output: нужен ли вам обратно текстовый выхлоп команды
    :return: список строк, предварительно очищенных от мусора. Если параметр output был False, то список будет пустым
    """
    if output:
        raw_output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return _prepare_output(raw_output.stdout)
    else:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return []


# def _get_device_descriptions(args: list) -> dict:
#     """
#     Нужен для того, чтобы из описания устройства получить словарь. Забейте
#
#     :param args:
#     :return:
#     """
#     res = {}
#     for arg in args:
#         pair = arg.split(':')
#         res[pair[0]] = pair[1]
#     return res


class AndroidAdb(object):
    def __init__(self, path: str, exceptions: bool = False) -> None:
        """
        Получаем adb и работаем с ним

        :param path: путь к adb. Его можно спросить у AndroidSdk()
        :param exceptions: Выбрасывать ли исключения, если что-то идёт сильно не так
        """
        self.__adb = os.path.expandvars(path)
        self.__device = None
        self.__logcat = None
        self.__package = None
        self.__exceptions = exceptions

    def get_devices(self) -> list:
        """
        Получение всех подключенных устройств

        :return: Список подключенных устройств в формате [{'serial': serial, 'description':{key:value}}]
        serial — id устройства, по которому можно делать adb -s
        description — словарь, описывающий устройство, например модель
        Если ни одного устройства не подключено, то будет либо исключение, либо пустой список
        """
        output = _execute_command([self.__adb, 'devices', '-l'])
        devices = []
        for line in output:
            if not any([line.startswith('List of'), line.startswith('*')]):
                device_dict = {}

                serial_type_desc = line.split('   ')
                d_serial = serial_type_desc[0]
                d_type_desc = serial_type_desc[-1].split(' ')
                # d_type = d_type_desc[1]
                # d_desc = _get_device_descriptions(d_type_desc[2:])
                d_desc = dict(x.split(':') for x in d_type_desc[2:])
                device_dict['serial'] = d_serial
                # device_dict['type'] = d_type
                device_dict['description'] = d_desc
                devices.append(device_dict)
        if not devices:
            if self.__exceptions:
                raise RuntimeError("Devices not found")
        return devices

    def set_device(self, serial: str) -> None:
        """
        Сделать устройство дефолтным

        :param serial: id того устройства, которое будет являться устройством по умолчанию
        Если подключено более одного устройства/эмулятора, то adb -s serial будет необходим. Взять serial устройства
        можно из get_devices()[индекс устройства в списке].get('serial')
        """
        self.__device = serial

    def install(self, apk_file: str, serial: str = None, replace: bool = False, downgrade: bool = False,
                permissions: bool = False, auto_permissions: bool = False, allow_test: bool = True,
                sdcard: bool = False) -> dict:
        """
        Установить apk файл на устройство

        :param apk_file: путь к apk
        :param serial: serial устройства. Если его нет, будет читаться тот, что установлен через set_device. Если
        всё равно нет — ключ '-s' использоваться не будет
        :param replace: разрешить ли установку поверх существующего приложения
        :param downgrade: разрешить ли даунгрейд (только для дебажных, вроде)
        :param permissions: автоматически предоставить рантайм пермишены. На Андроид 5 и ниже будут проблемы, т.к.
        тамошний adb не знает ключ -g. В общем случае лучше использовать auto_permissions, который берёт получение
        версии Андроида на себя. Но если вы точно знаете версию заранее, то можете сэкономить пару тактов процессора
        комплюктера и тилипона
        :param auto_permissions: распознать, нужны ли рантайм пермишены и, если да, предоставить их
        :param allow_test: позволять установку приложений с флагом "только для тестирования". В общем случае Студия
        создаёт именно такие приложения
        :param sdcard: устанавить на карту
        :return: словарь {'Success': bool, 'Message': str}. 'Message' есть только в случае проблем установки
        """
        command = ['install']
        if replace:
            command.append('-r')
        if downgrade:
            command.append('-d')
        if permissions:
            command.append('-g')
        if auto_permissions:
            if self.get_sdk_version() > 22:
                if auto_permissions:
                    command.append('-g')
        if allow_test:
            command.append('-t')
        if sdcard:
            command.append('-s')
        command.append(apk_file)

        output = self.__execute_adb_run(*command, serial=serial)
        return self.__check_install_remove(output, Mode.INSTALL)

    def set_package(self, package: str) -> None:
        """
        Задать имя пакета по умолчанию. Если какой-то метод просит, но не требует, передавать имя пакета, то, если
        его не передавать, скрипт передаст то имя, которое будет задано здесь

        :param package:
        """
        self.__package = package

    def uninstall(self, package: str = None) -> dict:
        """
        Удалить пакет с устройства

        :param package: имя пакета. Если предварительно был задан пакет по умолчанию, то можно и не передавать
        :return: словарь {'Success': bool, 'Message': str}. 'Message' есть только в случае проблем удаления
        """
        if not package:
            package = self.__package
            if not package:
                if self.__exceptions:
                    raise ValueError('Need package name')
                else:
                    package = 'null'
        output = self.__execute_adb_run('uninstall', package)
        return self.__check_install_remove(output, Mode.UNINSTALL)

    def dump_logcat(self, log_format: str = 'threadtime') -> list:
        """
        Получить дамп вывода логката. Удобно, если вы предварительно очистили вывод от старых записей

        :param log_format: формат вывода логката. Читайте справку. По умолчанию всё нормас, верьте мне
        :return: список строк логката в заданнм формате
        """
        self.__check_logcat()
        command = ['logcat', '-d']
        if log_format:
            command.extend(['-v', log_format])
        return self.__execute_adb_run(*command)

    def clear_logcat(self) -> None:
        """
        Очистить буфер логката от старых записей

        """
        self.__check_logcat()
        self.__execute_adb_run('logcat', '-c', output=False)

    def start_logcat(self, clear: bool = True, log_format: str = 'threadtime') -> None:
        """
        Начать читать логкат. Чтение будет происходить в отдельном потоке, из которого выхлоп потом можно забрать
         методом read_logcat()

        :param clear: предварительно очистить логкат от старых записей
        :param log_format: формат вывода логката. Читайте справку. По умолчанию всё нормас, верьте мне
        """
        self.__check_logcat()
        if clear:
            self.__check_logcat()
        command = []
        if log_format:
            command.extend(['-v', log_format])
        return self.__execute_adb_popen('logcat', *command)

    def stop_logcat(self) -> None:
        """
        Остановить поток логката, если он ещё жив и освободить ссылку на него. Экономим память, ёпти!
        В целом он нужен только если вы не делали чтение логката, т.к. чтение и так вызывает остановку.

        """
        if self.__logcat is not None:
            if self.__logcat.poll is not None:
                self.__logcat.send_signal(SIGTERM)
            self.__logcat = None

    def read_logcat(self) -> list:
        """
        Прочесть, чего там в логкате накопилось к этому времени и убить поток.

        :return: список строк, по которому можете итерироваться как Гвидо на душу положит
        """
        if self.__logcat is None:
            if self.__exceptions:
                raise RuntimeError('Reading logcat but it not works')

        self.__logcat.send_signal(SIGTERM)
        output = self.__logcat.stdout.read()
        self.stop_logcat()
        if output:
            output = _prepare_output(output)
            return output
        else:
            return []

    def __execute_adb_popen(self, *args, **kwargs) -> None:
        """
        Выполняем команды adb с переданными параметрами в отдельном треде

        :param args: аргументы. Список, кортеж, набор, словарь — это всё 1 аргумент! Так что если у вас итерируемый
        объект, то не забывайте его разворачивать, как мама в дестве учила: *[]
        :param kwargs: именованые аргументы. Пока тут только serial читается, остальные будут пропущены
        """
        command = [self.__adb]
        serial = kwargs.get('serial', self.__device)
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        self.__logcat = subprocess.Popen(command, stdout=subprocess.PIPE)

    def __execute_adb_run(self, *args, output: bool = True, **kwargs) -> list:
        """
        Выполняем команды adb с переданными параметрами в основном треде. И пусть весь мир подождёт

        :param args: аргументы. Список, кортеж, набор, словарь — это всё 1 аргумент! Так что если у вас итерируемый
        объект, то не забывайте его разворачивать, как мама в дестве учила: *[]
        :param output: нужен ли вам выхлоп команды. Если не нужен, то он всё равно будет, но пустым списком. Так что
         проверка вида if output будет False
        :param kwargs: именованые аргументы. Пока тут только serial читается, остальные будут пропущены
        :return: выхлоп в виде списка строк
        """
        command = [self.__adb]
        serial = kwargs.get('serial', self.__device)
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        return _execute_command(command, output=output)

    def __check_install_remove(self, output: list, command: Mode) -> dict:
        """
        Проверяем, успешно ли прошла установка/удаление

        :param output: выхлоп команды install/uninstall в виде списка строк
        :param command: енамчик, по которому можно понять, это была установка или удаление
        :return: словарь {'Success': bool, 'Message': str}. 'Message' есть только в случае проблем установки
        """
        command_result = {"Message": output[-1].split(' ')[-1]}
        if output[-1] == 'Success':
            command_result["Success"] = True
        else:
            if self.__exceptions:
                raise RuntimeError("%s error: %s" % (command.value, command_result.get("Message")))
            command_result["Success"] = False
        return command_result

    def __check_logcat(self, auto_kill: bool = False) -> bool:
        """
        Проверяем, а не использует ли у нас логкат сейчас.

        """
        if self.__logcat is not None:
            if self.__logcat.poll() is not None:
                if self.__exceptions:
                    raise RuntimeError('Previous logcat still working')
                else:
                    if auto_kill:
                        self.__logcat.send_signal(SIGTERM)
                        self.__logcat = None
                        return False
                    UserWarning('Previous logcat still working and will be stops')
                    return True
            else:
                if auto_kill:
                    self.__logcat = None
                    return False
                else:
                    UserWarning('Unexpected self.__logcat condition')
                    return True

    def get_android_version(self) -> str:
        """
        Узнать версию Андроида

        :return: строка с версей Андроида вида '5.1.1'
        """
        return self.get_prop('ro.build.version.release')

    def get_sdk_version(self) -> int:
        """
        Узнать sdk version Андроида

        :return: интовое значение с версией SDK вида 22. Если версию получить не удалось, будет отрицательное число.
        """
        v = self.get_prop('ro.build.version.sdk')
        if v:
            return int(v)
        else:
            return -1

    def get_security_patch(self) -> str:
        """
        Узнать дату патча Андроида

        :return: строка с датой вида '2015-11-01'
        """
        return self.get_prop('ro.build.version.security_patch')

    def get_prop(self, param: str) -> str:
        """
        Получить какой-нибудь property в виде строки

        :param param: название property, типа 'ro.product.locale.language'
        :return: строка со значением. Либо пустая строка, если есть проблемы
        """
        prop = self.__execute_adb_run('shell', 'getprop', param)
        if prop:
            return prop[0]
        else:
            return ''

    def create_activity(self, activity: str, package: str = None, args: list = None) -> None:
        """
        Вызываем активити пакета с заданными аргументами

        :param package: имя пакета. Если опущено, получем то, что было задано через .set_package()
        :param activity: полное имя активити, включая java package, в котором оно лежит
        :param args: список аргументов, которые могут быть нужны для этой активити
        """
        if not package:
            if self.__package is None:
                if self.__exceptions:
                    raise ValueError('Package was not set')
                else:
                    package = 'null'
            else:
                package = self.__package

        command = ['shell', 'am', 'start' '-n', package + '/' + activity]
        command.extend(args)
        self.__execute_adb_run(command, output=False)


if __name__ == '__main__':
    test_sdk_path = '/home/umnik/Android/Sdk'
    sdk = android_sdk.AndroidSdk(test_sdk_path, auto_set=['adb'])
    adb = AndroidAdb(sdk.get_adb())
    device = adb.get_devices()[0]
    print("Device:")
    for key in device:
        if key == 'description':
            for key_d in device.get(key):
                print('\t\t' + key_d + ':', device.get(key).get(key_d))
        else:
            print('\t' + key + ':', device.get(key))
    adb.set_device(device.get('serial'))

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
    adb.stop_logcat()

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
    print('')
    print('=' * 10)

    print('Android version:', adb.get_android_version())
    print('SDK version:', adb.get_sdk_version())
    print('Security patch:', adb.get_security_patch())
    print('')
    print('=' * 10)

    adb.set_package(test_package)
    adb.create_activity(['-a', 'test', '-e', 'key', 'value'])
