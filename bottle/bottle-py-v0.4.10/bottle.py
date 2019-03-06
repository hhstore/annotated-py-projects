# -*- coding: utf-8 -*-

###############################################################################
#                    代码注释说明
#
# Annotated_Author: hhstore
# Email: selfrebuild@gmail.com
# Date: 2015-08
#
###############################################################################



"""
Bottle is a fast and simple mirco-framework for small web-applications. It
offers request dispatching (Routes) with url parameter support, Templates,
key/value Databases, a build-in HTTP Server? and adapters for many third party
WSGI/HTTP-server and template engines. All in a single file and with no
dependencies other than the Python Standard Library.

Homepage and documentation: http://wiki.github.com/defnull/bottle

Special thanks to Stefan Matthias Aust [http://github.com/sma]
  for his contribution to SimpelTemplate


Example
-------

    from bottle import route, run, request, response, send_file, abort

    @route('/')
    def hello_world():
        return 'Hello World!'

    @route('/hello/:name')
    def hello_name(name):
        return 'Hello %s!' % name

    @route('/hello', method='POST')
    def hello_post():
        name = request.POST['name']
        return 'Hello %s!' % name

    @route('/static/:filename#.*#')
    def static_file(filename):
        send_file(filename, root='/path/to/static/files/')

    run(host='localhost', port=8080)

"""





__author__ = 'Marcel Hellkamp'
__version__ = '0.4.10'
__license__ = 'MIT'

###############################################################################
# ##########################      依赖导包       ###############################
###############################################################################
import cgi
import mimetypes
import os
import os.path
import sys
import traceback
import re
import random
import Cookie
import threading   # 关键依赖
import time

try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    import anydbm as dbm
except ImportError:
    import dbm






###############################################################################
###############################################################################
###############################################################################

# Exceptions and Events     异常处理 和 事件处理 定义部分.

class BottleException(Exception):  # 异常处理-基类
    """ A base class for exceptions used by bottle."""
    pass


class HTTPError(BottleException):  # HTTP 请求错误.
    """ A way to break the execution and instantly jump to an error handler. """

    def __init__(self, status, text):
        self.output = text
        self.http_status = int(status)

    def __str__(self):
        return self.output


class BreakTheBottle(BottleException):  # 中断 bottle 服务
    """ Not an exception, but a straight jump out of the controller code.

    Causes the WSGIHandler to instantly call start_response() and return the
    content of output """

    def __init__(self, output):
        self.output = output


class TemplateError(BottleException):  # 模板错误
    """ Thrown by template engines during compilation of templates """
    pass




###############################################################################
###############################################################################
###############################################################################




# WSGI abstraction: Request and response management
# 请求request 和响应 response 管理.
def WSGIHandler(environ, start_response):
    """The bottle WSGI-handler."""
    global request     # 引用全局变量
    global response

    request.bind(environ)
    response.bind()
    ###############################################################################

    try:
        handler, args = match_url(request.path, request.method)  # 调用,下面定义.
        if not handler:
            raise HTTPError(404, "Not found")
        output = handler(**args)
    except BreakTheBottle, shard:
        output = shard.output
    except Exception, exception:
        response.status = getattr(exception, 'http_status', 500)
        errorhandler = ERROR_HANDLER.get(response.status, error_default)
        try:
            output = errorhandler(exception)
        except:
            output = "Exception within error handler! Application stopped."

        if response.status == 500:
            request._environ['wsgi.errors'].write("Error (500) on '%s': %s\n" % (request.path, exception))

    db.close()  # DB cleanup

    ###############################################################################

    if hasattr(output, 'read'):
        fileoutput = output
        if 'wsgi.file_wrapper' in environ:
            output = environ['wsgi.file_wrapper'](fileoutput)
        else:
            output = iter(lambda: fileoutput.read(8192), '')
    elif isinstance(output, str):
        output = [output]

    ###############################################################################

    for c in response.COOKIES.values():
        response.header.add('Set-Cookie', c.OutputString())  # 响应头.

    # finish
    status = '%d %s' % (response.status, HTTP_CODES[response.status])
    start_response(status, list(response.header.items()))    # 关键代码
    return output


###############################################################################
###############################################################################
###############################################################################
# 针对threading.local() 说明:
#     - 1. 表示thread-local数据的一个类
#     - 2. thread-local数据是值只特定于线程的数据
#     - 3. 要管理thread-local数据，只需创建local（或其子类）的一个实例并在它上面存储属性
#     - 4. 该实例的值对于各自的线程将是不同的。
###############################################################################

# 请求-管理类.
class Request(threading.local):
    """ Represents a single request using thread-local namespace. """

    def bind(self, environ):  # 请求,绑定
        """ Binds the enviroment of the current request to this request handler """
        self._environ = environ
        self._GET = None
        self._POST = None
        self._GETPOST = None
        self._COOKIES = None
        self.path = self._environ.get('PATH_INFO', '/').strip()
        if not self.path.startswith('/'):
            self.path = '/' + self.path

    @property
    def method(self):  # 请求类型: GET,POST 等.
        ''' Returns the request method (GET,POST,PUT,DELETE,...) '''
        return self._environ.get('REQUEST_METHOD', 'GET').upper()

    @property
    def query_string(self):
        """ Content of QUERY_STRING """
        return self._environ.get('QUERY_STRING', '')

    @property
    def input_length(self):
        ''' Content of CONTENT_LENGTH '''
        try:
            return int(self._environ.get('CONTENT_LENGTH', '0'))
        except ValueError:
            return 0

    ###############################################################################

    @property
    def GET(self):  # GET 请求.
        """Returns a dict with GET parameters."""
        if self._GET is None:
            raw_dict = parse_qs(self.query_string, keep_blank_values=1)
            self._GET = {}
            for key, value in raw_dict.items():
                if len(value) == 1:
                    self._GET[key] = value[0]
                else:
                    self._GET[key] = value
        return self._GET

    @property
    def POST(self):  # POST 请求.
        """Returns a dict with parsed POST data."""
        if self._POST is None:
            raw_data = cgi.FieldStorage(fp=self._environ['wsgi.input'], environ=self._environ)
            self._POST = {}
            if raw_data:
                for key in raw_data:
                    if isinstance(raw_data[key], list):
                        self._POST[key] = [v.value for v in raw_data[key]]
                    elif raw_data[key].filename:
                        self._POST[key] = raw_data[key]
                    else:
                        self._POST[key] = raw_data[key].value
        return self._POST

    @property
    def params(self):
        ''' Returns a mix of GET and POST data. POST overwrites GET '''
        if self._GETPOST is None:
            self._GETPOST = dict(self.GET)                   # 调用GET()
            self._GETPOST.update(dict(self.POST))            # 调用POST()
        return self._GETPOST

    @property
    def COOKIES(self):
        """Returns a dict with COOKIES."""
        if self._COOKIES is None:
            raw_dict = Cookie.SimpleCookie(self._environ.get('HTTP_COOKIE', ''))     # 调用
            self._COOKIES = {}
            for cookie in raw_dict.values():
                self._COOKIES[cookie.key] = cookie.value
        return self._COOKIES



# 响应-管理类
class Response(threading.local):
    """ Represents a single response using thread-local namespace. """

    def bind(self):
        """ Clears old data and creates a brand new Response object """
        self._COOKIES = None

        self.status = 200
        self.header = HeaderDict()          # HTTP 头数据
        self.content_type = 'text/html'
        self.error = None

    @property
    def COOKIES(self):
        if not self._COOKIES:
            self._COOKIES = Cookie.SimpleCookie()
        return self._COOKIES

    def set_cookie(self, key, value, **kargs):
        """ Sets a Cookie. Optional settings: expires, path, comment, domain, max-age, secure, version, httponly """
        self.COOKIES[key] = value
        for k in kargs:
            self.COOKIES[key][k] = kargs[k]

    def get_content_type(self):
        '''Gives access to the 'Content-Type' header and defaults to 'text/html'.'''
        return self.header['Content-Type']

    def set_content_type(self, value):
        self.header['Content-Type'] = value

    content_type = property(get_content_type, set_content_type, None, get_content_type.__doc__)



###############################################################################
###############################################################################

# 头字典-管理类
class HeaderDict(dict):
    ''' A dictionary with case insensitive (titled) keys.

    You may add a list of strings to send multible headers with the same name.'''

    def __setitem__(self, key, value):
        return dict.__setitem__(self, key.title(), value)

    def __getitem__(self, key):
        return dict.__getitem__(self, key.title())

    def __delitem__(self, key):
        return dict.__delitem__(self, key.title())

    def __contains__(self, key):
        return dict.__contains__(self, key.title())

    def items(self):
        """ Returns a list of (key, value) tuples """
        for key, values in dict.items(self):
            if not isinstance(values, list):
                values = [values]   # 类型转换
            for value in values:
                yield (key, str(value))

    def add(self, key, value):
        """ Adds a new header without deleting old ones """
        if isinstance(value, list):
            for v in value:
                self.add(key, v)
        elif key in self:
            if isinstance(self[key], list):
                self[key].append(value)
            else:
                self[key] = [self[key], value]
        else:
            self[key] = [value]






###############################################################################
#                             异常处理部分
###############################################################################


# HTTP状态码: 500
# 处理: 抛出异常
def abort(code=500, text='Unknown Error: Appliction stopped.'):
    """ Aborts execution and causes a HTTP error. """
    raise HTTPError(code, text)


# HTTP状态码: 307
# 处理: 抛出异常, 重定向
def redirect(url, code=307):
    """ Aborts execution and causes a 307 redirect """
    response.status = code                # 响应 - 状态码
    response.header['Location'] = url     # 响应 - 头

    raise BreakTheBottle("")   # 抛出异常


# HTTP状态码: 401
# 异常处理: 发送一个静态文本,作相应
def send_file(filename, root, guessmime=True, mimetype='text/plain'):
    """ Aborts execution and sends a static files as response. """
    root = os.path.abspath(root) + '/'
    filename = os.path.normpath(filename).strip('/')
    filename = os.path.join(root, filename)

    if not filename.startswith(root):    # HTTP状态码: 401
        abort(401, "Access denied.")
    if not os.path.exists(filename) or not os.path.isfile(filename):
        abort(404, "File does not exist.")     # 文件不存在
    if not os.access(filename, os.R_OK):
        abort(401, "You do not have permission to access this file.")

    if guessmime:
        guess = mimetypes.guess_type(filename)[0]
        if guess:
            response.content_type = guess
        elif mimetype:
            response.content_type = mimetype
    elif mimetype:
        response.content_type = mimetype

    stats = os.stat(filename)
    # TODO: HTTP_IF_MODIFIED_SINCE -> 304 (Thu, 02 Jul 2009 23:16:31 CEST)
    if 'Content-Length' not in response.header:
        response.header['Content-Length'] = stats.st_size
    if 'Last-Modified' not in response.header:
        ts = time.gmtime(stats.st_mtime)
        ts = time.strftime("%a, %d %b %Y %H:%M:%S +0000", ts)
        response.header['Last-Modified'] = ts

    raise BreakTheBottle(open(filename, 'r'))    # 抛出异常


###############################################################################
###############################################################################
###############################################################################


# Routing   路由处理部分-定义

def compile_route(route):  # 编译路由串
    """ Compiles a route string and returns a precompiled RegexObject.

    Routes may contain regular expressions with named groups to support url parameters.
    Example: '/user/(?P<id>[0-9]+)' will match '/user/5' with {'id':'5'}

    A more human readable syntax is supported too.
    Example: '/user/:id/:action' will match '/user/5/kiss' with {'id':'5', 'action':'kiss'}
    """
    route = route.strip().lstrip('$^/ ').rstrip('$^ ')  # 字符串过滤字符.

    route = re.sub(r':([a-zA-Z_]+)(?P<uniq>[^\w/])(?P<re>.+?)(?P=uniq)', r'(?P<\1>\g<re>)', route)
    route = re.sub(r':([a-zA-Z_]+)', r'(?P<\1>[^/]+)', route)

    return re.compile('^/%s$' % route)  # 路由需要正则表达式处理.


###############################################################################
# 功能: URL 匹配
#
# 参数:
#    - url: 路由地址
#    - method: 请求的方法, GET, POST 等
###############################################################################
def match_url(url, method='GET'):  # 匹配 URL 地址 --- 在 WSGIHandler() 函数中调用.
    """Returns the first matching handler and a parameter dict or (None, None).

    This reorders the ROUTING_REGEXP list every 1000 requests. To turn this off, use OPTIMIZER=False"""

    url = '/' + url.strip().lstrip("/")  # URL 串过滤字符.

    # 路由匹配:
    # 先从全局的静态路由表里查找,是否已经存在.
    #
    # Search for static routes first
    route = ROUTES_SIMPLE.get(method, {}).get(url, None)  # 第一次搜索静态路由.

    if route:
        return (route, {})       # 找到静态路由,直接返回.

    # 如果未找到,搜索匹配
    #
    # Now search regexp routes
    routes = ROUTES_REGEXP.get(method, [])  # 没找到,搜索 路由的正则表达式串.

    for i in xrange(len(routes)):
        match = routes[i][0].match(url)
        if match:
            handler = routes[i][1]

            if i > 0 and OPTIMIZER and random.random() <= 0.001:
                # Every 1000 requests, we swap the matching route with its predecessor.
                # Frequently used routes will slowly wander up the list.
                routes[i - 1], routes[i] = routes[i], routes[i - 1]  # 交换

            return (handler, match.groupdict())  # 返回处理结果.
    return (None, None)     # 处理失败,返回 None


###############################################################################
# 功能: 添加路由至路由映射表
#
# 参数:
#     - route: 路由
#     - handler:
#     - method:
#     - simple:
# 结果: 更新2个全局路由字典
#     - ROUTES_SIMPLE
#     - ROUTES_REGEXP
#
def add_route(route, handler, method='GET', simple=False):
    """ Adds a new route to the route mappings.

        Example:
        def hello():
          return "Hello world!"
        add_route(r'/hello', hello)"""
    method = method.strip().upper()   # 对请求参数,作统一格式化

    if re.match(r'^/(\w+/)*\w*$', route) or simple:    # 正则匹配路由
        ROUTES_SIMPLE.setdefault(method, {})[route] = handler              # 更新全局路由字典
    else:
        route = compile_route(route)  # 调用, 定义在前面.
        ROUTES_REGEXP.setdefault(method, []).append([route, handler])      # 更新全局路由字典


###############################################################################
# 功能: 路由装饰器
#
# 参数:
#     - url:
#
# 依赖:
#     - 包裹函数: add_route()
#
def route(url, **kargs):
    """ Decorator for request handler. Same as add_route(url, handler)."""

    def wrapper(handler):
        add_route(url, handler, **kargs)
        return handler

    return wrapper


###############################################################################

def validate(**vkargs):  # 数据安全校验函数.---- 写成多层装饰器,技巧代码
    ''' Validates and manipulates keyword arguments by user defined callables
    and handles ValueError and missing arguments by raising HTTPError(400) '''

    def decorator(func):  # 装饰器
        def wrapper(**kargs):  # 包裹函数
            for key in vkargs:
                if key not in kargs:
                    abort(403, 'Missing parameter: %s' % key)
                try:
                    kargs[key] = vkargs[key](kargs[key])
                except ValueError, e:
                    abort(403, 'Wrong parameter format for: %s' % key)
            return func(**kargs)  # 注意返回值

        return wrapper  # 调用

    return decorator  # 调用


###############################################################################

# Error handling    出错处理部分定义.

def set_error_handler(code, handler):  # 错误的辅助处理函数.被下面 error()调用.
    """ Sets a new error handler. """
    code = int(code)  # 状态码 提示信息.将传入参数,转换成整型值.
    ERROR_HANDLER[code] = handler  # ERROR_HANDLER{}本身是个全局字典,这里整型值作键,填入 value 值.


###############################################################################

def error(code=500):  # 出错处理 -- 写成装饰器函数.
    """ Decorator for error handler. Same as set_error_handler(code, handler)."""

    def wrapper(handler):  # 包裹函数.
        set_error_handler(code, handler)
        return handler

    return wrapper  # 调用 内嵌包裹函数.


###############################################################################
######################## 服务适配器部分 ##########################################
# 1. web Server 这部分代码,多是导入现成的包,自己修改处理的代码,很少.
# 2. 注意这种开发思想.
# 3. 这里有 内嵌函数定义的应用,注意一下.
###############################################################################

# Server adapter   服务适配器部分-定义
# 由全局的run()函数, 定位到此处.
class ServerAdapter(object):
    def __init__(self, host='127.0.0.1', port=8080, **kargs):
        self.host = host
        self.port = int(port)
        self.options = kargs

    def __repr__(self):
        return "%s (%s:%d)" % (self.__class__.__name__, self.host, self.port)

    def run(self, handler):
        pass


###############################################################################
# 接口定义.调用.
# mark
class WSGIRefServer(ServerAdapter):  # 不同的 web 服务器,导入不同的包处理.并重写run()函数.
    def run(self, handler):  # 重写 run() 函数.
        from wsgiref.simple_server import make_server

        srv = make_server(self.host, self.port, handler)  # 调用其他人写的库,所以这个代码,自己处理的内容很少.
        srv.serve_forever()  # 开启服务.


class CherryPyServer(ServerAdapter):
    def run(self, handler):
        from cherrypy import wsgiserver

        server = wsgiserver.CherryPyWSGIServer((self.host, self.port), handler)
        server.start()


class FlupServer(ServerAdapter):
    def run(self, handler):  # 重写 run() 函数.
        from flup.server.fcgi import WSGIServer

        WSGIServer(handler, bindAddress=(self.host, self.port)).run()


class PasteServer(ServerAdapter):
    def run(self, handler):  # 重写 run() 函数.
        from paste import httpserver
        from paste.translogger import TransLogger

        app = TransLogger(handler)
        httpserver.serve(app, host=self.host, port=str(self.port))


class FapwsServer(ServerAdapter):
    """ Extreamly fast Webserver using libev (see http://william-os4y.livejournal.com/)
        Experimental ... """

    def run(self, handler):  # 重写 run() 函数.
        import fapws._evwsgi as evwsgi
        from fapws import base
        import sys

        evwsgi.start(self.host, self.port)
        evwsgi.set_base_module(base)

        def app(environ, start_response):  # 函数嵌套定义,特别注意.
            environ['wsgi.multiprocess'] = False
            return handler(environ, start_response)

        evwsgi.wsgi_cb(('', app))  # 调用内嵌的 app()函数
        evwsgi.run()







###############################################################################
#                        框架全局入口
###############################################################################
# 功能: 全局入口
#
# 参数:
#    - server: web服务器
#    - host: 访问IP
#    - port: 端口号
#    - optinmize: 性能优化开关(该单词拼写有误)
#    - kargs: 扩展参数
#
# 关键代码:
#       - server.run(WSGIHandler)    # 启动web服务
# 备注:
#     1. 注意run()函数默认参数选项.
#     2. server.run() 根据不同的 web Server ,进行选择.
#     3. 理解 bottle 库源码的组织结构.
#
###############################################################################

def run(server=WSGIRefServer, host='127.0.0.1', port=8080, optinmize=False, **kargs):
    """ Runs bottle as a web server, using Python's built-in wsgiref implementation by default.

    You may choose between WSGIRefServer, CherryPyServer, FlupServer and
    PasteServer or write your own server adapter.
    """
    global OPTIMIZER

    OPTIMIZER = bool(optinmize)
    quiet = bool('quiet' in kargs and kargs['quiet'])    # 传入该参数,运行后,不输出提示log信息

    # 对 server 参数作检查: 若 server 参数是类名, 进行一次 实例化 操作.
    # Instanciate server, if it is a class instead of an instance
    if isinstance(server, type) and issubclass(server, ServerAdapter):
        server = server(host=host, port=port, **kargs)  # 初始化服务参数.

    # 再次检查 server 参数
    if not isinstance(server, ServerAdapter):   # 若处理后的 server, 并非 ServerAdapter 的 实例,报错
        raise RuntimeError("Server must be a subclass of ServerAdapter")

    if not quiet:
        print 'Bottle server starting up (using %s)...' % repr(server)
        print 'Listening on http://%s:%d/' % (server.host, server.port)
        print 'Use Ctrl-C to quit.'
        print

    try:
        server.run(WSGIHandler)  # 启动web服务. 关键参数是 server 参数. 是 ServerAdapter() 类的实例.
    except KeyboardInterrupt:
        print "Shuting down..."








###############################################################################
#                        异常处理
###############################################################################

# Templates异常处理
class TemplateError(BottleException): pass


class TemplateNotFoundError(BottleException): pass


###############################################################################

class BaseTemplate(object):  # 模板的基类定义.
    def __init__(self, template='', filename='<template>'):
        self.source = filename
        if self.source != '<template>':
            fp = open(filename)
            template = fp.read()
            fp.close()
        self.parse(template)

    def parse(self, template):
        raise NotImplementedError

    def render(self, **args):
        raise NotImplementedError

    @classmethod
    def find(cls, name):
        files = [path % name for path in TEMPLATE_PATH if os.path.isfile(path % name)]
        if files:
            return cls(filename=files[0])
        else:
            raise TemplateError('Template not found: %s' % repr(name))


class MakoTemplate(BaseTemplate):  # 模板类-定义
    def parse(self, template):
        from mako.template import Template

        self.tpl = Template(template)

    def render(self, **args):
        return self.tpl.render(**args)


class SimpleTemplate(BaseTemplate):  # 简单的模板类定义

    re_python = re.compile(
        r'^\s*%\s*(?:(if|elif|else|try|except|finally|for|while|with|def|class)|(include.*)|(end.*)|(.*))')
    re_inline = re.compile(r'\{\{(.*?)\}\}')
    dedent_keywords = ('elif', 'else', 'except', 'finally')

    def parse(self, template):
        indent = 0
        strbuffer = []
        code = []
        self.subtemplates = {}

        class PyStmt(str):
            def __repr__(self): return 'str(' + self + ')'

        def flush():
            if len(strbuffer):
                code.append(" " * indent + "stdout.append(%s)" % repr(''.join(strbuffer)))
                code.append("\n" * len(strbuffer))  # to preserve line numbers
                del strbuffer[:]

        for line in template.splitlines(True):
            m = self.re_python.match(line)
            if m:
                flush()
                keyword, include, end, statement = m.groups()
                if keyword:
                    if keyword in self.dedent_keywords:
                        indent -= 1
                    code.append(" " * indent + line[m.start(1):])
                    indent += 1
                elif include:
                    tmp = line[m.end(2):].strip().split(None, 1)
                    name = tmp[0]
                    args = tmp[1:] and tmp[1] or ''
                    self.subtemplates[name] = SimpleTemplate.find(name)
                    code.append(" " * indent + "stdout.append(_subtemplates[%s].render(%s))\n" % (repr(name), args))
                elif end:
                    indent -= 1
                    code.append(" " * indent + '#' + line[m.start(3):])
                elif statement:
                    code.append(" " * indent + line[m.start(4):])
            else:
                splits = self.re_inline.split(line)  # text, (expr, text)*
                if len(splits) == 1:
                    strbuffer.append(line)
                else:
                    flush()
                    for i in xrange(1, len(splits), 2):
                        splits[i] = PyStmt(splits[i])
                    code.append(" " * indent + "stdout.extend(%s)\n" % repr(splits))
        flush()
        self.co = compile("".join(code), self.source, 'exec')

    def render(self, **args):
        ''' Returns the rendered template using keyword arguments as local variables. '''
        args['stdout'] = []
        args['_subtemplates'] = self.subtemplates
        eval(self.co, args, globals())
        return ''.join(args['stdout'])




###############################################################################
# 功能: 模板定义.
#
# 参数:
#    - template:
#    - template_adapter: 模板适配器
#    - **args:
#
###############################################################################

def template(template, template_adapter=SimpleTemplate, **args):
    ''' Returns a string from a template '''
    if template not in TEMPLATES:
        if template.find("\n") == -1 and template.find("{") == -1 and template.find("%") == -1:
            try:
                TEMPLATES[template] = template_adapter.find(template)
            except TemplateNotFoundError:
                pass
        else:
            TEMPLATES[template] = template_adapter(template)
    if template not in TEMPLATES:
        abort(500, 'Template not found')
    args['abort'] = abort
    args['request'] = request
    args['response'] = response
    return TEMPLATES[template].render(**args)


def mako_template(template_name, **args):
    return template(template_name, template_adapter=MakoTemplate, **args)





###############################################################################
#                           数据库处理部分
###############################################################################


# Database
class BottleBucket(object):
    '''Memory-caching wrapper around anydbm'''

    def __init__(self, name):
        self.__dict__['name'] = name
        self.__dict__['db'] = dbm.open(DB_PATH + '/%s.db' % name, 'c')
        self.__dict__['mmap'] = {}

    def __getitem__(self, key):
        if key not in self.mmap:
            self.mmap[key] = pickle.loads(self.db[key])
        return self.mmap[key]

    def __setitem__(self, key, value):
        self.mmap[key] = value

    def __delitem__(self, key):
        if key in self.mmap:
            del self.mmap[key]
        del self.db[key]

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)

    def __iter__(self):
        return iter(set(self.db.keys() + self.mmap.keys()))

    def __contains__(self, key):
        return bool(key in self.keys())

    def __len__(self):
        return len(self.keys())

    ###############################################################################

    def keys(self):  # 键
        return list(iter(self))

    def save(self):  # 保存
        self.close()
        self.__init__(self.name)

    def close(self):  # 关闭
        for key in self.mmap.keys():
            pvalue = pickle.dumps(self.mmap[key], pickle.HIGHEST_PROTOCOL)
            if key not in self.db or pvalue != self.db[key]:
                self.db[key] = pvalue
        self.mmap.clear()
        self.db.close()

    def clear(self):  # 清除
        for key in self.db.keys():
            del self.db[key]
        self.mmap.clear()

    def update(self, other):  # 更新
        self.mmap.update(other)

    def get(self, key, default=None):  # 获取
        try:
            return self[key]
        except KeyError:
            if default:
                return default
            raise






###############################################################################


class BottleDB(threading.local):  # 数据库的管理类定义, 注意继承的基类
    '''Holds multible BottleBucket instances in a thread-local way.'''

    def __init__(self):
        self.__dict__['open'] = {}

    def __getitem__(self, key):
        if key not in self.open and not key.startswith('_'):
            self.open[key] = BottleBucket(key)       # 调用
        return self.open[key]

    def __setitem__(self, key, value):
        if isinstance(value, BottleBucket):
            self.open[key] = value
        elif hasattr(value, 'items'):
            if key not in self.open:
                self.open[key] = BottleBucket(key)
            self.open[key].clear()
            for k, v in value.items():
                self.open[key][k] = v
        else:
            raise ValueError("Only dicts and BottleBuckets are allowed.")

    def __delitem__(self, key):
        if key not in self.open:
            self.open[key].clear()
            self.open[key].save()
            del self.open[key]

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)

    def save(self):  # 保存
        self.close()
        self.__init__()

    def close(self):  # 关闭
        for db in self.open.values():
            db.close()
        self.open.clear()







###############################################################################
#                       全局变量定义 - 配置参数
###############################################################################

# Modul initialization    模块的初始化参数.

DB_PATH = './'                                     # 默认数据库路径

DEBUG = False                                      # 默认调试开关
OPTIMIZER = False                                  # 默认优化开关

TEMPLATE_PATH = ['./%s.tpl', './views/%s.tpl']     # 默认模板路径
TEMPLATES = {}                                     # 模板

ROUTES_SIMPLE = {}  # 全局定义 -- 路由 -- 字典
ROUTES_REGEXP = {}  # 全局定义 -- 路由 -- 正则表达式-字典

ERROR_HANDLER = {}  # 全局定义 -- 错误处理

###############################################################################
HTTP_CODES = {  # HTTP-状态码
                100: 'CONTINUE',
                101: 'SWITCHING PROTOCOLS',
                200: 'OK',
                201: 'CREATED',
                202: 'ACCEPTED',
                203: 'NON-AUTHORITATIVE INFORMATION',
                204: 'NO CONTENT',
                205: 'RESET CONTENT',
                206: 'PARTIAL CONTENT',
                300: 'MULTIPLE CHOICES',
                301: 'MOVED PERMANENTLY',
                302: 'FOUND',
                303: 'SEE OTHER',
                304: 'NOT MODIFIED',
                305: 'USE PROXY',
                306: 'RESERVED',
                307: 'TEMPORARY REDIRECT',
                400: 'BAD REQUEST',
                401: 'UNAUTHORIZED',
                402: 'PAYMENT REQUIRED',
                403: 'FORBIDDEN',
                404: 'NOT FOUND',
                405: 'METHOD NOT ALLOWED',
                406: 'NOT ACCEPTABLE',
                407: 'PROXY AUTHENTICATION REQUIRED',
                408: 'REQUEST TIMEOUT',
                409: 'CONFLICT',
                410: 'GONE',
                411: 'LENGTH REQUIRED',
                412: 'PRECONDITION FAILED',
                413: 'REQUEST ENTITY TOO LARGE',
                414: 'REQUEST-URI TOO LONG',
                415: 'UNSUPPORTED MEDIA TYPE',
                416: 'REQUESTED RANGE NOT SATISFIABLE',
                417: 'EXPECTATION FAILED',
                500: 'INTERNAL SERVER ERROR',
                501: 'NOT IMPLEMENTED',
                502: 'BAD GATEWAY',
                503: 'SERVICE UNAVAILABLE',
                504: 'GATEWAY TIMEOUT',
                505: 'HTTP VERSION NOT SUPPORTED',
                }




###############################################################################
# 针对threading.local() 说明:
#     - 1. 表示thread-local数据的一个类
#     - 2. thread-local数据是值只特定于线程的数据
#     - 3. 要管理thread-local数据，只需创建local（或其子类）的一个实例并在它上面存储属性
#     - 4. 该实例的值对于各自的线程将是不同的。
# 官方文档参考:
#      - http://python.usyiyi.cn/python_278/library/threading.html
#      - https://docs.python.org/2/library/threading.html
###############################################################################

request = Request()  # 请求
response = Response()  # 响应
db = BottleDB()  # 数据库
local = threading.local()  # 本地线程

###############################################################################






###############################################################################
# 功能: 500错误 - 服务器内部错误
# 说明:
#     - debug模式: 详细的报错信息栈跟踪
#     - 生成环境: 服务器内部错误
#
###############################################################################
@error(500)
def error500(exception):  # 出错处理
    """If an exception is thrown, deal with it and present an error page."""
    if DEBUG:    # 调试模式报错信息
        return "<br>\n".join(traceback.format_exc(10).splitlines()).replace('  ', '&nbsp;&nbsp;')
    else:
        return """<b>Error:</b> Internal server error."""     # 服务器内部错误



###############################################################################
# 功能: 默认的出错处理 - 生成网站出错,报错信息页面
# 说明:
#     - 子调用: template(), 生成报错信息模板页面.
#
###############################################################################
def error_default(exception):
    status = response.status
    name = HTTP_CODES.get(status, 'Unknown').title()
    url = request.path
    """If an exception is thrown, deal with it and present an error page."""
    yield template('<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">' + \
                   '<html><head><title>Error {{status}}: {{msg}}</title>' + \
                   '</head><body><h1>Error {{status}}: {{msg}}</h1>' + \
                   '<p>Sorry, the requested URL {{url}} caused an error.</p>',
                   status=status,
                   msg=name,
                   url=url
                   )
    if hasattr(exception, 'output'):
        yield exception.output
    yield '</body></html>'
