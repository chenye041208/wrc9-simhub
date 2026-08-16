# -*- coding: utf-8 -*-
"""snap.py — 开发用截图工具：抓取仪表盘窗口图像，供界面检查与调整。

用法： python snap.py 输出.png [等待秒数]
"""
import ctypes
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def find_hwnd(title_prefix="WRC 9 遥测仪表盘"):
    """只匹配 tkinter 窗口（类名 TkTopLevel）且标题前缀一致，避免误抓其他窗口。"""
    hits = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                   wintypes.LPARAM)

    def cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value != "TkTopLevel":
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.startswith(title_prefix):
                    hits.append(hwnd)
        return True

    user32.EnumWindows(enum_proc(cb), 0)
    return hits[0] if hits else None


def snap(out, wait=0.0):
    if wait:
        time.sleep(wait)
    hwnd = find_hwnd()
    if not hwnd:
        print("ERROR: 找不到 WRC 9 窗口")
        sys.exit(1)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x1 | 0x2)  # 临时置顶
    time.sleep(0.4)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom),
                         all_screens=True)
    user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x1 | 0x2)  # 取消临时置顶
    img.save(out)
    print("saved %s %sx%s" % (out, img.size[0], img.size[1]))


if __name__ == "__main__":
    snap(sys.argv[1], wait=float(sys.argv[2]) if len(sys.argv) > 2 else 0.0)
