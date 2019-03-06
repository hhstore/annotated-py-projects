from collections import defaultdict


##################################################################################
#                              实现蓝图的辅助类:
#
# 说明:
#   - 此类对 Sanic对象中的接口方法, 作一层包裹, 实现若干 helper 方法
#   - helper 方法调用处:
#       - 在 Blueprint()类中, 各接口实现的 lambda 表达式里
#
##################################################################################
class BlueprintSetup:
    """
    """

    def __init__(self, blueprint, app, options):
        self.app = app
        self.blueprint = blueprint
        self.options = options

        url_prefix = self.options.get('url_prefix')    # 路由前缀
        if url_prefix is None:
            url_prefix = self.blueprint.url_prefix

        #: The prefix that should be used for all URLs defined on the
        #: blueprint.
        self.url_prefix = url_prefix    # 路由前缀

    # 辅助接口:
    #   - 调用 Sanic 对象的实现
    def add_route(self, handler, uri, methods):
        """
        A helper method to register a handler to the application url routes.
        """
        if self.url_prefix:
            uri = self.url_prefix + uri

        self.app.route(uri=uri, methods=methods)(handler)

    #
    # 辅助接口:
    #   - 调用 Sanic 对象的实现
    #
    def add_exception(self, handler, *args, **kwargs):
        """
        Registers exceptions to sanic
        """
        self.app.exception(*args, **kwargs)(handler)

    #
    # 辅助接口:
    #   - 调用 Sanic 对象的实现
    #
    def add_static(self, uri, file_or_directory, *args, **kwargs):
        """
        Registers static files to sanic
        """
        if self.url_prefix:
            uri = self.url_prefix + uri

        self.app.static(uri, file_or_directory, *args, **kwargs)

    #
    # 辅助接口: 注册中间件
    #   - 调用 Sanic 对象的实现 [sanic.Sanic.middleware()]
    #
    def add_middleware(self, middleware, *args, **kwargs):
        """
        Registers middleware to sanic
        """
        if args or kwargs:
            self.app.middleware(*args, **kwargs)(middleware)    # [sanic.Sanic.middleware()]
        else:
            self.app.middleware(middleware)


##################################################################################
#                              本模块入口: 蓝图实现
#
# 说明:
#   - 依赖 BlueprintSetup() 类
#   - 本类接口实现, 依赖 BlueprintSetup() 中各 helper 方法
#   - 实现若干装饰器, 类似 Sanic() 类接口
#
##################################################################################
class Blueprint:
    def __init__(self, name, url_prefix=None):
        """
        Creates a new blueprint
        :param name: Unique name of the blueprint
        :param url_prefix: URL to be prefixed before all route URLs
        """
        self.name = name                       # 蓝图名, 需唯一
        self.url_prefix = url_prefix           # 路由前缀
        self.deferred_functions = []           # 推迟执行的函数集合
        self.listeners = defaultdict(list)     # 监听

    #
    # 登记:
    #   - 延迟执行的函数
    #
    def record(self, func):
        """
        Registers a callback function that is invoked when the blueprint is
        registered on the application.
        """
        self.deferred_functions.append(func)

    #
    # 构建辅助对象:
    #   - 被 register() 调用
    #
    def make_setup_state(self, app, options):
        """
        """
        return BlueprintSetup(self, app, options)    # 调用上面模块, 构建对象

    #
    # 注册:
    #   - 执行已登记的延迟调用函数
    #
    def register(self, app, options):
        """
        """
        state = self.make_setup_state(app, options)     # 调用上一接口

        # 遍历延迟执行的函数, 执行调用
        for deferred in self.deferred_functions:
            deferred(state)    # 执行

    #
    # 路由装饰器:
    #   - s 是 BlueprintSetup()对象
    #
    def route(self, uri, methods=None):
        """
        """
        def decorator(handler):    # 装饰器
            # 登记延迟执行的函数
            self.record(lambda s: s.add_route(handler, uri, methods))   # s 是 BlueprintSetup()对象
            return handler
        return decorator

    #
    # 添加路由:
    #   - s 是 BlueprintSetup()对象
    #
    def add_route(self, handler, uri, methods=None):
        """
        """
        # 登记延迟执行的函数
        self.record(lambda s: s.add_route(handler, uri, methods))    # s 是 BlueprintSetup()对象
        return handler

    def listener(self, event):
        """
        """
        def decorator(listener):
            self.listeners[event].append(listener)
            return listener
        return decorator

    #
    # 中间件:
    #   - s 是 BlueprintSetup()对象
    #
    def middleware(self, *args, **kwargs):
        """
        """
        def register_middleware(middleware):
            # 登记延迟执行的函数
            self.record(
                lambda s: s.add_middleware(middleware, *args, **kwargs))    # s 是 BlueprintSetup()对象
            return middleware

        # Detect which way this was called, @middleware or @middleware('AT')
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            middleware = args[0]
            args = []
            return register_middleware(middleware)    # 注册中间件
        else:
            return register_middleware

    #
    # 异常处理装饰器:
    #   - s 是 BlueprintSetup()对象
    #
    def exception(self, *args, **kwargs):
        """
        """
        def decorator(handler):
            # 登记延迟执行的异常调用
            self.record(lambda s: s.add_exception(handler, *args, **kwargs))    # s 是 BlueprintSetup()对象
            return handler
        return decorator

    #
    # 静态资源处理:
    #   - s 是 BlueprintSetup()对象
    #
    def static(self, uri, file_or_directory, *args, **kwargs):
        """
        """
        # 登记静态文件处理函数
        self.record(
            lambda s: s.add_static(uri, file_or_directory, *args, **kwargs))    # s 是 BlueprintSetup()对象
