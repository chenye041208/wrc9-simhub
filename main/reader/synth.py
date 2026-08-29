# -*- coding: utf-8 -*-
"""reader/synth.py — 内置合成数据源（"脑补模式"）。

不经过任何 socket：直接用数学曲线生成与 wrc_shm.to_dashboard_dict
相同形状的数据字典，供仪表盘 S 键演示与 --self-test 自检使用。
"""

import math
import threading
import time


def synth_frame(t):
    """t 秒时刻的合成遥测字典（纯函数，可测试）。

    16 秒一个循环：前 12 秒 1→5 挡全油门加速，后 4 秒重刹 + 过弯。
    """
    rpm_max, rpm_idle = 8000.0, 900.0
    cycle = t % 16.0
    if cycle < 12.0:                        # 加速段：每 2.4s 升一挡
        seg = cycle / 2.4
        gear = min(5, int(seg) + 1)
        frac = seg - int(seg)
        throttle, brake = 1.0, 0.0
        speed = 30.0 + (gear - 1) * 26.0 + frac * 26.0
        g_lon = -0.45 - 0.15 * math.sin(t * 2.0)   # 刹车朝上惯例：负=加速
        rpm_pct = 0.45 + 0.53 * frac
    else:                                   # 制动 + 过弯段：4s
        seg = (cycle - 12.0) / 4.0
        gear = max(2, 5 - int(seg * 3))
        throttle = 0.0
        brake = max(0.0, 1.0 - seg * 1.6)   # 前段重刹渐松
        speed = 186.0 - seg * 96.0
        g_lon = 1.1 * (1.0 - seg)           # 刹车 G 渐弱
        rpm_pct = 0.35 + 0.10 * (1.0 - seg)
    rpm_pct = max(0.0, min(1.0, rpm_pct))
    rpm = rpm_idle + (rpm_max - rpm_idle) * rpm_pct

    steer = 0.55 * math.sin(t * 0.7)
    g_lat = 0.9 * math.sin(t * 0.7) + 0.15 * math.sin(t * 3.1)
    speed_ms = speed / 3.6
    wheel = speed_ms / 0.33                 # 轮半径≈0.33m → rad/s
    susp = [max(0.0, min(1.0, 0.5 + 0.18 * math.sin(t * f + p)))
            for f, p in ((2.3, 0.0), (2.7, 1.3), (3.1, 2.1), (2.5, 3.7))]

    return {
        "ok": True,
        "source": "synth",
        "ts": time.time(),
        "speed_ms": speed_ms,
        "speed_kmh": speed,
        "rpm": rpm,
        "rpm_max": rpm_max,
        "rpm_idle": rpm_idle,
        "rpm_pct": rpm / rpm_max,
        "gear": gear,
        "gear_label": str(gear),
        "throttle": throttle,
        "brake": brake,
        "clutch": 0.0,
        "steer": steer,
        "g_lat": g_lat,
        "g_lon": g_lon,
        "susp": susp,
        "susp_vel": [None, None, None, None],
        "wheel_speed": [wheel, wheel, wheel * 0.98, wheel * 1.02],
        "lap": None,
        "lap_time": None,
        "last_lap_time": None,
        "run_time": None,
        "distance": None,
        "progress": None,
        "race_pos": None,
        "attitude_valid": True,
        "attitude": None,
        "quality": {"packet_size_ok": True, "bad_fields": []},
    }


class SynthThread(threading.Thread):
    """按固定频率生成合成帧并注入 listener（listener 需有 inject(d) 方法）。"""

    def __init__(self, listener, hz=60.0):
        super().__init__(daemon=True, name="synth")
        self._listener = listener
        self._interval = 1.0 / hz
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        t0 = time.monotonic()
        while not self._stop.is_set():
            self._listener.inject(synth_frame(time.monotonic() - t0))
            time.sleep(self._interval)
