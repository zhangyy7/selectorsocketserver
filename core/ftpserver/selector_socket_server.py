import socket
import selectors
import logging.config
from conf import settings
from . import requesthandler


logging.config.dictConfig(settings.LOGGING_DIC)
logger = logging.getLogger(__name__)


class SelectorsSocketserver(object):
    """基于selectors实现的socketserver类"""
    request_queue_size = 5  # listen的参数，允许等待的最大连接数
    allow_reuse_address = False  # 这个标记是用来判断是否允许地址重用
    request_handler_relation = {}

    # 第一步
    def __init__(self, port, requesthandlerclass):
        self.port = port  # 端口
        self.socket = socket.socket()  # 实例化一个socket
        # self.socket.setblocking(False)
        # 定义selector的类型，DefaultSelector就是系统支持那种底层就用哪种底层(select|epoll)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.socket, selectors.EVENT_READ)
        self.RequestHandlerClass = requesthandlerclass
        self.__shutdown_request = False  # 请求实例关闭标记
        self.server_bind()
        self.server_activate()

    def server_bind(self):
        """由构造方法调用，用来bind socket"""
        if self.allow_reuse_address:
            self.socket.setsocketopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', self.port))
        self.server_address = self.socket.getsockname()

    def server_activate(self):
        """由构造方法调用，用来启监听"""
        self.socket.listen(self.request_queue_size)

    def server_close(self):
        """关闭服务连接"""
        self.socket.close()

    # 第二步
    def serve_forever(self):
        while True:
            # 如果系统支持异步模式(select,epoll等)，会返回一个列表，否则返回的是空列表
            flag = 0
            event_list = self.selector.select()
            for key, events in event_list:
                conn = key.fileobj
                client_address = conn.getsockname()
                if conn is self.socket:
                    new_conn, new_addr = conn.accept()
                    # new_conn.setblocking(False)
                    self.selector.register(new_conn, selectors.EVENT_READ)
                else:
                    try:
                        self.process_request(conn, client_address)  # 处理请求
                    except Exception as e:
                        print(e)
                        flag = 1
                        break
            if flag:
                continue

    def process_request(self, request, client_address):
        """这个方法就是调用finish_request"""
        self.finish_request(request, client_address)
        # self.shutdown_request(request)

    def finish_request(self, request, client_address):
        """调用真正处理请求的RequestHandlerClass"""
        my_exclusive_handler = SelectorsSocketserver.request_handler_relation.get(
            request.fileno(), 0)
        if my_exclusive_handler:
            my_exclusive_handler()
        else:
            exclusive_handler = self.RequestHandlerClass(
                request, client_address, self)
            SelectorsSocketserver.request_handler_relation[
                request.fileno()] = exclusive_handler

    def shutdown_request(self, request):
        try:
            request.shutdown(socket.SHUT_WR)
        except OSError:
            pass

        self.close_request(request)

    def close_request(self, request):
        request.close()

    def handle_error(self, request):
        """优雅的处理一个错误"""
        print('-' * 40)
        print('处理请求时发生了异常', end=' ')
        import traceback
        traceback.print_exc()
        print('-' * 40)


def main():
    server = SelectorsSocketserver(10001, requesthandler.RequestHandler)
    print("服务启动成功！")
    server.serve_forever()


if __name__ == '__main__':
    main()
