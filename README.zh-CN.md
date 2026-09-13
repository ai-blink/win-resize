# WindowResizer

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

WindowResizer 是一款 Windows 桌面应用程序，可查找应用程序窗口、移动或调整窗口
大小，并重复应用已保存的窗口配置文件。

当前已记录的版本：0.01.4

## 应用预览

![WindowResizer 主窗口](docs/images/windowresizer-main-window.png)

## 功能

- 选择正在运行的窗口，然后移动或调整其大小。
- 将窗口的位置和大小保存为可重复使用的配置文件。
- 通过完整的可执行文件路径匹配配置文件，以区分文件名相同的应用程序。
- 在应用到实际窗口之前预览已保存的布局。
- 检测到匹配的新窗口时，可选择自动应用配置文件。
- 分别启用配置文件的位置锁定和鼠标光标限制。
- 为配置文件操作注册全局快捷键，以便快速执行。
- 可选择浅色、深色或高对比度主题，并可调整应用程序 UI 缩放，而不会改变已保存的
  窗口几何信息。
- 关闭主窗口后，应用程序仍可在系统托盘中使用；完成工作后可通过明确的退出操作
  完全关闭应用程序。
- 防止同一 Windows 会话中出现重复的应用程序实例。

## 系统要求

- Windows 10 或 Windows 11
- 用于开发的 Python 3.12，或已构建的 Windows 可执行文件

以管理员权限运行的目标窗口可能无法由标准权限的 WindowResizer 进程控制。如有
必要，请以相同的权限级别运行 WindowResizer。

## 从源代码运行

在仓库根目录安装依赖项并启动应用程序：

~~~powershell
C:\Python312\python.exe -m pip install -r requirements.txt
C:\Python312\python.exe run_gui.py
~~~

文档中的命令使用已验证的 Python 3.12 路径，以避免意外使用指向其他版本的默认
python 命令。

## 构建可执行文件

~~~powershell
C:\Python312\python.exe final_build.py
~~~

构建成功后会生成 dist/WindowResizer.exe。dist/ 和 build/ 是生成的产物，
不受源代码管理。

## 验证更改

请运行与所改区域对应的回归测试。要运行已跟踪的完整测试套件，请使用：

~~~powershell
C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'
~~~

## 文档

安装和用户指南目前为韩语。补丁说明提供英语、韩语、简体中文和日语版本：

- [安装和运行指南（韩语）](docs/INSTALLATION.md)
- [用户指南（韩语）](docs/USER_GUIDE.md)
- [更新日志：English](docs/CHANGELOG.md) | [한국어](docs/CHANGELOG.ko.md) |
  [中文](docs/CHANGELOG.zh-CN.md) | [日本語](docs/CHANGELOG.ja.md)

## 仓库结构

- src/：应用程序源代码
- run_gui.py：开发启动入口
- final_build.py：PyInstaller 构建脚本
- requirements.txt：Python 依赖项
- tests/：已跟踪的回归测试
- docs/：用户文档和图片
