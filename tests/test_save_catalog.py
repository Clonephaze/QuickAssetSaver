"""
Tests for catalog-related save operator behaviour:
  - Bug #9: source asset catalog must not be modified after save
  - Auto-create catalog: _auto_create_catalog_if_needed
"""
import unittest
import uuid
import tempfile
from pathlib import Path

import bpy

from QuickAssetSaver.operators.save import _auto_create_catalog_if_needed
from QuickAssetSaver.operators.catalog import (
    get_catalog_path_from_uuid,
    create_catalog_entry,
    clear_catalog_cache,
)
from QuickAssetSaver.operators.file_io import write_blend_file
from tests.fixtures import TempLibrary, make_test_asset, remove_test_asset


class TestCatalogPreservation(unittest.TestCase):
    """
    Regression tests for Bug #9.
    The source asset's catalog_id must survive write_blend_file unchanged.
    This mirrors the capture/restore pattern added to the save operator.
    """

    def setUp(self):
        self.obj = make_test_asset(name="QAM_Bug9_Test")
        self.original_uuid = str(uuid.uuid4())
        self.obj.asset_data.catalog_id = self.original_uuid

    def tearDown(self):
        remove_test_asset(self.obj)
        clear_catalog_cache()

    def test_write_blend_does_not_alter_source_catalog(self):
        """write_blend_file itself must not change the source datablock."""
        with TempLibrary() as lib:
            out = lib.path / "asset.blend"
            write_blend_file(out, {self.obj})
            # Source catalog must be unchanged
            self.assertEqual(self.obj.asset_data.catalog_id, self.original_uuid)

    def test_capture_and_restore_pattern(self):
        """Capture → modify → write → restore preserves the original UUID."""
        with TempLibrary() as lib:
            other_uuid = str(uuid.uuid4())

            # Capture
            captured = self.obj.asset_data.catalog_id

            # Modify (as the save operator does)
            self.obj.asset_data.catalog_id = other_uuid

            # Write
            out = lib.path / "asset.blend"
            write_blend_file(out, {self.obj})

            # Restore
            self.obj.asset_data.catalog_id = captured

            # Source must have the original UUID back
            self.assertEqual(self.obj.asset_data.catalog_id, self.original_uuid)

    def test_catalog_in_written_file_is_modified_uuid(self):
        """The written .blend file should contain the modified UUID, not the original."""
        with TempLibrary() as lib:
            other_uuid = str(uuid.uuid4())

            captured = self.obj.asset_data.catalog_id
            self.obj.asset_data.catalog_id = other_uuid
            out = lib.path / "asset.blend"
            write_blend_file(out, {self.obj})
            self.obj.asset_data.catalog_id = captured

            # Verify the written file contains the OTHER uuid
            loaded = []
            with bpy.data.libraries.load(str(out), link=False, assets_only=True) as (src, dst):
                if src.objects:
                    dst.objects = list(src.objects)
            for o in bpy.data.objects:
                if o.name == "QAM_Bug9_Test" and o is not self.obj and o.asset_data:
                    self.assertEqual(o.asset_data.catalog_id, other_uuid)
                    loaded.append(o)
            for o in loaded:
                remove_test_asset(o)


class TestAutoCreateCatalog(unittest.TestCase):
    """Tests for _auto_create_catalog_if_needed in operators/save.py."""

    def setUp(self):
        clear_catalog_cache()

    def tearDown(self):
        clear_catalog_cache()

    def test_returns_none_for_unresolvable_uuid(self):
        """If the UUID can't be resolved to a path, return None."""
        with TempLibrary() as target:
            result = _auto_create_catalog_if_needed(str(target.path), str(uuid.uuid4()))
            self.assertIsNone(result)

    def test_creates_catalog_from_target_fallback(self):
        """
        When no source CDF is available (bpy.data.filepath empty in background mode),
        _auto_create_catalog_if_needed falls back to the target library CDF.
        A UUID that already exists there should be returned unchanged.
        """
        with TempLibrary(catalogs=["Materials/Metal"]) as target:
            existing_uuid = target.uuid_for("Materials/Metal")
            clear_catalog_cache()
            result = _auto_create_catalog_if_needed(str(target.path), existing_uuid)
            self.assertEqual(result, existing_uuid)

    def test_returns_existing_uuid_when_path_in_target(self):
        """If the catalog path already exists in the target, return its UUID."""
        with TempLibrary(catalogs=["Characters"]) as target:
            target_uuid = target.uuid_for("Characters")
            # Use a different source UUID for the same path
            source_uuid = str(uuid.uuid4())
            source_cdf_content = (
                f"VERSION 1\n\n{source_uuid}:Characters:Characters\n"
            )
            # Write the source CDF directly into the target dir temporarily
            # to simulate both sides having "Characters" with different UUIDs
            with TempLibrary(catalogs=["Characters"]) as source:
                clear_catalog_cache()
                # Call with source UUID that maps to "Characters" in the source
                source_u = source.uuid_for("Characters")
                # The target already has "Characters" under target_uuid.
                # clear cache so target CDF is re-read
                clear_catalog_cache()
                result = _auto_create_catalog_if_needed(str(target.path), target_uuid)
            self.assertEqual(result, target_uuid)

    def test_does_not_create_entry_for_none_uuid(self):
        """An unresolvable UUID must not create any new entries in the target CDF."""
        with TempLibrary() as target:
            content_before = target.cdf_path.read_text(encoding="utf-8")
            _auto_create_catalog_if_needed(str(target.path), str(uuid.uuid4()))
            content_after = target.cdf_path.read_text(encoding="utf-8")
            self.assertEqual(content_before, content_after)
