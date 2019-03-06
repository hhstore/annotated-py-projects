import asyncio

END = b'Bye-bye!\n'


#
# 协程执行:
#
@asyncio.coroutine
def echo_client():
    #
    # 异步返回:
    #
    reader, writer = yield from asyncio.open_connection('localhost', 8000)

    writer.write(b'Hello, world\n')
    writer.write(b'What a fine day it is.\n')
    writer.write(END)   # 结束标志

    while True:
        line = yield from reader.readline()
        print('\treceived:', line)
        if line == END or not line:
            break

    # 结束前, 通知服务器关闭
    writer.write(b"")
    # 客户端关闭
    writer.close()


if __name__ == '__main__':

    #
    # run client:
    #   - run server first.
    #
    loop = asyncio.get_event_loop()
    loop.run_until_complete(echo_client())    # 客户端
    loop.close()
