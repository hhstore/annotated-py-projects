#!/usr/bin/env python
# -*- coding: utf-8 -*-
from aiofiles import open as open_async    # Python3.5 标准库, 异步打开文件, file() 方法实现中引用
from mimetypes import guess_type
from os import path

from ujson import dumps as json_dumps

from .cookies import CookieJar    # 相对路径导包

#
# 常用状态码:
#   - 用于优化查询速度
#
COMMON_STATUS_CODES = {
    200: b'OK',
    400: b'Bad Request',
    404: b'Not Found',
    500: b'Internal Server Error',
}

#
# 全部状态码:
#
ALL_STATUS_CODES = {
    100: b'Continue',
    101: b'Switching Protocols',
    102: b'Processing',
    200: b'OK',
    201: b'Created',
    202: b'Accepted',
    203: b'Non-Authoritative Information',
    204: b'No Content',
    205: b'Reset Content',
    206: b'Partial Content',
    207: b'Multi-Status',
    208: b'Already Reported',
    226: b'IM Used',
    300: b'Multiple Choices',
    301: b'Moved Permanently',
    302: b'Found',
    303: b'See Other',
    304: b'Not Modified',
    305: b'Use Proxy',
    307: b'Temporary Redirect',
    308: b'Permanent Redirect',
    400: b'Bad Request',
    401: b'Unauthorized',
    402: b'Payment Required',
    403: b'Forbidden',
    404: b'Not Found',
    405: b'Method Not Allowed',
    406: b'Not Acceptable',
    407: b'Proxy Authentication Required',
    408: b'Request Timeout',
    409: b'Conflict',
    410: b'Gone',
    411: b'Length Required',
    412: b'Precondition Failed',
    413: b'Request Entity Too Large',
    414: b'Request-URI Too Long',
    415: b'Unsupported Media Type',
    416: b'Requested Range Not Satisfiable',
    417: b'Expectation Failed',
    422: b'Unprocessable Entity',
    423: b'Locked',
    424: b'Failed Dependency',
    426: b'Upgrade Required',
    428: b'Precondition Required',
    429: b'Too Many Requests',
    431: b'Request Header Fields Too Large',
    500: b'Internal Server Error',
    501: b'Not Implemented',
    502: b'Bad Gateway',
    503: b'Service Unavailable',
    504: b'Gateway Timeout',
    505: b'HTTP Version Not Supported',
    506: b'Variant Also Negotiates',
    507: b'Insufficient Storage',
    508: b'Loop Detected',
    510: b'Not Extended',
    511: b'Network Authentication Required'
}


##################################################################################
#                              HTTP 响应类(辅助类)
#
# 说明:
#   - 加深对 HTTP 协议本身的理解
#   - 此类填入初始化参数, 构造一个标准的 Response 对象.
#   - 包含2个接口:
#       - output(): 输出 Response 对象内容
#       - cookies(): 输出 cookie.
#   - 下面有4个常用接口, 基于此类实现.
#       - json()
#       - text()
#       - html()
#       - file()
#   - 统一格式化返回 HTTP 响应.
#   - 下面实现的接口, 借用此类, 格式化 HTTP 输出数据.
#
##################################################################################
class HTTPResponse:
    __slots__ = ('body', 'status', 'content_type', 'headers', '_cookies')

    def __init__(self, body=None, status=200, headers=None,
                 content_type='text/plain', body_bytes=b''):
        self.content_type = content_type

        if body is not None:
            try:
                # Try to encode it regularly
                self.body = body.encode('utf-8')         # 默认编码
            except AttributeError:
                # Convert it to a str if you can't
                self.body = str(body).encode('utf-8')    # 编码异常, 尝试转换成字符串
        else:
            self.body = body_bytes

        self.status = status
        self.headers = headers or {}           # HTTP 头
        self._cookies = None                   # cookie 内容

    #
    # 返回一个标准的 HTTP 响应
    #   - 注意调用处: sanic.server.HttpProtocol.write_response()
    #   - 注意一个 Response 对象的内容格式:
    #       - HTTP head 部分
    #       - HTTP body 部分
    #
    def output(self, version="1.1", keep_alive=False, keep_alive_timeout=None):
        # This is all returned in a kind-of funky way
        # We tried to make this as fast as possible in pure python
        timeout_header = b''
        if keep_alive and keep_alive_timeout:
            timeout_header = b'Keep-Alive: timeout=%d\r\n' % keep_alive_timeout

        headers = b''
        if self.headers:
            headers = b''.join(
                b'%b: %b\r\n' % (name.encode(), value.encode('utf-8'))
                for name, value in self.headers.items()
            )

        # Try to pull from the common codes first
        # Speeds up response rate 6% over pulling from all
        status = COMMON_STATUS_CODES.get(self.status)    # 加快HTTP状态码查询速度.
        if not status:
            status = ALL_STATUS_CODES.get(self.status)

        return (b'HTTP/%b %d %b\r\n'
                b'Content-Type: %b\r\n'
                b'Content-Length: %d\r\n'
                b'Connection: %b\r\n'
                b'%b%b\r\n'
                b'%b') % (
            version.encode(),              # HTTP 协议版本号
            self.status,                   # HTTP 状态码编号
            status,                        # HTTP 状态码信息
            self.content_type.encode(),    # HTTP 内容格式
            len(self.body),                # HTTP 内容长度
            b'keep-alive' if keep_alive else b'close',    # HTTP 连接状态
            timeout_header,
            headers,
            self.body                      # HTTP 响应内容部分
        )

    #
    # 返回 cookie 部分
    #
    @property
    def cookies(self):
        if self._cookies is None:
            self._cookies = CookieJar(self.headers)    # cookie 部分, 由 HTTP head 部分生成
        return self._cookies


##################################################################################
#                              HTTP 响应模块对外接口:
#
# 说明:
#   - 自定义接口:
#       - json(): 返回 json 格式内容的 HTTP 响应
#       - text(): 返回 text 格式的 HTTP 响应
#       - html(): 返回 html 格式的 HTTP 响应
#       - file(): 返回文件格式的 HTTP 响应
#           - 此接口, 通过异步方式实现.
#
##################################################################################
#
# 返回 json 格式的 HTTP 响应
#   - 应用场景: API 数据接口
#   - 根据 content_type 字段类型, 区分
#
def json(body, status=200, headers=None):
    # 返回 json 格式
    #   - 注意 content_type 类型
    return HTTPResponse(json_dumps(body), headers=headers, status=status,
                        content_type="application/json")


#
# 返回 text 格式的 HTTP 响应
#   - 根据 content_type 字段类型, 区分
#
def text(body, status=200, headers=None):
    # 返回文本格式
    return HTTPResponse(body, status=status, headers=headers,
                        content_type="text/plain; charset=utf-8")


#
# 返回 html 格式的 HTTP 响应
#   - 应用场景: 场景的 GET 请求返回页面
#   - 根据 content_type 字段类型, 区分
#
def html(body, status=200, headers=None):
    # 返回 HTML 格式
    return HTTPResponse(body, status=status, headers=headers,
                        content_type="text/html; charset=utf-8")


#
# 返回文件格式的 HTTP 响应
#   - 应用场景: 文件下载
#   - 实现: 异步实现
#       - 异步打开文件
#       - 异步读取文件
#   - 通过 body_bytes 参数传递文件数据流
#
async def file(location, mime_type=None, headers=None):
    filename = path.split(location)[-1]

    # 异步打开文件:
    async with open_async(location, mode='rb') as _file:
        out_stream = await _file.read()    # 异步读文件

    mime_type = mime_type or guess_type(filename)[0] or 'text/plain'

    # 在 body_bytes 参数返回文件流
    return HTTPResponse(status=200,
                        headers=headers,
                        content_type=mime_type,
                        body_bytes=out_stream)
