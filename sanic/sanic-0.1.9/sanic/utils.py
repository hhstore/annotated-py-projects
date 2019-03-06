import aiohttp                     # aiohttp.ClientSession() 使用
from sanic.log import log

HOST = '127.0.0.1'    # 默认 HOST
PORT = 42101          # 默认 端口


#############################################
#             本地 HTTP 请求处理
#
# 说明:
#   - 异步返回 HTTP 响应
#
#############################################
async def local_request(method, uri, cookies=None, *args, **kwargs):
    url = 'http://{host}:{port}{uri}'.format(host=HOST, port=PORT, uri=uri)
    log.info(url)

    #
    # 异步 session() 处理:
    #   - 返回 异步 HTTP 响应
    #   - aiohttp.ClientSession() 需查看相关代码
    #
    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with getattr(session, method)(url, *args, **kwargs) as response:
            response.text = await response.text()   # 异步 HTTP 响应
            response.body = await response.read()   # 异步 HTTP 响应
            return response


#############################################
#             sanic 框架端点测试
#
# 说明:
#   - 启动 web 服务, 处理 HTTP 请求, 并返回结果
#
#############################################
def sanic_endpoint_test(app, method='get', uri='/', gather_request=True,
                        loop=None, debug=False, *request_args,
                        **request_kwargs):
    results = []
    exceptions = []

    if gather_request:
        @app.middleware
        def _collect_request(request):
            results.append(request)

    #
    # 异步: 收集 HTTP 响应
    #   - 更新 results 内容
    #
    async def _collect_response(sanic, loop):
        try:
            #
            # 异步处理: 本地 HTTP 请求
            #
            response = await local_request(method, uri, *request_args,
                                           **request_kwargs)
            results.append(response)
        except Exception as e:
            exceptions.append(e)
        app.stop()

    #
    # server 启动:
    #   - 异步执行, 返回 HTTP 响应
    #   - after_start参数: _collect_response
    #
    app.run(host=HOST, debug=debug, port=42101,
            after_start=_collect_response, loop=loop)

    if exceptions:
        raise ValueError("Exception during request: {}".format(exceptions))

    #
    # 返回执行结果:
    #   - 由 results 提取
    #
    if gather_request:
        try:
            request, response = results   # 返回 results 内容
            return request, response
        except:
            raise ValueError(
                "Request and response object expected, got ({})".format(
                    results))
    else:
        try:
            return results[0]     # 返回 results 内容
        except:
            raise ValueError(
                "Request object expected, got ({})".format(results))
