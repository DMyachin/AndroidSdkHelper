#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

import remove_android_sdk
from remove_android_sdk import PathLike


class AndroidAapt(object):
    def __init__(self, path: PathLike) -> None:
        self.__aapt = os.path.expanduser(os.path.expandvars(path))


if __name__ == '__main__':
    test_sdk_path = '/home/umnik/Android/Sdk'
    sdk = remove_android_sdk.AndroidSdk(test_sdk_path, auto_set=['aapt'])
    aapt = AndroidAapt(sdk.get_aapt())
