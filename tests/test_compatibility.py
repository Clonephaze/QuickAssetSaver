"""Tests for QuickAssetSaver/compatibility.py — uses mock contexts, no real Blender UI needed."""
import unittest
from tests.fixtures import MockContext, MockSpace, make_asset_browser_context
from QuickAssetSaver.constants import EXCLUDED_LIBRARY_REFS, PROTECTED_LIBRARY_REFS


class TestIsAssetBrowserActive(unittest.TestCase):
    def setUp(self):
        from QuickAssetSaver import compatibility
        self.fn = compatibility.is_asset_browser_active

    def test_true_for_valid_asset_browser(self):
        ctx = MockContext(MockSpace())
        self.assertTrue(self.fn(ctx))

    def test_false_when_space_data_is_none(self):
        ctx = MockContext(None)
        self.assertFalse(self.fn(ctx))

    def test_false_for_view3d(self):
        ctx = MockContext(MockSpace(space_type="VIEW_3D"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_node_editor(self):
        ctx = MockContext(MockSpace(space_type="NODE_EDITOR"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_files_browse_mode(self):
        ctx = MockContext(MockSpace(browse_mode="FILES"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_empty_browse_mode(self):
        ctx = MockContext(MockSpace(browse_mode=""))
        self.assertFalse(self.fn(ctx))


class TestIsProtectedLibrary(unittest.TestCase):
    def setUp(self):
        from QuickAssetSaver import compatibility
        self.fn = compatibility.is_protected_library

    def test_true_for_essentials(self):
        ctx = MockContext(MockSpace(lib_ref="ESSENTIALS"))
        self.assertTrue(self.fn(ctx))

    def test_false_for_user_library(self):
        ctx = MockContext(MockSpace(lib_ref="My Assets"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_local(self):
        ctx = MockContext(MockSpace(lib_ref="LOCAL"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_no_params(self):
        space = MockSpace()
        space.params = None
        ctx = MockContext(space)
        self.assertFalse(self.fn(ctx))

    def test_false_for_none_space(self):
        ctx = MockContext(None)
        self.assertFalse(self.fn(ctx))


class TestIsUserLibrary(unittest.TestCase):
    def setUp(self):
        from QuickAssetSaver import compatibility
        self.fn = compatibility.is_user_library

    def test_true_for_named_library(self):
        ctx = MockContext(MockSpace(lib_ref="My Assets"))
        self.assertTrue(self.fn(ctx))

    def test_false_for_local(self):
        ctx = MockContext(MockSpace(lib_ref="LOCAL"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_current(self):
        ctx = MockContext(MockSpace(lib_ref="CURRENT"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_all(self):
        ctx = MockContext(MockSpace(lib_ref="ALL"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_essentials(self):
        ctx = MockContext(MockSpace(lib_ref="ESSENTIALS"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_none_params(self):
        space = MockSpace()
        space.params = None
        ctx = MockContext(space)
        self.assertFalse(self.fn(ctx))

    def test_all_excluded_refs_return_false(self):
        for ref in EXCLUDED_LIBRARY_REFS:
            ctx = MockContext(MockSpace(lib_ref=ref))
            self.assertFalse(
                self.fn(ctx),
                f"is_user_library should be False for excluded ref {ref!r}"
            )


class TestIsOnlineLibrary(unittest.TestCase):
    def setUp(self):
        from QuickAssetSaver import compatibility
        self.fn = compatibility.is_online_library

    def test_false_when_no_type_attr(self):
        # No asset_library_type attribute → default False (safe)
        ctx = MockContext(MockSpace(lib_ref="My Library"))
        self.assertFalse(self.fn(ctx))

    def test_false_for_custom_type(self):
        from tests.fixtures import MockParams
        space = MockSpace()
        space.params = MockParams("My Library")
        space.params.asset_library_type = "CUSTOM"
        ctx = MockContext(space)
        self.assertFalse(self.fn(ctx))

    def test_false_for_none_space(self):
        ctx = MockContext(None)
        self.assertFalse(self.fn(ctx))
