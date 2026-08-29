# WRC 9 遥测仪表盘

[![test](https://github.com/chenye041208/wrc9-simhub/actions/workflows/test.yml/badge.svg)](https://github.com/chenye041208/wrc9-simhub/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/chenye041208/wrc9-simhub)](https://github.com/chenye041208/wrc9-simhub/releases/latest)

WRC 9（PC）本地实时遥测仪表盘，专为 OBS 直播窗口采集设计。

- **直读补丁共享内存**（与 SimHub 同源）：无转发器、无端口、无防火墙配置
- 导播风格界面：全宽 RPM 条、大字档位/车速、俯视图悬挂与轮速（抱死/打滑变色）、
  G-G 图（四档变色小球）、油门/刹车/转向条（XInput 手柄补读）
- 直播友好：一键透明背景（无需色键滤镜）、窗口置顶、隐藏工具栏
- 零第三方依赖：仅 Python 3 标准库 + tkinter
- 内置合成数据源：不开游戏也能演示/自检（`--sim` / `--self-test`）

数据来源为第三方补丁 "WRC Telemetry Patch" 写入的本地共享内存，本项目只读取
公开接口，**不分发补丁本体**。

## 代码结构

源码在 `main/` 下，拆分为两个组件：

| 目录 | 说明 |
|---|---|
| `main/reader/` | **读取端**：共享内存直读 + 手柄补读 + 合成数据源（可独立运行监听打印） |
| `main/dashboard/` | **仪表盘端**：tkinter 桌面窗口（进程内导入 reader 取数）+ 双击启动器 |

## 快速开始

前置条件：先安装免费遥测补丁（WRC 7/8/9/10 通用，见本地 `docs/补丁安装说明.md`）。

**方式 A：下载打包好的 exe**

在 [Releases](../../releases) 页下载 `wrc9-dashboard.exe`，双击即用
（配置文件 `config.json` 会在 exe 同目录自动生成）。

**方式 B：源码运行**

```bat
git clone git@github.com:chenye041208/wrc9-simhub.git
cd wrc9-simhub/main/dashboard
启动仪表盘.bat        rem 或：python main.py
```

## 说明文档

完整说明随仓库在本地 `docs/` 目录维护（不入库）：

| 文档 | 内容 |
|---|---|
| `docs/使用说明.md` | 日常使用、OBS 直播配置、真机连接、校准、命令行、常见问题 |
| `docs/补丁安装说明.md` | 遥测补丁下载安装步骤与排障 |
| `docs/新手指南.html` | 图文新手教程 |
| `docs/README.md` | 开发文档：仓库/发版、代码结构、开发自测、数据来源 |
| `docs/文档编写指南.md` | 本目录文档的分工、写法与维护规则（维护者向） |
