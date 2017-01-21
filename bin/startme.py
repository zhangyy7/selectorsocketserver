#! /usr/bin/env python
# -*-coding: utf-8 -*-

from core.ftpclient import ftpclient
from core.ftpserver import selector_socket_server


def run():
    while True:
        choice = input("1.启动服务  2.运行客户端").strip()
        if choice == "1":
            selector_socket_server.main()
        elif choice == "2":
            ftpclient.main()
        else:
            continue
