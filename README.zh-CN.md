# WindowResizer

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

WindowResizer 是一款 Windows 桌面应用，用于查找应用窗口、移动或调整其大小，并反复应用已保存的窗口配置文件。

当前版本：0.02.0（用 .NET 10 WPF 重写；此前的 PyQt5 应用为 v0.01.5）

## 主要功能

- 搜索正在运行的窗口，并把配置文件一次应用到所有匹配的窗口（按钮、菜单、Enter 或全局快捷键）。
- 将窗口的位置和大小保存为配置文件（Ctrl+S），可用某个窗口覆盖配置文件的位置（可撤销），并在侧边栏编辑窗口中修改配置文件。
- 按完整可执行文件路径、进程名、窗口标题（包含、完全一致、正则）或它们的组合匹配配置文件，可区分文件名相同的应用。
- 锁定配置文件的位置：被拖走的窗口会回到应用时的位置。
- 配置文件的窗口在最前面时，把鼠标限制在该窗口内（支持退出键）。
- 对应用启动后新出现的窗口自动应用匹配的配置文件。
- 悬浮按钮：每个按钮各自保存窗口的位置和大小，按下后把刚才使用的窗口移到那里。属性窗口带实际大小预览，可从上一个窗口或在屏幕上直接指定的窗口获取位置。
- 每个配置文件的全局快捷键（多个组合、多种动作）、全部应用快捷键和置顶切换。
- 浅色、深色和跟随系统主题（支持 Windows 高对比度），75%–250% 的应用缩放，韩语或英语界面，随 Windows 启动，以及日志页面。
- 关闭主窗口后驻留在系统托盘，同一 Windows 会话只运行一份（第二次启动会把第一个窗口带到前面）。

## 0.02.0 尚未包含

- PyQt5 曾显示三秒的配置文件预览轮廓。
- 应用界面的中文和日文（只有韩语和英语；文档有四种语言）。
- 安装程序和更新机制。发行版是一个自包含的可执行文件。

## 系统要求

- Windows 10 或 Windows 11，64 位。发行版可执行文件自带 .NET 运行时，无需另外安装。

以管理员权限运行的窗口无法被普通权限的 WindowResizer 控制。必要时请以相同权限级别运行 WindowResizer。

## 运行发行版

从 GitHub 发布页下载 `WindowResizer.exe` 并运行。配置文件读写于可执行文件旁的 `profiles` 文件夹，设置保存在
`HKCU\Software\WindowResizer\Next` 下。详情见[安装与运行指南](docs/INSTALLATION.md)。

## 从源码构建

~~~powershell
dotnet build next\WindowResizer.slnx
dotnet test next\WindowResizer.slnx
powershell -NoProfile -File next\tools\publish.ps1
~~~

最后一条命令会把单文件可执行文件生成到 `next\publish\win-x64\`。构建需要 .NET 10 SDK。

## 文档

安装和使用指南为韩语；发布说明和更新日志提供英语、韩语、简体中文和日语版本。

- [安装与运行指南（韩语）](docs/INSTALLATION.md)
- [使用指南（韩语）](docs/USER_GUIDE.md)
- [更新日志：English](docs/CHANGELOG.md) | [한국어](docs/CHANGELOG.ko.md) |
  [中文](docs/CHANGELOG.zh-CN.md) | [日本語](docs/CHANGELOG.ja.md)
- 发布说明：`doc/releases/`

## 仓库结构

- next/：WPF 应用（src/ 为应用，tests/，tools/ 为发布脚本）
- doc/、docs/：发布说明、更新日志和用户文档
- src/、run_gui.py、final_build.py、tests/：此前的 PyQt5 应用（v0.01.5，标签 `last-pyqt5-stable`），仅供参考
