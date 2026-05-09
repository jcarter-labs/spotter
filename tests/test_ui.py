import queue
import unittest

from cluster import Spot
from scope_utils import drain_queue, extract_prefix, format_freq


def make_spot(**kwargs):
    defaults = dict(
        dx_call="UA9MA", spotter="W1AW", freq_khz=14025.0,
        band="20m", mode="CW", comment="CW 599", time_utc="1234Z",
        dx_dxcc="Russia", dx_continent="AS",
        spotter_dxcc="United States", spotter_continent="NA",
    )
    defaults.update(kwargs)
    return Spot(**defaults)


class TestFormatFreq(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(format_freq(14025.0), "14025.0 kHz")

    def test_round_number(self):
        self.assertEqual(format_freq(7000.0), "7000.0 kHz")

    def test_decimal(self):
        self.assertEqual(format_freq(14067.5), "14067.5 kHz")


class TestExtractPrefix(unittest.TestCase):
    def test_single_letter(self):
        self.assertEqual(extract_prefix("W1AW"), "W")

    def test_two_letter(self):
        self.assertEqual(extract_prefix("UA9MA"), "UA")

    def test_dl_prefix(self):
        self.assertEqual(extract_prefix("DL1ABC"), "DL")

    def test_ja_prefix(self):
        self.assertEqual(extract_prefix("JA1ABC"), "JA")


class TestDrainQueue(unittest.TestCase):
    def test_returns_all_items(self):
        q = queue.Queue()
        spots = [make_spot(dx_call=f"K{i}X") for i in range(3)]
        for s in spots:
            q.put(s)
        result = drain_queue(q)
        self.assertEqual(len(result), 3)

    def test_empty_queue_returns_empty_list(self):
        self.assertEqual(drain_queue(queue.Queue()), [])

    def test_queue_empty_after_drain(self):
        q = queue.Queue()
        q.put(make_spot())
        drain_queue(q)
        self.assertTrue(q.empty())

    def test_order_preserved(self):
        q = queue.Queue()
        calls = ["W1AW", "UA9MA", "JA1ABC"]
        for c in calls:
            q.put(make_spot(dx_call=c))
        result = drain_queue(q)
        self.assertEqual([s.dx_call for s in result], calls)


if __name__ == "__main__":
    unittest.main()
