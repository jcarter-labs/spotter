import queue
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

from cluster import Spot
from pota_client import PotaConnection, fetch_spots, filter_to_window, normalize_spot


def make_raw(**kwargs):
    defaults = dict(
        activator="K1ABC", frequency="14042.0", mode="CW",
        reference="US-1234", spotter="W1AW", comments="",
        spotTime="2026-08-16T23:35:21", source="GT2", expire=1200,
    )
    defaults.update(kwargs)
    return defaults


class TestNormalizeSpot(unittest.TestCase):
    def test_cw_mode_normalized(self):
        spot = normalize_spot(make_raw())
        self.assertIsNotNone(spot)
        self.assertEqual(spot.dx_call, "K1ABC")
        self.assertAlmostEqual(spot.freq_khz, 14042.0)
        self.assertEqual(spot.band, "20m")
        self.assertEqual(spot.feed, "POTA")

    def test_non_cw_mode_dropped(self):
        self.assertIsNone(normalize_spot(make_raw(mode="FT8")))

    def test_lowercase_mode_matched(self):
        spot = normalize_spot(make_raw(mode="cw"))
        self.assertIsNotNone(spot)
        self.assertEqual(spot.mode, "CW")

    def test_missing_activator_returns_none(self):
        raw = make_raw()
        del raw["activator"]
        self.assertIsNone(normalize_spot(raw))

    def test_invalid_frequency_returns_none(self):
        self.assertIsNone(normalize_spot(make_raw(frequency="not-a-number")))

    def test_missing_optional_fields_tolerated(self):
        raw = make_raw()
        del raw["spotter"]
        del raw["comments"]
        del raw["spotTime"]
        spot = normalize_spot(raw)
        self.assertIsNotNone(spot)
        self.assertEqual(spot.spotter, "")
        self.assertEqual(spot.comment, "")

    def test_extra_unknown_fields_ignored(self):
        spot = normalize_spot(make_raw(someNewField="whatever", grid4="EN83"))
        self.assertIsNotNone(spot)

    def test_potas_own_source_field_not_carried_through(self):
        # POTA's "source" (e.g. "RBN", "GT2") is a different concept from
        # our internal feed tag -- must not leak through as spot.feed.
        spot = normalize_spot(make_raw(source="RBN"))
        self.assertEqual(spot.feed, "POTA")


class TestFilterToWindow(unittest.TestCase):
    def _spot(self, freq_khz):
        return normalize_spot(make_raw(frequency=str(freq_khz)))

    def test_spot_inside_window_kept(self):
        result = filter_to_window([self._spot(14025.0)], center_khz=14025.0, bandwidth_khz=50.0)
        self.assertEqual(len(result), 1)

    def test_spot_outside_window_dropped(self):
        result = filter_to_window([self._spot(14200.0)], center_khz=14025.0, bandwidth_khz=50.0)
        self.assertEqual(result, [])

    def test_spot_at_window_edge_kept(self):
        # center 14025 +/- 25 -> edge = 14050, inclusive
        result = filter_to_window([self._spot(14050.0)], center_khz=14025.0, bandwidth_khz=50.0)
        self.assertEqual(len(result), 1)


class TestFetchSpots(unittest.TestCase):
    @patch("pota_client.requests.get")
    def test_returns_only_cw_spots(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            make_raw(activator="K1CW", mode="CW"),
            make_raw(activator="K2FT8", mode="FT8"),
        ]
        mock_get.return_value = mock_response

        spots = fetch_spots()
        self.assertEqual(len(spots), 1)
        self.assertEqual(spots[0].dx_call, "K1CW")

    @patch("pota_client.requests.get")
    def test_http_error_propagates(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.HTTPError):
            fetch_spots()

    @patch("pota_client.requests.get")
    def test_malformed_entry_skipped_not_crashed(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"mode": "CW"},  # missing activator/frequency entirely
            make_raw(activator="K1OK", mode="CW"),
        ]
        mock_get.return_value = mock_response

        spots = fetch_spots()
        self.assertEqual(len(spots), 1)
        self.assertEqual(spots[0].dx_call, "K1OK")


class TestPotaConnectionPolling(unittest.TestCase):
    @patch("pota_client.fetch_spots")
    def test_spots_within_window_queued(self, mock_fetch):
        mock_fetch.return_value = [normalize_spot(make_raw(frequency="14025.0"))]

        q = queue.Queue()
        conn = PotaConnection(q, window_fn=lambda: (14025.0, 50.0), poll_seconds=9999)
        conn.start()
        try:
            spot = q.get(timeout=2.0)
            self.assertEqual(spot.dx_call, "K1ABC")
        finally:
            conn.stop()

    @patch("pota_client.fetch_spots")
    def test_spots_outside_window_not_queued(self, mock_fetch):
        mock_fetch.return_value = [normalize_spot(make_raw(frequency="7025.0"))]  # 40m, outside 20m window

        q = queue.Queue()
        conn = PotaConnection(q, window_fn=lambda: (14025.0, 50.0), poll_seconds=9999)
        conn.start()
        time.sleep(0.3)
        conn.stop()
        self.assertTrue(q.empty())

    @patch("pota_client.fetch_spots")
    def test_fetch_failure_does_not_crash_thread(self, mock_fetch):
        mock_fetch.side_effect = requests.ConnectionError("no network")

        q = queue.Queue()
        conn = PotaConnection(q, window_fn=lambda: (14025.0, 50.0), poll_seconds=9999)
        conn.start()
        time.sleep(0.3)
        self.assertTrue(conn._thread.is_alive())
        conn.stop()


class TestTwoLaneStorage(unittest.TestCase):
    """Same call+band from different feeds must not collide in BandScope's
    internal store -- see master plan Stage 4D.
    """

    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls._root = tk.Tk()
        except tk.TclError:
            cls._root = None
        else:
            cls._root.withdraw()

    @classmethod
    def tearDownClass(cls):
        if cls._root is not None:
            cls._root.destroy()

    def test_same_call_band_different_feed_both_stored(self):
        if self._root is None:
            self.skipTest("no display available for Tk")
        from bandscope import BandScope

        scope = BandScope(self._root, center_khz=14025.0, bandwidth_khz=50.0)
        cluster_spot = Spot(dx_call="K1ABC", spotter="W1AW", freq_khz=14025.0,
                            band="20m", mode="CW", comment="", time_utc="",
                            feed="DXCLUSTER")
        pota_spot = Spot(dx_call="K1ABC", spotter="", freq_khz=14025.0,
                          band="20m", mode="CW", comment="", time_utc="",
                          feed="POTA")
        scope.add_spots([cluster_spot, pota_spot])
        self.assertEqual(len(scope._spots), 2)
        scope.destroy()


if __name__ == "__main__":
    unittest.main()
