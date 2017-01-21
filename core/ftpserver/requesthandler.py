import os
import hashlib
import platform
import logging.config
import json
import selectors
from conf import settings

logging.config.dictConfig(settings.LOGGING_DIC)
logger = logging.getLogger(__name__)


class RequestHandler(object):
    """ftp服务器端请求处理类"""

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        try:
            self.handle()
        except Exception as e:
            print(e)

    def __call__(self):
        """由实例+()调用，执行handle方法"""
        return self.handle()

    def handle(self):
        """处理客户端请求"""
        print("{} connect !".format(self.request.getsockname()))
        # self.sys_sep = os.sep
        head = self.request.recv(1024).decode()
        print(head)
        if not head:
            print("客户端已断开")
        logger.debug(head)
        head_dict = json.loads(head)
        print(head_dict)
        action = head_dict.get("action", 0)
        if not action:
            logger.error("not find action")
            self.request.send(b'6000')  # 请求有异常
        else:
            if hasattr(self, action):
                func = getattr(self, action)
                func(head_dict)
            else:
                self.request.send(b'1000')  # 指令错误
                logger.error("cmd error:not find {}".format(action))

    def get_dir_size(self, dirname):
        size = 0
        for root, dirs, files in os.walk(dirname):
            for name in files:
                current_path = os.path.join(root, name)
                size += os.path.getsize(current_path)
        return size

    def mkdir(self, cmd_dict):
        """处理用户创建目录的请求"""
        dir_path = cmd_dict.get("new_dir")
        if not dir_path:
            return self.request.send(b"6000")
        try:
            os.makedirs(os.path.join(self.current_dir, dir_path))
            return self.request.send(b'0000')
        except Exception:
            return self.request.send(b'2999')

    def put(self, cmd_dict):
        """处理客户端上传文件的请求"""
        logger.debug(cmd_dict)
        filename = cmd_dict["filename"]
        target_path_list = cmd_dict.get("target_path")
        try:
            size = int(cmd_dict["size"])
        except ValueError:
            logger.critical("size must be a integer")
            return self.request.send(b'6000')
        used_size = self.get_dir_size(self.client_home_dir)
        print(used_size, type(used_size))
        total_size = used_size + size
        # print(total_size,self.total_size)
        if total_size >= self.total_size:
            print("磁盘空间不够")
            return self.request.send(b'4444')
        if not target_path_list:
            target_path = self.current_dir
            logger.debug(target_path)
        else:
            target_path = os.path.join(self.current_dir, target_path_list[0])
            logger.debug(target_path)
        if not os.path.isdir(target_path):
            return self.request.send(b'3000')
        else:
            self.request.send(b'0000')
        with open(os.path.join(target_path, filename), 'wb') as f:
            self.server.selector.register(f, selectors.EVENT_READ)
            recv_size = 0
            # start = time.time()
            m = hashlib.md5()
            while recv_size < size:
                data = self.request.recv(min(1024, size - recv_size))
                m.update(data)
                f.write(data)
                recv_size += len(data)
            else:
                new_file_md5 = m.hexdigest()
                # print(new_file_md5)
                # print(time.time() - start)
                # print('接收到的文件大小为：', recv_size)
                print("文件{}接收成功".format(filename))
                self.server.selector.unregister(f)
        client_file_md5 = self.request.recv(1024).decode()
        status_code = '0000'
        if new_file_md5 != client_file_md5:
            logger.debug("md5校验失败")
            status_code = '2000'  # md5校验失败
        self.request.send(status_code.encode('utf-8'))

    def get(self, cmd_dict):
        """处理客户端下载文件的请求"""
        filepath = cmd_dict.get("filepath", 0)
        # print(filepath)
        if len(filepath.split(os.sep)) == 1:
            server_filepath = os.path.join(self.current_dir, filepath)
        else:
            server_filepath = os.path.join(self.client_home_dir, filepath)
        if not os.path.isfile(server_filepath):
            head = json.dumps({"status_code": "3000"}, ensure_ascii=False)
            print("---100---文件不存在", head)
            return self.request.send(head.encode())  # 文件路径不存在

        filename = os.path.basename(server_filepath)
        filesize = os.path.getsize(server_filepath)
        head_dict = {"filename": filename, "size": filesize}
        head = json.dumps(head_dict, ensure_ascii=False)
        self.request.send(head.encode())  # 发送文件信息给客户端
        print("---108---发给客户端的数据:", head)
        recv_info = json.loads(self.request.recv(1024).decode())
        client_status = recv_info.get("status_code", 0)

        if client_status == "0000":
            try:
                client_received_size = int(recv_info.get("received_size", 0))
            except ValueError:
                return
            m = hashlib.md5()
            with open(server_filepath, 'rb') as f:
                self.server.selector.register(f, selectors.EVENT_READ)
                f.seek(client_received_size)
                for line in f:
                    # recv_data = threading.Thread(
                    #     target=self.request.recv, args=(1024,))
                    # recv_data.start()
                    # if not recv_data:
                    m.update(line)
                    self.request.send(line)
                else:
                    file_md5 = m.hexdigest()
                    print("文件发送完毕！")
                    self.server.unregister(f)
            client_recv = self.request.recv(1024).decode()
            if client_recv == "0000":
                self.request.send(file_md5.encode())
            else:
                return
        else:
            return

    def register(self, userinfo_dict):
        """处理用户的注册请求"""
        print("开始注册")
        print(userinfo_dict)
        client_username = userinfo_dict.get("username", 0)
        client_password = userinfo_dict.get("password", 0)
        try:
            client_disk_size = int(userinfo_dict.get("disk_size", 0))
        except ValueError:
            return self.request.send(b'6000')
        if all((client_username, client_password, client_disk_size)):
            user_account_path = os.path.join(
                settings.DATA_PATH, client_username)
            user_home_path = os.path.join(
                settings.HOME_PATH, client_username)
            if os.path.isfile(user_account_path):
                return self.request.send(b'5000')  # 用户已存在
            if client_disk_size > settings.USER_DISK_MAXSIZE:
                return self.request.send(b'4000')
            os.mkdir(user_home_path)  # 创建用户的家目录
            with open(user_account_path, 'w') as f:
                userinfo = {"username": client_username,
                            "password": client_password,
                            "disk_size": client_disk_size}
                json.dump(userinfo, f, ensure_ascii=False)
            print("注册成功")
            return self.request.send(b'0000')
        else:
            return self.request.send(b'6000')  # 请求有异常

    def login(self, userinfo_dict):
        """用户登录"""
        print("开始登录")
        # print(userinfo_dict)
        client_username = userinfo_dict.get("username", 0)
        client_password = userinfo_dict.get("password", 0)
        if any((not client_username, not client_password)):  # 有任意一个条件为假
            msg = json.dumps({"status_code": "6000"}).encode()
            self.request.send(str(len(msg)).encode())
            self.request.recv(1024)
            return self.request.send(msg)  # 请求有异常
        user_path = os.path.join(settings.DATA_PATH, client_username)
        if not os.path.isfile(user_path):
            msg = json.dumps({"status_code": "7000"}).encode()
            self.request.send(str(len(msg)).encode())
            self.request.recv(1024)
            return self.request.send(msg)  # 用户名不存在
        with open(user_path, 'r') as f:
            userinfo = json.load(f)
        username = userinfo.get("username", 0)
        password = userinfo.get("password", 0)

        if any((not client_username == username, not client_password == password)):
            msg = json.dumps({"status_code": "8000"}).encode()
            self.request.send(str(len(msg)).encode())
            self.request.recv(1024)
            return self.request.send(msg)  # 请求有异常

        self.client_home_dir = os.path.join(
            settings.HOME_PATH, client_username)
        self.current_dir = self.client_home_dir
        self.total_size = userinfo.get("disk_size", 0)
        msg_dict = {"status_code": "0000", "dir": self.client_home_dir}
        msg = json.dumps(msg_dict, ensure_ascii=False).encode()
        self.request.send(str(len(msg)).encode())
        self.request.recv(1024)
        return self.request.send(msg)

    def ls(self, cmd):
        ls_dir = cmd.get("dir")
        myplatform = platform.uname().system
        if myplatform == "Windows":
            cmd = ["dir", ls_dir]
        else:
            cmd = "ls {}".format(ls_dir)
        print(cmd)
        msg = platform.subprocess.getoutput(cmd).encode()
        self.request.send(str(len(msg)).encode())
        self.request.recv(1024)
        return self.request.send(msg)

    def cd(self, cmd):
        """处理客户端切换目录请求"""
        print("切换目录")
        new_dir = cmd.get("dir", [])
        slice_start = len(self.client_home_dir)
        current_dir_list = self.current_dir.split(os.sep)
        status_code = '0000'
        if not new_dir:
            self.current_dir = self.client_home_dir
        elif new_dir[0] == "..":
            new_current_dir_list = current_dir_list[slice_start:-1]
            print("new_current_dir_list", os.sep.join(new_current_dir_list))
            self.current_dir = os.path.join(
                self.client_home_dir, os.sep.join(new_current_dir_list))
            print(self.current_dir)
        else:
            current_dir_list.append(new_dir[0])
            current_dir_temp = os.sep.join(current_dir_list)
            print("------265-------", self.current_dir)
            if os.path.isdir(current_dir_temp):
                self.current_dir = current_dir_temp
            else:
                status_code = '3000'
        print("------271-------", status_code)
        msg_dict = {"status_code": status_code, "new_dir": self.current_dir}
        msg = json.dumps(msg_dict, ensure_ascii=False).encode()
        self.request.send(str(len(msg)).encode())  # 发送结果长度
        print(len(msg))
        self.request.recv(1024)
        print("客户端已已确认")
        return self.request.send(msg)
