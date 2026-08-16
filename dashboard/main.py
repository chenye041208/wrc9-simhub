# -*- coding: utf-8 -*-
"""
dashboard/main.py — WRC 9 遥测仪表盘（独立桌面窗口版）

一个零依赖（仅 Python 标准库 + tkinter）的本地桌面窗口：
  * 直读补丁共享内存（telemetry.wrc_shm），无转发器、无端口配置；
  * 导播风格布局：顶部全宽 RPM 条、大字档位/车速、俯视图车辆（悬挂/轮速）、
    G-G 图、底部全宽转向条；
  * 内置合成数据源（telemetry.synth）：S 键演示与 --self-test 自检，
    不经过任何 socket；
  * 直播友好：窗口置顶、绿幕背景（OBS 色键，自动切换高对比配色）、
    一键隐藏工具栏、键盘快捷键。

快捷键：S=模拟器  T=置顶  G=绿幕  H=隐藏/显示工具栏  Q=退出

命令行：
    python dashboard/main.py [--sim] [--topmost] [--green]
    python dashboard/main.py --self-test 8     # 自检：自动开合成源，8 秒后自动退出
"""

import argparse
import json
import math
import os
import sys
import threading
import time
from collections import deque

import tkinter as tk

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：config.json 放在 exe 同目录
    PROJECT_ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    # 源码运行：项目根目录 = 本文件（dashboard/main.py）的上一级
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

from telemetry import gamepad_reader, synth, wrc_shm

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

# ---------------- 主题配色 ----------------
BG = "#0d1117"
PANEL = "#161b22"
CHROMA_GREEN = "#00ff00"   # OBS 色键绿

FONT = "Microsoft YaHei UI"
MONO = "Consolas"

# 正常主题：暗色底 + 柔和高亮
THEME_NORMAL = {
    "fg": "#e6edf3",          # 主读数
    "dim": "#8b949e",         # 次要文字/标签
    "rim": "#30363d",         # 表盘外圈
    "barborder": "#30363d",   # 条形边框
    "outline": False,         # 是否给文字/线条加黑色描边（透明模式用）
    "zone_lo": "#1f6f3f",     # 转速低区
    "zone_mid": "#7a5b17",    # 转速中区
    "zone_hi": "#7a2a26",     # 红区（未触发）
    "throttle": "#3fb950",
    "brake": "#f85149",
    "clutch": "#58a6ff",
    "steer": "#d29922",
    "grid": "#21262d",        # G-G 圆环
    "gridline": "#30363d",    # 十字线/边框
    "needle": "#f85149",
    "tick_major": "#e6edf3",
    "tick_minor": "#8b949e",
    "susp_ok": "#3fb950",
    "susp_hot": "#d29922",
    "shift_off": "#3a1215",
    "bold_small": False,      # 小字是否加粗（绿幕下抗抠图）
    # --- 导播布局新增 ---
    "car_body": "#1c232d",    # 俯视车身填充
    "car_edge": "#8b949e",    # 车身/车轮描边
    "wheel_ok": "#3fb950",    # 轮速正常
    "wheel_lock": "#f0883e",  # 抱死（橙）
    "wheel_slip": "#f85149",  # 打滑（红）
    "shift_flash": "#ff2020", # 换挡闪烁
    "gg_lo": "#3fb950",       # G-G 小球 最低档（绿）
    "gg_mid": "#ffd500",      # G-G 小球 中低档（黄）
    "gg_hi": "#f0883e",       # G-G 小球 中高档（橙）
    "gg_max": "#ff2020",      # G-G 小球 最高档（红）
}

# 绿幕主题：纯色高饱和，规避绿色系，粗线条，白字加粗 + 黑色描边
THEME_CHROMA = {
    "fg": "#ffffff",
    "dim": "#ffffff",
    "rim": "#ffffff",
    "barborder": "#000000",
    "outline": True,
    "zone_lo": "#0070f3",     # 蓝色代替绿色，防止被色键抠掉
    "zone_mid": "#ffb000",
    "zone_hi": "#8a1f1f",
    "throttle": "#00a2ff",    # 蓝色代替绿色
    "brake": "#ff3b30",
    "clutch": "#c58cff",
    "steer": "#ffd500",
    "grid": "#ffffff",
    "gridline": "#ffffff",
    "needle": "#ff3b30",
    "tick_major": "#ffffff",
    "tick_minor": "#ffffff",
    "susp_ok": "#00a2ff",
    "susp_hot": "#ffd500",
    "shift_off": "#5a1a1a",
    "bold_small": True,
    # --- 导播布局新增（禁绿色系，防止被色键抠掉） ---
    "car_body": "#111111",
    "car_edge": "#ffffff",
    "wheel_ok": "#00a2ff",    # 蓝色代替绿色
    "wheel_lock": "#ff9500",
    "wheel_slip": "#ff3b30",
    "shift_flash": "#ff2020",
    "gg_lo": "#00a2ff",       # 蓝色代替绿色
    "gg_mid": "#ffd500",
    "gg_hi": "#ff9500",
    "gg_max": "#ff3b30",
}

DEFAULT_GG_THRESHOLDS = (0.9, 0.7, 0.5)   # G-G 小球变色阈值（占半径比例）：红/橙/黄

DEFAULT_CONFIG = {
    # 以下为 WRC 9 补丁真机校准值（rpm 原生为 1/10；G 原生为 m/s² 且加速为正）
    "rpm_scale": 10.0,
    "g_scale": 9.81,
    "g_lon_flip": True,    # 刹车朝上惯例
    "gamepad": True,       # 手柄输入补读（油门=RT 刹车=LT 转向=左摇杆）
    "always_on_top": False,
    "green_screen": False,
    "transparent": True,   # 绿幕模式下用 -transparentcolor 实现真透明（无需 OBS 色键）
    "gg_thresholds": list(DEFAULT_GG_THRESHOLDS),  # G-G 小球变色阈值，见 validate_gg_thresholds
    "geometry": None,
}


def validate_gg_thresholds(value):
    """校验 G-G 小球颜色阈值：必须是 3 个 (0,1] 内严格递减的数。

    任何不合法输入（缺项/非数字/超范围/未递减）都回退默认值。
    """
    try:
        vals = [float(v) for v in value]
    except (TypeError, ValueError):
        return list(DEFAULT_GG_THRESHOLDS)
    if len(vals) != len(DEFAULT_GG_THRESHOLDS):
        return list(DEFAULT_GG_THRESHOLDS)
    if not all(0.0 < v <= 1.0 for v in vals):
        return list(DEFAULT_GG_THRESHOLDS)
    if not all(a > b for a, b in zip(vals, vals[1:])):
        return list(DEFAULT_GG_THRESHOLDS)
    return vals


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        merged = dict(DEFAULT_CONFIG)
        merged.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
        merged["gg_thresholds"] = validate_gg_thresholds(
            merged.get("gg_thresholds"))
        return merged
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def fmt_time(seconds):
    """秒 → mm:ss.t"""
    if seconds is None or seconds <= 0:
        return "--:--.-"
    m = int(seconds // 60)
    s = seconds - m * 60
    return "%02d:%04.1f" % (m, s)


# ---------------- 共享内存监听线程 ----------------
class TelemetryListener(threading.Thread):
    """后台直读补丁共享内存：解析最新帧、统计速率。

    演示/自检时由 synth.SynthThread 通过 inject() 直接注入合成数据，
    全程不经过任何 socket。
    """

    def __init__(self, rpm_scale=1.0, g_scale=1.0, g_lon_flip=False):
        super().__init__(daemon=True, name="shm-listener")
        self._lock = threading.Lock()
        self.rpm_scale = rpm_scale
        self.g_scale = g_scale
        self.g_lon_flip = g_lon_flip
        self._shm = wrc_shm.ShmReader()
        self._stop = threading.Event()
        self.latest = None          # 最近一次解析结果（dict）
        self.seq = 0                # 递增序号，供 UI 判断是否有新数据
        self.last_packet_ts = 0.0
        self._rate_times = deque()  # 最近 2 秒数据时间，用于算 pkt/s
        self.error = None

    # -- 外部控制 --
    def stop(self):
        self._stop.set()

    def inject(self, d):
        """合成数据源直接注入一帧（线程安全）。"""
        now = time.monotonic()
        with self._lock:
            self._rate_times.append(now)
            self.latest = d
            self.seq += 1
            self.last_packet_ts = now

    def snapshot(self):
        """返回 (latest, seq, rate, last_ts, error) 的一致性快照。"""
        with self._lock:
            now = time.monotonic()
            while self._rate_times and now - self._rate_times[0] > 2.0:
                self._rate_times.popleft()
            rate = len(self._rate_times) / 2.0
            return (self.latest, self.seq, rate, self.last_packet_ts,
                    self.error)

    # -- 线程主循环 --
    def run(self):
        try:
            while not self._stop.is_set():
                frame = self._shm.poll()
                if frame is None:
                    time.sleep(0.01)
                    continue
                d = wrc_shm.to_dashboard_dict(
                    frame, rpm_scale=self.rpm_scale,
                    g_scale=self.g_scale, g_lon_flip=self.g_lon_flip)
                if d is not None:
                    self.inject(d)
        finally:
            self._shm.close()


# ---------------- 主窗口 ----------------
class DashboardApp:
    def __init__(self, root, args):
        self.root = root
        self.cfg = load_config()
        if args.rpm_scale:
            self.cfg["rpm_scale"] = args.rpm_scale
        if args.topmost:
            self.cfg["always_on_top"] = True
        if args.green:
            self.cfg["green_screen"] = True

        self.col = dict(THEME_NORMAL)
        self.listener = TelemetryListener(
            rpm_scale=self.cfg["rpm_scale"],
            g_scale=self.cfg.get("g_scale", 1.0),
            g_lon_flip=self.cfg.get("g_lon_flip", False))
        self.listener.start()
        self.sim_thread = None
        self.last_seen_seq = -1
        self.last_draw = 0.0
        self.gamepad = (gamepad_reader.GamepadReader()
                        if self.cfg.get("gamepad", True) else None)
        self.toolbar_visible = True
        self._self_test = args.self_test
        self._after_jobs = []

        self._build_ui()
        self._apply_theme()
        self._apply_flags()
        self._bind_keys()

        if args.sim or args.self_test:
            self.toggle_sim(force_on=True)
        if args.self_test:
            self._later(int(args.self_test * 1000), self._self_test_done)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._tick()
        self._status_tick()

    # ---------- 主题 ----------
    def _bg(self):
        return CHROMA_GREEN if self.cfg.get("green_screen") else BG

    def _apply_theme(self):
        green = self.cfg.get("green_screen")
        self.col = dict(THEME_CHROMA if green else THEME_NORMAL)
        bg = self._bg()
        self.root.configure(bg=bg)
        self.main.configure(bg=bg)
        self.warn_label.configure(bg=bg)
        for cv in (self.rpm_bar, self.left, self.mid, self.right, self.steer_bar):
            cv.configure(bg=bg)
        # 真透明模式：把绿幕色声明为透明色，窗口背景直接消失（无需 OBS 色键）。
        # 注意：透明区域会“点击穿透”，拖窗口请用标题栏。
        try:
            transparent = CHROMA_GREEN if (green and self.cfg.get("transparent", True)) else ""
            self.root.attributes("-transparentcolor", transparent)
        except tk.TclError:
            pass
        self.last_seen_seq = -1  # 强制重绘

    def _font(self, size, bold=False, mono=False):
        weight = "bold" if (bold or self.col.get("bold_small")) else "normal"
        return (MONO if mono else FONT, int(size), weight)

    # ---------- 描边绘制助手（透明模式下让元素在任何背景上都清晰） ----------
    def _text(self, cv, x, y, **kw):
        """create_text 的封装：outline 主题下先画 4 向黑色描边再画正文。"""
        if self.col.get("outline"):
            shadow = dict(kw)
            shadow["fill"] = "#000000"
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.create_text(x + dx, y + dy, **shadow)
        cv.create_text(x, y, **kw)

    def _line(self, cv, coords, fill, width, **kw):
        """create_line 的封装：outline 主题下加黑色衬底。"""
        if self.col.get("outline"):
            cv.create_line(*coords, fill="#000000", width=width + 3, **kw)
        cv.create_line(*coords, fill=fill, width=width, **kw)

    def _ring(self, cv, bbox, color, width):
        """create_oval（仅边框）的封装：outline 主题下加黑色衬底。"""
        if self.col.get("outline"):
            cv.create_oval(*bbox, outline="#000000", width=width + 3)
        cv.create_oval(*bbox, outline=color, width=width)

    # ---------- UI 构建 ----------
    def _build_ui(self):
        self.root.title("WRC 9 遥测仪表盘")
        bg = self._bg()
        self.root.configure(bg=bg)
        if self.cfg.get("geometry"):
            try:
                self.root.geometry(self.cfg["geometry"])
            except tk.TclError:
                pass
        else:
            self.root.geometry("1040x560")
        self.root.minsize(820, 480)

        # 顶部工具栏
        self.toolbar = tk.Frame(self.root, bg=PANEL, height=40)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        self.toolbar.pack_propagate(False)

        self.dot_label = tk.Label(self.toolbar, text="●", fg="#8b949e", bg=PANEL,
                                  font=(FONT, 13))
        self.dot_label.pack(side=tk.LEFT, padx=(10, 2))
        self.status_label = tk.Label(self.toolbar, text="等待数据…",
                                     fg="#e6edf3", bg=PANEL, font=(FONT, 10),
                                     anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=(2, 10))

        self._mk_button("隐藏工具栏 (H)", self.toggle_toolbar).pack(side=tk.RIGHT, padx=3, pady=6)
        self._mk_button("绿幕 (G)", self.toggle_green).pack(side=tk.RIGHT, padx=3, pady=6)
        self._mk_button("置顶 (T)", self.toggle_topmost).pack(side=tk.RIGHT, padx=3, pady=6)
        self.btn_sim = self._mk_button("▶ 启动模拟器 (S)", self.toggle_sim)
        self.btn_sim.pack(side=tk.RIGHT, padx=3, pady=6)

        # 警示条（默认隐藏）
        self.warn_label = tk.Label(self.root, text="", fg="#d29922", bg=bg,
                                   font=(FONT, 9), anchor="w")

        # 主显示区（导播风格）：顶部全宽 RPM 条 / 三栏 / 底部全宽转向条
        self.main = tk.Frame(self.root, bg=bg)
        self.main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.rpm_bar = tk.Canvas(self.main, bg=bg, height=52,
                                 highlightthickness=0)
        self.rpm_bar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 0))

        self.steer_bar = tk.Canvas(self.main, bg=bg, height=46,
                                   highlightthickness=0)
        self.steer_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 6))

        self.cols = tk.Frame(self.main, bg=bg)
        self.cols.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.cols.grid_rowconfigure(0, weight=1)
        for gc in (0, 2, 4):
            self.cols.grid_columnconfigure(gc, weight=1, uniform="col3")

        self.left = tk.Canvas(self.cols, bg=bg, highlightthickness=0)
        self.left.grid(row=0, column=0, sticky="nsew", padx=4, pady=6)

        self.brake_bar = tk.Canvas(self.cols, bg=bg, width=30,
                                   highlightthickness=0)
        self.brake_bar.grid(row=0, column=1, sticky="ns", pady=6)

        self.mid = tk.Canvas(self.cols, bg=bg, highlightthickness=0)
        self.mid.grid(row=0, column=2, sticky="nsew", padx=4, pady=6)

        self.throttle_bar = tk.Canvas(self.cols, bg=bg, width=30,
                                      highlightthickness=0)
        self.throttle_bar.grid(row=0, column=3, sticky="ns", pady=6)

        self.right = tk.Canvas(self.cols, bg=bg, highlightthickness=0)
        self.right.grid(row=0, column=4, sticky="nsew", padx=4, pady=6)

    def _mk_button(self, text, cmd):
        return tk.Button(self.toolbar, text=text, command=cmd,
                         bg="#21262d", fg="#e6edf3", activebackground="#30363d",
                         activeforeground="#e6edf3", relief=tk.FLAT, bd=0,
                         font=(FONT, 9), padx=8, pady=2, cursor="hand2")

    def _apply_flags(self):
        self.root.attributes("-topmost", bool(self.cfg.get("always_on_top")))

    def _bind_keys(self):
        for key, fn in (("s", self.toggle_sim),
                        ("t", self.toggle_topmost), ("g", self.toggle_green),
                        ("h", self.toggle_toolbar), ("q", self.on_close)):
            self.root.bind("<Key-%s>" % key, lambda e, f=fn: f())
            self.root.bind("<Key-%s>" % key.upper(), lambda e, f=fn: f())

    # ---------- 按钮动作 ----------
    def toggle_sim(self, force_on=False):
        if self.sim_thread is not None and (self.sim_thread.is_alive() or not force_on):
            if self.sim_thread.is_alive():
                self.sim_thread.stop()
                self.sim_thread = None
                self.btn_sim.config(text="▶ 启动模拟器 (S)")
                return
        # 内置合成数据源：直接 inject 进 listener，不经过任何 socket
        self.sim_thread = synth.SynthThread(self.listener, hz=60.0)
        self.sim_thread.start()
        self.btn_sim.config(text="■ 停止模拟器 (S)")

    def toggle_topmost(self):
        self.cfg["always_on_top"] = not self.cfg.get("always_on_top")
        self._apply_flags()
        save_config(self.cfg)

    def toggle_green(self):
        self.cfg["green_screen"] = not self.cfg.get("green_screen")
        save_config(self.cfg)
        self._apply_theme()

    def toggle_toolbar(self):
        if self.toolbar_visible:
            self.toolbar.pack_forget()
        else:
            self.toolbar.pack(side=tk.TOP, fill=tk.X, before=self.main)
        self.toolbar_visible = not self.toolbar_visible

    # ---------- 定时任务管理 ----------
    def _later(self, ms, fn):
        """root.after 的封装：登记任务 id，便于关闭时统一取消。"""
        job = self.root.after(ms, fn)
        self._after_jobs.append(job)
        # 列表定期清理已执行的任务，避免无限增长
        if len(self._after_jobs) > 64:
            self._after_jobs = self._after_jobs[-32:]
        return job

    # ---------- 主循环 ----------
    def _tick(self):
        latest, seq, rate, last_ts, error = self.listener.snapshot()
        stale = (time.monotonic() - last_ts) > 1.5 if last_ts else True
        if seq != self.last_seen_seq or stale or time.monotonic() - self.last_draw > 0.5:
            self.last_seen_seq = seq
            self.last_draw = time.monotonic()
            data = latest if (latest and not stale) else None
            if data is not None:
                # 遥测协议没有踏板/转向：手柄输入补读（模拟器演示时除外）
                sim_on = self.sim_thread is not None and self.sim_thread.is_alive()
                if self.gamepad is not None and not sim_on:
                    gp = self.gamepad.poll()
                    if gp:
                        data = dict(data)
                        data["throttle"] = gp["throttle"]
                        data["brake"] = gp["brake"]
                        data["steer"] = gp["steer"]
                        data["clutch"] = gp["clutch"]
            self._draw_rpm_bar(data)
            self._draw_left(data)
            self._draw_brake_bar(data)
            self._draw_mid(data)
            self._draw_throttle_bar(data)
            self._draw_right(data)
            self._draw_steer(data)
        self._later(33, self._tick)

    def _status_tick(self):
        latest, seq, rate, last_ts, error = self.listener.snapshot()
        parts = []
        if error:
            self.dot_label.config(fg="#f85149")
            parts.append(error)
        elif last_ts and (time.monotonic() - last_ts) <= 1.5:
            self.dot_label.config(fg="#3fb950")
            parts.append("接收中 %.0f pkt/s" % rate)
        else:
            self.dot_label.config(fg="#8b949e")
            parts.append("等待数据…")
        parts.append("模式：共享内存直读")
        if self.sim_thread is not None and self.sim_thread.is_alive():
            parts.append("来源：模拟器")
        self.status_label.config(text="  |  ".join(parts))
        self.root.title("WRC 9 遥测仪表盘")

        # 警示条
        warns = []
        if latest and latest.get("ok"):
            if not latest.get("attitude_valid"):
                warns.append("roll/pitch 姿态字段异常（补丁已知问题，已自动忽略）")
            if not latest["quality"]["packet_size_ok"]:
                warns.append("非标准包长 %d 字节（期望 264）" % latest["packet_size"])
        if warns:
            self.warn_label.config(text="⚠ " + "；".join(warns))
            if not self.warn_label.winfo_ismapped():
                self.warn_label.pack(side=tk.TOP, fill=tk.X, before=self.main)
        elif self.warn_label.winfo_ismapped():
            self.warn_label.pack_forget()
        self._later(500, self._status_tick)

    # ---------- 顶部：全宽 RPM 条 ----------
    def _draw_rpm_bar(self, d):
        cv = self.rpm_bar
        cv.delete("all")
        col = self.col
        w = max(cv.winfo_width(), 300)
        h = max(cv.winfo_height(), 30)
        x0, x1 = 10.0, w - 10.0
        y0, y1 = 6.0, h - 6.0
        span = x1 - x0

        rpm = d.get("rpm") if d else None
        rpm_max = (d.get("rpm_max") if d else None) or 8000.0
        pct = (rpm / rpm_max) if rpm is not None else 0.0
        pct_c = max(0.0, min(1.0, pct))

        # 三段分区底色（低区 / 中区 / 红区）
        cv.create_rectangle(x0, y0, x0 + span * 0.60, y1,
                            fill=col["zone_lo"], outline="")
        cv.create_rectangle(x0 + span * 0.60, y0, x0 + span * 0.85, y1,
                            fill=col["zone_mid"], outline="")
        cv.create_rectangle(x0 + span * 0.85, y0, x1, y1,
                            fill=col["zone_hi"], outline="")

        # 当前转速高亮填充（颜色随所在分区变化）
        if pct_c > 0.003:
            if pct_c < 0.60:
                fill_col = col["throttle"]
            elif pct_c < 0.85:
                fill_col = col["steer"]
            else:
                fill_col = col["brake"]
            cv.create_rectangle(x0, y0, x0 + span * pct_c, y1,
                                fill=fill_col, outline="")
            # 当前位置标记线（进度一目了然）
            mx = x0 + span * pct_c
            self._line(cv, (mx, y0 - 3, mx, y1 + 3), col["fg"], 3)

        # 换挡闪烁：rpm_pct>0.95 时整条红闪
        shift_on = rpm is not None and pct > 0.95
        if shift_on and (time.monotonic() * 3) % 2 < 1:
            cv.create_rectangle(x0, y0, x1, y1,
                                outline=col["shift_flash"], width=5)
            self._text(cv, (x0 + x1) / 2, (y0 + y1) / 2, text="SHIFT",
                       fill=col["shift_flash"],
                       font=self._font(h * 0.5, bold=True, mono=True))

        # 外框 + 分区刻度线
        cv.create_rectangle(x0, y0, x1, y1, outline=col["barborder"], width=2)
        for q in (0.60, 0.85):
            qx = x0 + span * q
            self._line(cv, (qx, y0, qx, y1), col["barborder"], 2)

        # 条内嵌入：左侧大号档位，右侧 RPM 数字
        gear = (d.get("gear_label") if d else None) or "--"
        fs = max(18, int(h * 0.58))
        self._text(cv, x0 + 12, (y0 + y1) / 2, text=gear, anchor="w",
                   fill=col["fg"], font=self._font(fs, bold=True, mono=True))
        rpm_txt = ("%d RPM · %d%%" % (round(rpm), round(pct_c * 100))
                   ) if rpm is not None else "-- RPM"
        self._text(cv, x1 - 12, (y0 + y1) / 2, text=rpm_txt, anchor="e",
                   fill=col["fg"], font=self._font(fs * 0.72, bold=True, mono=True))

    # ---------- 左栏：大字读数 ----------
    def _draw_left(self, d):
        cv = self.left
        cv.delete("all")
        col = self.col
        w = max(cv.winfo_width(), 160)
        h = max(cv.winfo_height(), 200)
        cx = w / 2.0

        # 超大档位
        gear = (d.get("gear_label") if d else None) or "--"
        gear_fs = max(56, min(120, int(h * 0.30)))
        self._text(cv, cx, h * 0.06, text="档位", fill=col["dim"],
                   font=self._font(max(10, h * 0.035)))
        self._text(cv, cx, h * 0.30, text=gear, fill=col["fg"],
                   font=self._font(gear_fs, bold=True, mono=True))

        # 大字号车速（右侧小字 km/h）
        speed = d.get("speed_kmh") if d else None
        spd_txt = "%.0f" % speed if speed is not None else "---"
        spd_fs = max(30, min(64, int(h * 0.16)))
        self._text(cv, cx - 6, h * 0.62, text=spd_txt, anchor="e",
                   fill=col["fg"], font=self._font(spd_fs, bold=True, mono=True))
        self._text(cv, cx + 2, h * 0.62 + spd_fs * 0.22, text="km/h",
                   anchor="w", fill=col["dim"],
                   font=self._font(max(11, h * 0.04)))

        # 小字 RPM / 红线
        rpm = d.get("rpm") if d else None
        rpm_max = d.get("rpm_max") if d else None
        if rpm is not None:
            rpm_txt = "%d / %d rpm" % (round(rpm),
                                       round(rpm_max) if rpm_max else 0)
        else:
            rpm_txt = "-- / -- rpm"
        self._text(cv, cx, h * 0.84, text=rpm_txt, fill=col["dim"],
                   font=self._font(max(11, h * 0.04), mono=True))

        # 转速细进度条（车速下方）
        if rpm is not None and rpm_max:
            pb_w = w * 0.62
            px0 = cx - pb_w / 2.0
            py = h * 0.92
            f = max(0.0, min(1.0, rpm / rpm_max))
            cv.create_rectangle(px0, py, px0 + pb_w, py + 7,
                                outline=col["barborder"], width=1)
            fc = col["throttle"] if f < 0.60 else (
                col["steer"] if f < 0.85 else col["brake"])
            if f > 0.003:
                cv.create_rectangle(px0 + 1, py + 1,
                                    px0 + 1 + (pb_w - 2) * f, py + 6,
                                    fill=fc, outline="")

    # ---------- 分界条：刹车（左栏与中栏之间） ----------
    def _draw_brake_bar(self, d):
        cv = self.brake_bar
        cv.delete("all")
        col = self.col
        w = max(cv.winfo_width(), 20)
        h = max(cv.winfo_height(), 200)
        brake = d.get("brake") if d else None
        bar_w = 12.0
        bar_top, bar_bot = h * 0.06, h * 0.90
        bx0, bx1 = (w - bar_w) / 2.0, (w + bar_w) / 2.0
        cv.create_rectangle(bx0, bar_top, bx1, bar_bot,
                            outline=col["barborder"], width=2)
        if brake is not None:
            fh = max(0.0, min(1.0, brake)) * (bar_bot - bar_top - 4)
            if fh > 0:
                cv.create_rectangle(bx0 + 2, bar_bot - 2 - fh,
                                    bx1 - 1, bar_bot - 2,
                                    fill=col["brake"], outline="")
            pct_txt = "%d%%" % round(brake * 100)
        else:
            pct_txt = "--"
        self._text(cv, w / 2.0, bar_bot + 16, text=pct_txt,
                   fill=col["fg"], font=self._font(10, bold=True, mono=True))
        self._text(cv, w / 2.0, bar_top - 12, text="刹车",
                   fill=col["dim"], font=self._font(9))

    # ---------- 中栏：俯视图车辆（车轮=悬挂+轮速） ----------
    @staticmethod
    def _rrect(cv, x0, y0, x1, y1, r, **kw):
        """圆角矩形（沿四角圆弧采样点，多边形近似）。"""
        pts = []
        for ccx, ccy, a0 in ((x1 - r, y0 + r, -90.0), (x1 - r, y1 - r, 0.0),
                             (x0 + r, y1 - r, 90.0), (x0 + r, y0 + r, 180.0)):
            for i in range(5):
                ang = math.radians(a0 + 90.0 * i / 4.0)
                pts += [ccx + r * math.cos(ang), ccy + r * math.sin(ang)]
        return cv.create_polygon(pts, **kw)

    def _draw_mid(self, d):
        cv = self.mid
        cv.delete("all")
        col = self.col
        w = max(cv.winfo_width(), 200)
        h = max(cv.winfo_height(), 240)
        cx = w / 2.0

        susp = d.get("susp") if d else None
        wsp = d.get("wheel_speed") if d else None

        # --- 车身（圆角矩形，车头朝上） ---
        body_w = min(w * 0.55, h * 0.40)
        body_h = h * 0.56
        bx0, bx1 = cx - body_w / 2, cx + body_w / 2
        by0, by1 = h * 0.18, h * 0.18 + body_h
        self._rrect(cv, bx0, by0, bx1, by1, body_w * 0.22,
                    fill=col["car_body"], outline=col["car_edge"], width=3)
        # 车头方向小三角
        tri = 8
        cv.create_polygon(cx - tri, by0 - 4, cx + tri, by0 - 4, cx, by0 - 16,
                          fill=col["dim"], outline="")

        # --- 四角车轮块：内部竖直填充=悬挂压缩，颜色=轮速状态 ---
        labels4 = ["FL", "FR", "RL", "RR"]
        ww = body_w * 0.24
        wh = body_h * 0.22
        # 真车方位：FL 左上 / FR 右上 / RL 左下 / RR 右下
        pos = [(bx0 - ww * 0.45, by0 - wh * 0.15),          # FL
               (bx1 - ww * 0.55, by0 - wh * 0.15),          # FR
               (bx0 - ww * 0.45, by1 - wh * 0.85),          # RL
               (bx1 - ww * 0.55, by1 - wh * 0.85)]          # RR
        valid = bool(wsp) and any(v for v in wsp if v)
        mean = (sum(v or 0.0 for v in wsp) / 4.0) if valid else 0.0
        for i in range(4):
            wx0, wy0 = pos[i]
            wx1, wy1 = wx0 + ww, wy0 + wh
            v = wsp[i] if wsp and i < len(wsp) else None
            # 轮速状态：四轮均值>5 rad/s 时，偏慢=抱死(橙) 偏快=打滑(红)
            if v and mean > 5.0 and v < mean * 0.85:
                state_col = col["wheel_lock"]
            elif v and mean > 5.0 and v > mean * 1.18:
                state_col = col["wheel_slip"]
            else:
                state_col = col["wheel_ok"]
            cv.create_rectangle(wx0, wy0, wx1, wy1,
                                fill=col["car_body"], outline=state_col,
                                width=3)
            sv = susp[i] if susp and i < len(susp) else None
            if sv is not None:
                # 悬挂相对中间位的上下偏移（>0 压缩向上 / <0 拉伸向下）
                dev = max(-0.5, min(0.5, sv - 0.5))
                mid_y = (wy0 + wy1) / 2.0
                fh = abs(dev) * 2.0 * (wh - 6) / 2.0
                if fh > 1:
                    if dev >= 0:
                        cv.create_rectangle(wx0 + 3, mid_y - fh,
                                            wx1 - 2, mid_y,
                                            fill=state_col, outline="")
                    else:
                        cv.create_rectangle(wx0 + 3, mid_y,
                                            wx1 - 2, mid_y + fh,
                                            fill=state_col, outline="")
                self._line(cv, (wx0 + 3, mid_y, wx1 - 2, mid_y), col["dim"], 1)
            # 块旁两行小字：轮名+轮速值、悬挂偏移百分比
            label_y = wy1 + 10 if i < 2 else wy0 - 22
            self._text(cv, (wx0 + wx1) / 2, label_y,
                       text="%s %s" % (labels4[i],
                                       "%.0f" % v if v is not None else "--"),
                       fill=col["fg"], font=self._font(10, bold=True, mono=True))
            susp_txt = ("%+.0f%%" % ((sv - 0.5) * 100)) if sv is not None else "--"
            self._text(cv, (wx0 + wx1) / 2, label_y + 13, text=susp_txt,
                       fill=col["dim"], font=self._font(9, mono=True))
        # 图注
        self._text(cv, cx, h * 0.075, text="悬挂 / 轮速（俯视）",
                   fill=col["dim"], font=self._font(max(10, h * 0.032)))
        self._text(cv, cx, h * 0.925,
                   text="轮内条=悬挂上下(相对中间位)  边框色=轮速状态",
                   fill=col["dim"], font=self._font(8))
        self._text(cv, cx, h * 0.972,
                   text="数字=轮速(rad/s) / 悬挂偏移%",
                   fill=col["dim"], font=self._font(8))

    # ---------- 底部：全宽转向条 ----------
    def _draw_steer(self, d):
        cv = self.steer_bar
        cv.delete("all")
        col = self.col
        w = max(cv.winfo_width(), 300)
        h = max(cv.winfo_height(), 30)
        steer = d.get("steer") if d else None

        self._text(cv, 34, h / 2, text="转向", anchor="e", fill=col["fg"],
                   font=self._font(11, bold=True))
        x0, x1 = 48.0, w - 96.0
        y0, y1 = h / 2 - 9, h / 2 + 9
        cv.create_rectangle(x0, y0, x1, y1, outline=col["barborder"], width=2)
        mid_x = (x0 + x1) / 2.0
        # 中心零点 + 左右 50% 刻度
        self._line(cv, (mid_x, y0 - 5, mid_x, y1 + 5), col["dim"], 2)
        for q in (0.25, 0.75):
            qx = x0 + (x1 - x0) * q
            self._line(cv, (qx, y0, qx, y1), col["gridline"], 1)
        if steer is not None:
            sx = mid_x + max(-1.0, min(1.0, steer)) * ((x1 - x0) / 2.0 - 8)
            cv.create_rectangle(sx - 6, y0 + 2, sx + 6, y1 - 1,
                                fill=col["steer"],
                                outline=col["barborder"], width=1)
            val_txt = "%+.2f" % steer
        else:
            val_txt = "--"
        self._text(cv, w - 12, h / 2, text=val_txt, anchor="e",
                   fill=col["fg"], font=self._font(11, bold=True, mono=True))

    # ---------- 分界条：油门（中栏与右栏之间） ----------
    def _draw_throttle_bar(self, d):
        cv = self.throttle_bar
        cv.delete("all")
        col = self.col
        w = max(cv.winfo_width(), 20)
        h = max(cv.winfo_height(), 200)
        throttle = d.get("throttle") if d else None
        bar_w = 12.0
        bar_top, bar_bot = h * 0.06, h * 0.90
        bx0, bx1 = (w - bar_w) / 2.0, (w + bar_w) / 2.0
        cv.create_rectangle(bx0, bar_top, bx1, bar_bot,
                            outline=col["barborder"], width=2)
        if throttle is not None:
            fh = max(0.0, min(1.0, throttle)) * (bar_bot - bar_top - 4)
            if fh > 0:
                cv.create_rectangle(bx0 + 2, bar_bot - 2 - fh,
                                    bx1 - 1, bar_bot - 2,
                                    fill=col["throttle"], outline="")
            pct_txt = "%d%%" % round(throttle * 100)
        else:
            pct_txt = "--"
        self._text(cv, w / 2.0, bar_bot + 16, text=pct_txt,
                   fill=col["fg"], font=self._font(10, bold=True, mono=True))
        self._text(cv, w / 2.0, bar_top - 12, text="油门",
                   fill=col["dim"], font=self._font(9))

    # ---------- G-G 图 / 信息 ----------
    def _draw_right(self, d):
        cv = self.right
        cv.delete("all")
        col = self.col
        outline = col.get("outline")
        w = max(cv.winfo_width(), 180)
        h = max(cv.winfo_height(), 240)

        # G-G 图可用区域（全宽）
        cx = w / 2.0
        radius = max(50.0, min(w / 2.0 - 22.0, (h - 100.0) / 2.0, 160.0))
        cy = h / 2.0 + 12

        self._text(cv, cx, 18, text="G-G 图", fill=col["dim"],
                   font=self._font(11))
        # 网格：0.5g 间隔
        g_max = 2.0
        for ring in (0.5, 1.0, 1.5, 2.0):
            rr = ring / g_max * radius
            self._ring(cv, (cx - rr, cy - rr, cx + rr, cy + rr),
                       col["grid"], 2 if ring == 2.0 else 1)
        self._line(cv, (cx - radius, cy, cx + radius, cy),
                   col["gridline"], 2)
        self._line(cv, (cx, cy - radius, cx, cy + radius),
                   col["gridline"], 2)
        self._text(cv, cx, cy - radius - 12, text="刹车", fill=col["dim"],
                   font=self._font(9))
        self._text(cv, cx, cy + radius + 12, text="加速", fill=col["dim"],
                   font=self._font(9))
        self._text(cv, cx - radius - 6, cy, text="左", fill=col["dim"],
                   anchor="e", font=self._font(9))
        self._text(cv, cx + radius + 6, cy, text="右", fill=col["dim"],
                   anchor="w", font=self._font(9))

        # G-G 小球：限幅在显示半径内，颜色按占半径比例分四档
        if d and d.get("g_lat") is not None and d.get("g_lon") is not None:
            lat, lon = d["g_lat"], d["g_lon"]
            g_abs = math.hypot(lat, lon)
            if g_abs > g_max:            # 限幅：小球不超出最外圈
                f = g_max / g_abs
                lat, lon = lat * f, lon * f
            hx = cx - lat / g_max * radius
            hy = cy - lon / g_max * radius
            frac = min(g_abs, g_max) / g_max
            t = self.cfg["gg_thresholds"]
            if frac >= t[0]:
                ball = col["gg_max"]
            elif frac >= t[1]:
                ball = col["gg_hi"]
            elif frac >= t[2]:
                ball = col["gg_mid"]
            else:
                ball = col["gg_lo"]
            cv.create_oval(hx - 7, hy - 7, hx + 7, hy + 7,
                           fill=ball, outline="#000000" if outline else col["fg"],
                           width=2)
        if d and d.get("g_lat") is not None:
            self._text(cv, cx, cy + radius + 30,
                       text="横向 %+.2f g   纵向 %+.2f g"
                            % (d["g_lat"], d.get("g_lon") or 0.0),
                       fill=col["fg"], font=self._font(10, bold=True, mono=True))

    # ---------- 自检 / 关闭 ----------
    def _self_test_done(self):
        latest, seq, rate, last_ts, error = self.listener.snapshot()
        ok = (seq > 30 and latest and latest.get("ok")
              and latest.get("rpm") is not None)
        print("[SELF-TEST] packets=%d rate=%.1f error=%s rpm=%s speed=%s gear=%s"
              % (seq, rate, error,
                 None if not latest else latest.get("rpm"),
                 None if not latest else latest.get("speed_kmh"),
                 None if not latest else latest.get("gear_label")))
        print("[SELF-TEST] %s" % ("PASS" if ok else "FAIL"))
        self.on_close(exit_code=0 if ok else 1)

    def on_close(self, exit_code=0):
        try:
            self.cfg["geometry"] = self.root.geometry()
        except tk.TclError:
            pass
        save_config(self.cfg)
        for job in self._after_jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._after_jobs = []
        if self.sim_thread is not None and self.sim_thread.is_alive():
            self.sim_thread.stop()
        self.listener.stop()
        self.root.destroy()
        if self._self_test:
            raise SystemExit(exit_code)


def main():
    ap = argparse.ArgumentParser(description="WRC 9 遥测仪表盘（独立窗口）")
    ap.add_argument("--rpm-scale", type=float, default=None,
                    help="转速校准系数（真机校准用，默认读 config.json）")
    ap.add_argument("--sim", action="store_true",
                    help="启动时自动开启内置合成数据演示")
    ap.add_argument("--topmost", action="store_true", help="窗口置顶")
    ap.add_argument("--green", action="store_true", help="绿幕背景（OBS 色键）")
    ap.add_argument("--self-test", type=float, default=0.0, metavar="秒",
                    help="自检模式：自动开合成数据源，N 秒后打印结果并退出")
    args = ap.parse_args()

    root = tk.Tk()
    DashboardApp(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
