# -*- coding: utf-8 -*-
"""gamepad_reader 归一化逻辑测试（不依赖真实手柄）。"""

import unittest

from telemetry.gamepad_reader import DEFAULT_MAP, _norm_stick, _norm_trigger


class TestTriggerNorm(unittest.TestCase):
    def test_zero_and_full(self):
        self.assertEqual(_norm_trigger(0), 0.0)
        self.assertAlmostEqual(_norm_trigger(255), 1.0)

    def test_clamp(self):
        self.assertEqual(_norm_trigger(-5), 0.0)
        self.assertEqual(_norm_trigger(999), 1.0)


class TestStickNorm(unittest.TestCase):
    def test_center_deadzone(self):
        self.assertEqual(_norm_stick(0), 0.0)
        self.assertEqual(_norm_stick(3000), 0.0)    # 死区内
        self.assertEqual(_norm_stick(-3000), 0.0)

    def test_full_deflection(self):
        self.assertAlmostEqual(_norm_stick(32767), 1.0)
        self.assertAlmostEqual(_norm_stick(-32767), -1.0)

    def test_monotonic_outside_deadzone(self):
        a = _norm_stick(8000)
        b = _norm_stick(16000)
        self.assertGreater(b, a)
        self.assertGreater(a, 0.0)


class TestDefaults(unittest.TestCase):
    def test_default_mapping(self):
        self.assertEqual(DEFAULT_MAP["throttle"], "RT")
        self.assertEqual(DEFAULT_MAP["brake"], "LT")
        self.assertEqual(DEFAULT_MAP["steer"], "LX")


if __name__ == "__main__":
    unittest.main()
