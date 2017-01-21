# FTPServer
### 作者介绍：
* author：zhangyy
* nickname:逆光穿行
* github:[zhangyy.com](https://github.com/zhangyy7)

### 功能介绍：
- 用户注册
- 用户登录
- 上传文件到服务器
- 从服务器下载文件到本地
- 断点续传（仅下载文件时）
- 文件传输进度条
- 查看目录下的文件及子目录
- 在用户家目录范围内切换目录
- 在家目录范围内创建子目录

### 环境依赖：
* Python3.5.2

### 目录结构：

    FTPServer
    ├── index.py #程序唯一入口脚本
    ├── README.md
    ├── settings.py #配置文件
    ├── bin
    │   ├── __init__.py
    │   └── startme.py #主函数
    ├── core #程序核心目录
    │   ├── ftpclient
    |   |    └── ftpclient.py #客户端
    │   └── ftpserver
    |        └── ftpserver.py #服务端
    |── couf
    |    └── settings.py #服务端
    ├── data #用户账户数据文件目录
    │   
    └── logs #程序日志目录
        └── ftpserver.log #程序日志



###运行说明：
* 运行index.py文件，先启动服务，然后在另一台机器或者一个新的终端下运行客户端
* 默认没有账户，首次运行需要注册账户
