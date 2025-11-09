"""
Properties Module - Quick Asset Saver
======================================
Defines addon preferences, property groups, and configuration management.
Handles user settings like library path, default author, and options.
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import AddonPreferences, PropertyGroup

# Constants
MAX_FILENAME_AFFIX_LENGTH = 32  # Maximum length for prefix/suffix
NONE_LIBRARY_IDENTIFIER = "NONE"  # Identifier for "no library selected"


def build_library_enum_items():
    """
    Build enum items for asset library selection.

    Retrieves user-configured asset libraries from Blender preferences
    and formats them as enum items for property dropdowns.

    Returns:
        list: List of tuples in format (identifier, name, description, icon, index)
              Returns error item if no libraries are configured
    """
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
                NONE_LIBRARY_IDENTIFIER,
                "No Libraries Found",
                "No asset libraries configured in Blender preferences",
                "ERROR",
                0,
            )
        )

    return items


def validate_string_length(value, max_length, property_name):
    """
    Validate and truncate string to maximum length.

    Args:
        value: String value to validate
        max_length: Maximum allowed length
        property_name: Name of property for logging

    Returns:
        str: Validated (possibly truncated) string
    """
    if not value:
        return value

    if len(value) > max_length:
        print(
            f"Warning: {property_name} truncated from {len(value)} to {max_length} characters"
        )
        return value[:max_length]

    return value


class QuickAssetSaverPreferences(AddonPreferences):
    """
    Addon preferences for Quick Asset Saver.

    Stores user preferences including:
    - Default asset library
    - Default metadata (author, description, license, copyright)
    - File organization settings (catalog subfolders)
    - Filename conventions (prefix, suffix, date)
    - Auto-refresh behavior
    """

    bl_idname = __package__

    def get_preference_libraries(self, context):
        """Get asset libraries for preferences dropdown."""
        return build_library_enum_items()

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

    def update_filename_prefix(self, context):
        """Validate filename prefix length."""
        if len(self.filename_prefix) > MAX_FILENAME_AFFIX_LENGTH:
            print(
                f"Warning: Filename prefix too long, truncating to {MAX_FILENAME_AFFIX_LENGTH} characters"
            )
            self.filename_prefix = self.filename_prefix[:MAX_FILENAME_AFFIX_LENGTH]

    def update_filename_suffix(self, context):
        """Validate filename suffix length."""
        if len(self.filename_suffix) > MAX_FILENAME_AFFIX_LENGTH:
            print(
                f"Warning: Filename suffix too long, truncating to {MAX_FILENAME_AFFIX_LENGTH} characters"
            )
            self.filename_suffix = self.filename_suffix[:MAX_FILENAME_AFFIX_LENGTH]

    filename_prefix: StringProperty(
        name="Filename Prefix",
        description=f"Optional prefix to add to all saved asset filenames (e.g., 'MY_' results in MY_AssetName.blend). Max {MAX_FILENAME_AFFIX_LENGTH} characters",
        default="",
        maxlen=MAX_FILENAME_AFFIX_LENGTH,
        update=update_filename_prefix,
    )

    filename_suffix: StringProperty(
        name="Filename Suffix",
        description=f"Optional suffix to add to all saved asset filenames (e.g., '_v1' results in AssetName_v1.blend). Max {MAX_FILENAME_AFFIX_LENGTH} characters",
        default="",
        maxlen=MAX_FILENAME_AFFIX_LENGTH,
        update=update_filename_suffix,
    )

    include_date_in_filename: BoolProperty(
        name="Include Date in Filename",
        description="Append date stamp to filename (e.g., AssetName_2025-11-07.blend)",
        default=False,
    )

    max_bundle_size_mb: IntProperty(
        name="Max Bundle Size (MB)",
        description="Maximum total size in megabytes for bundled assets. Used to prevent memory issues when importing many assets",
        default=4096,  # 4GB default
        min=512,  # Minimum 512MB
        soft_max=16384,  # Soft max 16GB
        subtype="UNSIGNED",
    )

    def draw(self, context):
        """
        Draw the addon preferences UI.

        Displays settings for:
        - Default asset library selection
        - File organization options
        - Filename conventions
        - Default metadata values
        - Auto-refresh behavior

        Args:
            context: Blender context
        """
        layout = self.layout
        layout.label(text="Default Asset Library:")
        asset_row = layout.row()
        split = asset_row.split(factor=0.35)
        split.prop(self, "selected_library", text="")
        split.label(
            text="Add other libraries in the File Paths tab in Blender Preferences."
        )

        if self.selected_library and self.selected_library != NONE_LIBRARY_IDENTIFIER:
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

        layout.separator()
        layout.label(text="Asset Bundling:", icon="PACKAGE")
        layout.prop(self, "max_bundle_size_mb")


class QASSaveProperties(PropertyGroup):
    """
    Property group for asset saving workflow.

    Stores per-asset settings during the save process including:
    - Target library selection
    - Asset metadata (name, author, description, tags, license, copyright)
    - Catalog assignment
    - Conflict resolution strategy
    """

    def get_asset_libraries(self, context):
        """Get asset libraries for property dropdown."""
        return build_library_enum_items()

    def get_catalogs(self, context):
        """
        Get available catalogs from the selected library.

        Reads the blender_assets.cats.txt file from the selected library
        and returns catalog options for the enum property.

        Args:
            context: Blender context

        Returns:
            list: List of catalog enum items (identifier, name, description, icon, index)
                  Returns "Unassigned" if no library selected or no catalogs found
        """
        try:
            from .operators import get_catalogs_from_cdf
        except ImportError as e:
            # If import fails, return default
            print(f"Warning: Could not import get_catalogs_from_cdf: {e}")
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

        library_path = (
            self.selected_library
            if self.selected_library != NONE_LIBRARY_IDENTIFIER
            else None
        )
        if not library_path:
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

        try:
            catalogs, enum_items = get_catalogs_from_cdf(library_path)
            return (
                enum_items
                if enum_items
                else [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]
            )
        except Exception as e:
            print(f"Error loading catalogs from {library_path}: {e}")
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

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
    """
    Get the addon preferences instance.

    Retrieves the Quick Asset Saver addon preferences from Blender's
    addon system. Automatically initializes default library if none selected.

    Args:
        context: Blender context (optional, uses bpy.context if None)

    Returns:
        QuickAssetSaverPreferences: The addon preferences instance

    Note:
        Side effect: Sets selected_library to first available library
        if none is currently selected. This ensures a valid default.
    """
    if context is None:
        context = bpy.context

    preferences = context.preferences
    addon_prefs = preferences.addons[__package__].preferences

    # Initialize default library if none selected
    if (
        not addon_prefs.selected_library
        or addon_prefs.selected_library == NONE_LIBRARY_IDENTIFIER
    ):
        _initialize_default_library(addon_prefs, preferences)

    return addon_prefs


def _initialize_default_library(addon_prefs, preferences):
    """
    Initialize the default library selection.

    Helper function to set the selected_library to the first available
    library if no library is currently selected.

    Args:
        addon_prefs: QuickAssetSaverPreferences instance
        preferences: Blender preferences object
    """
    try:
        if hasattr(preferences, "filepaths") and hasattr(
            preferences.filepaths, "asset_libraries"
        ):
            asset_libs = preferences.filepaths.asset_libraries
            if (
                len(asset_libs) > 0
                and hasattr(asset_libs[0], "path")
                and asset_libs[0].path
            ):
                addon_prefs.selected_library = asset_libs[0].path
    except (AttributeError, IndexError, TypeError) as e:
        print(f"Warning: Could not initialize default library: {e}")


class QAS_BundlerProperties(PropertyGroup):
    """
    Property group for Quick Asset Bundler settings.

    Stores bundling configuration including:
    - Output bundle name
    - Save path for the bundle file
    - Duplicate handling strategy (overwrite vs increment)
    - Catalog file copy option
    """

    output_name: StringProperty(
        name="Bundle Name",
        description="Base name for the bundle file (date will be appended automatically)",
        default="AssetBundle",
    )

    save_path: StringProperty(
        name="Save Path",
        description="Directory where the bundle will be saved",
        default="",
        subtype="DIR_PATH",
    )

    duplicate_mode: EnumProperty(
        name="Duplicate Handling",
        description="How to handle duplicate asset types with the same name during bundling",
        items=[
            (
                "OVERWRITE",
                "Overwrite",
                "Replace duplicate datablocks with newer versions (avoids duplicate materials/textures/etc.)",
            ),
            (
                "INCREMENT",
                "Increment",
                "Rename duplicates with numeric suffix (e.g., Material.001)",
            ),
        ],
        default="OVERWRITE",
    )

    copy_catalog: BoolProperty(
        name="Copy Catalog File",
        description="Copy the asset catalog file alongside the bundle for easy sharing",
        default=True,
    )


classes = (
    QuickAssetSaverPreferences,
    QASSaveProperties,
    QAS_BundlerProperties,
)


def register():
    """
    Register all property classes and add them to WindowManager.

    Registers:
    - QuickAssetSaverPreferences (addon preferences)
    - QASSaveProperties (asset save workflow)
    - QAS_BundlerProperties (asset bundler settings)

    Also attaches property groups to WindowManager for global access.
    """
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.qas_save_props = bpy.props.PointerProperty(
        type=QASSaveProperties
    )
    bpy.types.WindowManager.qas_bundler_props = bpy.props.PointerProperty(
        type=QAS_BundlerProperties
    )


def unregister():
    """
    Unregister all property classes and clean up WindowManager.

    Removes property groups from WindowManager and unregisters classes
    in reverse order to ensure proper cleanup.
    """
    if hasattr(bpy.types.WindowManager, "qas_bundler_props"):
        del bpy.types.WindowManager.qas_bundler_props
    if hasattr(bpy.types.WindowManager, "qas_save_props"):
        del bpy.types.WindowManager.qas_save_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
