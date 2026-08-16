# -*- coding: utf-8 -*-
"""
wrc_shm.py — WRC Telemetry Patch 原生共享内存直读模块

不经过 DirtRally2.exe 转发器，直接读取补丁注入游戏后创建的共享内存
（与 SimHub 同源）。相比 DR2.0 模拟层（extradata3 UDP）：

  - 有真实悬挂行程数据（DR2.0 层全为 0）
  - 无 UDP 端口 / 防火墙 / 转发器进程依赖
  - 注意：转速仍需 ×10 校准（补丁自身的单位怪癖，原生结构体里也是 1/10）

协议里仍然没有的字段：油门/刹车/离合/转向、圈速、里程
（补丁根本没有从游戏里钩取这些数据，任何方案都拿不到）。

共享内存布局（补丁 Readme 公布，#pragma pack(1)，共 96 字节）：
    uint32  sequence_number       奇数 = 游戏正在写入
    uint32  version               结构体版本（当前为 1）
    int32   gear                  空挡=1, 一档=2, ...（0=倒挡）
    float   velocity[3]           左/上/前 [m/s]
    float   acceleration[3]       左/上/前 [m/s²]
    int32   engine_idle_rpm
    int32   engine_max_rpm
    int32   engine_rpm
    float   suspension_travel[4]  可动量程 FL,RL,RR,FR [m]
    float   suspension_position[4] 当前位置 0..travel
    float   unknown[4]
"""

import math
import struct
import time

SHARED_MEMORY_NAME = r"Local\WRC-8wSotWzFKAhBlbW10ZJBKaWMdWszbBXg"

STRUCT_FMT = "<IIi3f3f3i4f4f4f"
STRUCT_SIZE = struct.calcsize(STRUCT_FMT)   # 96
SUPPORTED_VERSION = 1

# 原生车轮顺序 FL,RL,RR,FR → 仪表盘统一顺序 FL,FR,RL,RR
_WHEEL_MAP = (0, 3, 1, 2)

G_EARTH = 9.81


class ShmError(Exception):
    pass


def parse_frame(data):
    """解析一帧 96 字节共享内存快照，返回原生字段字典（纯函数，可测试）。

    数据无效（长度不足 / 版本不符 / 非有限值）时返回 None。
    """
    if len(data) < STRUCT_SIZE:
        return None
    vals = struct.unpack(STRUCT_FMT, bytes(data[:STRUCT_SIZE]))
    (seq, version, gear,
     vx, vy, vz, ax, ay, az,
     idle_rpm, max_rpm, rpm) = vals[:12]
    susp_travel = vals[12:16]
    susp_position = vals[16:20]
    unknown = vals[20:24]
    if version != SUPPORTED_VERSION:
        return None
    floats = (vx, vy, vz, ax, ay, az) + susp_travel + susp_position
    if not all(math.isfinite(v) for v in floats):
        return None
    return {
        "seq": seq,
        "version": version,
        "gear": gear,                      # 0=倒挡 1=空挡 2=一档 ...
        "velocity": (vx, vy, vz),          # 左/上/前 m/s
        "acceleration": (ax, ay, az),      # 左/上/前 m/s²
        "idle_rpm": idle_rpm,
        "max_rpm": max_rpm,
        "rpm": rpm,
        "susp_travel": susp_travel,
        "susp_position": susp_position,
        "unknown": unknown,
    }


def to_dashboard_dict(frame, rpm_scale=1.0, g_scale=G_EARTH, g_lon_flip=True):
    """把 parse_frame 的结果转成与 dr2_parser.safe_parse 相同的字典形状。

    原生协议默认值即为真机校准值：rpm_scale=1.0（原生 RPM）、
    g_scale=9.81（m/s²→G）、g_lon_flip=True（刹车朝上惯例）。
    协议没有的字段（踏板/转向/圈速等）填 None 或 0。
    """
    if frame is None:
        return None
    vx, vy, vz = frame["velocity"]
    ax, ay, az = frame["acceleration"]

    speed_ms = math.sqrt(vx * vx + vy * vy + vz * vz)

    rpm = frame["rpm"] * rpm_scale
    rpm_max = frame["max_rpm"] * rpm_scale
    if rpm_max <= 0:
        rpm_max = 8000.0
    rpm_idle = frame["idle_rpm"] * rpm_scale
    if rpm_idle < 0 or rpm_idle >= rpm_max:
        rpm_idle = 0.0
    rpm_pct = max(0.0, min(1.2, rpm / rpm_max))

    # 档位：原生 0=倒挡 1=空挡 2=一档 → DR2 约定 -1=R 0=N 1..=前进挡
    native_gear = frame["gear"]
    if native_gear <= 0:
        gear = -1
    else:
        gear = native_gear - 1

    # 悬挂：位置/量程 → 0..1 比例（可越界少许，限幅），顺序映射到 FL,FR,RL,RR
    susp = []
    for i in _WHEEL_MAP:
        travel = frame["susp_travel"][i]
        pos = frame["susp_position"][i]
        frac = pos / travel if travel > 1e-6 else 0.0
        susp.append(max(0.0, min(1.0, frac)))

    g_lon = -az if g_lon_flip else az     # 刹车朝上惯例
    return {
        "ok": True,
        "source": "shm",
        "packet_size": STRUCT_SIZE,
        "ts": time.time(),
        "raw": frame,
        "speed_ms": speed_ms,
        "speed_kmh": speed_ms * 3.6,
        "rpm": float(rpm),
        "rpm_max": float(rpm_max),
        "rpm_idle": float(rpm_idle),
        "rpm_pct": rpm_pct,
        "gear": gear,
        "gear_label": "R" if gear < 0 else ("N" if gear == 0 else str(gear)),
        "throttle": 0.0,       # 协议不提供
        "brake": 0.0,          # 协议不提供
        "clutch": 0.0,         # 协议不提供
        "steer": 0.0,          # 协议不提供
        "g_lat": ax / g_scale,
        "g_lon": g_lon / g_scale,
        "susp": susp,
        "susp_vel": [None, None, None, None],
        # unknown[4] 经真机相关性分析鉴定为四轮转速 [rad/s]（顺序同车轮映射）
        "wheel_speed": [frame["unknown"][i] for i in _WHEEL_MAP],
        "lap": None,
        "lap_time": None,
        "last_lap_time": None,
        "run_time": None,
        "distance": None,
        "progress": None,
        "race_pos": None,
        "attitude_valid": True,    # 协议无姿态字段，直接静默不显示
        "attitude": None,
        "quality": {"packet_size_ok": True, "bad_fields": []},
    }


# ---------------- Windows 共享内存读取 ----------------

class ShmReader:
    """打开并轮询补丁共享内存。仅 Windows；读取失败时静默等待重试。"""

    def __init__(self, name=SHARED_MEMORY_NAME):
        self.name = name
        self._handle = None
        self._view = None
        self._next_retry = 0.0
        self.last_seq = -1
        self._kernel32 = None

    # -- 生命周期 --
    def _ensure_open(self):
        if self._view is not None:
            return True
        now = time.monotonic()
        if now < self._next_retry:
            return False
        self._next_retry = now + 2.0
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            # 64 位下必须把返回值声明为指针，否则默认 int 会截断地址
            k32.OpenFileMappingW.restype = ctypes.c_void_p
            k32.MapViewOfFile.restype = ctypes.c_void_p
            k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            FILE_MAP_READ = 0x0004
            handle = k32.OpenFileMappingW(FILE_MAP_READ, False, self.name)
            if not handle:
                return False
            # 尺寸传 0：映射整个节区，避免超出实际节区大小导致访问违例
            view = k32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0)
            if not view:
                k32.CloseHandle(handle)
                return False
            self._kernel32 = k32
            self._handle = handle
            self._view = view
            return True
        except (OSError, AttributeError):
            return False

    def close(self):
        if self._kernel32 is not None:
            if self._view is not None:
                self._kernel32.UnmapViewOfFile(self._view)
            if self._handle is not None:
                self._kernel32.CloseHandle(self._handle)
        self._kernel32 = self._handle = self._view = None

    # -- 读取 --
    def poll(self):
        """读取一帧；有新数据返回 parse_frame 字典，否则 None。

        利用 sequence_number 奇偶做无锁一致性校验：
        奇数表示游戏正在写入，读取后序号变化则丢弃重读。
        """
        if not self._ensure_open():
            return None
        import ctypes
        try:
            for _ in range(4):
                buf = ctypes.string_at(self._view, STRUCT_SIZE)
                seq = struct.unpack_from("<I", buf, 0)[0]
                if seq & 1:                      # 游戏正在写
                    continue
                if seq == self.last_seq:         # 无新数据
                    return None
                frame = parse_frame(buf)
                if frame is None:
                    return None
                seq2 = struct.unpack_from("<I", ctypes.string_at(self._view, 4), 0)[0]
                if seq2 != seq or (seq2 & 1):
                    continue                     # 读到一半被改写，重读
                self.last_seq = seq
                return frame
        except OSError:
            # 映射被持有方销毁（游戏退出/补丁卸载），关闭后等待下次重试
            self.close()
        return None


# ---------------- 命令行自检 ----------------

def _cli_watch():
    """直读共享内存并打印，验证补丁是否在喂数据：python wrc_shm.py"""
    reader = ShmReader()
    print("等待补丁共享内存 %s …" % SHARED_MEMORY_NAME)
    try:
        while True:
            frame = reader.poll()
            if frame:
                d = to_dashboard_dict(frame)
                print("档位%(gear_label)s 转速%(rpm).0f/%(rpm_max).0f "
                      "车速%(speed_kmh).1fkm/h G(%(g_lat)+.2f,%(g_lon)+.2f) "
                      "悬挂FL%%.2f" % d % d["susp"][0])
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()


if __name__ == "__main__":
    _cli_watch()
