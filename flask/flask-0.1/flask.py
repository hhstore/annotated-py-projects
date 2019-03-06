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
#   - flask 部分模块实现,严重依赖 werkzeug
#   - werkzeug 最新版本,模块组织结构发生改变.
#   - 故替换部分失效导包语句,请注意
#   - 下面最后一条导包语句,已失效, 暂未找到有效的替换
#
from werkzeug.wrappers import Request as RequestBase, Response as ResponseBase    # 关键依赖
from werkzeug.local import LocalStack, LocalProxy     # 文件末尾, _request_ctx_stack, current_app 中依赖
from werkzeug.wsgi import SharedDataMiddleware        # Flask() 模块 中引用
from werkzeug.utils import cached_property
from werkzeug import create_environ    # 已失效

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
    """The request object used by default in flask.  Remembers the
    matched endpoint and view arguments.

    It is what ends up as :class:`~flask.request`.  If you want to replace
    the request object used you can subclass this and set
    :attr:`~flask.Flask.request_class` to your subclass.
    """

    def __init__(self, environ):
        RequestBase.__init__(self, environ)
        self.endpoint = None
        self.view_args = None


class Response(ResponseBase):     # 未独立实现, 依赖 werkzeug.Response
    """The response object that is used by default in flask.  Works like the
    response object from Werkzeug but is set to have a HTML mimetype by
    default.  Quite often you don't have to create this object yourself because
    :meth:`~flask.Flask.make_response` will take care of that for you.

    If you want to replace the response object used you can subclass this and
    set :attr:`~flask.Flask.request_class` to your subclass.
    """
    default_mimetype = 'text/html'


class _RequestGlobals(object):    # 预定义接口: _RequestContext() 中 引用
    pass


class _RequestContext(object):    # 请求上下文, 在 flask.request_context() 中 引用
    """The request context contains all request relevant information.  It is
    created at the beginning of the request and pushed to the
    `_request_ctx_stack` and removed at the end of it.  It will create the
    URL adapter and request object for the WSGI environment provided.
    """

    def __init__(self, app, environ):
        self.app = app
        self.url_adapter = app.url_map.bind_to_environ(environ)
        self.request = app.request_class(environ)

        # 带上下文的 session 实现
        self.session = app.open_session(self.request)

        # 关键: 待上下文的 g 实现
        self.g = _RequestGlobals()    # 预定义接口

        self.flashes = None

    def __enter__(self):
        _request_ctx_stack.push(self)

    def __exit__(self, exc_type, exc_value, tb):
        # do not pop the request stack if we are in debug mode and an
        # exception happened.  This will allow the debugger to still
        # access the request object in the interactive shell.
        if tb is None or not self.app.debug:
            _request_ctx_stack.pop()


def url_for(endpoint, **values):    # 实现依赖: werkzeug.LocalStack 模块
    """Generates a URL to the given endpoint with the method provided.

    :param endpoint: the endpoint of the URL (name of the function)
    :param values: the variable arguments of the URL rule
    """
    return _request_ctx_stack.top.url_adapter.build(endpoint, values)


def flash(message):     # 向页面 输出 一条 消息
    """Flashes a message to the next request.  In order to remove the
    flashed message from the session and to display it to the user,
    the template has to call :func:`get_flashed_messages`.

    :param message: the message to be flashed.
    """

    # session : 文件末尾定义的 全局上下文对象
    session['_flashes'] = (session.get('_flashes', [])) + [message]


def get_flashed_messages():
    """Pulls all flashed messages from the session and returns them.
    Further calls in the same request to the function will return
    the same messages.
    """
    flashes = _request_ctx_stack.top.flashes
    if flashes is None:
        _request_ctx_stack.top.flashes = flashes = \
            session.pop('_flashes', [])
    return flashes


def render_template(template_name, **context):    # 渲染模板页面: 通过查找 templates 目录
    """Renders a template from the template folder with the given
    context.

    :param template_name: the name of the template to be rendered
    :param context: the variables that should be available in the
                    context of the template.
    """

    # current_app : 文件结尾定义的 全局上下文对象
    # 实现依赖 werkzeug
    current_app.update_template_context(context)
    return current_app.jinja_env.get_template(template_name).render(context)


def render_template_string(source, **context):   # 渲染模板页面: 通过传入的模板字符串
    """Renders a template from the given template source string
    with the given context.

    :param template_name: the sourcecode of the template to be
                          rendered
    :param context: the variables that should be available in the
                    context of the template.
    """
    # 同上
    current_app.update_template_context(context)
    return current_app.jinja_env.from_string(source).render(context)


def _default_template_ctx_processor():    # 默认的模板上下文 处理机
    """Default template context processor.
    Injects `request`, `session` and `g`.
    """
    reqctx = _request_ctx_stack.top     # 文件末尾定义的 全局上下文对象

    return dict(
        request=reqctx.request,
        session=reqctx.session,
        g=reqctx.g
    )


def _get_package_path(name):     # 获取 模块包 路径, Flask() 中 引用
    """Returns the path to a package or cwd if that cannot be found."""
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
    """The flask object implements a WSGI application and acts as the central
    object.  It is passed the name of the module or package of the
    application.  Once it is created it will act as a central registry for
    the view functions, the URL rules, template configuration and much more.

    The name of the package is used to resolve resources from inside the
    package or the folder the module is contained in depending on if the
    package parameter resolves to an actual python package (a folder with
    an `__init__.py` file inside) or a standard module (just a `.py` file).

    For more information about resource loading, see :func:`open_resource`.

    Usually you create a :class:`Flask` instance in your main module or
    in the `__init__.py` file of your package like this::

        from flask import Flask
        app = Flask(__name__)
    """

    #: the class that is used for request objects.  See :class:`~flask.request`
    #: for more information.
    request_class = Request      # 请求类

    #: the class that is used for response objects.  See
    #: :class:`~flask.Response` for more information.
    response_class = Response    # 响应类

    #: path for the static files.  If you don't want to use static files
    #: you can set this value to `None` in which case no URL rule is added
    #: and the development server will no longer serve any static files.
    static_path = '/static'      # 静态资源路径

    #: if a secret key is set, cryptographic components can use this to
    #: sign cookies and other things.  Set this to a complex random value
    #: when you want to use the secure cookie for instance.
    secret_key = None            # 密钥配置

    #: The secure cookie uses this for the name of the session cookie
    session_cookie_name = 'session'      # 安全cookie

    #: options that are passed directly to the Jinja2 environment
    # 模板参数
    jinja_options = dict(
        autoescape=True,
        extensions=['jinja2.ext.autoescape', 'jinja2.ext.with_']
    )

    def __init__(self, package_name):
        #: the debug flag.  Set this to `True` to enable debugging of
        #: the application.  In debug mode the debugger will kick in
        #: when an unhandled exception ocurrs and the integrated server
        #: will automatically reload the application if changes in the
        #: code are detected.
        self.debug = False     # 调试模式开关

        #: the name of the package or module.  Do not change this once
        #: it was set by the constructor.
        #
        # 注意:
        #   - 这个参数,不是随便乱给的
        #   - 要跟实际的 项目工程目录名对应,否则无法找到对应的工程
        #
        self.package_name = package_name

        #: where is the app root located?
        #
        # 注意:
        #   - 调用前面定义的 全局私有方法
        #   - 依赖前面的传入参数, 通过该参数, 获取 项目工程源码根目录.
        #
        self.root_path = _get_package_path(self.package_name)    # 获取项目根目录

        #: a dictionary of all view functions registered.  The keys will
        #: be function names which are also used to generate URLs and
        #: the values are the function objects themselves.
        #: to register a view function, use the :meth:`route` decorator.
        self.view_functions = {}         # 视图函数集

        #: a dictionary of all registered error handlers.  The key is
        #: be the error code as integer, the value the function that
        #: should handle that error.
        #: To register a error handler, use the :meth:`errorhandler`
        #: decorator.
        self.error_handlers = {}           # 出错处理

        #: a list of functions that should be called at the beginning
        #: of the request before request dispatching kicks in.  This
        #: can for example be used to open database connections or
        #: getting hold of the currently logged in user.
        #: To register a function here, use the :meth:`before_request`
        #: decorator.
        self.before_request_funcs = []     # 预处理

        #: a list of functions that are called at the end of the
        #: request.  Tha function is passed the current response
        #: object and modify it in place or replace it.
        #: To register a function here use the :meth:`after_request`
        #: decorator.
        self.after_request_funcs = []      # 结束清理

        #: a list of functions that are called without arguments
        #: to populate the template context.  Each returns a dictionary
        #: that the template context is updated with.
        #: To register a function here, use the :meth:`context_processor`
        #: decorator.
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

        #: the Jinja2 environment.  It is created from the
        #: :attr:`jinja_options` and the loader that is returned
        #: by the :meth:`create_jinja_loader` function.
        # todo: 待深入, jinja2 模板配置
        self.jinja_env = Environment(loader=self.create_jinja_loader(),
                                     **self.jinja_options)
        self.jinja_env.globals.update(
            url_for=url_for,
            get_flashed_messages=get_flashed_messages
        )

    # 加载 templates 目录文件
    def create_jinja_loader(self):
        """Creates the Jinja loader.  By default just a package loader for
        the configured package is returned that looks up templates in the
        `templates` folder.  To add other loaders it's possible to
        override this method.
        """
        if pkg_resources is None:
            # 加载 模板目录 文件
            return FileSystemLoader(os.path.join(self.root_path, 'templates'))
        return PackageLoader(self.package_name)

    def update_template_context(self, context):
        """Update the template context with some commonly used variables.
        This injects request, session and g into the template context.

        :param context: the context as a dictionary that is updated in place
                        to add extra variables.
        """
        reqctx = _request_ctx_stack.top
        for func in self.template_context_processors:
            context.update(func())

    #
    # 对外运行接口: 借用werkzeug.run_simple 实现
    #
    def run(self, host='localhost', port=5000, **options):
        """Runs the application on a local development server.  If the
        :attr:`debug` flag is set the server will automatically reload
        for code changes and show a debugger in case an exception happened.

        :param host: the hostname to listen on.  set this to ``'0.0.0.0'``
                     to have the server available externally as well.
        :param port: the port of the webserver
        :param options: the options to be forwarded to the underlying
                        Werkzeug server.  See :func:`werkzeug.run_simple`
                        for more information.
        """
        from werkzeug import run_simple    # todo: 待深入, 关键依赖: 核心运行模块
        if 'debug' in options:
            self.debug = options.pop('debug')
        options.setdefault('use_reloader', self.debug)
        options.setdefault('use_debugger', self.debug)

        return run_simple(host, port, self, **options)    # 关键依赖:

    def test_client(self):
        """Creates a test client for this application.  For information
        about unit testing head over to :ref:`testing`.
        """
        from werkzeug import Client        # todo: 待深入, 关键依赖:
        return Client(self, self.response_class, use_cookies=True)

    def open_resource(self, resource):
        """Opens a resource from the application's resource folder.  To see
        how this works, consider the following folder structure::

            /myapplication.py
            /schemal.sql
            /static
                /style.css
            /template
                /layout.html
                /index.html

        If you want to open the `schema.sql` file you would do the
        following::

            with app.open_resource('schema.sql') as f:
                contents = f.read()
                do_something_with(contents)

        :param resource: the name of the resource.  To access resources within
                         subfolders use forward slashes as separator.
        """
        if pkg_resources is None:
            return open(os.path.join(self.root_path, resource), 'rb')
        return pkg_resources.resource_stream(self.package_name, resource)

    #
    # 关键接口: 创建 or 打开一个 会话(session)
    #   - 实现方式: 使用 cookie 实现
    #   - 默认把全部session数据, 存入一个 cookie 中.
    #   - 对比 flask-0.4 版本, 部分重构
    #
    def open_session(self, request):
        """Creates or opens a new session.
        Default implementation stores all session data in a signed cookie.
        This requires that the :attr:`secret_key` is set.

        :param request: an instance of :attr:`request_class`.
        """
        key = self.secret_key
        if key is not None:
            return SecureCookie.load_cookie(request, self.session_cookie_name,
                                            secret_key=key)

    #
    # 关键接口: 更新session
    #
    def save_session(self, session, response):
        """Saves the session if it needs updates.  For the default
        implementation, check :meth:`open_session`.

        :param session: the session to be saved (a
                        :class:`~werkzeug.contrib.securecookie.SecureCookie`
                        object)
        :param response: an instance of :attr:`response_class`
        """
        if session is not None:
            session.save_cookie(response, self.session_cookie_name)

    # 添加路由规则, route() 装饰器的实现,依赖
    def add_url_rule(self, rule, endpoint, **options):
        """Connects a URL rule.  Works exactly like the :meth:`route`
        decorator but does not register the view function for the endpoint.

        Basically this example::

            @app.route('/')
            def index():
                pass

        Is equivalent to the following::

            def index():
                pass
            app.add_url_rule('index', '/')
            app.view_functions['index'] = index

        :param rule: the URL rule as string
        :param endpoint: the endpoint for the registered URL rule.  Flask
                         itself assumes the name of the view function as
                         endpoint
        :param options: the options to be forwarded to the underlying
                        :class:`~werkzeug.routing.Rule` object
        """
        options['endpoint'] = endpoint
        options.setdefault('methods', ('GET',))

        # 路由规则添加
        self.url_map.add(Rule(rule, **options))

    #
    # 路由装饰器定义:
    #
    def route(self, rule, **options):
        """A decorator that is used to register a view function for a
        given URL rule.  Example::

            @app.route('/')
            def index():
                return 'Hello World'

        Variables parts in the route can be specified with angular
        brackets (``/user/<username>``).  By default a variable part
        in the URL accepts any string without a slash however a different
        converter can be specified as well by using ``<converter:name>``.

        Variable parts are passed to the view function as keyword
        arguments.

        The following converters are possible:

        =========== ===========================================
        `int`       accepts integers
        `float`     like `int` but for floating point values
        `path`      like the default but also accepts slashes
        =========== ===========================================

        Here some examples::

            @app.route('/')
            def index():
                pass

            @app.route('/<username>')
            def show_user(username):
                pass

            @app.route('/post/<int:post_id>')
            def show_post(post_id):
                pass

        An important detail to keep in mind is how Flask deals with trailing
        slashes.  The idea is to keep each URL unique so the following rules
        apply:

        1. If a rule ends with a slash and is requested without a slash
           by the user, the user is automatically redirected to the same
           page with a trailing slash attached.
        2. If a rule does not end with a trailing slash and the user request
           the page with a trailing slash, a 404 not found is raised.

        This is consistent with how web servers deal with static files.  This
        also makes it possible to use relative link targets safely.

        The :meth:`route` decorator accepts a couple of other arguments
        as well:

        :param rule: the URL rule as string
        :param methods: a list of methods this rule should be limited
                        to (``GET``, ``POST`` etc.).  By default a rule
                        just listens for ``GET`` (and implicitly ``HEAD``).
        :param subdomain: specifies the rule for the subdoain in case
                          subdomain matching is in use.
        :param strict_slashes: can be used to disable the strict slashes
                               setting for this rule.  See above.
        :param options: other options to be forwarded to the underlying
                        :class:`~werkzeug.routing.Rule` object.
        """
        def decorator(f):
            self.add_url_rule(rule, f.__name__, **options)    # 添加路由规则
            self.view_functions[f.__name__] = f               # 更新 视图函数集合, 前面定义,{}
            return f
        return decorator

    #
    # 错误处理装饰器定义:
    #
    def errorhandler(self, code):
        """A decorator that is used to register a function give a given
        error code.  Example::

            @app.errorhandler(404)
            def page_not_found():
                return 'This page does not exist', 404

        You can also register a function as error handler without using
        the :meth:`errorhandler` decorator.  The following example is
        equivalent to the one above::

            def page_not_found():
                return 'This page does not exist', 404
            app.error_handlers[404] = page_not_found

        :param code: the code as integer for the handler
        """
        def decorator(f):
            self.error_handlers[code] = f     # 前述定义{}
            return f
        return decorator

    #
    # 请求前,预处理:
    #   - 注册预处理函数
    #
    def before_request(self, f):
        """Registers a function to run before each request."""
        self.before_request_funcs.append(f)
        return f

    #
    # 请求结束, 清理工作:
    #   - 注册清理函数
    #
    def after_request(self, f):
        """Register a function to be run after each request."""
        self.after_request_funcs.append(f)
        return f

    #
    # 模板上下文处理函数
    #
    def context_processor(self, f):
        """Registers a template context processor function."""
        self.template_context_processors.append(f)
        return f

    #
    # 请求匹配:
    #
    def match_request(self):
        """Matches the current request against the URL map and also
        stores the endpoint and view arguments on the request object
        is successful, otherwise the exception is stored.
        """
        rv = _request_ctx_stack.top.url_adapter.match()
        request.endpoint, request.view_args = rv
        return rv

    #
    # 处理请求:
    #   - 处理 路由URL 和 对应的 视图函数
    #
    def dispatch_request(self):
        """Does the request dispatching.  Matches the URL and returns the
        return value of the view or error handler.  This does not have to
        be a response object.  In order to convert the return value to a
        proper response object, call :func:`make_response`.
        """
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
        """Converts the return value from a view function to a real
        response object that is an instance of :attr:`response_class`.

        The following types are allowd for `rv`:

        ======================= ===========================================
        :attr:`response_class`  the object is returned unchanged
        :class:`str`            a response object is created with the
                                string as body
        :class:`unicode`        a response object is created with the
                                string encoded to utf-8 as body
        :class:`tuple`          the response object is created with the
                                contents of the tuple as arguments
        a WSGI function         the function is called as WSGI application
                                and buffered as response object
        ======================= ===========================================

        :param rv: the return value from the view function
        """
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
        """Called before the actual request dispatching and will
        call every as :meth:`before_request` decorated function.
        If any of these function returns a value it's handled as
        if it was the return value from the view and further
        request handling is stopped.
        """
        for func in self.before_request_funcs:
            rv = func()    # 执行预处理函数
            if rv is not None:
                return rv

    #
    # 在返回响应前, 作 清理工作, 与上配对
    #
    def process_response(self, response):
        """Can be overridden in order to modify the response object
        before it's sent to the WSGI server.  By default this will
        call all the :meth:`after_request` decorated functions.

        :param response: a :attr:`response_class` object.
        :return: a new response object or the same, has to be an
                 instance of :attr:`response_class`.
        """
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
        """The actual WSGI application.  This is not implemented in
        `__call__` so that middlewares can be applied:

            app.wsgi_app = MyMiddleware(app.wsgi_app)

        :param environ: a WSGI environment
        :param start_response: a callable accepting a status code,
                               a list of headers and an optional
                               exception context to start the response
        """
        with self.request_context(environ):     # 请求上下文
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
        """Creates a request context from the given environment and binds
        it to the current context.  This must be used in combination with
        the `with` statement because the request is only bound to the
        current context for the duration of the `with` block.

        Example usage::

            with app.request_context(environ):
                do_something_with(request)

        :params environ: a WSGI environment
        """
        return _RequestContext(self, environ)     # 请求上下文, 上述已定义该模块

    def test_request_context(self, *args, **kwargs):
        """Creates a WSGI environment from the given values (see
        :func:`werkzeug.create_environ` for more information, this
        function accepts the same arguments).
        """
        return self.request_context(create_environ(*args, **kwargs))

    def __call__(self, environ, start_response):
        """Shortcut for :attr:`wsgi_app`"""
        return self.wsgi_app(environ, start_response)


###################################################################
#                     全局上下文变量定义(context locals)
# 说明:
#   - 此处全局的 g, session, 需要深入理解
#   - 需要深入去看 werkzeug.LocalStack() 的实现
#   - 为了支持多线程, 线程无关的
#
###################################################################

_request_ctx_stack = LocalStack()    # 依赖 werkzeug.LocalStack 模块
current_app = LocalProxy(lambda: _request_ctx_stack.top.app)
request = LocalProxy(lambda: _request_ctx_stack.top.request)


# 特别注意此处实现:
#   - g: 请求上下文 栈对象
#   - session: 请求上下文 栈对象
#
session = LocalProxy(lambda: _request_ctx_stack.top.session)    # flash()函数 中 引用
g = LocalProxy(lambda: _request_ctx_stack.top.g)
