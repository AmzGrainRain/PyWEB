from os import path

from http_server.server import Server
from http_server.request import Request
from http_server.response import Response, DefaultHeaders

DefaultHeaders['Cache-Control'] = 'no-cache'
DefaultHeaders['Access-Control-Allow-Origin'] = 'same-origin'
DefaultHeaders['Content-Security-Policy'] = 'script-src \'self\''
DefaultHeaders['Connection'] = 'keep-alive'
DefaultHeaders['X-Powered'] = 'PyWeb'

app = Server('127.0.0.1', 3000)
current_dir = path.dirname(path.abspath(__file__))
app.set_static_dir(path.join(current_dir, 'www'))


@app.get('/login')
def home(req: Request, res: Response) -> None:
    if req.query_string is None:
        res.send_html('没传数据')
        return

    if 'id' not in req.query_string.keys():
        res.send_html('缺少必要参数')
        return

    if 'password' not in req.query_string.keys():
        res.send_html('缺少必要参数')
        return

    if req.query_string['id'] == 'khlee' and req.query_string['password'] == '123':
        res.send_html('登录成功')
        return
    else:
        res.send_html('登录失败')
        return


app.run()
