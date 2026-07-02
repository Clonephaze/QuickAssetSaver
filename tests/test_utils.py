"""Tests for QuickAssetSaver/operators/utils.py"""
import unittest
import tempfile
from pathlib import Path
from QuickAssetSaver.operators.utils import (
    sanitize_name,
    build_asset_filename,
    increment_filename,
)
from tests.fixtures import MockPrefs


class TestSanitizeName(unittest.TestCase):
    def test_plain_name_unchanged(self):
        self.assertEqual(sanitize_name("MyAsset"), "MyAsset")

    def test_forward_slash_replaced(self):
        result = sanitize_name("Materials/Metal")
        self.assertNotIn("/", result)

    def test_backslash_replaced(self):
        result = sanitize_name("Assets\\Metal")
        self.assertNotIn("\\", result)

    def test_windows_invalid_chars_replaced(self):
        for ch in '<>:"|?*':
            result = sanitize_name(f"file{ch}name")
            self.assertNotIn(ch, result, f"char {ch!r} should be replaced")

    def test_path_traversal_blocked(self):
        result = sanitize_name("../../etc/passwd")
        self.assertNotIn("/", result)
        self.assertNotIn("..", result.split("_")[0])  # leading traversal gone

    def test_empty_string_returns_asset(self):
        self.assertEqual(sanitize_name(""), "asset")

    def test_none_returns_asset(self):
        self.assertEqual(sanitize_name(None), "asset")

    def test_non_string_returns_asset(self):
        self.assertEqual(sanitize_name(42), "asset")

    def test_respects_max_length(self):
        long_name = "a" * 300
        self.assertLessEqual(len(sanitize_name(long_name)), 128)

    def test_custom_max_length(self):
        result = sanitize_name("a" * 200, max_length=64)
        self.assertLessEqual(len(result), 64)

    def test_strips_leading_spaces(self):
        result = sanitize_name("  asset")
        self.assertFalse(result.startswith(" "))

    def test_strips_trailing_dots(self):
        result = sanitize_name("asset...")
        self.assertFalse(result.endswith("."))

    def test_unicode_passthrough(self):
        # Unicode letters are valid — should not be stripped
        result = sanitize_name("Matériaux")
        self.assertIn("Mat", result)

    def test_only_invalid_chars_returns_asset(self):
        result = sanitize_name(".....")
        self.assertEqual(result, "asset")


class TestBuildAssetFilename(unittest.TestCase):
    def _make_prefs(self, prefix="", suffix="", date=False):
        p = MockPrefs()
        p.filename_prefix = prefix
        p.filename_suffix = suffix
        p.include_date_in_filename = date
        return p

    def test_no_affixes(self):
        result = build_asset_filename("MyAsset", self._make_prefs())
        self.assertEqual(result, "MyAsset")

    def test_with_prefix(self):
        result = build_asset_filename("MyAsset", self._make_prefs(prefix="LIB"))
        self.assertTrue(result.startswith("LIB"))
        self.assertIn("MyAsset", result)

    def test_with_suffix(self):
        result = build_asset_filename("MyAsset", self._make_prefs(suffix="v1"))
        self.assertTrue(result.endswith("v1"))
        self.assertIn("MyAsset", result)

    def test_with_prefix_and_suffix(self):
        result = build_asset_filename("Asset", self._make_prefs(prefix="P", suffix="S"))
        self.assertIn("Asset", result)
        self.assertIn("P", result)
        self.assertIn("S", result)

    def test_date_appended(self):
        result = build_asset_filename("Asset", self._make_prefs(date=True))
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2}")

    def test_empty_prefix_ignored(self):
        result = build_asset_filename("Asset", self._make_prefs(prefix=""))
        self.assertFalse(result.startswith("_"))

    def test_returns_string(self):
        result = build_asset_filename("Asset", self._make_prefs())
        self.assertIsInstance(result, str)


class TestIncrementFilename(unittest.TestCase):
    def test_no_conflict_returns_base(self):
        with tempfile.TemporaryDirectory() as d:
            result = increment_filename(Path(d), "asset", ".blend")
            self.assertEqual(result.name, "asset.blend")

    def test_conflict_increments_to_001(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "asset.blend").touch()
            result = increment_filename(p, "asset", ".blend")
            self.assertEqual(result.name, "asset_001.blend")

    def test_multiple_conflicts_increment_sequentially(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "asset.blend").touch()
            (p / "asset_001.blend").touch()
            (p / "asset_002.blend").touch()
            result = increment_filename(p, "asset", ".blend")
            self.assertEqual(result.name, "asset_003.blend")

    def test_returns_path_object(self):
        with tempfile.TemporaryDirectory() as d:
            result = increment_filename(Path(d), "asset", ".blend")
            self.assertIsInstance(result, Path)

    def test_result_is_inside_base_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            result = increment_filename(p, "asset", ".blend")
            self.assertEqual(result.parent.resolve(), p.resolve())

    def test_handles_string_base_path(self):
        with tempfile.TemporaryDirectory() as d:
            # Should accept string paths too
            result = increment_filename(d, "asset", ".blend")
            self.assertIsInstance(result, Path)
