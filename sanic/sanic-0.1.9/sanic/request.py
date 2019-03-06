#!/usr/bin/env python
# -*- coding: utf-8 -*-
from cgi import parse_header
from collections import namedtuple
from http.cookies import SimpleCookie
from httptools import parse_url
from urllib.parse import parse_qs
from ujson import loads as json_loads
from sanic.exceptions import InvalidUsage

from .log import log

#
# 如果 media 文件类型未知, 默认配置如下类型
#
DEFAULT_HTTP_CONTENT_TYPE = "application/octet-stream"


# HTTP/1.1: https://www.w3.org/Protocols/rfc2616/rfc2616-sec7.html#sec7.2.1
# > If the media type remains unknown, the recipient SHOULD treat it
# > as type "application/octet-stream"


##################################################################################
#                              辅助类: 实现 Request 用
#
# 说明:
#   - 自定义数据类型: 扩展自 dict
#   - 2个接口方法:
#       - get() : 返回首个元素
#       - getlist() : 返回全部内容
#
##################################################################################
class RequestParameters(dict):
    """
    Hosts a dict with lists as values where:
     - get returns the first value of the list
     - getlist returns the whole shebang
    """

    def __init__(self, *args, **kwargs):
        self.super = super()
        self.super.__init__(*args, **kwargs)

    #
    # 返回首个元素
    #
    def get(self, name, default=None):
        values = self.super.get(name)
        return values[0] if values else default

    #
    # 返回全部内容
    #
    def getlist(self, name, default=None):
        return self.super.get(name, default)


##################################################################################
#                              Request 类: HTTP 请求
#
# 说明:
#   - 自定义数据类型: 扩展自 dict
#   - 包含 HTTP 请求相关信息(URL, headers 等)
#   - 自定义 Request 接口:
#       - json()
#       - form()
#       - files()
#       - args()
#       - cookies()
#
##################################################################################
class Request(dict):
    """
    Properties of an HTTP request such as URL, headers, etc.
    """
    __slots__ = (
        'url', 'headers', 'version', 'method', '_cookies',
        'query_string', 'body',
        'parsed_json', 'parsed_args', 'parsed_form', 'parsed_files',
    )

    def __init__(self, url_bytes, headers, version, method):
        # TODO: Content-Encoding detection
        url_parsed = parse_url(url_bytes)             # URL 解析
        self.url = url_parsed.path.decode('utf-8')    # URL 信息
        self.headers = headers                        # HTTP 头
        self.version = version                        # HTTP 协议版本
        self.method = method                          # HTTP 方法类型
        self.query_string = None
        if url_parsed.query:
            self.query_string = url_parsed.query.decode('utf-8')  # 查询字符串

        # Init but do not inhale
        self.body = None
        self.parsed_json = None            # HTTP 内容(json 格式)
        self.parsed_form = None            # HTTP 内容(form 格式)
        self.parsed_files = None           # HTTP 内容(文件 格式)
        self.parsed_args = None            # HTTP 参数
        self._cookies = None               # cookie 内容

    #
    # 解析 json 格式数据:
    #   - HTTP POST 请求提交
    #   - 常见于 ajax 请求
    #
    @property
    def json(self):
        if not self.parsed_json:
            try:
                self.parsed_json = json_loads(self.body)  # 解析body内容
            except Exception:
                raise InvalidUsage("Failed when parsing body as json")

        return self.parsed_json

    #
    # HTTP POST 请求, form 提交参数:
    #   - 根据 form 表单数据格式类型, 解析 form 参数
    #   - 包含 form 提交文件数据的解析
    #
    @property
    def form(self):
        if self.parsed_form is None:
            self.parsed_form = RequestParameters()  # 表单参数
            self.parsed_files = RequestParameters()  # 文件参数

            #
            # 通过 HTTP 请求头, 字段标签, 识别 POST 请求体的内容类型
            #
            content_type = self.headers.get(
                'Content-Type', DEFAULT_HTTP_CONTENT_TYPE)
            content_type, parameters = parse_header(content_type)  # 解析HTTP头信息

            try:
                #
                # 常规 form 表单数据格式
                #
                if content_type == 'application/x-www-form-urlencoded':
                    self.parsed_form = RequestParameters(
                        parse_qs(self.body.decode('utf-8')))
                elif content_type == 'multipart/form-data':  # 表单数据格式2:
                    # TODO: Stream this instead of reading to/from memory
                    boundary = parameters['boundary'].encode('utf-8')

                    #
                    # 多部分表单解析:
                    #   - 框架自定义实现
                    #   - 解析含有多个部分的 form 表单
                    #   - 解析上传的文件数据
                    #
                    self.parsed_form, self.parsed_files = (
                        parse_multipart_form(self.body, boundary))
            except Exception:
                log.exception("Failed when parsing form")

        return self.parsed_form

    #
    # HTTP POST 请求, form 上传文件:
    #   - 实现依赖上面的 form()接口
    #   - 解析文件类型数据
    #
    @property
    def files(self):
        if self.parsed_files is None:
            # 调用表单解析实现
            self.form  # compute form to get files

        return self.parsed_files

    #
    # 解析参数格式数据
    #
    @property
    def args(self):
        if self.parsed_args is None:
            if self.query_string:  # 查询字符串
                self.parsed_args = RequestParameters(
                    parse_qs(self.query_string))
            else:
                self.parsed_args = {}  # 解析参数

        return self.parsed_args

    #
    # 通过 HTTP 请求头, 提取 cookie
    #
    @property
    def cookies(self):
        if self._cookies is None:
            #
            # 通过 HTTP 请求头, 提取 cookie 字段
            #
            cookie = self.headers.get('Cookie') or self.headers.get('cookie')
            if cookie is not None:
                cookies = SimpleCookie()
                cookies.load(cookie)  # 解析cookie
                self._cookies = {name: cookie.value
                                 for name, cookie in cookies.items()}
            else:
                self._cookies = {}
        return self._cookies


File = namedtuple('File', ['type', 'body', 'name'])  # 文件类型


#
# HTTP POST 请求, form 表单提交处理
#   - 解析含有多个部分的表单:
#   - 针对文件类型数据, 作处理
#
def parse_multipart_form(body, boundary):
    """
    Parses a request body and returns fields and files
    :param body: Bytes request body
    :param boundary: Bytes multipart boundary
    :return: fields (RequestParameters), files (RequestParameters)
    """
    files = RequestParameters()     # 文件
    fields = RequestParameters()    # 文件域

    form_parts = body.split(boundary)

    # 遍历
    for form_part in form_parts[1:-1]:
        file_name = None  # 文件名
        file_type = None  # 文件类型
        field_name = None  # 文件域
        line_index = 2
        line_end_index = 0

        while not line_end_index == -1:
            line_end_index = form_part.find(b'\r\n', line_index)  # 换行分割
            form_line = form_part[line_index:line_end_index].decode('utf-8')
            line_index = line_end_index + 2

            if not form_line:
                break

            colon_index = form_line.index(':')
            form_header_field = form_line[0:colon_index]
            form_header_value, form_parameters = parse_header(
                form_line[colon_index + 2:])

            if form_header_field == 'Content-Disposition':
                if 'filename' in form_parameters:
                    file_name = form_parameters['filename']
                field_name = form_parameters.get('name')
            elif form_header_field == 'Content-Type':
                file_type = form_header_value

        post_data = form_part[line_index:-4]  # POST提交数据

        #
        # 判断是否是文件类型数据:
        #
        if file_name or file_type:
            file = File(type=file_type, name=file_name, body=post_data)  # 创建文件

            if field_name in files:
                files[field_name].append(file)
            else:
                files[field_name] = [file]
        else:
            value = post_data.decode('utf-8')  # 非文件类型数据
            if field_name in fields:
                fields[field_name].append(value)
            else:
                fields[field_name] = [value]

    return fields, files
