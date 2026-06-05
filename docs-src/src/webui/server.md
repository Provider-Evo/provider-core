# src/webui/server.py

该模块提供独立 WebUI 服务器与线程化服务器封装，用于将 WebUI 作为独立服务运行时复用。

当前主项目以内嵌路由方式在根路径 `/` 提供 WebUI 页面。
