"""Tests for catalog CDF read/write operations."""
import unittest
import uuid
from QuickAssetSaver.operators.catalog import (
    get_catalogs_from_cdf,
    get_catalog_path_from_uuid,
    create_catalog_entry,
    clear_catalog_cache,
)
from tests.fixtures import TempLibrary


class TestGetCatalogsFromCdf(unittest.TestCase):
    def setUp(self):
        clear_catalog_cache()

    def tearDown(self):
        clear_catalog_cache()

    def test_returns_empty_dict_for_missing_cdf(self):
        with TempLibrary() as lib:
            lib.cdf_path.unlink()  # remove the CDF
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertEqual(catalogs, {})

    def test_first_enum_item_is_always_unassigned(self):
        with TempLibrary() as lib:
            _, items = get_catalogs_from_cdf(str(lib.path))
            self.assertEqual(items[0][0], "UNASSIGNED")

    def test_parses_catalog_path_and_uuid(self):
        u = str(uuid.uuid4())
        with TempLibrary() as lib:
            lib.cdf_path.write_text(f"VERSION 1\n\n{u}:Materials/Metal:Metal\n", encoding="utf-8")
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertIn("Materials/Metal", catalogs)
            self.assertEqual(catalogs["Materials/Metal"], u)

    def test_parses_multiple_entries(self):
        u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())
        with TempLibrary() as lib:
            lib.cdf_path.write_text(
                f"VERSION 1\n\n{u1}:Materials:Materials\n{u2}:Characters:Characters\n",
                encoding="utf-8",
            )
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertIn("Materials", catalogs)
            self.assertIn("Characters", catalogs)
            self.assertEqual(len(catalogs), 2)

    def test_skips_comment_lines(self):
        u = str(uuid.uuid4())
        with TempLibrary() as lib:
            lib.cdf_path.write_text(
                f"VERSION 1\n# This is a comment\n{u}:Materials:Materials\n",
                encoding="utf-8",
            )
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertNotIn("# This is a comment", catalogs)
            self.assertIn("Materials", catalogs)

    def test_skips_version_line(self):
        with TempLibrary() as lib:
            lib.cdf_path.write_text("VERSION 1\n\n", encoding="utf-8")
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertNotIn("VERSION 1", catalogs)

    def test_skips_malformed_lines(self):
        u = str(uuid.uuid4())
        with TempLibrary() as lib:
            lib.cdf_path.write_text(
                f"VERSION 1\n\njust_a_word_with_no_colon\n{u}:Good:Good\n",
                encoding="utf-8",
            )
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertIn("Good", catalogs)
            self.assertNotIn("just_a_word_with_no_colon", catalogs)

    def test_handles_nested_catalog_path(self):
        u = str(uuid.uuid4())
        with TempLibrary() as lib:
            lib.cdf_path.write_text(
                f"VERSION 1\n\n{u}:Characters/Heroes/Mages:Mages\n",
                encoding="utf-8",
            )
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertIn("Characters/Heroes/Mages", catalogs)


class TestGetCatalogPathFromUuid(unittest.TestCase):
    def setUp(self):
        clear_catalog_cache()

    def tearDown(self):
        clear_catalog_cache()

    def test_resolves_uuid_to_path(self):
        with TempLibrary(catalogs=["Materials/Metal"]) as lib:
            u = lib.uuid_for("Materials/Metal")
            result = get_catalog_path_from_uuid(str(lib.path), u)
            self.assertEqual(result, "Materials/Metal")

    def test_returns_none_for_unknown_uuid(self):
        with TempLibrary() as lib:
            result = get_catalog_path_from_uuid(str(lib.path), str(uuid.uuid4()))
            self.assertIsNone(result)

    def test_returns_none_for_unassigned_string(self):
        with TempLibrary() as lib:
            result = get_catalog_path_from_uuid(str(lib.path), "UNASSIGNED")
            self.assertIsNone(result)

    def test_returns_none_for_empty_uuid(self):
        with TempLibrary() as lib:
            result = get_catalog_path_from_uuid(str(lib.path), "")
            self.assertIsNone(result)

    def test_returns_none_for_invalid_uuid_format(self):
        with TempLibrary() as lib:
            result = get_catalog_path_from_uuid(str(lib.path), "not-a-uuid")
            self.assertIsNone(result)

    def test_returns_none_when_cdf_missing(self):
        with TempLibrary() as lib:
            lib.cdf_path.unlink()
            result = get_catalog_path_from_uuid(str(lib.path), str(uuid.uuid4()))
            self.assertIsNone(result)


class TestCreateCatalogEntry(unittest.TestCase):
    def setUp(self):
        clear_catalog_cache()

    def tearDown(self):
        clear_catalog_cache()

    def test_creates_entry_and_returns_valid_uuid(self):
        with TempLibrary() as lib:
            result = create_catalog_entry(str(lib.path), "Materials")
            uuid.UUID(result)  # raises ValueError if invalid

    def test_entry_appears_in_cdf(self):
        with TempLibrary() as lib:
            result_uuid = create_catalog_entry(str(lib.path), "Materials/Metal")
            content = lib.cdf_path.read_text(encoding="utf-8")
            self.assertIn("Materials/Metal", content)
            self.assertIn(result_uuid, content)

    def test_creates_cdf_when_missing(self):
        with TempLibrary() as lib:
            lib.cdf_path.unlink()
            self.assertFalse(lib.cdf_path.exists())
            create_catalog_entry(str(lib.path), "NewCatalog")
            self.assertTrue(lib.cdf_path.exists())

    def test_returns_same_uuid_for_duplicate_path(self):
        with TempLibrary() as lib:
            first = create_catalog_entry(str(lib.path), "Materials/Metal")
            clear_catalog_cache()
            second = create_catalog_entry(str(lib.path), "Materials/Metal")
            self.assertEqual(first, second)

    def test_preserves_existing_entries(self):
        with TempLibrary(catalogs=["Existing"]) as lib:
            existing_uuid = lib.uuid_for("Existing")
            create_catalog_entry(str(lib.path), "NewCatalog")
            content = lib.cdf_path.read_text(encoding="utf-8")
            self.assertIn("Existing", content)
            self.assertIn(existing_uuid, content)
            self.assertIn("NewCatalog", content)

    def test_display_name_is_last_path_component(self):
        with TempLibrary() as lib:
            create_catalog_entry(str(lib.path), "Characters/Heroes")
            content = lib.cdf_path.read_text(encoding="utf-8")
            # Line format: UUID:Characters/Heroes:Heroes
            self.assertIn(":Heroes", content)

    def test_nested_path_stored_correctly(self):
        with TempLibrary() as lib:
            result_uuid = create_catalog_entry(str(lib.path), "A/B/C")
            clear_catalog_cache()
            resolved = get_catalog_path_from_uuid(str(lib.path), result_uuid)
            self.assertEqual(resolved, "A/B/C")

    def test_multiple_distinct_catalogs(self):
        with TempLibrary() as lib:
            u1 = create_catalog_entry(str(lib.path), "Materials")
            clear_catalog_cache()
            u2 = create_catalog_entry(str(lib.path), "Characters")
            self.assertNotEqual(u1, u2)
            clear_catalog_cache()
            catalogs, _ = get_catalogs_from_cdf(str(lib.path))
            self.assertIn("Materials", catalogs)
            self.assertIn("Characters", catalogs)
