import re

#
# 高阶数据类型:
#   - defaultdict
#   - namedtuple: 具名元组, 特征: 元组内元素 field, 可被命名
#
from collections import defaultdict, namedtuple    # 注意: 数据类型
from functools import lru_cache                    # LRU缓存装饰器

from .config import Config
from .exceptions import NotFound, InvalidUsage

#
# 路由元组:
#   - 特征:
#       - Route.handler = xxx
#       - Route.methods = xxx
#       - Route.pattern = xxx
#       - Route.parameters = xxx
#
Route = namedtuple('Route', ['handler', 'methods', 'pattern', 'parameters'])

#
# 参数元组:
#   - 特征:
#       - Parameter.name = xxx
#       - Parameter.cast = xxx
#
Parameter = namedtuple('Parameter', ['name', 'cast'])


#
# 正则表达式:
#   - 数据类型过滤
#
REGEX_TYPES = {
    'string': (str, r'[^/]+'),
    'int': (int, r'\d+'),
    'number': (float, r'[0-9\\.]+'),
    'alpha': (str, r'[A-Za-z]+'),
}


def url_hash(url):
    return url.count('/')


#
# 异常: 路由已存在
#
class RouteExists(Exception):
    pass


###############################################################
#             路由管理器
#
# 说明:
#   - 提供2个接口: add/get
#   - 是 Sanic()类中, 路由装饰器实现的核心依赖
#   - 引用位置: sanic.sanic.Sanic.route(), 此装饰器, 依赖本类
#
###############################################################
class Router:
    """
    Router supports basic routing with parameters and method checks
    Usage:
        @sanic.route('/my/url/<my_parameter>', methods=['GET', 'POST', ...])
        def my_route(request, my_parameter):
            do stuff...
    or
        @sanic.route('/my/url/<my_paramter>:type', methods['GET', 'POST', ...])
        def my_route_with_type(request, my_parameter):
            do stuff...

    Parameters will be passed as keyword arguments to the request handling
    function. Provided parameters can also have a type by appending :type to
    the <parameter>. Given parameter must be able to be type-casted to this.
    If no type is provided, a string is expected.  A regular expression can
    also be passed in as the type. The argument given to the function will
    always be a string, independent of the type.
    """
    routes_static = None             # 静态路由集
    routes_dynamic = None            # 动态路由集
    routes_always_check = None       # 检查路由列表

    def __init__(self):
        self.routes_all = {}                         # 全部路由集
        self.routes_static = {}                      # 静态路由集
        self.routes_dynamic = defaultdict(list)      # 动态路由集
        self.routes_always_check = []

    #
    # 添加一个处理器 到 路由列表
    #   - 根据路由类型, 添加到对应路由集
    #
    def add(self, uri, methods, handler):
        """
        Adds a handler to the route list
        :param uri: Path to match
        :param methods: Array of accepted method names.
        If none are provided, any method is allowed
        :param handler: Request handler function.
        When executed, it should provide a response object.
        :return: Nothing
        """
        if uri in self.routes_all:    # 路由已存在
            raise RouteExists("Route already registered: {}".format(uri))

        # Dict for faster lookups of if method allowed
        if methods:
            methods = frozenset(methods)    # 加速查找

        parameters = []
        properties = {"unhashable": None}

        #
        # 添加参数:
        #
        def add_parameter(match):
            # We could receive NAME or NAME:PATTERN
            name = match.group(1)
            pattern = 'string'
            if ':' in name:
                name, pattern = name.split(':', 1)

            default = (str, pattern)

            # Pull from pre-configured types
            _type, pattern = REGEX_TYPES.get(pattern, default)      # 正则判断

            parameter = Parameter(name=name, cast=_type)
            parameters.append(parameter)

            # Mark the whole route as unhashable if it has the hash key in it
            if re.search('(^|[^^]){1}/', pattern):
                properties['unhashable'] = True
            # Mark the route as unhashable if it matches the hash key
            elif re.search(pattern, '/'):
                properties['unhashable'] = True

            return '({})'.format(pattern)

        pattern_string = re.sub(r'<(.+?)>', add_parameter, uri)
        pattern = re.compile(r'^{}$'.format(pattern_string))

        #
        # 路由项:
        #
        route = Route(
            handler=handler, methods=methods, pattern=pattern,
            parameters=parameters)

        #
        # 添加路由到对应字典:
        #
        self.routes_all[uri] = route
        if properties['unhashable']:
            self.routes_always_check.append(route)
        elif parameters:
            self.routes_dynamic[url_hash(uri)].append(route)     # 动态路由
        else:
            self.routes_static[uri] = route                      # 静态路由

    #
    # 从请求中提取对应的 handler.
    #
    def get(self, request):
        """
        Gets a request handler based on the URL of the request, or raises an
        error
        :param request: Request object
        :return: handler, arguments, keyword arguments
        """
        return self._get(request.url, request.method)    # 调用如下子函数

    #
    # 缓存路由:
    #   - 返回[路由处理器, 参数数组, 参数字典]
    #   - 添加到缓存中
    #
    @lru_cache(maxsize=Config.ROUTER_CACHE_SIZE)
    def _get(self, url, method):
        """
        Gets a request handler based on the URL of the request, or raises an
        error.  Internal method for caching.
        :param url: Request URL
        :param method: Request method
        :return: handler, arguments, keyword arguments
        """

        #
        # 路由匹配:
        #   - 先匹配静态路由集.
        #       - 匹配成功, 结束.
        #       - 匹配失败, 尝试匹配 动态路由集.
        #           - 匹配成功, 结束.
        #           - 匹配失败, 尝试匹配 最后的路由部分.
        #               - 匹配成功, 结束.
        #               - 匹配失败, 抛出异常.
        #
        # Check against known static routes
        route = self.routes_static.get(url)       # 查找静态路由集

        if route:
            match = route.pattern.match(url)      # 匹配成功
        else:
            # Move on to testing all regex routes
            for route in self.routes_dynamic[url_hash(url)]:  # 查找动态路由集
                match = route.pattern.match(url)
                if match:
                    break
            else:
                # Lastly, check against all regex routes that cannot be hashed
                for route in self.routes_always_check:
                    match = route.pattern.match(url)
                    if match:     # 匹配成功, 返回
                        break
                else:
                    raise NotFound('Requested URL {} not found'.format(url))   # 路由匹配失败, 抛出异常

        #
        # 路由匹配成功, 继续处理:
        #   - method 不匹配, 抛出异常
        #
        if route.methods and method not in route.methods:
            raise InvalidUsage(
                'Method {} not allowed for URL {}'.format(
                    method, url), status_code=405)

        kwargs = {p.name: p.cast(value)
                  for value, p
                  in zip(match.groups(1), route.parameters)}
        return route.handler, [], kwargs
