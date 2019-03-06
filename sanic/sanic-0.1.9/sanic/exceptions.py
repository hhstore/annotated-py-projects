from .response import text
from traceback import format_exc


#########################################
#             项目自定义异常类
#
# 说明:
#   - 框架异常的基类
#
#
#########################################
class SanicException(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


# 404:
class NotFound(SanicException):
    status_code = 404


# 400:
class InvalidUsage(SanicException):
    status_code = 400


# 500:
class ServerError(SanicException):
    status_code = 500


# 404:
class FileNotFound(NotFound):
    status_code = 404

    def __init__(self, message, path, relative_url):
        super().__init__(message)
        self.path = path
        self.relative_url = relative_url


# 408:
class RequestTimeout(SanicException):
    status_code = 408


# 413:
class PayloadTooLarge(SanicException):
    status_code = 413


#########################################
#             异常处理器
#
# 说明:
#   - 处理异常
#
#########################################
class Handler:
    handlers = None

    def __init__(self, sanic):
        self.handlers = {}
        self.sanic = sanic

    def add(self, exception, handler):
        self.handlers[exception] = handler

    def response(self, request, exception):
        """
        Fetches and executes an exception handler and returns a response object
        :param request: Request
        :param exception: Exception to handle
        :return: Response object
        """
        handler = self.handlers.get(type(exception), self.default)
        response = handler(request=request, exception=exception)
        return response

    def default(self, request, exception):
        #
        # 判断异常类型, 属于框架自身的异常
        #   - 返回异常状态码, 默认500
        #
        if issubclass(type(exception), SanicException):
            return text(
                "Error: {}".format(exception),
                status=getattr(exception, 'status_code', 500))
        elif self.sanic.debug:    # 判断是否为调试模式
            return text(
                "Error: {}\nException: {}".format(
                    exception, format_exc()), status=500)
        else:
            return text(
                "An error occurred while generating the request", status=500)
