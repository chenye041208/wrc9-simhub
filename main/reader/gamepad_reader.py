# -*- coding: utf-8 -*-
"""
gamepad_reader.py — XInput 手柄输入直读（零第三方依赖，ctypes）

遥测协议里没有的油门/刹车/转向，从手柄硬件通道补读：
    RT 扳机 → 油门    LT 扳机 → 刹车    左摇杆 X → 转向
（XInput 通道布局是微软固定标准，与游戏内键位绑定无关；
  若你的习惯不同，可在 config.json 里改映射。）

注意：读的是物理输入，和游戏内生效值可能有轻微死区/线性度差异。
"""

import ctypes

# XInput 结构体（16 字节）
class _XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", _XINPUT_GAMEPAD),
    ]


ERROR_DEVICE_NOT_CONNECTED = 1167
MAX_PADS = 4

# 标准通道默认值
DEFAULT_MAP = {"throttle": "RT", "brake": "LT", "steer": "LX"}

_STICK_DEADZONE = 0.10   # 左摇杆死区（手柄漂移余量）


def _norm_stick(raw, deadzone=_STICK_DEADZONE):
    """摇杆原始值 (-32768..32767) → -1..1，带死区归一。"""
    v = max(-1.0, min(1.0, raw / 32767.0))
    if abs(v) <= deadzone:
        return 0.0
    sign = 1.0 if v > 0 else -1.0
    return sign * (abs(v) - deadzone) / (1.0 - deadzone)


def _norm_trigger(raw):
    """扳机原始值 (0..255) → 0..1。"""
    return max(0.0, min(1.0, raw / 255.0))


class GamepadReader:
    """轮询 XInput 手柄。未连接时 poll() 返回 None。"""

    def __init__(self, index=0, mapping=None):
        self.index = index
        self.mapping = dict(DEFAULT_MAP)
        if mapping:
            self.mapping.update(mapping)
        self._xinput = None
        self._state = _XINPUT_STATE()
        for dll in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                self._xinput = ctypes.windll.LoadLibrary(dll)
                break
            except OSError:
                continue

    @property
    def available(self):
        return self._xinput is not None

    def poll(self):
        """读取一次。返回 {"throttle","brake","steer","connected"} 或 None。"""
        if self._xinput is None:
            return None
        rc = self._xinput.XInputGetState(self.index, ctypes.byref(self._state))
        if rc != 0:
            return None
        gp = self._state.Gamepad
        channels = {
            "RT": _norm_trigger(gp.bRightTrigger),
            "LT": _norm_trigger(gp.bLeftTrigger),
            "LX": _norm_stick(gp.sThumbLX),
            "LY": _norm_stick(gp.sThumbLY),
        }
        m = self.mapping
        return {
            "connected": True,
            "throttle": channels.get(m["throttle"], 0.0),
            "brake": channels.get(m["brake"], 0.0),
            "steer": channels.get(m["steer"], 0.0),
            "clutch": 0.0,   # 手柄无离合
        }


if __name__ == "__main__":
    # 命令行自检：python gamepad_reader.py
    import time
    r = GamepadReader()
    if not r.available:
        print("未找到 XInput DLL")
    else:
        print("摇动手柄（Ctrl+C 退出）…")
        try:
            while True:
                d = r.poll()
                if d:
                    print("油门 %.2f  刹车 %.2f  转向 %+.2f   "
                          % (d["throttle"], d["brake"], d["steer"]), end="\r")
                else:
                    print("手柄未连接…", end="\r")
                time.sleep(0.05)
        except KeyboardInterrupt:
            print()
