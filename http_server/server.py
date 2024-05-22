import functools
from typing import Callable
import os

import socket
from socket import socket as create_socket

from http_server.request import Request
from http_server.response import Response
from http_server.http_status import HttpStatus


class Server:
    __host: str
    __port: int
    __static_dir: str
    __get: dict[str, Callable[[Request, Response], None]]
    __post: dict[str, Callable[[Request, Response], None]]

    def __init__(self, host: str, port: int):
        self.__host = host
        self.__port = port
        self.__static_dir = ''
        self.__get = {}
        self.__post = {}

    def __process_static(self, req_path: str, res: Response):
        file_path: str = os.path.join(self.__static_dir, req_path)

        if os.path.isdir(file_path):
            file_path = os.path.join(file_path, 'index.html')

        if not os.path.exists(file_path):
            res.set_status(HttpStatus.Not_Found).end()
            return

        res.send_file(file_path)

    def __process_get(self, req: Request, res: Response) -> None:
        if req.path not in self.__post.keys():
            self.__process_static(req.path, res)
            return None
        self.__post[req.path](req, res)

    def __process_post(self, req: Request, res: Response) -> None:
        if req.path not in self.__post.keys():
            res.set_status(HttpStatus.Not_Found)
            return None
        self.__post[req.path](req, res)

    def set_static_dir(self, path: str):
        self.__static_dir = path
        print(path)

        return self

    def run(self) -> None:
        sock_conn = create_socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_conn.bind((self.__host, self.__port))
        sock_conn.listen(1)

        while True:
            conn, addr = sock_conn.accept()
            req = Request(conn)
            res = Response(conn)

            if req.method == 'GET':
                self.__process_get(req, res)
                continue

            if req.method == 'POST':
                self.__process_post(req, res)
                continue

            conn.close()

    def get(self, path: str):
        def decorator(func: Callable[[Request, Response], None]):
            @functools.wraps(func)
            def inner(_req: Request, _res: Response):
                self.__get[path] = func
            return inner
        return decorator

    def post(self, path: str):
        def decorator(func: Callable[[Request, Response], None]):
            @functools.wraps(func)
            def inner(_req: Request, _res: Response):
                self.__post[path] = func
            return inner
        return decorator
