#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Print 'Hello World' every two seconds, using a coroutine."""

import asyncio


#
# 协程装饰器:
#   - 跟踪代码定义处: coroutines.coroutine()
#
@asyncio.coroutine
def greet_every_two_seconds():
    while True:
        print('Hello World')
        yield from asyncio.sleep(2)     # 异步返回


if __name__ == '__main__':
    loop = asyncio.get_event_loop()     # 事件循环
    try:
        loop.run_until_complete(greet_every_two_seconds())     # 运行
    finally:
        loop.close()
