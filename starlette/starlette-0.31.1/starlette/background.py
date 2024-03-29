import sys
import typing

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec

from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool  # todo x: 线程池模式

P = ParamSpec("P")


class BackgroundTask:
    def __init__(
        self, func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.is_async = is_async_callable(func)

    async def __call__(self) -> None:
        if self.is_async:
            await self.func(*self.args, **self.kwargs)
        else:
            #
            # todo x: 使用线程池模式
            #
            await run_in_threadpool(self.func, *self.args, **self.kwargs)


#
# todo x: 后台任务, 用于异步执行, 基于线程池模式 + anyio
#
class BackgroundTasks(BackgroundTask):
    def __init__(self, tasks: typing.Optional[typing.Sequence[BackgroundTask]] = None):
        self.tasks = list(tasks) if tasks else []

    def add_task(
        self, func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        task = BackgroundTask(func, *args, **kwargs)
        self.tasks.append(task)

    async def __call__(self) -> None:
        #
        # todo x: 迭代执行
        #
        for task in self.tasks:
            await task()
