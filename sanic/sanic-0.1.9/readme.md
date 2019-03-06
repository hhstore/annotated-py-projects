# Sanic-0.1.9 版本阅读笔记:

## 基于 sanic 的项目搜索:


- [github - snaic ](https://github.com/search?l=Python&q=sanic+&type=Repositories&utf8=%E2%9C%93)
- 只能找到零星的代码使用, 暂时未找到有影响力的项目.



## 项目示例代码:

- examples 目录下, 有 sanic 框架, 各模块使用示例.
- 这部分代码, 也需要看一下.


## 阅读记录:


```

-> % tree ./sanic -L 2
./sanic
├── __init__.py
├── __main__.py            # 项目顶级入口.
├── blueprints.py          # (已读) 蓝图部分
├── config.py              # (已读) 默认配置项
├── cookies.py             # (已读) cookie 处理
├── exceptions.py          # (已读) 自定义异常, 以及异常处理器
├── log.py                 # (已读) 日志配置
├── request.py             # (已读) [核心模块] HTTP 请求部分.
├── response.py            # (已读) [核心模块] HTTP 响应部分
├── router.py              # (已读) 路由管理
├── sanic.py               # (已读) [阅读入口] [核心模块]
├── server.py              # (已读) [核心模块] 服务启动 (异步实现)
├── static.py              # (已读) 静态资源文件处理(异步实现)
├── utils.py               # (已读) 框架测试代码
└── views.py               # (已读) 视图基类, 实现 Restful API 用.

0 directories, 15 files


```


## 阅读入口:

- [main.py](./sanic/__main__.py)
- [sanic.py](./sanic/sanic.py)
- [server.py](./sanic/server.py)
- [request.py](./sanic/request.py)
- [response.py](./sanic/response.py)



## 关于模板支持:

- [参考: Templates support - issue](https://github.com/channelcat/sanic/issues/113)
    - 此 issue 提供了示例写法.


```python
from sanic import Sanic
from sanic.response import html

from jinja2 import Environment, PackageLoader

env = Environment(loader=PackageLoader('app', 'templates'))

app = Sanic(__name__)

@app.route('/')
async def test(request):
    data = {'name': 'name'}

    template = env.get_template('index.html')
    html_content = template.render(name=data["name"])
    return html(html_content)


app.run(host="0.0.0.0", port=8000)

```



# 参考文档:

- [异步IO](http://www.liaoxuefeng.com/wiki/0014316089557264a6b348958f449949df42a6d3a2e542c000/00143208573480558080fa77514407cb23834c78c6c7309000)
- [协程](http://www.liaoxuefeng.com/wiki/0014316089557264a6b348958f449949df42a6d3a2e542c000/001432090171191d05dae6e129940518d1d6cf6eeaaa969000)





