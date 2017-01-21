#! /usr/bin/env python
# -*-coding: utf-8 -*-
import os


HOME_PATH = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'home')

if not os.path.exists(HOME_PATH):
    os.makedirs(HOME_PATH)

DATA_PATH = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'data')

if not os.path.exists(DATA_PATH):
    os.makedirs(DATA_PATH)

USER_DISK_MAXSIZE = 1073741824  # 每个用户允许的最大磁盘空间为1G

ERROR_CODE = {
    "0000": "成功",
    "1000": "指令错误",
    "2000": "MD5校验失败",
    "3000": "文件路径错误",
    "4000": "权限错误",
    "4444": "可用空间不足",
    "5000": "用户名已存在",
    "6000": "请求异常",
    "7000": "用户名不存在",
    "8000": "用户名或密码不正确",
    "9000": "报文体错误",
    "9999": "文件传输中断",
    "2999": "内部错误"
}


# 定义三种日志输出格式 开始

standard_format = '[%(asctime)s][%(threadName)s:%(thread)d]\
                   [task_id:%(name)s][%(filename)s:%(lineno)d]\
                   [%(levelname)s][%(message)s]'.replace(' ', '')

simple_format = '[%(levelname)s]\
                 [%(asctime)s]\
                 [%(filename)s:%(lineno)d]\
                 %(message)s'.replace(' ', '')

id_simple_format = '[%(levelname)s][%(asctime)s] %(message)s'.replace(' ', '')

# 定义日志输出格式 结束

logfile_dir = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'log')  # log文件的目录

logfile_name = 'ftpserver.log'  # log文件名

# 如果不存在定义的日志目录就创建一个
if not os.path.isdir(logfile_dir):
    os.mkdir(logfile_dir)

# log文件的全路径
logfile_path = os.path.join(logfile_dir, logfile_name)

# log配置字典
LOGGING_DIC = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': standard_format
        },
        'simple': {
            'format': simple_format
        },
    },
    'filters': {},
    'handlers': {
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',  # 打印到屏幕
            'formatter': 'simple'
        },
        'default': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',  # 保存到文件
            'filename': logfile_path,  # 日志文件
            'maxBytes': 1024 * 1024 * 5,  # 日志大小 5M
            'backupCount': 5,
            'formatter': 'standard',
            'encoding': 'utf-8',  # 日志文件的编码，再也不用担心中文log乱码了
        },
    },
    'loggers': {
        '': {
            # 这里把上面定义的两个handler都加上，即log数据既写入文件又打印到屏幕
            'handlers': ['default', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
