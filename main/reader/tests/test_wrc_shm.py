# -*- coding: utf-8 -*-
"""wrc_shm 原生共享内存协议解析测试。"""

import struct
import unittest

from reader.wrc_shm import (STRUCT_FMT, STRUCT_SIZE, SUPPORTED_VERSION,
                               parse_frame, to_dashboard_dict)


def make_frame(seq=100, version=SUPPORTED_VERSION, gear=4,
               velocity=(1.0, 0.5, 30.0), acceleration=(12.0, -9.8, 8.0),
               idle=2200, maxrpm=8800, rpm=6500,
               travel=(0.20, 0.20, 0.18, 0.18),
               position=(0.10, 0.15, 0.05, 0.09)):
    return struct.pack(STRUCT_FMT, seq, version, gear,
                       *velocity, *acceleration, idle, maxrpm, rpm,
                       *travel, *position, 0.0, 0.0, 0.0, 0.0)


class TestStructLayout(unittest.TestCase):
    def test_struct_size_is_96(self):
        self.assertEqual(STRUCT_SIZE, 96)


class TestParseFrame(unittest.TestCase):
    def test_valid_frame(self):
        f = parse_frame(make_frame())
        self.assertIsNotNone(f)
        self.assertEqual(f["gear"], 4)
        self.assertEqual(f["rpm"], 6500)
        self.assertAlmostEqual(f["velocity"][2], 30.0)
        self.assertEqual(len(f["susp_travel"]), 4)

    def test_short_buffer(self):
        self.assertIsNone(parse_frame(b"\x00" * 64))

    def test_bad_version(self):
        self.assertIsNone(parse_frame(make_frame(version=99)))

    def test_nan_rejected(self):
        self.assertIsNone(parse_frame(make_frame(velocity=(0, 0, float("nan")))))


class TestDashboardDict(unittest.TestCase):
    def setUp(self):
        self.d = to_dashboard_dict(parse_frame(make_frame()))

    def test_ok_and_source(self):
        self.assertTrue(self.d["ok"])
        self.assertEqual(self.d["source"], "shm")

    def test_speed_is_velocity_magnitude(self):
        # sqrt(1^2 + 0.5^2 + 30^2) * 3.6
        import math
        expect = math.sqrt(1 + 0.25 + 900) * 3.6
        self.assertAlmostEqual(self.d["speed_kmh"], expect, places=3)

    def test_rpm_native_no_scale(self):
        self.assertEqual(self.d["rpm"], 6500.0)
        self.assertEqual(self.d["rpm_max"], 8800.0)
        self.assertEqual(self.d["rpm_idle"], 2200.0)

    def test_gear_mapping(self):
        # 原生 0=倒挡 1=空挡 2=一档
        cases = {0: ("R", -1), 1: ("N", 0), 2: ("1", 1), 6: ("5", 5)}
        for native, (label, num) in cases.items():
            d = to_dashboard_dict(parse_frame(make_frame(gear=native)))
            self.assertEqual(d["gear_label"], label)
            self.assertEqual(d["gear"], num)

    def test_g_conversion_and_flip(self):
        # g_lat = ax/9.81；g_lon 默认翻转 = -az/9.81
        self.assertAlmostEqual(self.d["g_lat"], 12.0 / 9.81, places=3)
        self.assertAlmostEqual(self.d["g_lon"], -8.0 / 9.81, places=3)

    def test_g_no_flip(self):
        d = to_dashboard_dict(parse_frame(make_frame()), g_lon_flip=False)
        self.assertAlmostEqual(d["g_lon"], 8.0 / 9.81, places=3)

    def test_susp_fraction_and_order(self):
        # 原生顺序 FL,RL,RR,FR → 输出 FL,FR,RL,RR
        # travel=(.20,.20,.18,.18) pos=(.10,.15,.05,.09)
        # FL=.10/.20=.50  RL=.15/.20=.75  RR=.05/.18≈.278  FR=.09/.18=.50
        s = self.d["susp"]
        self.assertAlmostEqual(s[0], 0.50, places=3)   # FL
        self.assertAlmostEqual(s[1], 0.50, places=3)   # FR
        self.assertAlmostEqual(s[2], 0.75, places=3)   # RL
        self.assertAlmostEqual(s[3], 0.05 / 0.18, places=3)  # RR

    def test_unavailable_fields_are_zero_or_none(self):
        for k in ("throttle", "brake", "clutch", "steer"):
            self.assertEqual(self.d[k], 0.0)
        for k in ("lap_time", "last_lap_time", "distance"):
            self.assertIsNone(self.d[k])

    def test_none_frame(self):
        self.assertIsNone(to_dashboard_dict(None))


if __name__ == "__main__":
    unittest.main()
