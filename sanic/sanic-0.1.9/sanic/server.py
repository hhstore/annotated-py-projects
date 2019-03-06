import asyncio                    # python3 自带异步 IO 框架
from functools import partial
from inspect import isawaitable     # python3 支持异步 await
from multidict import CIMultiDict
from signal import SIGINT, SIGTERM
from time import time

#
# httptools:
#   - https://github.com/MagicStack/httptools
#       - httptools is a Python binding for nodejs HTTP parser.
#
from httptools import HttpRequestParser
from httptools.parser.errors import HttpParserError
from .exceptions import ServerError


#
# uvloop:
#   - https://github.com/MagicStack/uvloop
#       - uvloop is a fast, drop-in replacement of the built-in asyncio event loop.
#       - uvloop is implemented in Cython and uses libuv under the hood.
#   - http://magic.io/blog/uvloop-make-python-networking-great-again/
#       - 译文: https://python.freelycode.com/contribution/detail/211
#       - uvloop: 一个完整的 asyncio 事件循环的替代品，它建立在 libuv 基础之上，由Cython编写而成。
#       - Uvloop 使得 Asyncio 更加快速，事实上，它至少是 Nodejs，Gevent 或者其他 Python 异步框架速度的两倍。
#       - Uvloop 的性能表现可以与用Go编写的项目相媲美。
#       - Uvloop 和 asyncio，结合python 3.5中的 async/await，可以更容易的用python编写出更高效的代码。
#
try:
    import uvloop as async_loop     # 关键依赖包, 使用 uvloop 替代 asyncio
except ImportError:
    async_loop = asyncio            # 若未安装, 使用默认的 asyncio

from .log import log
from .request import Request
from .exceptions import RequestTimeout, PayloadTooLarge, InvalidUsage


class Signal:
    stopped = False


current_time = None


#
# HTTP 协议:
#
class HttpProtocol(asyncio.Protocol):
    __slots__ = (
        # event loop, connection
        'loop', 'transport', 'connections', 'signal',
        # request params
        'parser', 'request', 'url', 'headers',
        # request config
        'request_handler', 'request_timeout', 'request_max_size',
        # connection management
        '_total_request_size', '_timeout_handler', '_last_communication_time')

    def __init__(self, *, loop, request_handler, error_handler,
                 signal=Signal(), connections={}, request_timeout=60,
                 request_max_size=None):
        self.loop = loop
        self.transport = None
        self.request = None              # 请求
        self.parser = None
        self.url = None
        self.headers = None              # 请求头
        self.signal = signal
        self.connections = connections
        self.request_handler = request_handler     # 请求处理器
        self.error_handler = error_handler         # 出错处理器
        self.request_timeout = request_timeout
        self.request_max_size = request_max_size
        self._total_request_size = 0
        self._timeout_handler = None
        self._last_request_time = None
        self._request_handler_task = None

    # -------------------------------------------- #
    # Connection
    # -------------------------------------------- #

    def connection_made(self, transport):
        self.connections.add(self)
        self._timeout_handler = self.loop.call_later(
            self.request_timeout, self.connection_timeout)
        self.transport = transport
        self._last_request_time = current_time

    def connection_lost(self, exc):
        self.connections.discard(self)
        self._timeout_handler.cancel()
        self.cleanup()

    def connection_timeout(self):
        # Check if
        time_elapsed = current_time - self._last_request_time
        if time_elapsed < self.request_timeout:
            time_left = self.request_timeout - time_elapsed
            self._timeout_handler = \
                self.loop.call_later(time_left, self.connection_timeout)
        else:
            if self._request_handler_task:
                self._request_handler_task.cancel()
            exception = RequestTimeout('Request Timeout')
            self.write_error(exception)

    # -------------------------------------------- #
    # Parsing
    # -------------------------------------------- #

    def data_received(self, data):
        # Check for the request itself getting too large and exceeding
        # memory limits
        self._total_request_size += len(data)
        if self._total_request_size > self.request_max_size:
            exception = PayloadTooLarge('Payload Too Large')
            self.write_error(exception)

        # Create parser if this is the first time we're receiving data
        if self.parser is None:
            assert self.request is None
            self.headers = []
            self.parser = HttpRequestParser(self)

        # Parse request chunk or close connection
        try:
            self.parser.feed_data(data)
        except HttpParserError:
            exception = InvalidUsage('Bad Request')
            self.write_error(exception)

    def on_url(self, url):
        self.url = url

    #
    # HTTP 请求: 补全 head 信息
    #   -  更新 headers 字段
    #
    def on_header(self, name, value):
        if name == b'Content-Length' and int(value) > self.request_max_size:
            exception = PayloadTooLarge('Payload Too Large')
            self.write_error(exception)

        self.headers.append((name.decode(), value.decode('utf-8')))

    #
    # HTTP 请求: 写入 head 信息
    #
    def on_headers_complete(self):
        remote_addr = self.transport.get_extra_info('peername')
        if remote_addr:
            self.headers.append(('Remote-Addr', '%s:%s' % remote_addr))

        #
        # 构建 HTTP 请求
        #
        self.request = Request(
            url_bytes=self.url,
            headers=CIMultiDict(self.headers),
            version=self.parser.get_http_version(),
            method=self.parser.get_method().decode()
        )

    #
    # HTTP 请求: 写入 body 部分
    #
    def on_body(self, body):
        if self.request.body:
            self.request.body += body
        else:
            self.request.body = body

    def on_message_complete(self):
        #
        # 任务创建:
        #
        self._request_handler_task = self.loop.create_task(
            self.request_handler(self.request, self.write_response))

    # -------------------------------------------- #
    # Responding
    #   -  HTTP 响应部分
    # -------------------------------------------- #

    #
    # HTTP 响应: 正常响应
    #   - 写出 HTTP 响应
    #   - 长连接, 更新连接时间
    #
    def write_response(self, response):
        try:
            keep_alive = self.parser.should_keep_alive() and not self.signal.stopped
            #
            # 输出 HTTP 响应
            #
            self.transport.write(
                response.output(  # HTTP Response, 写一个响应
                    self.request.version, keep_alive, self.request_timeout))

            if not keep_alive:             # 非长连接, 关闭
                self.transport.close()
            else:
                # Record that we received data
                self._last_request_time = current_time
                self.cleanup()
        except Exception as e:
            self.bail_out("Writing response failed, connection closed {}".format(e))

    #
    # HTTP 响应: 出错响应
    #
    def write_error(self, exception):
        try:
            response = self.error_handler.response(self.request, exception)    # 出错响应处理
            version = self.request.version if self.request else '1.1'          # HTTP 协议版本
            self.transport.write(response.output(version))                     # HTTP Response, 写一个响应
            self.transport.close()
        except Exception as e:
            self.bail_out("Writing error failed, connection closed {}".format(e))

    #
    # 异常记录:
    #
    def bail_out(self, message):
        exception = ServerError(message)
        self.write_error(exception)
        log.error(message)

    #
    # 清理:
    #   - 将字段复位为空
    #
    def cleanup(self):
        self.parser = None
        self.request = None
        self.url = None
        self.headers = None
        self._request_handler_task = None
        self._total_request_size = 0

    def close_if_idle(self):
        """
        Close the connection if a request is not being sent or received
        :return: boolean - True if closed, false if staying open
        """
        if not self.parser:
            self.transport.close()
            return True
        return False


#
# 更新当前时间:
#   - 更新全局变量值
#   - 长连接中, 更新请求超时时间.
#
def update_current_time(loop):
    """
    Caches the current time, since it is needed
    at the end of every keep-alive request to update the request timeout time
    :param loop:
    :return:
    """
    global current_time
    current_time = time()
    loop.call_later(1, partial(update_current_time, loop))


#
# 触发事件集:
#
def trigger_events(events, loop):
    """
    :param events: one or more sync or async functions to execute
    :param loop: event loop
    """
    if events:
        if not isinstance(events, list):   # 事件列表格式化
            events = [events]
        for event in events:          # 事件遍历
            result = event(loop)      # 事件执行
            if isawaitable(result):   # 支持异步await
                loop.run_until_complete(result)


#
# 启动异步 HTTP 服务器:
#   - 在独立的进程中启动
#
def serve(host, port, request_handler, error_handler, before_start=None,
          after_start=None, before_stop=None, after_stop=None,
          debug=False, request_timeout=60, sock=None,
          request_max_size=None, reuse_port=False, loop=None):
    """
    Starts asynchronous HTTP Server on an individual process.
    :param host: Address to host on
    :param port: Port to host on
    :param request_handler: Sanic request handler with middleware
    :param after_start: Function to be executed after the server starts
    listening. Takes single argument `loop`
    :param before_stop: Function to be executed when a stop signal is
    received before it is respected. Takes single argumenet `loop`
    :param debug: Enables debug output (slows server)
    :param request_timeout: time in seconds
    :param sock: Socket for the server to accept connections from
    :param request_max_size: size in bytes, `None` for no limit
    :param reuse_port: `True` for multiple workers
    :param loop: asyncio compatible event loop
    :return: Nothing
    """
    loop = loop or async_loop.new_event_loop()      # 关键模块: 事件循环
    asyncio.set_event_loop(loop)

    if debug:
        loop.set_debug(debug)

    #
    # before_start 钩子:
    #   - 触发事件集
    #   - 在真实 web 服务启动之前, 启动初始化
    #
    trigger_events(before_start, loop)

    connections = set()    # 连接集
    signal = Signal()

    #
    # 构建 server 参数:
    #
    server = partial(
        HttpProtocol,
        loop=loop,
        connections=connections,
        signal=signal,
        request_handler=request_handler,
        error_handler=error_handler,
        request_timeout=request_timeout,
        request_max_size=request_max_size,
    )

    # 服务器协程创建:
    server_coroutine = loop.create_server(
        server,
        host,
        port,
        reuse_port=reuse_port,
        sock=sock
    )

    # Instead of pulling time at the end of every request,
    # pull it once per minute
    loop.call_soon(partial(update_current_time, loop))

    try:
        http_server = loop.run_until_complete(server_coroutine)     # 启动协程
    except Exception:
        log.exception("Unable to start server")
        return

    #
    # after_start 清理钩子:
    #   - 触发事件集
    #   - 在真实 web 服务结束之后, 启动清理
    #
    trigger_events(after_start, loop)

    # Register signals for graceful termination
    for _signal in (SIGINT, SIGTERM):
        loop.add_signal_handler(_signal, loop.stop)

    # -------------------------------------------- #
    #                   服务器启动:
    # -------------------------------------------- #

    try:
        loop.run_forever()      # 服务器启动, 死循环
    finally:
        log.info("Stop requested, draining connections...")

        # Run the on_stop function if provided
        #
        # before_stop 清理钩子:
        #   - web 服务结束后, 执行清理
        #
        trigger_events(before_stop, loop)

        # Wait for event loop to finish and all connections to drain
        http_server.close()
        loop.run_until_complete(http_server.wait_closed())

        # Complete all tasks on the loop
        signal.stopped = True
        for connection in connections:
            connection.close_if_idle()

        while connections:
            loop.run_until_complete(asyncio.sleep(0.1))

        #
        # after_stop 清理钩子:
        #   - web 服务结束后, 执行清理
        #
        trigger_events(after_stop, loop)

        loop.close()
