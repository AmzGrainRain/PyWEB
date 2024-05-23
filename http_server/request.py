import socket
from tempfile import NamedTemporaryFile
from os import path
import os


def parse_query_string(query_string: str) -> dict[str, any]:
    data: dict[str, any] = {}

    if len(query_string) == 0:
        return data

    try:
        # 'a=1&b=2=&c' -> ['a=1', 'b=2=', 'c']
        for pair_str in query_string.split('&'):
            # 找到第一个 '=' (应对极端情况: pair_str = 'b=2=')
            i: int = pair_str.index('=')

            # 若不存在 '=' 则认为它不包含值
            if i == -1:
                data[pair_str] = None
                continue

            # 提取键、值并保存到字典
            data[pair_str[:i]] = pair_str[i + 1:]
    except Exception as err:
        print(err)

    return data


def parse_full_path(full_path: str) -> tuple[str, dict[str, str]]:
    # 查找 '?'
    i: int = full_path.find('?')

    # 若路径不包含查询字符串则不做任何处理直接返回
    if i == -1:
        return full_path, {}

    # 提取请求路径部分
    path_: str = full_path[:i]
    # 提取查询字符串并解析它
    query_string: dict[str, any] = parse_query_string(full_path[i + 1:])

    return path_, query_string


def parse_header(header_list: tuple[str, ...]) -> dict[str, str]:
    data: dict[str, str] = {}

    for item in header_list:
        #
        i = item.index(':')

        if i == -1:
            continue

        try:

            key = item[:i].strip()
            value = item[i + 1:].strip()
            data[key] = value
        except ValueError:
            print(f"Error parsing header '{item}': Missing valid name-value structure.")
            continue

    return data


def process_form_data(sock_conn: socket.socket, container: bytearray, content_length: int) -> dict[str, str]:
    pass


def process_xform_data(sock_conn: socket.socket, container: bytearray, content_length: int) -> dict[str, str]:
    pass


def process_file_upload(sock_conn: socket.socket, container: bytearray, content_length: int) -> str:
    f = NamedTemporaryFile(delete=False)
    received_length = 0
    while received_length < content_length:
        data = sock_conn.recv(min(content_length - received_length, 1024))
        if not data:
            raise Exception("Client connection closed before receiving complete body.")
        f.write(data)
        received_length += len(data)

    file_path = f.name
    f.close()
    return file_path


def process_text_body(sock_conn: socket.socket, container: bytearray, content_length: int) -> str:
    binary_body: bytearray = bytearray()
    received_length: int = 0
    while received_length < content_length:
        data = sock_conn.recv(min(content_length - received_length, 1024))
        if not data:
            raise Exception("Client connection closed before receiving complete body.")
        binary_body.extend(data)
        received_length += len(data)


class Request:
    raw_headers: str
    raw_headers_tuple: tuple[str, ...]

    method: str
    full_path: str
    path: str
    query_string: dict[str, str] | None
    http_version: str

    headers: dict[str, any]
    body: dict[str, str] | str | None

    def __init__(self, sock_conn: socket.socket) -> None:
        binary_header: bytearray = bytearray()
        while b'\r\n\r\n' not in binary_header:
            data = sock_conn.recv(1024)
            if not data:
                break
            binary_header.extend(data)

        headers_end: int = binary_header.index(b'\r\n\r\n')
        self.raw_headers = binary_header[:headers_end].decode('utf-8')
        self.raw_headers_tuple = tuple(self.raw_headers.splitlines())

        meta_info: tuple[str, ...] = tuple(self.raw_headers_tuple[0].split(' '))
        self.method = meta_info[0]
        self.full_path = meta_info[1]
        self.path, self.query_string = parse_full_path(meta_info[1])
        self.http_version = meta_info[2]
        self.headers = parse_header(self.raw_headers_tuple[1:])

        # 数据长度
        if 'Content-Length' not in self.headers.keys():
            self.body = None
            return
        content_length: int = int(self.headers['Content-Length'])
        if content_length == 0:
            self.body = ''
            return

        # 数据格式
        if 'Content-Type' not in self.headers.keys():
            raise Exception('Client http message invaild.')
        content_type: str = self.headers['Content-Type']

        # 剩余字节
        data_begin: int = headers_end + 4
        overflow_reading_count: int = len(binary_header) - data_begin
        content_length -= overflow_reading_count

        if content_type.startswith('multipart/form-data'):
            self.body = process_form_data(
                sock_conn,
                binary_header[content_length:overflow_reading_count],
                content_length
            )
            return

        if content_type.startswith('x-www-form-urlencoded'):
            self.body = process_xform_data(
                sock_conn,
                binary_header[content_length:overflow_reading_count],
                content_length
            )
            return

        if content_type.startswith('application/octet-stream'):
            self.body = process_file_upload(
                sock_conn,
                binary_header[content_length:overflow_reading_count],
                content_length
            )
            return

        self.body = process_text_body(
            sock_conn,
            binary_header[content_length:overflow_reading_count],
            content_length
        )

    def __del__(self):
        if 'Content-Length' not in self.headers.keys():
            return

        if 'Content-Type' not in self.headers.keys():
            return

        ct: str = self.headers['Content-Type']
        if not ct.startswith('multipart/form-data') and not ct.startswith('application/octet-stream'):
            return

        if not path.exists(self.body):
            return

        os.remove(self.body)

    def cleanup(self):
        if hasattr(self, 'body') and isinstance(self.body, str) and path.exists(self.body):
            os.remove(self.body)
