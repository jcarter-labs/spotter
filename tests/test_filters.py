import time
import unittest

from cluster import Spot
from filters import DedupCache, prefix_to_dxcc


def make_spot(**kwargs):
    defaults = dict(
        dx_call="UA9MA", spotter="W1AW", freq_khz=14025.0,
        band="20m", mode="CW", comment="CW 599", time_utc="1234Z",
        dx_dxcc="Russia", dx_continent="AS",
        spotter_dxcc="United States", spotter_continent="NA",
    )
    defaults.update(kwargs)
    return Spot(**defaults)


class TestDedupWithinWindow(unittest.TestCase):
    def test_second_spot_suppressed(self):
        cache = DedupCache(window_minutes=10)
        spot = make_spot(dx_call="UA9MA", band="20m")
        self.assertFalse(cache.is_dup(spot))
        cache.record(spot)
        self.assertTrue(cache.is_dup(spot))

    def test_different_band_not_suppressed(self):
        cache = DedupCache(window_minutes=10)
        spot_20 = make_spot(dx_call="UA9MA", band="20m")
        spot_40 = make_spot(dx_call="UA9MA", band="40m")
        cache.record(spot_20)
        self.assertFalse(cache.is_dup(spot_40))


class TestDedupAfterWindow(unittest.TestCase):
    def test_passes_after_window_expires(self):
        cache = DedupCache(window_minutes=0)
        spot = make_spot(dx_call="UA9MA", band="20m")
        cache.record(spot)
        time.sleep(0.05)
        self.assertFalse(cache.is_dup(spot))


class TestPrefixToDxcc(unittest.TestCase):
    def test_us_callsign(self):
        dxcc, continent = prefix_to_dxcc("W1AW")
        self.assertEqual(dxcc, "United States")
        self.assertEqual(continent, "NA")

    def test_russian_callsign(self):
        dxcc, continent = prefix_to_dxcc("UA9MA")
        self.assertEqual(dxcc, "Russia")
        self.assertEqual(continent, "AS")

    def test_japanese_callsign(self):
        dxcc, continent = prefix_to_dxcc("JA1ABC")
        self.assertEqual(dxcc, "Japan")
        self.assertEqual(continent, "AS")

    def test_unknown_prefix(self):
        dxcc, continent = prefix_to_dxcc("ZZ9ZZZ")
        self.assertEqual(dxcc, "Unknown")
        self.assertEqual(continent, "")


if __name__ == "__main__":
    unittest.main()
