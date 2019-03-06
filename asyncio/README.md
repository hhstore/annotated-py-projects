# annotated-py-asyncio
asyncio 源码注解.

- [asyncio](https://github.com/python/asyncio)
- python 3.3 版本, 添加此库, 
- python 3.4 版本之后, 被添加到标准库中.


## 版本说明:

- [asyncio-3.4.3](https://github.com/python/asyncio/releases/tag/3.4.3)
    - 发布时间:  5 Feb 2015
    - 阅读时间:  2017-02-21



## 源码结构:


```text

-> % tree asyncio -L 1

asyncio
├── __init__.py
├── base_events.py
├── base_subprocess.py
├── constants.py
├── coroutines.py
├── events.py
├── futures.py
├── locks.py
├── log.py
├── proactor_events.py
├── protocols.py
├── queues.py
├── selector_events.py
├── selectors.py
├── sslproto.py
├── streams.py
├── subprocess.py
├── tasks.py
├── test_support.py
├── test_utils.py
├── transports.py
├── unix_events.py
├── windows_events.py
└── windows_utils.py

0 directories, 24 files


```


## 阅读顺序:

- 由示例代码开始阅读, 然后找到 lib 入口.

- [examples/hello_coroutine.py](./asyncio-3.4.3/examples/hello_coroutine.py)
    - get_event_loop()
        - 定位到: [asyncio/events.py](./asyncio-3.4.3/asyncio/events.py)
        - asyncio.events.get_event_loop()
    - run_until_complete()
        - 定位到: [base_events.py](./asyncio-3.4.3/asyncio/base_events.py)
        - asyncio.base_events.BaseEventLoop.run_until_complete()
        - BaseEventLoop()
            - create_task()
                - tasks.Task(coro, loop=self)
                - [tasks.py](./asyncio-3.4.3/asyncio/tasks.py)
    - @asyncio.coroutine
        - 定位到: [coroutines.py](./asyncio-3.4.3/asyncio/coroutines.py)
        - 协程装饰器
        - asyncio.coroutines.coroutine()
            - 定位到: [futures.py](./asyncio-3.4.3/asyncio/coroutines.py/futures.py)
            - futures.Future 对象
- [examples/tcp_echo.py](./asyncio-3.4.3/examples/tcp_echo.py)
    - start_client()
        - asyncio.Task()
        - [tasks.py](./asyncio-3.4.3/asyncio/tasks.py)

- locks.py:
    - 各种同步机制

- queues.py:
    - 自定义的队列: 优先级队列等

- protocols.py
    - 协议模块.
    - 流, 数据报等
    - streams.py
    - base_subprocess.py
    - subprocess.py
    - sslproto.py

- transports.py
    - 传输层

- selectors.py
    - 选择器
    - selector_events.py


## 官方文档参考:

- https://docs.python.org/3/library/asyncio.html
    - 模块主要内容:
        - a pluggable event loop with various system-specific implementations;
        - transport and protocol abstractions (similar to those in Twisted);
        - concrete support for TCP, UDP, SSL, subprocess pipes, delayed calls, and others (some may be system-dependent);
        - a Future class that mimics the one in the concurrent.futures module, but adapted for use with the event loop;
        - coroutines and tasks based on yield from (PEP 380), to help write concurrent code in a sequential fashion;
        - cancellation support for Futures and coroutines;
        - synchronization primitives for use between coroutines in a single thread, mimicking those in the threading module;
        - an interface for passing work off to a threadpool, for times when you absolutely, positively have to use a library that makes blocking I/O calls.
    - 关键模块查阅说明文档


