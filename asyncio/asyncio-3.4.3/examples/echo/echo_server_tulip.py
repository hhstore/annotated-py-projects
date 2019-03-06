import asyncio
import logging
import time


END = b'Bye-bye!\n'

"""
- 说明:
    - 改写原 echo 示例代码:
    - 完善了代码执行逻辑
    - 更清晰暂时执行过程

- 启动顺序:
    - 先启动 server, 再启动 client.

"""


#
# 主协程:
#   - 启动一个任务协程, 执行具体任务
#   - 主协程, 直接返回
#
@asyncio.coroutine
def echo_server():
    yield from asyncio.start_server(handle_connection, 'localhost', 8000)
    print("[server] return...")


#
# 任务协程:
#   - 执行具体的任务
#
@asyncio.coroutine
def handle_connection(reader, writer):
    print("\t[coroutine] start...")
    #
    # 死循环:
    #
    while True:
        data = yield from reader.readline()  # 异步读客户端数据
        print("\t |receive data: %s" % data)

        time.sleep(2)       # 减缓响应时间
        writer.write(data)  # 写回客户端数据

        if data == END:
            break
    print("\t[coroutine] stop...")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(echo_server())  # 启动一个协程处理

    try:
        print("[main] run forever...")
        loop.run_forever()  # 主进程, 死循环
    finally:
        loop.close()
