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

    def __process_static(self, req_path: str, res: Response) -> None:
        req_path = req_path.lstrip('/')
        file_path: str = os.path.join(self.__static_dir, req_path)

        if os.path.isdir(file_path):
            file_path = os.path.join(file_path, 'index.html')

        if not os.path.exists(file_path):
            res.set_status(HttpStatus.Not_Found).send().close()
            return

        res.send_file(file_path)

    def __process_get(self, req: Request, res: Response) -> None:
        func: Callable[[Request, Response], None] | None = self.__get.get(req.path)
        if func is None:
            self.__process_static(req.path, res)
            return None
        func(req, res)

    def __process_post(self, req: Request, res: Response) -> None:
        func: Callable[[Request, Response], None] | None = self.__post.get(req.path)
        if func is None:
            res.set_status(HttpStatus.Not_Found)
            return None
        func(req, res)

    def __process_request(self, conn: socket.socket) -> None:
        try:
            req = Request(conn)
            res = Response(conn)

            if req.method == 'GET':
                self.__process_get(req, res)
                return

            if req.method == 'POST':
                self.__process_post(req, res)
                return

            res.set_status(HttpStatus.Bad_Request).send().close()

        except Exception as err:
            print(err)
            try:
                if not conn.recv(1) or conn.fileno() == -1:
                    return
            except Exception as inner_err:
                print(inner_err)
                return
            Response(conn).set_status(HttpStatus.Internal_Server_Error).send().close()

    def set_static_dir(self, path: str):
        self.__static_dir = path
        return self

    def run(self) -> None:
        sock_conn = create_socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_conn.bind((self.__host, self.__port))
        sock_conn.listen(1)

        while True:
            conn, _addr = sock_conn.accept()
            self.__process_request(conn)
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
