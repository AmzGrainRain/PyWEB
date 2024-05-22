import socket
import tempfile
from os import path
import os


def parse_query_string(query_string: str) -> dict[str, any]:
    data: dict[str, any] = {}

    try:
        pairs: list[str] = query_string.split('&')
        if len(pairs) == 0:
            return data

        for pair_str in pairs:
            pivot: int = pair_str.find('=')
            if pivot == -1:
                data[pair_str] = None
                continue
            key = pair_str[:pivot]
            value = pair_str[pivot + 1:]
            data[key] = value
    except Exception as err:
        print(err)

    return data


def path_parse(full_path: str) -> tuple[str, dict[str, str]]:
    if '?' not in full_path:
        return full_path, {}

    pivot: int = full_path.find('?')
    path_: str = full_path[:pivot]
    query_string: dict[str, any] = parse_query_string(full_path[pivot + 1:])

    return path_, query_string


def parse_header(header_list: tuple[str, ...]) -> dict[str, str]:
    data: dict[str, str] = {}

    for item in header_list:
        if ':' not in item:
            continue

        try:
            i = item.index(':')
            key = item[:i].strip()
            value = item[i + 1:].strip()
            data[key] = value
        except ValueError:
            print(f"Error parsing header '{item}': Missing valid name-value structure.")
            continue

    return data


class Request:
    raw_headers: str
    raw_headers_tuple: tuple[str, ...]

    method: str
    full_path: str
    path: str
    query_string: dict[str, str] | None
    http_version: str

    headers: dict[str, any]
    body: bytearray | str | None

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
        self.path, self.query_string = path_parse(meta_info[1])
        self.http_version = meta_info[2]

        self.headers = parse_header(self.raw_headers_tuple[1:])

        if 'Content-Length' not in self.headers.keys():
            self.body = None
            return

        content_length: int = int(self.headers['Content-Length'])
        if content_length == 0:
            self.body = bytearray()
            return

        if 'Content-Type' not in self.headers.keys():
            raise Exception('Client http message invaild.')
        content_type: str = self.headers['Content-Type']

        if content_type.startswith('multipart/form-data') or content_type.startswith('application/octet-stream'):
            f = tempfile.NamedTemporaryFile(delete=False)
            received_length = 0
            while received_length < content_length:
                data = sock_conn.recv(min(content_length - received_length, 1024))
                if not data:
                    raise Exception("Client connection closed before receiving complete body.")
                f.write(data)
                received_length += len(data)

            self.body = f.name
            f.close()
        else:
            binary_body: bytearray = bytearray()
            received_length: int = 0
            while received_length < content_length:
                data = sock_conn.recv(min(content_length - received_length, 1024))
                if not data:
                    raise Exception("Client connection closed before receiving complete body.")
                binary_body.extend(data)
                received_length += len(data)

            self.body = binary_body

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
