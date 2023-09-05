# starlette 源码分析:

## 版本:

- starlette: [0.13.1 ](https://github.com/encode/starlette/releases/tag/0.31.1)

## 说明:

- fastapi 依赖 starlette 实现绝大部分的核心功能.
- so, 分析 starlette 有助于理解 fastapi 的实现原理.
- starlette 只依赖 [anyio](https://github.com/agronholm/anyio)

## 项目结构:

-

## 源码分析:

- 入口: [starlette/applications.py](starlette-0.31.1/starlette/applications.py)
- 后台任务: [starlette/background.py](starlette-0.31.1/starlette/background.py)
    - 异步线程池 + anyio
- 异步线程池: [starlette/concurrency.py](starlette-0.31.1/starlette/concurrency.py)
