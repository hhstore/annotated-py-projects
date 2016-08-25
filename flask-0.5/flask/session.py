# -*- coding: utf-8 -*-
"""
flask.session 说明:
    - 基于 Werkzeug 的 secure cookie模块, 实现 session

"""

from werkzeug.contrib.securecookie import SecureCookie


class Session(SecureCookie):
    """扩展 session, 支持 持久 session 和 非持久 session 切换.
    """

    def _get_permanent(self):
        return self.get('_permanent', False)

    def _set_permanent(self, value):
        self['_permanent'] = bool(value)

    # 自定义属性写法: 支持读写
    permanent = property(_get_permanent, _set_permanent)

    # 删除
    del _get_permanent, _set_permanent


class _NullSession(Session):
    """本类功能:
        - 若无法获取 session, 则生成友好的出错信息.
        - 允许只读访问 空 session, 不允许改写.
    """

    def _fail(self, *args, **kwargs):
        raise RuntimeError('the session is unavailable because no secret '
                           'key was set.  Set the secret_key on the '
                           'application to something unique and secret')

    # 设置只读模式
    # 做法是: 覆盖如下方法, 调用时都抛出异常.
    __setitem__ = __delitem__ = clear = pop = popitem = \
        update = setdefault = _fail
    del _fail
