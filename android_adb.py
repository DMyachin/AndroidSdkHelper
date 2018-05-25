#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import subprocess
import time
from enum import Enum, unique

import android_sdk


@unique
class Mode(Enum):
    INSTALL = "Installation"
    UNINSTALL = "Uninstalling"


class AdbError(Exception):
    def __init__(self) -> None:
        pass


class DeviceNotFoundError(AdbError):
    def __init__(self, message: str) -> None:
        self.message = message


class PackageManagerError(AdbError):
    def __init__(self) -> None:
        pass


class PackageNameError(PackageManagerError):
    def __init__(self, message: str) -> None:
        self.message = message


class InstallRemoveError(PackageManagerError):
    def __init__(self, message: str) -> None:
        self.message = message


class LogcatError(AdbError):
    def __init__(self) -> None:
        pass


class LogcatNotDefinedError(LogcatError):
    def __init__(self, message: str) -> None:
        self.message = message


class LogcatWorkingError(LogcatError):
    def __init__(self, message: str) -> None:
        self.message = message


class AndroidEnvironmentError(AdbError):
    def __init__(self, message: str) -> None:
        self.message = message


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


def __process_la(ls_la_lines: list) -> list:
    """Разбираем выхлоп ls -la на группы

    :param ls_la_lines: выхлоп комады ls -la в виде списка строк
    :return: список из словарей с ключами:
     права, количество ссылок на объект, владелец, группа, размер, дата, время, имя
    """
    pattern = re.compile('^([drwx-]*) +(\d*) *(\w+) +(\w+) *(\d*) +([\d\-]+) +([\d:]+) (.*)$')
    result = []
    description = {}
    for string in ls_la_lines:
        match = re.match(pattern, string)
        if match is not None:
            if not string.endswith('.'):
                description['rights'] = match.group(1)
                description['links'] = match.group(2)
                description['owner'] = match.group(3)
                description['group'] = match.group(4)
                description['size'] = match.group(5)
                description['date'] = match.group(6)
                description['time'] = match.group(7)
                description['name'] = match.group(8)
                result.append(description)
    return result


def _parse_la(la_result: list) -> tuple:
    """
    Разбор строк для ls -la, дабы отделить полезные данные от ошибок

    :param la_result: список строк, которые отдаёт ls -la
    :return: кортеж из строк с информацией типа времени и имени и список файлов с ошибкой доступа
    """
    errors = []
    ok_strings = []
    for la in la_result:
        if any([la.endswith('Permission denied'), la.endswith('No such file or directory')]):
            errors.append((la.split(': ')[-2], la.split(': ')[-1]))
        else:
            ok_strings.append(la)
    if ok_strings:
        ok_strings = __process_la(ok_strings)
    return ok_strings, errors


def _check_install_remove(output: list, command: Mode) -> dict:
    """
    Проверяем, успешно ли прошла установка/удаление

    :param output: выхлоп команды install/uninstall в виде списка строк
    :param command: енамчик, по которому можно понять, это была установка или удаление
    :return: словарь {'Success': bool, 'Message': str}. 'Message' есть только в случае проблем установки
    """
    command_result = {}
    for line in output:
        if 'Success' in line:
            command_result["Success"] = True
        elif 'Failure' in line:
            command_result = {"Message": line.split(' ')[-1]}
            raise InstallRemoveError(command.value + ' error: ' + command_result["Message"])
    return command_result


class AndroidAdb(object):
    def __init__(self, path: str) -> None:
        """
        Получаем adb и работаем с ним

        :param path: путь к adb. Его можно спросить у AndroidSdk()
        """
        self.__adb = os.path.expanduser(os.path.expandvars(path))
        self.__device = None
        self.__logcat = None
        self.__package = None
        self.__exit_lines = None

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
            raise DeviceNotFoundError('Devices not found')
        return devices

    def set_device(self, serial: str) -> None:
        """
        Сделать устройство дефолтным

        :param serial: id того устройства, которое будет являться устройством по умолчанию
        Если подключено более одного устройства/эмулятора, то adb -s serial будет необходим. Взять serial устройства
        можно из get_devices()[индекс устройства в списке].get('serial')
        """
        self.__device = serial

    def set_package(self, package: str) -> None:
        """
        Задать имя пакета по умолчанию. Если какой-то метод просит, но не требует, передавать имя пакета, то, если
        его не передавать, скрипт передаст то имя, которое будет задано здесь

        :param package:
        """
        self.__package = package

    def reconnect_device(self) -> None:
        """
        Переподключить устройство

        """
        self.__execute_adb_run('reconnect')

    def install(self, apk_file: str, replace: bool = False, downgrade: bool = False,
                permissions: bool = False, auto_permissions: bool = False, allow_test: bool = True,
                sdcard: bool = False) -> dict:
        """
        Установить apk файл на устройство

        :param apk_file: путь к apk
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
        elif auto_permissions:
            if self.get_sdk_version() > 22:
                if auto_permissions:
                    command.append('-g')
        if allow_test:
            command.append('-t')
        if sdcard:
            command.append('-s')
        command.append(apk_file)

        output = self.__execute_adb_run(*command)
        return _check_install_remove(output, Mode.INSTALL)

    def is_installed(self, package: str = None) -> bool:
        """
        Проверить, установлен ли пакет
        :param package: пакет, который нужно проверить. Если пакет не передан, используем тот, что был задан по
         умолчанию. Если пакет по умолчанию не установлен — ловим искллючение
        :return: булевое установлен или нет
        """
        command = ['list', 'packages']
        if package is None:
            if self.__package is not None:
                package = self.__package
            else:
                raise PackageNameError('Package name not defined')

        pm_lines = self.execute_pm(*command)
        if 'package:' + package in pm_lines:
            return True
        else:
            return False

    def uninstall(self, package: str = None) -> dict:
        """
        Удалить пакет с устройства

        :param package: имя пакета. Если предварительно был задан пакет по умолчанию, то можно и не передавать
        :return: словарь {'Success': bool, 'Message': str}. 'Message' есть только в случае проблем удаления
        """
        if not package:
            package = self.__package
            if not package:
                raise PackageNameError('Package name not defined')
        output = self.__execute_adb_run('uninstall', package)
        return _check_install_remove(output, Mode.UNINSTALL)

    def execute_pm(self, *args, output: bool = True) -> list:
        """
        Выполняет переданные менеджеру пакетов команды

        :param args: аргументы
        :param output: нужен ли результат выполнения команды в виде списка строк
        :return:
        """
        return self.adb_shell_run('pm', *args, output=output)

    def start_logcat(self, clear: bool = True, log_format: str = 'threadtime') -> None:
        """
        Начать читать логкат. Чтение будет происходить в отдельном потоке, из которого потом нужно будет забрать данные

        :param clear: предварительно очистить логкат от старых записей
        :param log_format: формат вывода логката. Читайте справку. По умолчанию всё нормас, верьте мне
        """
        self.__check_logcat()
        if clear:
            self.clear_logcat()
        command = []
        if log_format:
            command.extend(['-v', log_format])
        return self.__execute_adb_popen('logcat', *command)

    def dump_logcat(self, log_format: str = 'threadtime') -> list:
        """
        Получить дамп вывода логката. Удобно, если вы предварительно очистили вывод от старых записей

        :param log_format: формат вывода логката. Читайте справку. По умолчанию всё нормас, верьте мне
        :return: список строк логката
        """
        self.__check_logcat()
        command = ['logcat', '-d']
        if log_format:
            command.extend(['-v', log_format])
        results = self.__execute_adb_run(*command)
        self.stop_logcat()
        return results

    def clear_logcat(self) -> None:
        """
        Очистить буфер логката от старых записей

        """
        self.__check_logcat()
        self.__execute_adb_run('logcat', '-c', output=False)

    def stop_logcat(self) -> None:
        """
        Остановить поток логката, если он ещё жив и освободить ссылку на него.
         Нужно только если вы не делали чтение логката.

        """
        if self.__logcat is not None:
            if self.__logcat.poll is not None:
                self.__logcat.terminate()
                time.sleep(2)
        self.__logcat = None

    def read_logcat(self, timeout: int = None) -> list:
        """
        Прочесть, чего там в логкате накопилось к этому времени и убить поток.

        :return: список строк, по которому можете итерироваться как Гвидо на душу положит
        """
        if self.__logcat is None:
            raise LogcatNotDefinedError('Logcat not defined')

        if timeout is None:
            timeout = 3
        try:
            out, err = self.__logcat.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.__logcat.terminate()
            out, err = self.__logcat.communicate()
        self.stop_logcat()
        return _prepare_output(out)

    def read_logcat_while_line(self, end_line: str, start_line: str = None,
                               timeout: int = None, decode: str = 'utf-8') -> list:
        """
        Читать логкат, накапливая строки в списке, пока не встретим какую-то ключевую строку. После этого забираем
        весь накопленный список строк

        :param end_line: ключевая строка, по которой процесс чтения будет прекращён
        :param start_line: ключевая строка, по которой процесс накопления списка строк начнётся. Все строки,
         которые будут в логе до этой ключевой, будут проигнорированы. Если строка не передана, накапливание начнётся
         сразу же
        :param timeout: максимальное время, в секундах, выделяемое на ожидание финальной строки
        :param decode: в какой кодировке декодировать строки. По умолчанию используется utf-8
        :return: список накопленных строк. Пустые строки в список не попадают
        """
        # if self.__logcat is None:
        #     raise LogcatNotDefinedError('Logcat not defined')
        #
        # start_time = time.time()
        # if not timeout:
        #     timeout = float('inf')
        #
        # found = False
        # result = []
        # if start_line is not None:
        #     can_start = False
        # else:
        #     can_start = True
        #
        # while not found:
        #     if time.time() - start_time > timeout:
        #         self.stop_logcat()
        #         raise TimeoutError('Timeout for reading logcat')
        #     else:
        #         log_str = self.__logcat.stdout.readline().decode(decode).strip()
        #         if end_line in log_str:
        #             found = True
        #
        #     if can_start:
        #         if log_str not in ('', '\n', '\r'):
        #             result.append(log_str)
        #     else:
        #         if start_line in log_str:
        #             result.append(log_str)
        #             can_start = True
        #
        # self.stop_logcat()
        # return result
        if start_line is not None:
            start_line = [start_line]
        return self.read_logcat_while_lines([end_line], start_line, timeout, decode)

    def set_logcat_exit_lines(self, lines: list) -> None:
        """
        Заранее (пере)определить строки, по которым возможен выход при чтении логката. Полезно добавлять сюда ключевые
         слова, описывающие, к примеру, падение приложения. Они не являются ожидаемыми, при этом позволят не
         отваливаться по таймауту, а выйти сразу после падения
        :param lines: список ключевых строк
        """
        if isinstance(lines, (list, set, tuple)):
            self.__exit_lines = lines
        else:
            raise TypeError('Expected list or tuple or set but %s got' % type(list))

    def clear_logcat_exit_lines(self) -> None:
        """
        Очистить дополнительный список строк, при появлении которых в логкате, мы бы оттуда сразу вышли
        """
        self.__exit_lines = None

    def read_logcat_while_lines(self, end_lines: list, start_lines: list = None, timeout: int = None,
                                decode: str = 'utf-8') -> list:
        """
        Читать логкат, накапливая строки в списке, пока не встретим какую-то ключевую строку из переданного списока
         строк. Вы можете определить и свои строки, которые ожидаете и, например, ключевые строчки, связанные с
         падениями и иными внезапными завершениями. Если будет встречена любая строка из списка, забираем накопленый лог

        :param end_lines: список ключевых строк, по которым нужно прекратить чтение логката и предоставить накопленный
         список строк. Список автоматически расширяется теми строками, которые были переданы методу
         set_logcat_exit_lines(). Дублирующие ключевые слова будут автоматически удалены
        :param start_lines: список ключевых строк, с которых нужно начать накапливать строки. Если его нет, то строки
         будут накапливаться с первой же
        :param timeout: максимальное время в секундах, выделенное на ожидание финальной строки
        :param decode: кодировка для декодирования строк. По умолчанию utf-8
        :return: список накопленных строк
        """
        if self.__logcat is None:
            raise LogcatNotDefinedError('Logcat not defined')

        start_time = time.time()

        if start_lines:
            pattern_start = re.compile('|'.join(start_lines))
        else:
            pattern_start = None

        if self.__exit_lines is not None:
            end_lines += self.__exit_lines
        pattern_end = re.compile('|'.join(set(end_lines)))
        found = False
        result = []
        if start_lines is not None:
            can_start = False
        else:
            can_start = True

        while not found:
            if timeout is not None:
                if time.time() - start_time > timeout:
                    self.stop_logcat()
                    raise TimeoutError('Timeout for reading logcat')
            log_str = self.__logcat.stdout.readline().decode(decode).strip()
            if not can_start:
                if re.search(pattern_start, log_str):
                    can_start = True
            if can_start:
                if log_str not in ('', '\n', '\r'):
                    result.append(log_str)
            if re.search(pattern_end, log_str):
                found = True
        self.stop_logcat()
        return result

    def __execute_adb_popen(self, *args) -> None:
        """
        Выполняем команды adb с переданными параметрами в отдельном треде

        :param args: аргументы. Список, кортеж, набор, словарь — это всё 1 аргумент! Так что если у вас итерируемый
        объект, то не забывайте его разворачивать, как мама в дестве учила: *[]
        """
        command = [self.__adb]
        serial = self.__device
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        self.__logcat = subprocess.Popen(command, stdout=subprocess.PIPE)

    def __execute_adb_run(self, *args, output: bool = True, ) -> list:
        """
        Выполняем команды adb с переданными параметрами в основном треде. И пусть весь мир подождёт

        :param args: аргументы. Список, кортеж, набор, словарь — это всё 1 аргумент! Так что если у вас итерируемый
        объект, то не забывайте его разворачивать, как мама в дестве учила: *[]
        :param output: нужен ли вам выхлоп команды. Если не нужен, то он всё равно будет, но пустым списком. Так что
         проверка вида if output будет False
        :return: выхлоп в виде списка строк
        """
        command = [self.__adb]
        serial = self.__device
        if serial is not None:
            command.extend(['-s', serial])
        command.extend([*args])
        return _execute_command(command, output=output)

    def __check_logcat(self, auto_kill: bool = False) -> bool:
        """
        Проверяем, а не использует ли у нас логкат сейчас.

        :type auto_kill: булевое рибивать ли процесс логката, если он не был убит в прошлый раз или выбросить исключение
        :return: булевое жив ли процесс на данный момент
        """
        if self.__logcat is not None:
            if self.__logcat.poll() is not None:
                if auto_kill:
                    self.stop_logcat()
                    return False
                else:
                    raise LogcatWorkingError('Previous logcat still working')
            else:
                if auto_kill:
                    self.__logcat = None
                    return False
                else:
                    return True
        return False

    def get_android_version(self) -> str:
        """
        Узнать версию Андроида

        :return: строка с версей Андроида вида '5.1.1'
        """
        return self.get_prop('ro.build.version.release')

    def get_sdk_version(self) -> int:
        """
        Узнать sdk version (API level) Андроида

        :return: интовое значение с версией SDK вида 22. Если версию получить не удалось, будет отрицательное число.
        """
        v = self.get_prop('ro.build.version.sdk')
        if v:
            return int(v)
        else:
            return -1

    def get_api_level(self) -> int:
        """
        Узнать sdk version (API level) Андроида

        :return: интовое значение с API level, например 22. Если версию получить не удалось, будет отрицательное число.
        """
        return self.get_sdk_version()

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
        :return: строка со значением. Либо пустая строка, если такого property нет
        """
        prop = self.adb_shell_run('getprop', param)
        if prop:
            return prop[0]
        else:
            return ''

    def create_activity(self, activity: str, package: str = None, args: list = None) -> None:
        """
        Вызываем активити пакета с заданными аргументами

        :param package: имя пакета. Если опущено, будет использоваться имя пакета, установленное по умолчаиню
        :param activity: полное имя активити, включая java package, в котором оно лежит
        :param args: список аргументов, которые могут быть нужны для этой активити
        """
        if not package:
            if self.__package is None:
                raise PackageNameError('Package was not set')
            else:
                package = self.__package

        command = ['am', 'start', '-n', package + '/' + activity]
        if args:
            command.extend(args)
        self.adb_shell_run(*command, output=False)

    def push(self, source: list, destination: str, sync: bool = False) -> list:
        """
        Закинуть файлы и каталоги на устройство

        :param source: список файлов и каталогов. Структура каталогов будет сохранена
        :param destination: куда пушим. Если заданного пути нет, он будет создан
        :param sync: пушить только те файлы, которых не хватает на устройстве и те, которые на устройстве более старые
        :return: список строк, по которым можно понять, какие файлы залились, а какие — нет
        """
        command = ['push', *source, destination]
        if sync:
            command.append('--sync')

        self.mkdir(destination)
        adb_lines = self.__execute_adb_run(*command)
        result = []
        for res_line in adb_lines:
            if '%]' not in res_line:
                result.append(res_line)
        return result

    def pull(self, source: list, destination: str, save_time: bool = False) -> list:
        """
        Стянуть файлы и каталоги с устройства

        :param source: откуда тянем
        :param destination: директория, в которую заливаем. Если конечного пути нет, то он будет создан
        :param save_time: сохранять ли даты файлов, как они значатся на устройстве
        :return: список строк, по которым можно понять, стянулись ли файлы
        """
        if not os.path.exists(destination):
            os.makedirs(destination)

        command = ['pull', *source, destination]
        if save_time:
            command.append('-a')

        adb_lines = self.__execute_adb_run(*command)
        result = []
        for res_line in adb_lines:
            if '%]' not in res_line:
                result.append(res_line)
        return result

    def remove(self, files: list, safe: bool = True) -> list:
        """
        Удалить на устройстве файлы и папки

        :param safe: выполнять ли рекурсивное удаление. Если False, то -r проставлен не будет и вы не затрёте
         по ошибке всю карту памяти из-за опечатки
        :param files: список файлов и папок. Подстановочные символы разрешены
        :return: если список не пустой, значит были какие-то проблемы. Можно понять, какие именно
        """
        command = ['rm']
        if safe:
            command.append('-f')
        else:
            command.append('-rf')
        command.append(files)

        return self.adb_shell_run(*command)

    def adb_shell_run(self, *args, from_package: bool = False, check_android: bool = True, output: bool = True) -> list:
        """
        Выполнить переданную команду в шелле в основном потоке скрипта

        :param from_package: выполнить команду от имени пакета. Только для Android 5+ и только для дебажных сборок.
         Может не работать на Samsung и других маргинальных устройствах
        :param check_android: проверить, подходит ли версия Android для выполенния операции от имени пакета
        :param args: аргументы
        :param output: нужен ли вам выхлоп выполнения команды в виде списка строк
        :return: список строк
        """
        command = ['shell']
        if from_package:
            if check_android:
                if not self.get_sdk_version() > 20:
                    raise AndroidEnvironmentError('Current API level is %d but 21 or above need' %
                                                  self.get_sdk_version())
            command.extend(['run-as', self.__package])
        command.extend(args)
        return self.__execute_adb_run(*command, output=output)

    def mkdir(self, destination: str) -> None:
        """
        Создать директорию любого уровня вложенности

        :param destination: путь, который нужно создать
        """
        command = ['mkdir', '-p', destination]
        self.adb_shell_run(*command, output=False)

    def rmdir(self, destination: str) -> None:
        """Удалить директорию и все вложенные объекты. Осторожно!

        :param destination: путь, который нужно рекурсивно удалить. Удаляются вложенные объекты, но не наддиректории
        """
        command = ['rm', '-rf', destination]
        self.adb_shell_run(*command, output=False)

    def get_full_ls_info(self, target: str, from_package: bool = False) -> tuple:
        """
        Получить информацию о каждом файле в переданной папке, включая его дату, вес, количество ссылок, права

        :param target: папка, в которой выполнить ls -la
        :param from_package: выполнить операцию от имени пакета, заданного по умолчанию
        :return: кортеж из двух элементов. Первый — список словарей, описывающих каждый файл в папке, см. ниже.
        Второй элемент — список файлов, инфорацию о которых получить не удалось.
        Состав словаря: 'rights', 'links', 'owner', 'group', 'size', 'date', 'time', 'name'.
        В младших версиях Android некоторые ключи будут возвращать None
        """
        files_info = None
        files = self.adb_shell_run('ls', '-la', target, from_package=from_package)
        if files:
            files_info = _parse_la(files)
        if files_info:
            return files_info
        else:
            return None, None

    def get_file_ls_info(self, target: str, from_package: bool = False) -> dict:
        """
        Получить информацию о переданном файле, включая его дату, вес, количество сылок, права и др.

        :param target: путь к файлу
        :param from_package: выполнить операцию от установленного по умолчанию имени пакета
        :return: словарь с ключами: 'rights', 'links', 'owner', 'group', 'size', 'date', 'time', 'name'.
        Если данные о файле получить не удалось, будет возвращён словарь с единственным ключём 'reply', который может
         содержать описание причины провала (строка). А может содержать пустую строку, если причины не известны
        В младших версиях Android некоторые ключи будут возвращать пустую строку
        """
        file_info = self.get_full_ls_info(target, from_package)
        if file_info[0]:
            return file_info[0][0]
        else:
            if file_info[1]:
                return {'reply': file_info[1][0][1]}
            else:
                return {'reply': ''}



if __name__ == '__main__':
    test_sdk_path = '$ANDROID_HOME'
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
    #
    # adb.start_logcat()
    # test_apk = r'/home/umnik/Documents/Work/Android/CLSDKExample/app/build/outputs/apk/app-debug.apk'
    # test_package = 'com.kaspersky.clsdkexample'
    # res = adb.install(test_apk, replace=True)
    # print("App is installed:", res)
    # res = adb.install(test_apk, replace=True)
    # print("App is installed:", res)
    # res = adb.uninstall(test_package)
    # print("App is removed:", res)
    # res = adb.install(test_apk)
    # print("App is installed:", res)
    # res = adb.install(test_apk)
    # print("App is installed:", res)
    # res = adb.uninstall(test_package)
    # print("App is removed:", res)
    # logcat = adb.read_logcat()
    # for line in logcat:
    #     print(line)
    # adb.stop_logcat()
    #
    # print('')
    # print('=' * 10)
    # adb.clear_logcat()
    # res = adb.install(test_apk, replace=True)
    # print("App is installed:", res)
    # res = adb.install(test_apk, replace=True)
    # print("App is installed:", res)
    # res = adb.uninstall(test_package)
    # print("App is removed:", res)
    # res = adb.install(test_apk)
    # print("App is installed:", res)
    # res = adb.install(test_apk)
    # print("App is installed:", res)
    # res = adb.uninstall(test_package)
    # print("App is removed:", res)
    # logcat = adb.dump_logcat()
    # for line in logcat:
    #     print(line)
    # print('')
    # print('=' * 10)
    #
    # print('Android version:', adb.get_android_version())
    # print('SDK version:', adb.get_sdk_version())
    # print('Security patch:', adb.get_security_patch())
    # print('')
    # print('=' * 10)

    # qq = adb.push(source=[r'D:\!\SDK_Android\install.cfg', r'D:\!\SDK_Android\install.sh', r'D:\!\SDK_Android\SKIP'],
    #               destination='/sdcard/', sync=True)
    #
    # import pprint
    # pprint.pprint(qq)

    # qq = adb.pull(source=['/sdcard/install.cfg', '/sdcard/install.sh',
    #                       '/sdcard/SKIP/'], destination=r'D:\!!!!!\qqq', save_time=False)
    #
    # pprint.pprint (qq)

    # adb.remove(files=['/sdcard/install.cfg', '/sdcard/install.sh', '/sdcard/SKIP/'])
    print(adb.get_file_ls_info('qqq'))
    # for i in f_lst:
    #     print(i)
