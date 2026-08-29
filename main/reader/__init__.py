# -*- coding: utf-8 -*-
"""reader — 读取端组件：车辆数据读取。

- wrc_shm：WRC Telemetry Patch 共享内存直读（主数据源，可独立运行监听打印）
- gamepad_reader：XInput 手柄输入补读（油门/刹车/转向）
- synth：内置合成数据源（演示/自检用，不经过任何 socket）
"""
