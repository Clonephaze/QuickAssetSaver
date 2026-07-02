"""
Tests that the addon registers cleanly and all expected types/operators exist.
These run after the addon is registered by blender_test_runner.py.
"""
import unittest
import bpy


class TestWindowManagerProps(unittest.TestCase):
    """All four PropertyGroups must be attached to WindowManager after registration."""

    def test_qam_save_props_exists(self):
        self.assertTrue(hasattr(bpy.types.WindowManager, "qam_save_props"))

    def test_qam_bundler_props_exists(self):
        self.assertTrue(hasattr(bpy.types.WindowManager, "qam_bundler_props"))

    def test_qam_manage_props_exists(self):
        self.assertTrue(hasattr(bpy.types.WindowManager, "qam_manage_props"))

    def test_qam_metadata_edit_exists(self):
        self.assertTrue(hasattr(bpy.types.WindowManager, "qam_metadata_edit"))

    def test_save_props_accessible_on_wm_instance(self):
        wm = bpy.context.window_manager
        props = wm.qam_save_props
        self.assertIsNotNone(props)

    def test_bundler_props_accessible_on_wm_instance(self):
        wm = bpy.context.window_manager
        self.assertIsNotNone(wm.qam_bundler_props)

    def test_manage_props_accessible_on_wm_instance(self):
        wm = bpy.context.window_manager
        self.assertIsNotNone(wm.qam_manage_props)

    def test_metadata_edit_accessible_on_wm_instance(self):
        wm = bpy.context.window_manager
        self.assertIsNotNone(wm.qam_metadata_edit)


class TestSavePropsFields(unittest.TestCase):
    """Save PropertyGroup must expose the fields the panel and operator use."""

    def setUp(self):
        self.props = bpy.context.window_manager.qam_save_props

    def test_has_selected_library(self):
        self.assertTrue(hasattr(self.props, "selected_library"))

    def test_has_catalog(self):
        self.assertTrue(hasattr(self.props, "catalog"))

    def test_has_auto_create_catalog(self):
        self.assertTrue(hasattr(self.props, "auto_create_catalog"))

    def test_auto_create_catalog_default_false(self):
        self.assertFalse(self.props.auto_create_catalog)

    def test_has_asset_display_name(self):
        self.assertTrue(hasattr(self.props, "asset_display_name"))

    def test_has_asset_file_name(self):
        self.assertTrue(hasattr(self.props, "asset_file_name"))

    def test_has_conflict_resolution(self):
        self.assertTrue(hasattr(self.props, "conflict_resolution"))

    def test_conflict_resolution_default_increment(self):
        self.assertEqual(self.props.conflict_resolution, "INCREMENT")

    def test_has_show_success_message(self):
        self.assertTrue(hasattr(self.props, "show_success_message"))

    def test_has_metadata_fields(self):
        for field in ("asset_description", "asset_author", "asset_license", "asset_copyright"):
            with self.subTest(field=field):
                self.assertTrue(hasattr(self.props, field))


class TestBundlerPropsFields(unittest.TestCase):
    def setUp(self):
        self.props = bpy.context.window_manager.qam_bundler_props

    def test_has_output_name(self):
        self.assertTrue(hasattr(self.props, "output_name"))

    def test_output_name_default_nonempty(self):
        self.assertTrue(self.props.output_name)

    def test_has_save_path(self):
        self.assertTrue(hasattr(self.props, "save_path"))

    def test_has_duplicate_mode(self):
        self.assertTrue(hasattr(self.props, "duplicate_mode"))

    def test_has_copy_catalog(self):
        self.assertTrue(hasattr(self.props, "copy_catalog"))


class TestManagePropsFields(unittest.TestCase):
    def setUp(self):
        self.props = bpy.context.window_manager.qam_manage_props

    def test_has_move_target_library(self):
        self.assertTrue(hasattr(self.props, "move_target_library"))

    def test_has_move_target_catalog(self):
        self.assertTrue(hasattr(self.props, "move_target_catalog"))

    def test_has_move_conflict_resolution(self):
        self.assertTrue(hasattr(self.props, "move_conflict_resolution"))


class TestMetadataEditFields(unittest.TestCase):
    def setUp(self):
        self.props = bpy.context.window_manager.qam_metadata_edit

    def test_has_edit_name(self):
        self.assertTrue(hasattr(self.props, "edit_name"))

    def test_has_edit_tags(self):
        self.assertTrue(hasattr(self.props, "edit_tags"))

    def test_has_source_file(self):
        self.assertTrue(hasattr(self.props, "source_file"))

    def test_has_changes_method(self):
        self.assertTrue(callable(getattr(self.props, "has_changes", None)))

    def test_has_changes_false_when_synced(self):
        # orig_* and edit_* are equal by default → no changes
        self.assertFalse(self.props.has_changes())


class TestOperatorsRegistered(unittest.TestCase):
    EXPECTED_OPS = [
        ("qam", "save_asset_to_library_direct"),
        ("qam", "open_library_folder"),
        ("qam", "bundle_assets"),
        ("qam", "open_bundle_folder"),
        ("qam", "move_selected_to_library"),
        ("qam", "delete_selected_assets"),
        ("qam", "swap_selected_with_asset"),
        ("qam", "apply_metadata_changes"),
        ("qam", "toggle_edit_mode"),
        ("qam", "tag_add"),
        ("qam", "tag_remove"),
    ]

    def test_all_operators_registered(self):
        for module, name in self.EXPECTED_OPS:
            with self.subTest(op=f"{module}.{name}"):
                mod = getattr(bpy.ops, module, None)
                self.assertIsNotNone(mod, f"bpy.ops.{module} not found")
                self.assertTrue(
                    hasattr(mod, name),
                    f"Operator {module}.{name} not registered"
                )
