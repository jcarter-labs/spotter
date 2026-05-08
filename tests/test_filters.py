import time
import unittest

from cluster import Spot
from filters import DedupCache, SpotFilter, passes, prefix_to_dxcc


def make_spot(**kwargs):
    defaults = dict(
        dx_call="UA9MA", spotter="W1AW", freq_khz=14025.0,
        band="20m", mode="CW", comment="CW 599", time_utc="1234Z",
        dx_dxcc="Russia", dx_continent="AS",
        spotter_dxcc="United States", spotter_continent="NA",
    )
    defaults.update(kwargs)
    return Spot(**defaults)


class TestBandFilter(unittest.TestCase):
    def test_accepts_matching_band(self):
        f = SpotFilter(bands=["20m"])
        self.assertTrue(passes(make_spot(band="20m"), f))

    def test_rejects_other_band(self):
        f = SpotFilter(bands=["20m"])
        self.assertFalse(passes(make_spot(band="40m"), f))


class TestModeFilter(unittest.TestCase):
    def test_accepts_matching_mode(self):
        f = SpotFilter(modes=["CW", "FT8"])
        self.assertTrue(passes(make_spot(mode="CW"), f))

    def test_rejects_other_mode(self):
        f = SpotFilter(modes=["CW", "FT8"])
        self.assertFalse(passes(make_spot(mode="SSB"), f))


class TestDxPrefixFilter(unittest.TestCase):
    def test_accepts_matching_prefix(self):
        f = SpotFilter(dx_prefixes=["UA"])
        self.assertTrue(passes(make_spot(dx_call="UA9MA"), f))

    def test_rejects_other_prefix(self):
        f = SpotFilter(dx_prefixes=["UA"])
        self.assertFalse(passes(make_spot(dx_call="W1AW"), f))


class TestDxContinentFilter(unittest.TestCase):
    def test_accepts_matching_continent(self):
        f = SpotFilter(dx_continents=["EU"])
        self.assertTrue(passes(make_spot(dx_continent="EU"), f))

    def test_rejects_other_continent(self):
        f = SpotFilter(dx_continents=["EU"])
        self.assertFalse(passes(make_spot(dx_continent="NA"), f))


class TestDxDxccFilter(unittest.TestCase):
    def test_accepts_matching_dxcc(self):
        f = SpotFilter(dx_dxcc=["Russia"])
        self.assertTrue(passes(make_spot(dx_dxcc="Russia"), f))

    def test_rejects_other_dxcc(self):
        f = SpotFilter(dx_dxcc=["Russia"])
        self.assertFalse(passes(make_spot(dx_dxcc="United States"), f))


class TestSpotterPrefixFilter(unittest.TestCase):
    def test_accepts_matching_spotter(self):
        f = SpotFilter(spotter_prefixes=["W"])
        self.assertTrue(passes(make_spot(spotter="W1AW"), f))

    def test_rejects_other_spotter(self):
        f = SpotFilter(spotter_prefixes=["W"])
        self.assertFalse(passes(make_spot(spotter="VE7CC"), f))


class TestCombinedFilters(unittest.TestCase):
    def test_all_must_pass(self):
        f = SpotFilter(bands=["20m"], modes=["CW"], dx_continents=["AS"])
        self.assertTrue(passes(make_spot(band="20m", mode="CW", dx_continent="AS"), f))

    def test_one_fails_rejects(self):
        f = SpotFilter(bands=["20m"], modes=["CW"], dx_continents=["AS"])
        self.assertFalse(passes(make_spot(band="20m", mode="SSB", dx_continent="AS"), f))


class TestNoFilters(unittest.TestCase):
    def test_empty_filter_passes_all(self):
        f = SpotFilter()
        self.assertTrue(passes(make_spot(), f))
        self.assertTrue(passes(make_spot(band="160m", mode="RTTY", dx_continent="AF"), f))


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
