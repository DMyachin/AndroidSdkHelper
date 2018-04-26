#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

import android_sdk


class AndroidAapt(object):
    def __init__(self, path: str) -> None:
        self.__aapt = os.path.expanduser(os.path.expandvars(path))


if __name__ == '__main__':
    test_sdk_path = '/home/umnik/Android/Sdk'
    sdk = android_sdk.AndroidSdk(test_sdk_path, auto_set=['aapt'])
    aapt = AndroidAapt(sdk.get_aapt())
