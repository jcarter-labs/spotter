import json
import os
import tempfile
import unittest

from config import Config


class TestDefaultConfigCreated(unittest.TestCase):
    def test_defaults_loaded_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            cfg = Config(path)
            cfg.load()
            self.assertIn("host", cfg.data)
            self.assertIn("port", cfg.data)
            self.assertIn("dedup_minutes", cfg.data)
            self.assertIn("filter", cfg.data)


class TestSaveAndReload(unittest.TestCase):
    def test_values_persist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            cfg = Config(path)
            cfg.load()
            cfg.data["host"] = "dx.example.com"
            cfg.data["port"] = 7300
            cfg.data["callsign"] = "W1AW"
            cfg.save()

            cfg2 = Config(path)
            cfg2.load()
            self.assertEqual(cfg2.data["host"], "dx.example.com")
            self.assertEqual(cfg2.data["port"], 7300)
            self.assertEqual(cfg2.data["callsign"], "W1AW")


class TestPartialConfigMergesDefaults(unittest.TestCase):
    def test_missing_keys_filled_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with open(path, "w") as f:
                json.dump({"host": "dx.example.com"}, f)

            cfg = Config(path)
            cfg.load()
            self.assertEqual(cfg.data["host"], "dx.example.com")
            self.assertIn("port", cfg.data)
            self.assertIn("dedup_minutes", cfg.data)


if __name__ == "__main__":
    unittest.main()
