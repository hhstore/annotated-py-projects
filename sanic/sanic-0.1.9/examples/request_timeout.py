from sanic import Sanic
import asyncio
from sanic.response import text
from sanic.config import Config
from sanic.exceptions import RequestTimeout


# 默认超时时间: 1秒
Config.REQUEST_TIMEOUT = 1
app = Sanic(__name__)


#
# 测试超时请求:
#
@app.route('/')
async def test(request):
    await asyncio.sleep(3)         # 等待3秒, 超时 [改成 0.3, OK]
    return text('Hello, world!')


@app.exception(RequestTimeout)
def timeout(request, exception):
    return text('RequestTimeout from error_handler.', 408)

app.run(host='0.0.0.0', port=8000)
