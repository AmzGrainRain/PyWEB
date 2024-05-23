from os import path

from http_server.server import Server
from http_server.request import Request
from http_server.response import Response, DefaultHeaders
from http_server.http_status import HttpStatus

DefaultHeaders['Cache-Control'] = 'no-cache'
DefaultHeaders['Access-Control-Allow-Origin'] = 'same-origin'
DefaultHeaders['Content-Security-Policy'] = 'script-src \'self\''
DefaultHeaders['Connection'] = 'keep-alive'
DefaultHeaders['X-Powered'] = 'PyWeb'

app = Server('127.0.0.1', 3000)
current_dir = path.dirname(path.abspath(__file__))
app.set_static_dir(path.join(current_dir, 'www'))


@app.post('/login')
def home(req: Request, res: Response) -> None:
    print(req.body)


app.run()

