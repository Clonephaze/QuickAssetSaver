"""Tests for QuickAssetSaver/constants.py"""
import unittest
from QuickAssetSaver.constants import (
    VIRTUAL_LIBRARY_REFS,
    PROTECTED_LIBRARY_REFS,
    EXCLUDED_LIBRARY_REFS,
    COMPANION_FOLDER_GROUPS,
    COMPANION_FOLDER_NAMES,
    THUMBNAIL_EXTENSIONS,
    METADATA_EXTENSIONS,
    MIN_BLEND_FILE_SIZE,
    MAX_INCREMENTAL_FILES,
    LARGE_SELECTION_WARNING_THRESHOLD,
    DEFAULT_MAX_BUNDLE_SIZE_MB,
    LARGE_BUNDLE_WARNING_MB,
)


class TestLibraryRefSets(unittest.TestCase):
    def test_virtual_refs_is_frozenset(self):
        self.assertIsInstance(VIRTUAL_LIBRARY_REFS, frozenset)

    def test_protected_refs_is_frozenset(self):
        self.assertIsInstance(PROTECTED_LIBRARY_REFS, frozenset)

    def test_excluded_refs_is_frozenset(self):
        self.assertIsInstance(EXCLUDED_LIBRARY_REFS, frozenset)

    def test_local_in_virtual(self):
        self.assertIn("LOCAL", VIRTUAL_LIBRARY_REFS)

    def test_current_in_virtual(self):
        self.assertIn("CURRENT", VIRTUAL_LIBRARY_REFS)

    def test_all_in_virtual(self):
        self.assertIn("ALL", VIRTUAL_LIBRARY_REFS)

    def test_essentials_in_protected(self):
        self.assertIn("ESSENTIALS", PROTECTED_LIBRARY_REFS)

    def test_essentials_not_in_virtual(self):
        self.assertNotIn("ESSENTIALS", VIRTUAL_LIBRARY_REFS)

    def test_excluded_is_union_of_virtual_and_protected(self):
        self.assertEqual(EXCLUDED_LIBRARY_REFS, VIRTUAL_LIBRARY_REFS | PROTECTED_LIBRARY_REFS)

    def test_virtual_refs_subset_of_excluded(self):
        self.assertTrue(VIRTUAL_LIBRARY_REFS.issubset(EXCLUDED_LIBRARY_REFS))

    def test_protected_refs_subset_of_excluded(self):
        self.assertTrue(PROTECTED_LIBRARY_REFS.issubset(EXCLUDED_LIBRARY_REFS))


class TestCompanionFolders(unittest.TestCase):
    def test_companion_folder_groups_is_list(self):
        self.assertIsInstance(COMPANION_FOLDER_GROUPS, list)

    def test_companion_folder_names_is_list(self):
        self.assertIsInstance(COMPANION_FOLDER_NAMES, list)

    def test_companion_folder_names_flat(self):
        # Names list should be flat strings, not nested lists
        for name in COMPANION_FOLDER_NAMES:
            self.assertIsInstance(name, str)

    def test_textures_variants_present(self):
        self.assertIn("textures", COMPANION_FOLDER_NAMES)
        self.assertIn("Textures", COMPANION_FOLDER_NAMES)

    def test_companion_names_matches_flattened_groups(self):
        expected = [name for group in COMPANION_FOLDER_GROUPS for name in group]
        self.assertEqual(COMPANION_FOLDER_NAMES, expected)


class TestFileExtensions(unittest.TestCase):
    def test_thumbnail_extensions_all_start_with_dot(self):
        for ext in THUMBNAIL_EXTENSIONS:
            self.assertTrue(ext.startswith("."), f"{ext!r} should start with '.'")

    def test_metadata_extensions_all_start_with_dot(self):
        for ext in METADATA_EXTENSIONS:
            self.assertTrue(ext.startswith("."), f"{ext!r} should start with '.'")

    def test_png_in_thumbnails(self):
        self.assertIn(".png", THUMBNAIL_EXTENSIONS)

    def test_json_in_metadata(self):
        self.assertIn(".json", METADATA_EXTENSIONS)


class TestNumerics(unittest.TestCase):
    def test_min_blend_file_size_positive(self):
        self.assertGreater(MIN_BLEND_FILE_SIZE, 0)

    def test_max_incremental_files_large(self):
        self.assertGreaterEqual(MAX_INCREMENTAL_FILES, 999)

    def test_large_selection_threshold_positive(self):
        self.assertGreater(LARGE_SELECTION_WARNING_THRESHOLD, 0)

    def test_default_bundle_size_at_least_512mb(self):
        self.assertGreaterEqual(DEFAULT_MAX_BUNDLE_SIZE_MB, 512)

    def test_large_bundle_warning_less_than_default(self):
        self.assertLess(LARGE_BUNDLE_WARNING_MB, DEFAULT_MAX_BUNDLE_SIZE_MB)

    def test_large_bundle_warning_is_75_percent(self):
        self.assertEqual(LARGE_BUNDLE_WARNING_MB, int(DEFAULT_MAX_BUNDLE_SIZE_MB * 0.75))
