# -*- coding: utf-8 -*-


"""
签注说明:
    - date: 2016-01-27
    - author: hhstore
    - 说明:
        - 删除部分无关紧要的原注释,不影响理解
        - 部分源码注释,作了精简翻译.

flask: 微型web框架.
    - 核心依赖:
        - Werkzeug :
            - 功能实现: request, response
            - 导入接口: 部分未实现接口, 直接导入用
        - jinja2 :
            - 功能实现:
            - 导入接口: 模板

    - 核心功能模块:
        - Request()    # 未实现,借用自 Werkzeug
        - Response()   # 未实现,借用自 Werkzeug
        - Flask()      # 核心功能类

    - 点评:
        - 对比 bottle.py框架, flask第一版的代码并不多, 但是 有几个关键模块,没有自己实现.
        - 而 bottle.py 的 web框架 核心组件, 都是自己实现的,未依赖任何其他第三方模块.

"""


from __future__ import with_statement
import os
import sys

from threading import local

from jinja2 import (            # flask 部分模块实现,依赖 jinja2
    Environment,
    PackageLoader,
    FileSystemLoader
)


# 说明:
#   - 最新版本的 werkzeug 模块组织结构发生改变, 下面这条导包语句,已失效
#
from werkzeug import (          # flask 部分模块实现,严重依赖 werkzeug
    Request as RequestBase,     # 关键依赖
    Response as ResponseBase,   # 关键依赖
    LocalStack,                 # 文件末尾, _request_ctx_stack 中依赖
    LocalProxy,                 # 文件末尾, current_app 中依赖
    create_environ,
    cached_property,
    SharedDataMiddleware        # Flask() 模块 中引用
)

from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, InternalServerError
from werkzeug.contrib.securecookie import SecureCookie

from werkzeug import abort, redirect      # werkzeug 依赖: 本文件未使用,但导入以用作 对外接口
from jinja2 import Markup, escape         # jinja2 的依赖: 本文件未使用,但导入以用作 对外接口


try:
    import pkg_resources
    pkg_resources.resource_stream
except (ImportError, AttributeError):
    pkg_resources = None


################################################################################
#                             代码主体部分
# 说明:
#   - 主要模块:
#       - Request()     # 未独立实现, 依赖 werkzeug
#       - Response()    # 未独立实现, 依赖 werkzeug
#       - Flask()       # web 框架核心模块
#
#   - 对外接口函数:
#       - url_for()
#       - flash()
#       - get_flashed_messages
#       - render_template()
#       - render_template_string()
#
#   - 全局上下文对象:    [ 特别注意理解: 为何是上下文的?]
#       - _request_ctx_stack
#       - current_app
#       - request
#       - session
#       - g
#
#   - 辅助模块:
#       - _RequestGlobals()
#       - _RequestContext()
#
# todo: 注解说明
#
################################################################################

class Request(RequestBase):       # 未独立实现, 依赖 werkzeug.Request
    def __init__(self, environ):
        RequestBase.__init__(self, environ)
        self.endpoint = None
        self.view_args = None


class Response(ResponseBase):     # 未独立实现, 依赖 werkzeug.Response
    default_mimetype = 'text/html'


class _RequestGlobals(object):    # 预定义接口: _RequestContext() 中 引用
    pass


class _RequestContext(object):    # 请求上下文, 在 flask.request_context() 中 引用

    def __init__(self, app, environ):
        self.app = app
        self.url_adapter = app.url_map.bind_to_environ(environ)
        self.request = app.request_class(environ)
        self.session = app.open_session(self.request)
        self.g = _RequestGlobals()    # 预定义接口
        self.flashes = None

    def __enter__(self):
        _request_ctx_stack.push(self)

    def __exit__(self, exc_type, exc_value, tb):
        if tb is None or not self.app.debug:
            _request_ctx_stack.pop()


def url_for(endpoint, **values):    # 实现依赖: werkzeug.LocalStack 模块
    return _request_ctx_stack.top.url_adapter.build(endpoint, values)


def flash(message):     # 向页面 输出 一条 消息
    # session : 文件末尾定义的 全局上下文对象
    session['_flashes'] = (session.get('_flashes', [])) + [message]


def get_flashed_messages():
    flashes = _request_ctx_stack.top.flashes
    if flashes is None:
        _request_ctx_stack.top.flashes = flashes = \
            session.pop('_flashes', [])
    return flashes


def render_template(template_name, **context):    # 渲染模板页面: 通过查找 templates 目录
    # current_app : 文件结尾定义的 全局上下文对象
    # 实现依赖 werkzeug
    current_app.update_template_context(context)
    return current_app.jinja_env.get_template(template_name).render(context)


def render_template_string(source, **context):   # 渲染模板页面: 通过传入的模板字符串
    # 同上
    current_app.update_template_context(context)
    return current_app.jinja_env.from_string(source).render(context)


def _default_template_ctx_processor():    # 默认的模板上下文 处理机
    reqctx = _request_ctx_stack.top     # 文件末尾定义的 全局上下文对象

    return dict(
        request=reqctx.request,
        session=reqctx.session,
        g=reqctx.g
    )


def _get_package_path(name):     # 获取 模块包 路径, Flask() 中 引用
    try:
        return os.path.abspath(os.path.dirname(sys.modules[name].__file__))
    except (KeyError, AttributeError):
        return os.getcwd()


###################################################################
#                       核心功能接口
#
#
#
###################################################################
class Flask(object):

    request_class = Request      # 请求类

    response_class = Response    # 响应类

    static_path = '/static'      # 静态资源路径

    secret_key = None            # 密钥配置

    session_cookie_name = 'session'      # 安全cookie

    # 模板参数
    jinja_options = dict(
        autoescape=True,
        extensions=['jinja2.ext.autoescape', 'jinja2.ext.with_']
    )

    def __init__(self, package_name):
        self.debug = False     # 调试模式开关

        # 注意:
        #   - 这个参数,不是随便乱给的
        #   - 要跟实际的 项目工程目录名对应,否则无法找到对应的工程
        #
        self.package_name = package_name

        # 注意:
        #   - 调用前面定义的 全局私有方法
        #   - 依赖前面的传入参数, 通过该参数, 获取 项目工程源码根目录.
        #
        self.root_path = _get_package_path(self.package_name)    # 获取项目根目录

        self.view_functions = {}         # 视图函数集

        self.error_handlers = {}           # 出错处理

        self.before_request_funcs = []     # 预处理

        self.after_request_funcs = []      # 结束清理

        self.template_context_processors = [_default_template_ctx_processor]

        # todo: 待深入
        self.url_map = Map()    # 关键依赖: werkzeug.routing.Map

        if self.static_path is not None:    # 处理静态资源
            #
            # todo: 待深入 关键依赖: werkzeug.routing.Rule
            self.url_map.add(Rule(self.static_path + '/<filename>',
                                  build_only=True, endpoint='static'))

            if pkg_resources is not None:
                target = (self.package_name, 'static')
            else:
                target = os.path.join(self.root_path, 'static')

            #
            # todo: 待深入, 关键依赖: werkzeug.SharedDataMiddleware
            self.wsgi_app = SharedDataMiddleware(self.wsgi_app, {
                self.static_path: target
            })

        # todo: 待深入, jinja2 模板配置
        self.jinja_env = Environment(loader=self.create_jinja_loader(),
                                     **self.jinja_options)
        self.jinja_env.globals.update(
            url_for=url_for,
            get_flashed_messages=get_flashed_messages
        )

    # 加载 templates 目录文件
    def create_jinja_loader(self):
        if pkg_resources is None:
            # 加载 模板目录 文件
            return FileSystemLoader(os.path.join(self.root_path, 'templates'))
        return PackageLoader(self.package_name)

    def update_template_context(self, context):
        reqctx = _request_ctx_stack.top
        for func in self.template_context_processors:
            context.update(func())

    #
    # 对外运行接口: 借用werkzeug.run_simple 实现
    #
    def run(self, host='localhost', port=5000, **options):
        from werkzeug import run_simple    # todo: 待深入, 关键依赖: 核心运行模块
        if 'debug' in options:
            self.debug = options.pop('debug')
        options.setdefault('use_reloader', self.debug)
        options.setdefault('use_debugger', self.debug)

        return run_simple(host, port, self, **options)    # 关键依赖:

    def test_client(self):
        from werkzeug import Client        # todo: 待深入, 关键依赖:
        return Client(self, self.response_class, use_cookies=True)

    def open_resource(self, resource):
        if pkg_resources is None:
            return open(os.path.join(self.root_path, resource), 'rb')
        return pkg_resources.resource_stream(self.package_name, resource)

    #
    # 创建 session
    #
    def open_session(self, request):
        key = self.secret_key
        if key is not None:
            return SecureCookie.load_cookie(request, self.session_cookie_name,
                                            secret_key=key)

    #
    # 关键代码: 保存session
    #
    def save_session(self, session, response):
        if session is not None:
            session.save_cookie(response, self.session_cookie_name)

    # 添加路由规则, route() 装饰器的实现,依赖
    def add_url_rule(self, rule, endpoint, **options):
        options['endpoint'] = endpoint
        options.setdefault('methods', ('GET',))

        # 路由规则添加
        self.url_map.add(Rule(rule, **options))

    #
    # 路由装饰器定义:
    #
    def route(self, rule, **options):
        def decorator(f):
            self.add_url_rule(rule, f.__name__, **options)    # 添加路由规则
            self.view_functions[f.__name__] = f               # 更新 视图函数集合, 前面定义,{}
            return f
        return decorator

    #
    # 错误处理装饰器定义:
    #
    def errorhandler(self, code):
        def decorator(f):
            self.error_handlers[code] = f     # 前述定义{}
            return f
        return decorator

    #
    # 请求前,预处理:
    #   - 注册预处理函数
    #
    def before_request(self, f):
        self.before_request_funcs.append(f)
        return f

    #
    # 请求结束, 清理工作:
    #   - 注册清理函数
    #
    def after_request(self, f):
        self.after_request_funcs.append(f)
        return f

    #
    # 模板上下文处理函数
    #
    def context_processor(self, f):
        self.template_context_processors.append(f)
        return f

    #
    # 请求匹配:
    #
    def match_request(self):
        rv = _request_ctx_stack.top.url_adapter.match()
        request.endpoint, request.view_args = rv
        return rv

    #
    # 处理请求:
    #   - 处理 路由URL 和 对应的 视图函数
    #
    def dispatch_request(self):
        try:
            endpoint, values = self.match_request()    # 请求匹配
            return self.view_functions[endpoint](**values)
        except HTTPException, e:
            handler = self.error_handlers.get(e.code)
            if handler is None:
                return e
            return handler(e)
        except Exception, e:
            handler = self.error_handlers.get(500)
            if self.debug or handler is None:
                raise
            return handler(e)

    # 返回响应
    def make_response(self, rv):
        if isinstance(rv, self.response_class):
            return rv
        if isinstance(rv, basestring):
            return self.response_class(rv)
        if isinstance(rv, tuple):
            return self.response_class(*rv)
        return self.response_class.force_type(rv, request.environ)

    #
    # 请求前, 执行预处理工作中:
    #
    def preprocess_request(self):
        for func in self.before_request_funcs:
            rv = func()    # 执行预处理函数
            if rv is not None:
                return rv

    #
    # 在返回响应前, 作 清理工作, 与上配对
    #
    def process_response(self, response):
        session = _request_ctx_stack.top.session
        if session is not None:
            self.save_session(session, response)     # 保存 session

        for handler in self.after_request_funcs:     # 请求结束后, 清理工作
            response = handler(response)
        return response

    #
    # 对外接口:
    #
    def wsgi_app(self, environ, start_response):
        with self.request_context(environ):
            rv = self.preprocess_request()      # 请求前, 预处理
            if rv is None:
                rv = self.dispatch_request()    # 处理请求

            response = self.make_response(rv)            # 返回响应
            response = self.process_response(response)   # 返回响应前, 作清理工作

            return response(environ, start_response)

    #
    # 请求上下文
    #
    def request_context(self, environ):
        return _RequestContext(self, environ)     # 请求上下文, 上述已定义该模块

    def test_request_context(self, *args, **kwargs):
        return self.request_context(create_environ(*args, **kwargs))

    def __call__(self, environ, start_response):
        """Shortcut for :attr:`wsgi_app`"""
        return self.wsgi_app(environ, start_response)


# context locals
_request_ctx_stack = LocalStack()    # 依赖 werkzeug.LocalStack 模块
current_app = LocalProxy(lambda: _request_ctx_stack.top.app)
request = LocalProxy(lambda: _request_ctx_stack.top.request)
session = LocalProxy(lambda: _request_ctx_stack.top.session)    # flash()函数 中 引用
g = LocalProxy(lambda: _request_ctx_stack.top.g)
