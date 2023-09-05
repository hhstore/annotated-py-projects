# fastapi 源码注解:

- version: [0.103.1](https://github.com/tiangolo/fastapi/releases/tag/0.103.1)
- 下载的 `.zip` 源码包, 删除了不重要的一些测试代码和文档目录/脚本等.

## 说明:

## 源码目录结构:

```ruby
# fastapi/fastapi-0.103.1/fastapi


❯ tree . -L 2
.
├── __init__.py
├── _compat.py
├── applications.py
├── background.py
├── concurrency.py
├── datastructures.py
├── dependencies
│   ├── __init__.py
│   ├── models.py
│   └── utils.py
├── encoders.py
├── exception_handlers.py
├── exceptions.py
├── logger.py
├── middleware
│   ├── __init__.py
│   ├── asyncexitstack.py
│   ├── cors.py
│   ├── gzip.py
│   ├── httpsredirect.py
│   ├── trustedhost.py
│   └── wsgi.py
├── openapi
│   ├── __init__.py
│   ├── constants.py
│   ├── docs.py
│   ├── models.py
│   └── utils.py
├── param_functions.py
├── params.py
├── py.typed
├── requests.py
├── responses.py
├── routing.py
├── security
│   ├── __init__.py
│   ├── api_key.py
│   ├── base.py
│   ├── http.py
│   ├── oauth2.py
│   ├── open_id_connect_url.py
│   └── utils.py
├── staticfiles.py
├── templating.py
├── testclient.py
├── types.py
├── utils.py
└── websockets.py

```

## 核心链路/模块:

- [fastapi/applications.py](fastapi/applications.py)
- 依赖注入:
    - 核心是 [routing.py](fastapi/routing.py) 内部装饰器实现
    - [fastapi/params.py](fastapi/params.py)
