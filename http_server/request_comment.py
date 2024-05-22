import socket
import tempfile
from os import path
import os


# 解析查询字符串为字典的函数
def parse_query_string(query_string: str) -> dict[str, any]:
    # 初始化数据字典
    data: dict[str, any] = {}

    try:
        # 将查询字符串按&分割成键值对列表
        pairs: list[str] = query_string.split('&')

        # 如果没有键值对，直接返回空字典
        if len(pairs) == 0:
            return data

        # 遍历键值对列表
        for pair_str in pairs:
            # 查找等号位置以分离键和值
            pivot: int = pair_str.find('=')
            if pivot == -1:
                # 如果没有等号，键为整个字符串，值设为None
                data[pair_str] = None
                continue
            key = pair_str[:pivot]  # 提取键
            value = pair_str[pivot + 1:]  # 提取值
            data[key] = value  # 将键值对存入字典
    except Exception as err:
        # 捕获并打印异常信息
        print(err)

    return data


# 解析路径和查询字符串的函数
def path_parse(full_path: str) -> tuple[str, dict[str, str]]:
    # 如果路径中没有查询字符串，直接返回路径和空字典
    if '?' not in full_path:
        return full_path, {}

    # 分离路径和查询字符串
    pivot: int = full_path.find('?')
    path_: str = full_path[:pivot]
    query_string: dict[str, any] = parse_query_string(full_path[pivot + 1:])  # 解析查询字符串

    return path_, query_string


# 解析HTTP头信息为字典的函数
def parse_header(header_list: tuple[str, ...]) -> dict[str, str]:
    data: dict[str, str] = {}  # 初始化头信息字典

    # 遍历原始头信息列表
    for item in header_list:
        if ':' not in item:
            continue  # 跳过无效的行

        try:
            # 分离键和值
            i = item.index(':')
            key = item[:i].strip()  # 提取并清理键
            value = item[i + 1:].strip()  # 提取并清理值
            data[key] = value  # 存储键值对
        except ValueError:
            # 打印错误信息并继续处理其他头信息
            print(f"Error parsing header '{item}': Missing valid name-value structure.")
            continue

    return data


# 请求类，用于解析HTTP请求
class Request:
    # 初始化请求对象
    def __init__(self, sock_conn: socket.socket) -> None:
        binary_header: bytearray = bytearray()  # 初始化二进制头信息缓存
        # 接收数据直到读到完整的HTTP头（\r\n\r\n）
        while b'\r\n\r\n' not in binary_header:
            data = sock_conn.recv(1024)
            if not data:
                break
            binary_header.extend(data)

        # 分离头信息和后续内容的边界
        headers_end: int = binary_header.index(b'\r\n\r\n')
        self.raw_headers = binary_header[:headers_end].decode('utf-8')  # 解码原始头信息
        self.raw_headers_tuple = tuple(self.raw_headers.splitlines())  # 将头信息转换为元组

        # 解析请求行信息
        meta_info: tuple[str, ...] = tuple(self.raw_headers_tuple[0].split(' '))
        self.method = meta_info[0]  # HTTP方法
        self.full_path = meta_info[1]  # 完整路径
        self.path, self.query_string = path_parse(meta_info[1])  # 分离路径与查询字符串
        self.http_version = meta_info[2]  # HTTP版本

        # 解析头信息为字典
        self.headers = parse_header(self.raw_headers_tuple[1:])

        # 处理请求体，根据Content-Length决定如何读取
        if 'Content-Length' not in self.headers.keys():
            self.body = None  # 无请求体时置为None
            return

        content_length: int = int(self.headers['Content-Length'])
        if content_length == 0:
            self.body = bytearray()  # 空请求体
            return

        if 'Content-Type' not in self.headers.keys():
            raise Exception('Client http message invaild.')  # 缺少Content-Type异常

        # 根据Content-Type处理不同类型的请求体
        content_type: str = self.headers['Content-Type']
        if content_type.startswith(('multipart/form-data', 'application/octet-stream')):
            # 临时文件存储二进制或表单数据
            with tempfile.NamedTemporaryFile(delete=False) as f:
                received_length = 0
                while received_length < content_length:
                    data = sock_conn.recv(min(content_length - received_length, 1024))
                    if not data:
                        raise Exception("Client connection closed before receiving complete body.")
                    f.write(data)
                    received_length += len(data)

                self.body = f.name
        else:
            # 直接读取并存储非特殊类型的请求体
            binary_body: bytearray = bytearray()
            received_length: int = 0
            while received_length < content_length:
                data = sock_conn.recv(min(content_length - received_length, 1024))
                if not data:
                    raise Exception("Client connection closed before receiving complete body.")
                binary_body.extend(data)
                received_length += len(data)

            self.body = binary_body

    # 析构函数，清理临时文件
    def __del__(self):
        if 'Content-Length' not in self.headers.keys():
            return

        if 'Content-Type' not in self.headers.keys():
            return

        ct: str = self.headers['Content-Type']
        if not ct.startswith(('multipart/form-data', 'application/octet-stream')):
            return

        if not path.exists(self.body):
            return

        os.remove(self.body)

    # 手动调用的清理方法，与析构函数功能相同，用于确保资源释放
    def cleanup(self):
        if hasattr(self, 'body') and isinstance(self.body, str) and path.exists(self.body):
            os.remove(self.body)
