#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .exceptions import InvalidUsage


##################################################################################
#                              自定义 view 的基类:
# 说明:
#   - 使用场景: 实现 Restful API
#   - 用户自定义实现 get(), post(), put(), patch(), delete() 等接口方法
#
##################################################################################
class HTTPMethodView:
    """ Simple class based implementation of view for the sanic.
    You should implement methods (get, post, put, patch, delete) for the class
    to every HTTP method you want to support.

    For example:
        class DummyView(View):

            def get(self, request, *args, **kwargs):
                return text('I am get method')

            def put(self, request, *args, **kwargs):
                return text('I am put method')
    etc.

    If someone tries to use a non-implemented method, there will be a
    405 response.

    If you need any url params just mention them in method definition:
        class DummyView(View):

            def get(self, request, my_param_here, *args, **kwargs):
                return text('I am get method with %s' % my_param_here)

    To add the view into the routing you could use
        1) app.add_route(DummyView(), '/')
        2) app.route('/')(DummyView())
    """

    def __call__(self, request, *args, **kwargs):
        handler = getattr(self, request.method.lower(), None)    # 自动获取 request 方法, 钩子

        # 由钩子获取 HTTP 方法, 自动调用
        if handler:
            return handler(request, *args, **kwargs)    # 执行 HTTP 方法
        raise InvalidUsage(
            'Method {} not allowed for URL {}'.format(
                request.method, request.url), status_code=405)
