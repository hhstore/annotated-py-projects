
# 阅读补充:

## 1. 基本概念:

### 1.1 协程:

- “协程 是为非抢占式多任务产生子程序的计算机程序组件，协程允许不同入口点在不同位置暂停或开始执行程序”。
- 从技术的角度来说，“协程就是你可以暂停执行的函数”。
- 如果你把它理解成“就像生成器一样”，那么你就想对了。


### 1.2 事件循环:

- 事件循环 “是一种等待程序分配事件或消息的编程架构”。
- 基本上来说事件循环就是，“当A发生时，执行B”。
- 或许最简单的例子来解释这一概念就是用每个浏览器中都存在的JavaScript事件循环。
- 当你点击了某个东西（“当A发生时”），这一点击动作会发送给JavaScript的事件循环，并检查是否存在注册过的 onclick 回调来处理这一点击（“执行B”）。
- 只要有注册过的回调函数就会伴随点击动作的细节信息被执行。
- 事件循环被认为是一种循环是因为它不停地收集事件并通过循环来发如何应对这些事件。



### 1.3 Python 的事件循环:

- 对 Python 来说，用来提供事件循环的 asyncio 被加入标准库中。
- asyncio 重点解决网络服务中的问题，事件循环在这里将来自套接字（socket）的 I/O 已经准备好读和/或写作为“当A发生时”（通过selectors模块）。
- 除了 GUI 和 I/O，事件循环也经常用于在别的线程或子进程中执行代码，并将事件循环作为调节机制（例如，合作式多任务）。
- 如果你恰好理解 Python 的 GIL，事件循环对于需要释放 GIL 的地方很有用。
- 事件循环提供一种循环机制，让你可以“在A发生时，执行B”。
- 基本上来说事件循环就是监听当有什么发生时，同时事件循环也关心这件事并执行相应的代码。
- Python 3.4 以后通过标准库 asyncio 获得了事件循环的特性。


### 1.4 async, await:

- 将 async/await 看做异步编程的 API
- 基本上 async 和 await 产生神奇的生成器，我们称之为协程，
- 同时需要一些额外的支持例如 awaitable 对象以及将普通生成器转化为协程。
- 所有这些加到一起来支持并发，这样才使得 Python 更好地支持异步编程。
- 相比类似功能的线程，这是一个更妙也更简单的方法。



```

在 Python 3.4 中，用于异步编程并被标记为协程的函数看起来是这样的：

    # This also works in Python 3.5.
    @asyncio.coroutine
    def py34_coro():
        yield from stuff()


Python 3.5 添加了types.coroutine 修饰器，也可以像 asyncio.coroutine 一样将生成器标记为协程。
你可以用 async def 来定义一个协程函数，虽然这个函数不能包含任何形式的 yield 语句；只有 return 和 await 可以从协程中返回值。

    async def py35_coro():
        await stuff()


你将发现不仅仅是 async，Python 3.5 还引入 await 表达式（只能用于async def中）。
虽然await的使用和yield from很像，但await可以接受的对象却是不同的。
await 当然可以接受协程，因为协程的概念是所有这一切的基础。
但是当你使用 await 时，其接受的对象必须是awaitable 对象：必须是定义了__await__()方法且这一方法必须返回一个不是协程的迭代器。
协程本身也被认为是 awaitable 对象（这也是collections.abc.Coroutine 继承 collections.abc.Awaitable的原因）。
这一定义遵循 Python 将大部分语法结构在底层转化成方法调用的传统，就像 a + b 实际上是a.__add__(b) 或者 b.__radd__(a)。


为什么基于async的协程和基于生成器的协程会在对应的暂停表达式上面有所不同？
主要原因是出于最优化Python性能的考虑，确保你不会将刚好有同样API的不同对象混为一谈。
由于生成器默认实现协程的API，因此很有可能在你希望用协程的时候错用了一个生成器。
而由于并不是所有的生成器都可以用在基于协程的控制流中，你需要避免错误地使用生成器。


用async def可以定义得到协程。
定义协程的另一种方式是通过types.coroutine修饰器
    -- 从技术实现的角度来说就是添加了 CO_ITERABLE_COROUTINE标记
    -- 或者是collections.abc.Coroutine的子类。
你只能通过基于生成器的定义来实现协程的暂停。


awaitable 对象要么是一个协程要么是一个定义了__await__()方法的对象
    -- 也就是collections.abc.Awaitable
    -- 且__await__()必须返回一个不是协程的迭代器。


await表达式基本上与 yield from 相同但只能接受awaitable对象（普通迭代器不行）。
async定义的函数要么包含return语句
    -- 包括所有Python函数缺省的return None
    -- 和/或者 await表达式（yield表达式不行）。
async函数的限制确保你不会将基于生成器的协程与普通的生成器混合使用，因为对这两种生成器的期望是非常不同的。


```




### 1.5 关于 python 协程 和 golang 的对比讨论:

- [From Python to Go and Back Again](https://news.ycombinator.com/item?id=10402307)
    - [PPT](https://docs.google.com/presentation/d/1LO_WI3N-3p2Wp9PDWyv5B6EGFZ8XTOTNJ7Hd40WOUHo/mobilepresent?pli=1&slide=id.g70b0035b2_1_154)
    - 关于此PPT 的观点: go 比 pypy 性能高不了多少, 但是复杂度和调试难度增加很高
    - 结尾鼓吹 rust.
- 异步库参考:
    - [hyper](https://github.com/Lukasa/hyper)
    - [curio](https://github.com/dabeaz/curio)
        - 将asyncio看作是一个利用async/await API 进行异步编程的框架
        - David 将 async/await 看作是异步编程的API创建了 curio 项目来实现他自己的事件循环。
        - 允许像 curio 一样的项目不仅可以在较低层面上拥有不同的操作方式
        - （例如 asyncio 利用 future 对象作为与事件循环交流的 API，而 curio 用的是元组）

---

## 2. 源码模块:

### 2.1 (futures.py)[./futures.py]


#### 2.1.1 参考:


- [Python 3.5 协程究竟是个啥](http://www.snarky.ca/how-the-heck-does-async-await-work-in-python-3-5)
    - 译: [Python 3.5 协程究竟是个啥](https://juejin.im/entry/56ea295ed342d300546e1e22)
    - [译: github](https://github.com/xitu/gold-miner/blob/master/TODO/how-the-heck-does-async-await-work-in-python-3-5.md)
    - [译: 博客](http://blog.rainy.im/2016/03/10/how-the-heck-does-async-await-work-in-python-3-5/)


- [Python 协程：从 yield/send 到 async/await](http://www.woola.net/detail/2016-10-18-python-coprocessor.html)
    - future 源码剖析

- [concurrent.futures 源码阅读笔记（Python）](https://toutiao.io/posts/9sygwc/preview)
    - concurrent.futures 是一个异步库
    - [concurrent.futures — Asynchronous computation](http://pythonhosted.org/futures/index.html)



#### 2.1.2 生成器（Generator）VS 迭代器（iterator）:

- [improve-your-python-yield-and-generators-explained](http://www.jeffknupp.com/blog/2013/04/07/improve-your-python-yield-and-generators-explained/)
    - 译文:[提高你的Python: 解释‘yield’和‘Generators（生成器）’](https://www.oschina.net/translate/improve-your-python-yield-and-generators-explained)
    - 在Python之外，最简单的生成器应该是被称为协程（coroutines）的东西。
    - generator是用来产生一系列值的
    - yield则像是generator函数的返回结果
    - yield唯一所做的另一件事就是保存一个generator函数的状态
    - generator就是一个特殊类型的迭代器（iterator）
    - 和迭代器相似，我们可以通过使用next()来从generator中获取下一个值
    - 通过隐式地调用next()来忽略一些值

- [生成器与迭代器的关系](http://kuanghy.github.io/2016/05/18/python-iteration)
    - 生成器(generator)是一个特殊的迭代器，它的实现更简单优雅。yield 是生成器实现 __next__() 方法的关键

- [python黑魔法---迭代器（iterator）](http://www.jianshu.com/p/dcf83643deeb)

- [生成器](http://www.liaoxuefeng.com/wiki/001374738125095c955c1e6d8bb493182103fac9270762a000/00138681965108490cb4c13182e472f8d87830f13be6e88000)



