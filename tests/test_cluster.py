import queue
import unittest
from unittest.mock import MagicMock, patch

from cluster import ClusterConnection, detect_band, detect_mode, parse_spot


class TestParseValidSpot(unittest.TestCase):
    def test_standard_spot(self):
        line = "DX de W1AW:      14025.0  UA9MA        CW 599                         1234Z"
        spot = parse_spot(line)
        self.assertIsNotNone(spot)
        self.assertEqual(spot.dx_call, "UA9MA")
        self.assertEqual(spot.spotter, "W1AW")
        self.assertAlmostEqual(spot.freq_khz, 14025.0)
        self.assertEqual(spot.time_utc, "1234Z")

    def test_comment_captured(self):
        line = "DX de VE7CC:     7025.0   JA1ABC       CW 599 QSL                     0900Z"
        spot = parse_spot(line)
        self.assertIn("CW 599 QSL", spot.comment)


class TestParseMalformedLine(unittest.TestCase):
    def test_banner_text(self):
        self.assertIsNone(parse_spot("Hello W1AW, this is DX cluster"))

    def test_blank_line(self):
        self.assertIsNone(parse_spot(""))

    def test_non_spot_text(self):
        self.assertIsNone(parse_spot("WWV de W0MU <18>:   SFI=92, A=4, K=1"))


class TestBandDetection(unittest.TestCase):
    def test_20m(self):
        self.assertEqual(detect_band(14025.0), "20m")

    def test_40m(self):
        self.assertEqual(detect_band(7100.0), "40m")

    def test_80m(self):
        self.assertEqual(detect_band(3750.0), "80m")

    def test_out_of_band(self):
        self.assertIsNone(detect_band(99999.0))

    def test_boundary_low(self):
        self.assertEqual(detect_band(14000.0), "20m")

    def test_boundary_high(self):
        self.assertEqual(detect_band(14350.0), "20m")


class TestModeDetection(unittest.TestCase):
    def test_cw(self):
        self.assertEqual(detect_mode("CW 599"), "CW")

    def test_ft8(self):
        self.assertEqual(detect_mode("FT8 -10dB"), "FT8")

    def test_ft4(self):
        self.assertEqual(detect_mode("FT4 -05dB"), "FT4")

    def test_rtty(self):
        self.assertEqual(detect_mode("RTTY 599"), "RTTY")

    def test_ssb(self):
        self.assertEqual(detect_mode("SSB 59"), "SSB")

    def test_usb(self):
        self.assertEqual(detect_mode("USB good signal"), "SSB")

    def test_unknown(self):
        self.assertEqual(detect_mode("nice one!"), "UNKNOWN")


class TestQueuePopulated(unittest.TestCase):
    @patch("cluster.socket.socket")
    def test_valid_spot_queued(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        spot_line = b"DX de W1AW:      14025.0  UA9MA        CW 599                         1234Z\r\n"
        mock_sock.recv.side_effect = [spot_line, b""]
        mock_sock.makefile.return_value.__iter__ = lambda s: iter([
            "DX de W1AW:      14025.0  UA9MA        CW 599                         1234Z"
        ])

        q = queue.Queue()
        conn = ClusterConnection("dx.example.com", 7300, "W1AW", q)
        conn.start()
        try:
            spot = q.get(timeout=1.0)
            self.assertEqual(spot.dx_call, "UA9MA")
        finally:
            conn.stop()


class TestMalformedLinesNotQueued(unittest.TestCase):
    @patch("cluster.socket.socket")
    def test_banner_not_queued(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.makefile.return_value.__iter__ = lambda s: iter([
            "Hello W1AW, welcome to the cluster",
            "Enter your callsign:",
        ])

        q = queue.Queue()
        conn = ClusterConnection("dx.example.com", 7300, "W1AW", q)
        conn.start()
        import time; time.sleep(0.3)
        conn.stop()
        self.assertTrue(q.empty())


class TestThreadStopsCleanly(unittest.TestCase):
    @patch("cluster.socket.socket")
    def test_stop_joins_within_one_second(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.makefile.return_value.__iter__ = lambda s: iter([])

        q = queue.Queue()
        conn = ClusterConnection("dx.example.com", 7300, "W1AW", q)
        conn.start()
        conn.stop()
        self.assertFalse(conn._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
