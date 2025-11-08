"""
Properties Module - Quick Asset Saver
======================================
Defines addon preferences, property groups, and configuration management.
Handles user settings like library path, default author, and options.
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences, PropertyGroup


class QuickAssetSaverPreferences(AddonPreferences):
    """Addon preferences for Quick Asset Saver."""

    bl_idname = __package__

    def get_preference_libraries(self, context):
        items = []
        prefs = bpy.context.preferences
        if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
            asset_libs = prefs.filepaths.asset_libraries
            for idx, lib in enumerate(asset_libs):
                if hasattr(lib, "name") and hasattr(lib, "path") and lib.path:
                    items.append(
                        (
                            lib.path,
                            lib.name,
                            f"Save to: {lib.path}",
                            "ASSET_MANAGER",
                            idx,
                        )
                    )

        if not items:
            items.append(
                (
                    "NONE",
                    "No Libraries Found",
                    "No asset libraries configured in Blender",
                    "ERROR",
                    0,
                )
            )

        return items

    selected_library: EnumProperty(
        name="Default Asset Library",
        description="Default library where assets will be saved",
        items=get_preference_libraries,
    )

    default_author: StringProperty(
        name="Default Author",
        description="Default author name to embed in saved asset metadata",
        default="",
    )

    auto_refresh: BoolProperty(
        name="Auto-Refresh Asset Browser",
        description="Automatically refresh the Asset Browser after saving an asset",
        default=True,
    )

    default_description: StringProperty(
        name="Default Description",
        description="Default description text for new assets",
        default="",
    )

    default_license: StringProperty(
        name="Default License",
        description="Default license for new assets",
        default="",
    )

    default_copyright: StringProperty(
        name="Default Copyright",
        description="Default copyright notice for new assets",
        default="",
    )

    use_catalog_subfolders: BoolProperty(
        name="Organize by Catalog",
        description="Automatically create subfolders based on catalog structure (e.g., Materials/Metal). Keeps your library organized",
        default=True,
    )

    filename_prefix: StringProperty(
        name="Filename Prefix",
        description="Optional prefix to add to all saved asset filenames (e.g., 'MY_' results in MY_AssetName.blend)",
        default="",
        maxlen=32,
    )

    filename_suffix: StringProperty(
        name="Filename Suffix",
        description="Optional suffix to add to all saved asset filenames (e.g., '_v1' results in AssetName_v1.blend)",
        default="",
        maxlen=32,
    )

    include_date_in_filename: BoolProperty(
        name="Include Date in Filename",
        description="Append date stamp to filename (e.g., AssetName_2025-11-07.blend)",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Default Asset Library:")
        asset_row = layout.row()
        split = asset_row.split(factor=0.35)
        split.prop(self, "selected_library", text="")
        split.label(text="Add other libraries in the File Paths tab in Blender Preferences.")

        if self.selected_library and self.selected_library != "NONE":
            row = layout.row()
            row.label(text=f"Path: {self.selected_library}", icon="FILE_FOLDER")

        layout.separator()
        layout.label(text="Organization:")
        layout.prop(self, "use_catalog_subfolders")

        layout.separator()
        layout.label(text="Filename Conventions:", icon="FILE_BLEND")
        layout.prop(self, "filename_prefix")
        layout.prop(self, "filename_suffix")
        layout.prop(self, "include_date_in_filename")

        layout.separator()
        layout.label(text="Default Metadata:", icon="FILE_CACHE")
        layout.prop(self, "default_author")
        layout.prop(self, "default_description")
        layout.prop(self, "default_license")
        layout.prop(self, "default_copyright")

        layout.separator()
        layout.prop(self, "auto_refresh")


class QASSaveProperties(PropertyGroup):
    """Property group for asset saving workflow."""

    def get_asset_libraries(self, context):
        items = []
        prefs = bpy.context.preferences
        if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
            asset_libs = prefs.filepaths.asset_libraries
            for idx, lib in enumerate(asset_libs):
                if hasattr(lib, "name") and hasattr(lib, "path") and lib.path:
                    items.append(
                        (
                            lib.path,
                            lib.name,
                            f"Save to: {lib.path}",
                            "ASSET_MANAGER",
                            idx,
                        )
                    )

        if not items:
            items.append(
                ("NONE", "No Libraries", "No asset libraries configured", "ERROR", 0)
            )

        return items

    def get_catalogs(self, context):
        from .operators import get_catalogs_from_cdf

        library_path = self.selected_library if self.selected_library != "NONE" else None
        if not library_path:
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

        catalogs, enum_items = get_catalogs_from_cdf(library_path)
        return enum_items if enum_items else [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

    selected_library: EnumProperty(
        name="Target Library",
        description="Asset library to save to",
        items=get_asset_libraries,
    )

    last_asset_name: StringProperty(
        name="Last Asset Name",
        description="Internal tracking of last selected asset to prevent overwriting user edits",
        default="",
        options={"SKIP_SAVE", "HIDDEN"},
    )

    asset_display_name: StringProperty(
        name="Asset Name",
        description="Display name of the asset as it will appear in the library",
        default="",
    )

    asset_file_name: StringProperty(
        name="File Name",
        description="Sanitized filename (read-only, auto-generated from asset name)",
        default="",
        options={"SKIP_SAVE"},
    )

    catalog: EnumProperty(
        name="Catalog",
        description="Catalog to assign the asset to",
        items=get_catalogs,
    )

    asset_description: StringProperty(
        name="Description",
        description="Optional description for the asset metadata",
        default="",
    )

    asset_tags: StringProperty(
        name="Tags",
        description="Comma-separated tags for the asset",
        default="",
    )

    asset_author: StringProperty(
        name="Author",
        description="Author name for this asset",
        default="",
    )

    asset_license: StringProperty(
        name="License",
        description="License for this asset",
        default="",
    )

    asset_copyright: StringProperty(
        name="Copyright",
        description="Copyright notice for this asset",
        default="",
    )

    conflict_resolution: EnumProperty(
        name="If File Exists",
        description="What to do if a file with the same name already exists",
        items=[
            ("INCREMENT", "Increment", "Save as Name_001.blend, etc.", "DUPLICATE", 0),
            ("OVERWRITE", "Overwrite", "Replace the existing file", "FILE_REFRESH", 1),
            ("CANCEL", "Cancel", "Don't save if file exists", "CANCEL", 2),
        ],
        default="INCREMENT",
    )


def get_addon_preferences(context=None):
    """Get the addon preferences."""
    if context is None:
        context = bpy.context

    preferences = context.preferences
    addon_prefs = preferences.addons[__package__].preferences

    if not addon_prefs.selected_library or addon_prefs.selected_library == "NONE":
        if hasattr(preferences, "filepaths") and hasattr(preferences.filepaths, "asset_libraries"):
            asset_libs = preferences.filepaths.asset_libraries
            if len(asset_libs) > 0 and hasattr(asset_libs[0], "path"):
                addon_prefs.selected_library = asset_libs[0].path

    return addon_prefs


classes = (
    QuickAssetSaverPreferences,
    QASSaveProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.qas_save_props = bpy.props.PointerProperty(type=QASSaveProperties)


def unregister():
    if hasattr(bpy.types.WindowManager, "qas_save_props"):
        del bpy.types.WindowManager.qas_save_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
