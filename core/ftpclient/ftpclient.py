#! /usr/bin/env python
# -*-coding: utf-8 -*-
import socket
import hashlib
import os
import json
import getpass
import sys
import shutil

from conf import settings


class FtpClient(object):
    """ftp客户端"""

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.client = socket.socket()
        self.connect_to_server(self.ip, self.port)

    def connect_to_server(self, ip, port):
        self.client.connect((self.ip, self.port))

    def route(self, cmd):
        """判断cmd是否存在，存在则执行cmd指令"""
        if cmd:
            action, *_ = cmd.split(maxsplit=1)
            if hasattr(self, action):
                func = getattr(self, action)
                return func(cmd)
            else:
                return '1000'
        else:
            return '1000'

    def put(self, cmd):
        """上传文件到客户端"""
        cmd, local_filepath, *remote_filepath = cmd.strip().split()
        # print(local_filepath)
        try:
            if os.path.isfile(local_filepath):
                head = {
                    "action": "put",
                    # 获取文件名
                    "filename": os.path.basename(local_filepath),
                    # 获取文件大小
                    "size": os.path.getsize(local_filepath),
                    "target_path": remote_filepath
                }
                self.client.send(json.dumps(
                    head, ensure_ascii=False).encode(encoding='utf_8'))
                # print("发送head完毕")
                response = self.client.recv(1024).decode()
                # print(server_response)
                if response != "0000":
                    print(settings.ERROR_CODE.get(response))
                    return
                m = hashlib.md5()
                with open(local_filepath, 'rb') as f:
                    complete_size = 0
                    for line in f:
                        m.update(line)
                        self.client.send(line)
                        complete_size += len(line)
                        self.progressbar(complete_size, head.get("size"))
                    else:
                        # print(time.time() - start)
                        file_md5 = m.hexdigest()
                        print("文件{}发送完毕！".format(local_filepath))
                self.client.send(file_md5.encode('utf-8'))
                server_file_md5 = self.client.recv(1024).decode('utf-8')
                # print(server_file_md5, file_md5)
                if server_file_md5 == file_md5:
                    return True
            else:
                raise OSError("文件不存在")
        except Exception as e:
            print(e)

    def get(self, cmd):
        """从服务端下载文件"""
        print("开始下载")
        try:
            cmd, remote_filepath, local_file_path = cmd.strip().split()
        except ValueError:
            return print("请告诉我要把文件下载到哪个目录")
        head = {
            "action": "get",
            "filepath": remote_filepath
        }
        self.client.send(json.dumps(head).encode())  # 发送下载请求
        # print("发送请求给服务端")
        server_response = json.loads(self.client.recv(1024).decode())

        if server_response.get("status_code", 0) == '3000':  # 服务端返回异常状态码
            return '3000'
        else:  # 服务端返回的不是异常状态
            server_file_name = server_response.get("filename", 0)
            try:
                server_file_size = int(server_response.get("size", 0))
            except ValueError as e:
                print(e)
                return e
            if all((server_file_name, server_file_size)):  # 判断服务端返回的2个数据是否正常
                local_file_path_name = os.path.join(
                    local_file_path, server_file_name)
                temp_file_path = "{}.temp".format(local_file_path_name)
                if os.path.isfile(temp_file_path):
                    received_size = os.path.getsize(temp_file_path)
                else:
                    received_size = 0
                request_info = {"status_code": "0000",
                                "received_size": received_size}
                self.client.send(
                    json.dumps(request_info).encode()
                )  # 发送成功状态码和已接收的文件大小给服务器

            else:
                # 告诉服务端发给我的数据有异常,并返回
                return self.client.send(
                    json.dumps({"status_code": "9000"}).encode())
            m = hashlib.md5()
            try:
                with open(temp_file_path, 'ab+') as f:
                    while received_size < server_file_size:  # 开始接收文件
                        data = self.client.recv(
                            min(1024, server_file_size - received_size))
                        if not data:
                            break
                        m.update(data)
                        f.write(data)
                        self.progressbar(received_size, server_file_size)
                        received_size += len(data)
                    else:
                        self.progressbar(received_size, server_file_size)
                        print("文件接收完毕！")
            except KeyboardInterrupt:
                # return self.client.send(b"9999")  # 告诉服务器文件传输被中断了
                self.client.close()
                exit("谢谢使用")
            shutil.copyfile(temp_file_path, local_file_path_name)
            shutil.os.remove(temp_file_path)
            self.client.send("0000".encode())  # 告诉服务器我已经接收完毕了
            recv_file_md5 = m.hexdigest()
            server_file_md5 = self.client.recv(1024).decode()
            # print(recv_file_md5, server_file_md5)
            if recv_file_md5 == server_file_md5:
                return "0000"

    def progressbar(self, complete, total):
        one_star = total / 100
        star_count = int(complete // one_star)
        precentage = complete / total
        output_precentage = "{:.1%}".format(precentage)
        output = output_precentage.center(star_count, "*")
        sys.stdout.write("\r{}".format(output))
        sys.stdout.flush()
        if complete == total:
            sys.stdout.write("\n")

    def register(self, username, password, disk_size):
        """
        用户注册
        param disk_size: 磁盘空闲大小，单位MB

        """
        bt_disk_size = int(disk_size) * 1024 * 1024
        m = hashlib.md5()
        m.update(password.encode())
        password = m.hexdigest()
        info_dict = {
            "action": "register",
            "username": username,
            "password": password,
            "disk_size": bt_disk_size
        }
        # print(info_dict)
        self.client.send(json.dumps(info_dict, ensure_ascii=False).encode())
        return self.client.recv(1024).decode()

    def login(self, username, password):
        m = hashlib.md5()
        m.update(password.encode())
        password = m.hexdigest()
        info_dict = {
            "action": "login",
            "username": username,
            "password": password
        }
        self.client.send(json.dumps(info_dict).encode())
        try:
            result_size = int(json.loads(self.client.recv(1024).decode()))
        except ValueError:
            return self.client.send(b'6000')
        self.client.send(b'0000')
        recv_size = 0
        data_list = []
        while recv_size < result_size:
            data = self.client.recv(min(1024, result_size - recv_size))
            data_list.append(data)
            recv_size += len(data)
        recv_data = b''.join(data_list).decode()
        recv_dict = json.loads(recv_data)
        # print(recv_dict)
        recv_status = recv_dict.get("status_code", 0)
        if recv_status == '0000':
            recv_dir = recv_dict.get("dir")
            self.my_current_dir = recv_dir
            self.my_username = username
            self.my_pwd = password
        return recv_status

    def cd(self, command):
        """切换目录"""
        cmd, *new_dir = command.strip().split(maxsplit=1)
        # print(new_dir)
        cmd_dict = {"action": cmd, "dir": new_dir}
        self.client.send(json.dumps(cmd_dict, ensure_ascii=False).encode())
        try:
            total_size = int(self.client.recv(1024).decode())
        except ValueError:
            print("服务器返回的结果长度不是数字")
            return
        # print("total_size", total_size)
        self.client.send(b'0000')
        recv_size = 0
        recv_data_list = []
        while recv_size < total_size:
            data = self.client.recv(min(1024, total_size - recv_size))
            recv_data_list.append(data)
            recv_size += len(data)
        recv_data = b"".join(recv_data_list).decode()
        response_dict = json.loads(recv_data)
        # print("recv_dir:", response_dict.get("new_dir"))
        self.my_current_dir = response_dict.get("new_dir")
        return response_dict.get("status_code")

    def mkdir(self, command):
        """创建目录"""
        cmd, new_dir = command.strip().split()
        cmd_dict = {"action": cmd, "new_dir": new_dir}
        self.client.send(json.dumps(cmd_dict).encode())
        result = self.client.recv(1024).decode()
        print(result)
        return result

    def ls(self, command):
        """查看目录下的子目录和文件"""
        cmd, *new_dir = command.strip().split()
        # print(new_dir)
        if not new_dir:
            new_dir.append(self.my_current_dir)
        cmd_dict = {"action": cmd, "dir": new_dir[0]}
        # print(cmd_dict)
        self.client.send(json.dumps(cmd_dict, ensure_ascii=False).encode())
        server_response_size = int(self.client.recv(1024).decode())
        # print(server_response_size)
        if server_response_size == 1000:
            return
        self.client.send(b'0000')
        recv_size = 0
        recv_data_list = []
        while recv_size < server_response_size:
            data = self.client.recv(
                min(1024, server_response_size - recv_size))
            recv_size += len(data)
            recv_data_list.append(data)
        cmd_result = b''.join(recv_data_list)
        print(cmd_result.decode())
        return


class InterActive(object):
    """与用户交互"""

    def __init__(self, ip, port):
        self.client = FtpClient(ip, port)

    def interactive(self):
        command = input("{}#".format(self.client.my_current_dir)).strip()
        if command == 'exit':
            exit("GoodBye")
        self.client.route(command)

    def login(self):
        username = input("请输入用户名:\n>>").strip()
        password = getpass.getpass("请输入密码：\n>>").strip()
        return self.client.login(username, password)

    def register(self):
        username = input("请输入用户名:\n>>").strip()
        password = getpass.getpass("请输入密码：\n>>").strip()
        disk_size = input("请输入您所需磁盘空间，单位MB，最大1024MB").strip()
        return self.client.register(username, password, disk_size)


def main():
    while True:
        try:
            ip = input("请输入IP服务器IP地址：\n>>").strip()
            port = int(input("请输入端口号：\n>>").strip())
            conn = InterActive(ip, port)
            break
        except ValueError:
            print("端口号必须是数字！")
            continue
        except ConnectionRefusedError:
            exit("服务端未开启，请联系管理员！")
    while True:
        choice = input("1.注册  2.登录")
        if choice == "1":
            while True:
                result = conn.register()
                # print("result", result)
                if result == "0000":
                    print("注册成功，请登录！")
                    break
                else:
                    print(result, settings.ERROR_CODE.get(result))
                    continue
        if choice == "2":
            print("开始登录")
            result = conn.login()
            # print("result", result)
            if result == "0000":
                print("登录成功！")
                break
            else:
                print(settings.ERROR_CODE.get(result))
        if choice == "exit":
            exit("Goodbye")
        else:
            continue
    while True:
        try:
            conn.interactive()
        except ConnectionAbortedError:
            continue


if __name__ == '__main__':
    # client = FtpClient('localhost', 9999)
    # # client.put(r'D:\Temp\11111.JPG', '123')
    # client.get(r'11111.JPG', r'D:\QMDownload')
    main()
