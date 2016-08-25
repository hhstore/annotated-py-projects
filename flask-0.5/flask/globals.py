# -*- coding: utf-8 -*-
"""
flask.globals 说明:
    - 全局对象定义
    - 上下文对象
    - 给当前激活的上下文, 定义全部的全局对象.

    ~~~~~~~~~~~~~
    Defines all the global objects that are proxies to the current
    active context.

"""

# 关键依赖:
#   - 需要看下 werkzeug 如何实现的
from werkzeug import LocalStack, LocalProxy

###################################################################
#                请求上下文
# 说明:
#   - 关键模块
#   - 注意对 `请求上下文` 和 `请求上下文 - 全局对象` 概念的理解.
#       - 是 请求相关的
#       - 是 上下文相关的
#       - 是 全局对象
#   - 本模块的对象, 非常关键, 涉及 Flask() 核心功能的实现.
#
###################################################################

# 请求上下文栈
# context locals
_request_ctx_stack = LocalStack()

#
# 请求上下文栈顶对象:
#

# 上下文当前 app:
current_app = LocalProxy(lambda: _request_ctx_stack.top.app)
# 上下文请求:
request = LocalProxy(lambda: _request_ctx_stack.top.request)
# 上下文 session:
session = LocalProxy(lambda: _request_ctx_stack.top.session)
# 上下文 g 对象:
g = LocalProxy(lambda: _request_ctx_stack.top.g)
