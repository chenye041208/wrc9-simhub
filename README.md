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

## 安装方式

### 1. 安装遥测补丁（前置条件）

WRC 9 无官方遥测接口，需先安装免费补丁（详见 [patch/安装说明.txt](patch/安装说明.txt)）：

1. 注册登录 RaceDepartment，下载
   [WRC Telemetry Patch](https://www.racedepartment.com/downloads/wrc-telemetry-patch.38991/)（WRC 7/8/9/10 通用）
2. 解压到游戏目录，运行一次 `InstallWrc10.bat`

### 2. 安装仪表盘（二选一）

**方式 A：下载打包好的 exe**

在 [Releases](../../releases) 页下载 `wrc9-dashboard.exe`，双击即用
（配置文件 `config.json` 会在 exe 同目录自动生成）。

**方式 B：源码运行**

```bat
git clone git@github.com:chenye041208/wrc9-simhub.git
cd wrc9-simhub
启动仪表盘.bat        rem 或：python dashboard/main.py
```

## 使用说明

### 日常使用

1. 启动 WRC 9
2. 打开仪表盘（exe 或 `启动仪表盘.bat`）
3. 左上角显示绿色「接收中 xx pkt/s ｜ 模式：共享内存直读」即成功

无游戏时想看效果：按 `S` 开启内置模拟器（合成数据，不经网络）。

### 快捷键

| 按键 | 功能 |
|---|---|
| `S` | 启动/停止模拟器 |
| `T` | 窗口置顶 |
| `G` | 透明模式（OBS 直播用） |
| `H` | 隐藏/显示工具栏 |
| `Q` | 退出 |

### OBS 直播配置

1. OBS → 来源 → 添加「窗口采集」→ 窗口选 `WRC 9 遥测仪表盘`，
   采集方式选「Windows 10 (1903 及以上)」
2. 仪表盘按 `G` 进入透明模式：背景直接消失，**无需色键滤镜**
3. 按 `T` 置顶、`H` 隐藏工具栏，画面只剩仪表

### 配置项（config.json）

| 配置 | 说明 | 默认 |
|---|---|---|
| `rpm_scale` | 转速校准（补丁转速为真值 1/10） | `10.0` |
| `g_scale` | G 值校准（m/s²→G） | `9.81` |
| `g_lon_flip` | 纵向 G 翻转（刹车朝上惯例） | `true` |
| `gamepad` | 手柄补读油门/刹车/转向 | `true` |
| `transparent` | 透明模式用真透明（false 则退回绿幕+色键） | `true` |
| `gg_thresholds` | G-G 小球变色阈值 `[红, 橙, 黄]`（0~1 严格递减，非法自动回退） | `[0.9, 0.7, 0.5]` |

### 命令行

```bat
python dashboard/main.py --sim            rem 启动并开启模拟器
python dashboard/main.py --self-test 8    rem 自检：8 秒后打印结果并退出
python dashboard/main.py --topmost --green
python telemetry/wrc_shm.py               rem 无界面直读共享内存，排查补丁
python -m unittest discover -s tests -v   rem 跑单元测试
```

### 常见问题

- **一直「等待数据…」**：补丁没装好或游戏没启动——重新运行游戏目录的
  `InstallWrc10.bat`；游戏每次 Steam/Epic 更新都会覆盖补丁，需重装
- **转速明显不对**：检查 `config.json` 的 `rpm_scale` 是否为 10
- **油门/刹车/转向不动**：由手柄补读（RT/LT/左摇杆），没接手柄则不显示
- **和 SimHub 冲突吗**：不冲突，两者只是读同一块共享内存，互不干扰

更多图文说明见 [docs/使用说明.md](docs/使用说明.md) 与
[docs/新手指南.html](docs/新手指南.html)。
