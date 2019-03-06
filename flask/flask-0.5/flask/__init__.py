# -*- coding: utf-8 -*-
"""
flask 说明:
    - flask 基于 Werkzeug 和 jinja2 实现
    - 代码遵循大量 Python 最佳实践.
    - 代码质量很高, 值得学习.

v0.5 版本说明:
    - 本版本, 较之 v0.4, 代码改动很小, 只是单纯的作了模块化拆分.
    - 应特别注意对比 v0.4 和 v0.5 的变化, 体会模块化拆分技巧.
    - 注意本 __init__.py 的用法, 如何设计一个 lib 结构.

    ~~~~~

    A microframework based on Werkzeug.  It's extensively documented
    and follows best practice patterns.
"""


###################################################################
#                   第三方包 导入接口:
# 说明:
# - 从 Werkzeug 和 jinja2 导入的组件, 在 flask 中,并未使用
# - 只是作公共接口提供给外部, 这样 flask 自己就不需要再实现了.
###################################################################

# 异常, 路由重定向
from werkzeug import abort, redirect
from jinja2 import Markup, escape


###################################################################
#                      flask 中实现的对外接口:
# 说明:
# - 注意模块化拆分
#
###################################################################

# 全局入口, 核心类:
from .app import Flask, Request, Response

# 配置参数:
from .config import Config

# 公共组件接口 API:
from .helpers import url_for, jsonify, json_available, flash, \
    send_file, send_from_directory, get_flashed_messages, \
    get_template_attribute

# 全局变量定义: 上下文变量
# 关键模块, 需要特别注意理解
from .globals import current_app, g, request, session, _request_ctx_stack

# 关键模块, 为后续版本的 Blueprint 模块
from .module import Module

# 模板渲染:
from .templating import render_template, render_template_string

# only import json if it's available
# Json 支持:
if json_available:
    from .helpers import json
