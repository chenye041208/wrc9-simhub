# -*- coding: utf-8 -*-
"""dashboard.main 配置校验测试（G-G 小球变色阈值）。"""

import unittest

from dashboard.main import DEFAULT_GG_THRESHOLDS, validate_gg_thresholds

DEFAULTS = list(DEFAULT_GG_THRESHOLDS)


class TestValidateGgThresholds(unittest.TestCase):
    def test_valid_custom_kept(self):
        self.assertEqual(validate_gg_thresholds([0.8, 0.6, 0.4]),
                         [0.8, 0.6, 0.4])

    def test_default_config_value_passes(self):
        self.assertEqual(validate_gg_thresholds(DEFAULTS), DEFAULTS)

    def test_wrong_length_falls_back(self):
        self.assertEqual(validate_gg_thresholds([0.9, 0.7]), DEFAULTS)
        self.assertEqual(validate_gg_thresholds([0.9, 0.8, 0.7, 0.6]), DEFAULTS)

    def test_non_numeric_falls_back(self):
        self.assertEqual(validate_gg_thresholds(["a", 0.7, 0.5]), DEFAULTS)
        self.assertEqual(validate_gg_thresholds(None), DEFAULTS)
        self.assertEqual(validate_gg_thresholds("0.9,0.7,0.5"), DEFAULTS)

    def test_out_of_range_falls_back(self):
        self.assertEqual(validate_gg_thresholds([1.5, 0.7, 0.5]), DEFAULTS)
        self.assertEqual(validate_gg_thresholds([0.9, 0.7, 0.0]), DEFAULTS)
        self.assertEqual(validate_gg_thresholds([0.9, 0.7, -0.1]), DEFAULTS)

    def test_not_descending_falls_back(self):
        self.assertEqual(validate_gg_thresholds([0.5, 0.7, 0.9]), DEFAULTS)
        self.assertEqual(validate_gg_thresholds([0.7, 0.7, 0.5]), DEFAULTS)

    def test_numeric_strings_accepted(self):
        self.assertEqual(validate_gg_thresholds(["0.9", "0.7", "0.5"]),
                         [0.9, 0.7, 0.5])


if __name__ == "__main__":
    unittest.main()
