import os.path
from typing import BinaryIO

import socket
from os import path

from http_server.http_status import HttpStatus
from http_server.mime import MimeList

DefaultHeaders: dict[str, str] = {}


class Response:
    # socket 连接实例指针（万不可不要在此处关闭 socket）
    __conn: socket.socket
    # http 响应状态码
    __status: HttpStatus
    # 响应头
    __headers: dict[str, any]
    # 缓存的响应头
    __cached_header: str | None

    def __init__(self, conn: socket.socket) -> None:
        self.__conn = conn
        self.__status = HttpStatus.No_Content
        self.__headers = DefaultHeaders
        self.__cached_header = None

    def allow_cors(self):
        """
        允许本次响应跨域
        :return: 链式调用实例
        """

        self.__headers['Access-Control-Allow-Origin'] = 'cross-origin'
        return self

    def set_status(self, status: HttpStatus):
        """
        设置 HTTP 响应状态
        :param status: HttpStatus 枚举值
        :return: 链式调用实例
        """

        self.__status = status
        return self

    def set_header(self, key: str, value: any):
        """
        设置 HTTP 响应头
        :param key: 键
        :param value: 值
        :return: 链式调用实例
        """

        self.__headers[key] = value
        return self

    def get_header(self, key: str) -> str | None:
        """
        获取 HTTP 响应头的值
        :param key: 键
        :return: any | 不存在则返回 None
        """

        return self.__headers[key]

    def append_header(self, key: str, new_value: str):
        """给某个响应头追加属性\n
        如果被添加属性的响应头不存在则会创建一个响应头，它的初始属性就是在此处提供的 new_value\n

        例1：\n
        get_header('Content-Type') # 返回 text/html\n
        append_header('Content-Type', 'charset=utf-8')\n
        get_header('Content-Type') # 返回 text/html; charset=utf-8\n

        例2：\n
        get_header('Content-Length') # 返回 None\n
        append_header('Content-Length', '200')\n
        get_header('Content-Length') # 返回 200\n

        :param key: 键
        :param new_value: 追加的属性
        :return: 链式调用实例
        """

        # 如果被追加属性的响应头不存在
        if key not in self.__headers.keys():
            # 创建它，并把追加的属性作为初始属性
            self.__headers[key] = new_value
            return self

        # 把新的属性拼接进去
        old_value = self.__headers[key] + f'; {new_value}'
        # 更新响应头
        self.__headers[key] = old_value
        return self

    def set_content_type(self, mime: str):
        """
        设置响应数据的 mime 类型
        :param mime: MimeList 字典的值
        :return: 链式调用实例
        """

        self.__headers['Content-Type'] = mime
        return self

    def __generate_http_response_message(self, body: str = ''):
        """
        根据已设置的 status、headers 生成 HTTP 响应报文
        :param body: 要发送的数据
        :return: 响应报文
        """

        # 检查缓存，如果存在缓存则直接返回（此处用来应对 HTTP 长连接）
        if self.__cached_header is not None:
            return self.__cached_header

        # 拼接信息头
        msg = f'HTTP/1.1 {self.__status.value} {self.__status.name.replace('_', ' ')}\r\n'
        # 拼接响应头
        for k, v in self.__headers.items():
            msg += f'{k}: {v}\r\n'
        # 拼接响应数据
        return msg + '\r\n' + body

    def clear_http_message_cache(self):
        """
        清除 HTTP 响应报文缓存
        :return: 链式调用实例
        """

        self.__cached_header = None
        return self

    def send_message_without_data(self):
        """
        直接发送响应报文而不携带数据
        :return: 链式调用实例
        """

        self.__conn.sendall(self.__generate_http_response_message().encode('utf-8'))
        return self

    def send_text(self, text: str):
        """
        发送文本数据
        :param text: 文本
        :return: 链式调用实例
        """

        self.__status = HttpStatus.OK
        self.__headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.__headers['Content-Length'] = len(text.encode('utf-8'))
        self.__conn.sendall(self.__generate_http_response_message(text).encode('utf-8'))
        return self

    def send_html(self, html_str: str):
        """
        发送 html 文本
        :param html_str: 文本
        :return: 链式调用实例
        """

        self.__status = HttpStatus.OK
        self.__headers['Content-Type'] = 'text/html; charset=utf-8'
        self.__headers['Content-Length'] = len(html_str.encode('utf-8'))
        self.__conn.sendall(self.__generate_http_response_message(html_str).encode('utf-8'))
        return self

    def send_json(self, json_str: str):
        """
        发送 json 格式数据
        :param json_str: JSON 序列化后的字符串
        :return: 链式调用实例
        """

        self.__status = HttpStatus.OK
        self.__headers['Content-Type'] = 'application/json; charset=utf-8'
        self.__headers['Content-Length'] = len(json_str.encode('utf-8'))
        self.__conn.sendall(self.__generate_http_response_message(json_str).encode('utf-8'))
        return self

    def send_file(self, file_path: str):
        self.__status = HttpStatus.OK

        # 文件扩展名
        ext_name: str = f'.{path.splitext(file_path)[1]}'
        # 文件大小（字节）
        file_size: int = os.path.getsize(file_path)
        # 文件分块发送的块大小（MB）
        chunk_size: int = 1024 * 1024

        # 文件类型
        self.__headers['Content-Type'] = MimeList[ext_name] if ext_name in MimeList.keys() else 'text/plain'
        # 文件大小
        self.__headers['Content-Length'] = file_size
        # 告诉客户端请求结束后 不要立即关闭 http 连接（http 长连接支持）
        self.__headers['Connection'] = 'Keep-Alive'

        try:
            # 以二进制读模式打开文件, 无需关心文件类型和编码
            file: BinaryIO = open(file_path, 'rb')
            # 先发送不携带文件数据的响应头
            self.send_message_without_data()
            # 分块发送文件数据给客户端
            while True:
                # 读取 1MB
                data = file.read(chunk_size)
                if not data:
                    break
                # 发送给客户端
                self.__conn.sendall(data)
        except FileNotFoundError as err:
            print(err)
            self.set_status(HttpStatus.Not_Found).end()
        except Exception as err:
            print(err)
            self.set_status(HttpStatus.Not_Found).end()

        return self

    def close(self):
        self.__cached_header = None
        self.__conn.close()
