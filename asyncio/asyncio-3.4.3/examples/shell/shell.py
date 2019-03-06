#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Examples using create_subprocess_exec() and create_subprocess_shell()."""

import asyncio
import signal
from asyncio.subprocess import PIPE


#
# 执行 shell 命令:
#
@asyncio.coroutine
def cat(loop):

    #
    # 异步返回:
    #   - 调用接口:
    #
    proc = yield from asyncio.create_subprocess_shell("cat",
                                                      stdin=PIPE,
                                                      stdout=PIPE)
    print("pid: %s" % proc.pid)

    message = "Hello World!"
    print("cat write: %r" % message)

    stdout, stderr = yield from proc.communicate(message.encode('ascii'))
    print("cat read: %r" % stdout.decode('ascii'))

    exitcode = yield from proc.wait()
    print("(exit code %s)" % exitcode)


@asyncio.coroutine
def ls(loop):
    proc = yield from asyncio.create_subprocess_exec("ls",
                                                     stdout=PIPE)
    while True:
        line = yield from proc.stdout.readline()
        if not line:
            break
        print("ls>>", line.decode('ascii').rstrip())
    try:
        proc.send_signal(signal.SIGINT)
    except ProcessLookupError:
        pass


@asyncio.coroutine
def test_call(*args, timeout=None):
    proc = yield from asyncio.create_subprocess_exec(*args)
    try:
        exitcode = yield from asyncio.wait_for(proc.wait(), timeout)
        print("%s: exit code %s" % (' '.join(args), exitcode))
    except asyncio.TimeoutError:
        print("timeout! (%.1f sec)" % timeout)
        proc.kill()
        yield from proc.wait()


#
# 运行:
#
loop = asyncio.get_event_loop()
loop.run_until_complete(cat(loop))    # 执行shell命令
loop.run_until_complete(ls(loop))     # 执行shell命令
loop.run_until_complete(test_call("bash", "-c", "sleep 3", timeout=1.0))    # 执行shell命令
loop.close()
