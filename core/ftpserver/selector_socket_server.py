"""server modules."""
# ! /usr/bin/env python
# -*- coding: utf-8 -*-
import selectors
import socket
import queue
import collections
import os
import json
import platform
import asyncio
import _io

from conf import settings


class SelectSocketServer(object):
    """server."""

    def __init__(self, port, requesthandler):
        """初始化相关参数.

        :param requesthandler:处理请求的类
        """
        self.port = port
        self.requesthandler = requesthandler
        self.selector = selectors.DefaultSelector()
        self.socket = socket.socket()
        self.socket.setblocking(False)
        self.socket.bind(('', port))
        self.socket.listen(5)
        self.request_handler_relation = {}
        self.selector.register(self.socket, selectors.EVENT_READ)

    def get_handler(self, request):
        """获取每个客户端连接的专属handler."""
        exclusive_handler = self.request_handler_relation.get(
            request.fileno(), 0)
        if exclusive_handler:
            # print("老客户")
            handler = exclusive_handler
        else:
            handler = self.requesthandler(request, self)
            self.request_handler_relation[request.fileno()] = handler
            # print("新客户")
        return handler

    def get_request(self):
        """获取连接."""
        request, addr = self.socket.accept()
        request.setblocking(False)
        self.selector.register(request, selectors.EVENT_READ)
        return request, addr

    def close_request(self, request):
        """关闭请求连接."""
        self.selector.unregister(request)  # 取消关注
        del self.request_handler_relation[request.fileno()]
        request.close()

    def serv_forever(self):
        """程序主循环."""
        while True:
            ready = self.selector.select()  # 此方法返回已激活的连接列表
            for key, event in ready:
                socketobj = key.fileobj
                if socketobj is self.socket:  # 如果激活的是server
                    request, addr = self.get_request()
                    print("{} is connected!".format(request.getpeername()))
                else:  # 激活的连接不是server，那么肯定就是客户端连接了
                    # 获取自己的handler，每个客户端连接有一个专属的handler
                    # print(socketobj)
                    handler = self.get_handler(socketobj)
                    if event & selectors.EVENT_READ:  # 可读事件激活
                        # print("可读事件激活！")
                        try:
                            handler.read_loop()
                        except MyConnectionError as e:
                            print("客户端已断开")
                            self.close_request(socketobj)
                            continue
                        self.selector.modify(socketobj, selectors.EVENT_WRITE)
                        # print("将事件改为可写！")
                    elif event & selectors.EVENT_WRITE:  # 可写事件激活
                        # print("可写事件激活！")
                        is_wirte_finish = handler.write_loop()
                        if is_wirte_finish[0] == 1:
                            self.selector.modify(
                                socketobj, selectors.EVENT_READ)
                            # print("将事件改为可读！")
                    else:
                        pass


class RequestHandler(object):
    """请求处理类.

    负责处理请求，每一个新的客户端连接进来必须实例化此类，已连接的客户端不要重复实例化
    可读事件请调用read方法，可写事件请调用write方法。如果有个性化需求需要继承此类，建议不要重写这两个方法
    其余方法为业务逻辑，继承此类，可重写。
    """

    loop = asyncio.get_event_loop()

    def __init__(self, request, server):
        """构造方法.

        self.request_queue: 读完客户端数据后把要发送的结果数据放到这个队列里
        self.is_wirte_finish：1-数据已发完 0-数据未发完
        self.client_recv_size：客户端已收到的文件大小，文件发送完毕后需置为none
        self.recv_size：服务端已收到的文件大小，接收完毕后需置为none
        self.send_fileobj：待发送的文件对象，发送完毕需要重新置为none
        self.recv_fileobj：上传中的文件对象，接收完毕需要重新置为none
        """
        self.request = request
        self.server = server
        self.request_queue = collections.defaultdict(queue.Queue)
        self.is_wirte_finish = 1
        self.file_size = None
        self.client_recv_size = None
        self.recv_size = None
        self.send_fileobj = None
        self.recv_fileobj = None
        self.response_message = None
        self.is_put = 0
        self.is_put_finish = 0
        self.put_filesize = 0
        self.is_put_done = 0
        self.put_total_filesize = 0
        self.put_fileobj = 0
        # print(self.response_message)

    def read_loop(self):
        """调用协程方法read."""
        try:
            return RequestHandler.loop.run_until_complete(
                asyncio.gather(self.read()))
        except MyConnectionError as e:
            print(e)
            print("dfsdfsdf")

    def write_loop(self):
        """调用协程方法write."""
        return RequestHandler.loop.run_until_complete(
            asyncio.gather(self.write()))

    @asyncio.coroutine
    def read(self):
        """处理可读事件."""
        temp_list = []
        while True:  # 由于select是水平触发的，一旦有可读事件激活就代表读缓冲区满了，必须把数据全部读完
            try:
                data = self.request.recv(1024)
            except BlockingIOError:  # 处理读穿异常
                if not temp_list:
                    print("直接返回")
                    return
                break
            temp_list.append(data)
        datas = b''.join(temp_list)
        if not self.is_put_done:
            cmd_dic = json.loads(datas.decode())
            action = cmd_dic.get('action', 0)
            res_dict = {}
            if not action:
                res_dict = {"status": "1000"}
            else:
                if hasattr(self, action):
                    func = getattr(self, action)
                    res_dict = yield from func(cmd_dic)  # 没有异常的时候res_dict是None
                else:
                    res_dict = {"status": "2000"}
            if res_dict:
                response_message = json.dumps(res_dict).encode()
                message_size = len(response_message)
                self.request_queue["temp"].put(response_message)
                self.request_queue["output"].put(
                    str(message_size).encode())
        else:
            # print("上传文件")
            self.request_queue["output"].put(datas)

    def clean_var(self):
        """将发送文件相关的参数重置为默认值."""
        self.is_wirte_finish = 1
        self.client_recv_size = None
        self.recv_size = None
        self.send_fileobj = None
        self.recv_fileobj = None
        self.response_message = None

    def clean_put(self):
        """将上传文件相关的参数重置为默认值."""
        self.is_put = 0
        self.is_put_finish = 0
        self.put_filesize = 0
        self.is_put_done = 0
        self.put_total_filesize = 0
        self.put_filesize = 0
        self.put_fileobj = 0
        self.response_message = None

    @asyncio.coroutine
    def send_file(self):
        """一点一点读取文件."""
        # print("调用发文件方法")
        data = self.send_fileobj.read(8192)
        return data

    @asyncio.coroutine
    def write(self):
        """可写事件调用这个方法，将数据发给客户端."""
        if self.request_queue["output"].qsize() > 0:
            self.response_message = self.request_queue["output"].get()
            print("待发数据：", self.response_message)
        if self.response_message:
            # print(self.response_message)
            if isinstance(self.response_message, _io.BufferedReader):
                self.send_fileobj = self.response_message
                self.send_fileobj.seek(self.client_recv_size)
                if not self.file_size:
                    self.file_size = os.path.getsize(
                        self.send_fileobj.fileno())
                self.is_wirte_finish = 0
                if self.client_recv_size < self.file_size:
                    data = yield from self.send_file()
                    self.client_recv_size += len(data)
                    self.request.sendall(data)
                    return self.is_wirte_finish
                else:
                    self.clean_var()
                    return self.is_wirte_finish
            else:
                if self.is_put_done:
                    yield from self.write_data_file()
                    # print("调用写文件方法：", self.is_wirte_finish)
                    if self.put_filesize == self.put_total_filesize:
                        self.clean_put()
                    return self.is_wirte_finish
                else:
                    self.request.sendall(self.response_message)
                    # print("调用发数据方法:", self.response_message)
                    if self.is_put_finish:
                        print("将is_done改为1")
                        self.is_put_done = 1
                    return self.is_wirte_finish
        else:
            self.clean_var()
            return self.is_wirte_finish

    @asyncio.coroutine
    def write_data_file(self):
        """文件上传时写入文件方法."""
        if self.put_filesize < self.put_total_filesize:
            self.put_fileobj.write(self.response_message)
            self.put_filesize += len(self.response_message)

    @asyncio.coroutine
    def finish(self, cmd=None):
        """这个方法是将要发给客户端的数据放到消息队列里."""
        print("调用finish")
        if cmd:
            self.client_recv_size = int(cmd.get("received_size", 0))
        if self.is_put:
            self.is_put_finish = 1
        self.send_data = self.request_queue["temp"].get()
        return self.request_queue["output"].put(self.send_data)

    @asyncio.coroutine
    def register(self, userinfo_dict):
        """处理用户的注册请求."""
        # print("开始注册")
        client_username = userinfo_dict.get("username", 0)
        client_password = userinfo_dict.get("password", 0)
        try:
            client_disk_size = int(userinfo_dict.get("disk_size", 0))
        except ValueError:
            return {"status": "6000"}
        if all((client_username, client_password, client_disk_size)):
            user_account_path = os.path.join(
                settings.DATA_PATH, client_username)
            user_home_path = os.path.join(
                settings.HOME_PATH, client_username)
            if os.path.isfile(user_account_path):
                return {"status": "5000"}  # 用户已存在
            if client_disk_size > settings.USER_DISK_MAXSIZE:
                return {"status": "4000"}
            try:
                os.mkdir(user_home_path)  # 创建用户的家目录
            except Exception:
                return {"status": "3999"}  # 目录创建失败
            with open(user_account_path, 'w') as f:
                userinfo = {"username": client_username,
                            "password": client_password,
                            "disk_size": client_disk_size}
                json.dump(userinfo, f, ensure_ascii=False)
            # print("注册成功")
            value = {"status": "0000"}
            response_message = json.dumps(value).encode()
            message_size = len(response_message)
            self.request_queue["temp"].put(response_message)
            self.request_queue["output"].put(str(message_size).encode())
        else:
            return {"status": "6000"}  # 请求有异常

    @asyncio.coroutine
    def login(self, userinfo_dict):
        """用户登录."""
        print("开始登录")
        client_username = userinfo_dict.get("username", 0)
        client_password = userinfo_dict.get("password", 0)
        if any((not client_username, not client_password)):  # 有任意一个条件为假
            return {"status": "6000"}  # 请求有异常
        user_path = os.path.join(settings.DATA_PATH, client_username)
        if not os.path.isfile(user_path):
            return {"status": "7000"}  # 用户名不存在
        # print("user_path:", user_path)
        with open(user_path, 'r') as f:
            userinfo = json.load(f)
        username = userinfo.get("username", 0)
        password = userinfo.get("password", 0)

        if any((not client_username == username,
                not client_password == password)):
            return {"status": "8000"}  # 用户名或密码不正确

        self.client_home_dir = os.path.join(
            settings.HOME_PATH, client_username)
        self.current_dir = self.client_home_dir
        value = {"status": "0000", "dir": self.current_dir}
        response_message = json.dumps(value).encode()
        message_size = len(response_message)
        self.request_queue["temp"].put(response_message)
        self.request_queue["output"].put(str(message_size).encode())

    @asyncio.coroutine
    def ls(self, cmd):
        """执行ls命令."""
        ls_dir = cmd.get("dir")
        myplatform = platform.uname().system
        if myplatform == "Windows":
            cmd = ["dir", ls_dir]
        else:
            cmd = "ls {}".format(ls_dir)
        # print(cmd)
        dir_details = {"status": "0000",
                       "new_dir": platform.subprocess.getoutput(cmd)}
        # print("dir_details:", dir_details)
        response_message = json.dumps(dir_details).encode()
        message_size = len(response_message)
        self.request_queue["temp"].put(response_message)
        self.request_queue["output"].put(str(message_size).encode())

    @asyncio.coroutine
    def get(self, cmd):
        """执行get命令."""
        file_path = cmd.get("filepath", 0)

        if len(file_path.split(os.sep)) == 1:
            file_path = os.path.join(self.current_dir, file_path)
        else:
            file_path = os.path.join(self.client_home_dir, file_path)

        if os.path.isfile(file_path):
            filename = os.path.basename(file_path)
            filesize = os.path.getsize(file_path)
            message_head = {"status": "0000",
                            "filename": filename, "filesize": filesize}
            f = open(file_path, 'rb')
            self.request_queue["temp"].put(f)
        else:
            message_head = {"status": "3000"}  # 文件不存在
        message = json.dumps(message_head).encode()
        self.request_queue["output"].put(message)

    @asyncio.coroutine
    def put(self, cmd):
        """执行put方法."""
        self.put_filename = cmd.get("filename")
        self.is_put = 1
        self.put_total_filesize = cmd.get("size")
        self.target_path = cmd.get("target_path")[0]
        self.put_fileobj = open(os.path.join(
            self.target_path, self.put_filename), 'ab')
        response_message = json.dumps({"status": "0000"}).encode()
        len_res = len(response_message)
        self.request_queue["output"].put(str(len_res).encode())
        self.request_queue["temp"].put(response_message)


class MyConnectionError(Exception):
    """socket异常类."""

    pass


def main():
    """启动程序需执行此函数."""
    server = SelectSocketServer(10001, RequestHandler)
    server.serv_forever()


if __name__ == '__main__':
    main()
