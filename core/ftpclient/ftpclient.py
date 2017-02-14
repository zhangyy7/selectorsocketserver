"""ftp客户端模块."""
# ! /usr/bin/env python
# -*- coding: utf-8 -*-
import socket
import hashlib
import os
import json
import getpass
import sys
import shutil

from conf import settings


class FtpClient(object):
    """ftp客户端."""

    def __init__(self, host, port):
        """接收ip地址和端口号，调用连接方法."""
        self.my_current_dir = object()
        self.my_username = object()
        self.my_pwd = object()
        self.host = host
        self.port = port
        self.client = socket.socket()
        self.connect_to_server()

    def connect_to_server(self):
        """连接到服务器."""
        self.client.connect((self.host, self.port))

    def route(self, cmd):
        """解析输入的命令并执行对应的方法."""
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
        """上传文件到客户端."""
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
                res_size = int(self.client.recv(1024).decode())
                print(res_size)
                finish = json.dumps({"action": "finish"}).encode()
                self.client.sendall(finish)
                recv_size = 0
                res_data_list = []
                while recv_size < res_size:
                    data = self.client.recv(1024)
                    res_data_list.append(data)
                    recv_size += len(data)
                res_datas = b''.join(res_data_list).decode()
                response_dict = json.loads(res_datas)
                response = response_dict.get("status")
                if response != "0000":
                    print(settings.ERROR_CODE.get(response))
                    return
                # md5obj = hashlib.md5()
                with open(local_filepath, 'rb') as fileobj:
                    complete_size = 0
                    for line in fileobj:
                        # md5obj.update(line)
                        self.client.send(line)
                        complete_size += len(line)
                        self.progressbar(complete_size, head.get("size"))
                    # file_md5 = md5obj.hexdigest()
                    print("文件{}发送完毕！".format(local_filepath))
                # self.client.send(file_md5.encode('utf-8'))
                # server_file_md5 = self.client.recv(1024).decode('utf-8')
                # print(server_file_md5, file_md5)
                # if server_file_md5 == file_md5:
                #     return True
            else:
                raise OSError("文件不存在")
        except Exception as ex:
            print(ex)

    def get(self, cmd):
        """从服务端下载文件."""
        try:
            cmd, remote_filepath, local_file_path = cmd.strip().split()
        except ValueError:
            return print("请告诉我要把文件下载到哪个目录")
        head = {
            "action": cmd,
            "filepath": remote_filepath
        }
        self.client.send(json.dumps(head).encode())  # 发送下载请求
        # print("发送请求给服务端")
        server_r = self.client.recv(1024).decode()
        print("收到的信息：", server_r, type(server_r))
        server_response = json.loads(server_r)
        print("收到的文件头信息：", server_response.get("status", 0))

        if server_response.get("status", 0) == '3000':  # 服务端返回异常状态码
            print("直接返回了")
            return '3000'
        else:  # 服务端返回的不是异常状态
            server_file_name = server_response.get("filename", 0)
            try:
                server_file_size = int(server_response.get("filesize", 0))
            except ValueError as ex:
                print(ex)
                return ex
            if all((server_file_name, server_file_size)):  # 判断服务端返回的2个数据是否正常
                local_file_path_name = os.path.join(
                    local_file_path, server_file_name)
                temp_file_path = "{}.temp".format(local_file_path_name)
                if os.path.isfile(temp_file_path):
                    received_size = os.path.getsize(temp_file_path)
                else:
                    received_size = 0
                request_info = {"action": "finish",
                                "received_size": received_size}
                self.client.send(
                    json.dumps(request_info).encode()
                )  # 发送成功状态码和已接收的文件大小给服务器

            else:
                # 告诉服务端发给我的数据有异常,并返回
                return self.client.send(
                    json.dumps({"status_code": "9000"}).encode())
            md5obj = hashlib.md5()
            try:
                with open(temp_file_path, 'ab+') as fileobj:
                    while received_size < server_file_size:  # 开始接收文件
                        data = self.client.recv(
                            min(1024, server_file_size - received_size))
                        if not data:
                            break
                        md5obj.update(data)
                        fileobj.write(data)
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
            # self.client.send("0000".encode())  # 告诉服务器我已经接收完毕了
            # recv_file_md5 = m.hexdigest()
            # server_file_md5 = self.client.recv(1024).decode()
            # # print(recv_file_md5, server_file_md5)
            # if recv_file_md5 == server_file_md5:
            return "0000"

    @staticmethod
    def progressbar(complete, total):
        """进度条."""
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
        """用户注册."""
        bt_disk_size = int(disk_size) * 1024 * 1024
        md5obj = hashlib.md5()
        md5obj.update(password.encode())
        password = md5obj.hexdigest()
        info_dict = {
            "action": "register",
            "username": username,
            "password": password,
            "disk_size": bt_disk_size
        }
        # print(info_dict)
        self.client.send(json.dumps(info_dict, ensure_ascii=False).encode())
        total_size = int(self.client.recv(1024).decode())
        recv_size = 0
        datas = []
        print("total_size:", total_size)
        while recv_size < total_size:
            data = self.client.recv(min(1024, total_size - recv_size))
            recv_size += len(data)
            datas.append(data)
        result = b''.join(datas).decode()
        result = json.loads(result)
        return result

    def login(self, username, password):
        """登陆."""
        md5obj = hashlib.md5()
        md5obj.update(password.encode())
        password = md5obj.hexdigest()
        request_msg = {
            "action": "login",
            "username": username,
            "password": password
        }
        self.client.send(json.dumps(request_msg).encode())
        try:
            response_len = int(self.client.recv(1024))
        except ValueError:
            return
        finish_cmd = {"action": "finish"}
        self.client.send(json.dumps(finish_cmd).encode())
        response_list = []
        recv_size = 0
        print("结果长度：", response_len)
        while recv_size < response_len:
            data = self.client.recv(min(1024, response_len - recv_size))
            response_list.append(data)
            recv_size += len(data)
        response_msg = b''.join(response_list)
        response_dict = json.loads(response_msg.decode())
        print(response_dict)
        response_status = response_dict.get("status", 0)
        # print(response_dict)
        if response_status == '0000':
            recv_dir = response_dict.get("dir")
            self.my_current_dir = recv_dir
            self.my_username = username
            self.my_pwd = password
        return response_status

    def cd(self, command):
        """切换目录."""
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
        """创建目录."""
        cmd, new_dir = command.strip().split()
        cmd_dict = {"action": cmd, "new_dir": new_dir}
        self.client.send(json.dumps(cmd_dict).encode())
        result = self.client.recv(1024).decode()
        print(result)
        return result

    def ls(self, command):
        """查看目录下的子目录和文件."""
        print("调用ls")
        cmd, *new_dir = command.strip().split()
        # print(new_dir)
        if not new_dir:
            new_dir.append(self.my_current_dir)
        cmd_dict = {"action": cmd, "dir": new_dir[0]}
        # print(cmd_dict)
        self.client.send(json.dumps(cmd_dict, ensure_ascii=False).encode())
        try:
            total_size = int(self.client.recv(1024))
        except ValueError:
            return
        finish_cmd = {"action": "finish"}
        self.client.send(json.dumps(finish_cmd).encode())
        datas = []
        recv_size = 0
        print(total_size)
        while recv_size < total_size:
            data = self.client.recv(min(1024, total_size - recv_size))
            recv_size += len(data)
            datas.append(data)
        cmd_result = b''.join(datas)
        result_dict = json.loads(cmd_result.decode())
        result_status = result_dict.get("status", 0)
        new_dir = result_dict.get("new_dir", 0)
        if all((result_status == "0000", new_dir)):
            print(new_dir)
        return


class InterActive(object):
    """与用户交互的类."""

    def __init__(self, ip, port):
        """实例化一个客户端类."""
        self.client = FtpClient(ip, port)

    def interactive(self):
        """获取用户输入的命令，把命令交给route去解析."""
        command = input("{}#".format(self.client.my_current_dir)).strip()
        if command == 'exit':
            exit("GoodBye")
        self.client.route(command)

    def login(self):
        """获取用户输入的用户名密码，交给客户端类去处理."""
        username = input("请输入用户名:\n>>").strip()
        password = getpass.getpass("请输入密码：\n>>").strip()
        return self.client.login(username, password)

    def register(self):
        """获取用户输入的用户名密码，交给客户端类去处理."""
        username = input("请输入用户名:\n>>").strip()
        password = getpass.getpass("请输入密码：\n>>").strip()
        disk_size = input("请输入您所需磁盘空间，单位MB，最大1024MB").strip()
        return self.client.register(username, password, disk_size)


def main():
    """程序主函数."""
    while True:
        try:
            host = input("请输入IP服务器IP地址：\n>>").strip()
            port = int(input("请输入端口号：\n>>").strip())
            conn = InterActive(host, port)
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
                print("result", result)
                if result.get("status") == "0000":
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
