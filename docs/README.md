# WRC 9 遥测仪表盘

本地运行的 WRC 9（PC）实时遥测仪表盘：**直读补丁原生共享内存**（与 SimHub 同源，
**无需转发器、无需任何端口配置**）→ 独立桌面窗口实时显示转速、车速、档位、
俯视图悬挂/轮速、G-G 图等信息。零第三方依赖（仅 Python 3 标准库 + tkinter），
专为 OBS 直播窗口采集设计。

> 详细使用步骤（补丁下载、OBS 配置、真机校准）见 **[使用说明.md](使用说明.md)**。

## 模块结构

| 目录/文件 | 说明 |
|---|---|
| `patch/` | **模块 1 · 插件补丁包**：`安装说明.txt`（指向补丁官方下载页，不分发本体） |
| `telemetry/` | **模块 3 · 车辆数据读取**：`wrc_shm.py`（共享内存直读，可独立 `python telemetry/wrc_shm.py` 监听打印）、`gamepad_reader.py`（XInput 手柄补读油门/刹车/转向）、`synth.py`（内置合成数据源，演示/自检用，不经 socket） |
| `dashboard/` | **模块 2 · 仪表盘显示**：`main.py`（tkinter 独立窗口，导播风格布局） |
| `tools/` | 开发工具：`snap.py`（窗口截图，依赖 PIL） |
| `docs/` | 文档：README、使用说明、新手指南 |
| `tests/` | 单元测试（20 项） |
| `启动仪表盘.bat` | Windows 双击启动器（无控制台窗口） |
| `config.json` | 运行后生成：校准系数、置顶、绿幕、窗口位置等配置 |

## 快速开始

```bat
rem 1. 装好 WRC Telemetry Patch（见 patch/安装说明.txt）→ 2. 启动 WRC 9 → 3. 双击启动
启动仪表盘.bat

rem 无游戏自测（自动开内置合成数据源，8 秒后自动退出并打印结果）
python dashboard/main.py --self-test 8

rem 跑单元测试
python -m unittest discover -s tests -v
```

## 数据来源说明

WRC 9 无官方遥测接口。第三方补丁 "WRC Telemetry Patch"（RaceDepartment 免费下载，
需注册）通过 DLL 注入把游戏数据写入本地共享内存。本工具**直读该共享内存**
（96 字节原生结构体：档位/速度/加速度/转速/悬挂行程），装好补丁后开游戏、
开仪表盘即可，**不需要转发器，也没有端口/防火墙问题**。本项目只读取公开接口，
**不分发补丁本体**。

遥测协议本身不提供的字段：圈速、里程、燃油、离合。
油门/刹车/转向由手柄输入补读（XInput），车轮块以颜色标出抱死/打滑。
