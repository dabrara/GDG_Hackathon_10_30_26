"""Tests for RAM-based Gemma model selection."""
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "select_model.py"
spec = importlib.util.spec_from_file_location("select_model", MODULE)
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class ModelSelectionTests(unittest.TestCase):
    def test_ram_bands(self):
        cases = [
            (4, "gemma4:e2b"),
            (15.9, "gemma4:e2b"),
            (16, "gemma4:e4b"),
            (23.9, "gemma4:e4b"),
            (24, "gemma4:12b"),
            (31.9, "gemma4:12b"),
            (32, "gemma4:26b"),
            (47.9, "gemma4:26b"),
            (48, "gemma4:31b"),
            (128, "gemma4:31b"),
        ]
        for ram, expected in cases:
            with self.subTest(ram=ram):
                self.assertEqual(selector.choose_model(ram), expected)

    def test_every_option_is_gemma4(self):
        self.assertTrue(all(tag.startswith("gemma4:") for _, tag, _ in selector.MODELS))
        self.assertFalse(any("cloud" in tag for _, tag, _ in selector.MODELS))


if __name__ == "__main__":
    unittest.main()
