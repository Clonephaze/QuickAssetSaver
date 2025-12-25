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
DEBUG_MODE = False  # Set to True for debug output

# Cache for enum items to prevent garbage collection
# Blender's EnumProperty callbacks can have strings GC'd before display
_LIBRARY_ENUM_CACHE = []


def debug_print(*args, **kwargs):
    """Print debug messages only when DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)


def get_library_path_by_name(library_name):
    """
    Get the library path for a given library name.

    Args:
        library_name: Name of the asset library

    Returns:
        str: Library path or None if not found
    """
    if not library_name or library_name == NONE_LIBRARY_IDENTIFIER:
        return None

    prefs = bpy.context.preferences
    if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
        for lib in prefs.filepaths.asset_libraries:
            if hasattr(lib, "name") and lib.name == library_name:
                return lib.path
    return None


def get_library_by_identifier(identifier):
    """
    Get library name and path from an ASCII-safe identifier.
    
    Args:
        identifier: ASCII-safe identifier (e.g., "LIB_0", "LIB_1")
    
    Returns:
        tuple: (library_name, library_path) or (None, None) if not found
    """
    if not identifier or identifier == NONE_LIBRARY_IDENTIFIER:
        return None, None
    
    # Extract index from identifier
    if identifier.startswith("LIB_"):
        try:
            index = int(identifier.split("_")[1])
            prefs = bpy.context.preferences
            if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
                asset_libs = prefs.filepaths.asset_libraries
                if 0 <= index < len(asset_libs):
                    lib = asset_libs[index]
                    if hasattr(lib, "name") and hasattr(lib, "path"):
                        # Safely get name and path, handling encoding issues
                        try:
                            lib_name = str(lib.name) if lib.name else f"Library_{index}"
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            lib_name = f"Library_{index}"
                        
                        try:
                            lib_path = str(lib.path) if lib.path else None
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            lib_path = None
                        
                        return lib_name, lib_path
        except (ValueError, IndexError, AttributeError) as e:
            debug_print(f"Error getting library by identifier '{identifier}': {e}")
    
    return None, None


def build_library_enum_items():
    """
    Build enum items for asset library selection.

    Retrieves user-configured asset libraries from Blender preferences
    and formats them as enum items for property dropdowns.

    Note:
        Uses ASCII-safe identifiers (LIB_0, LIB_1, etc.) to avoid Unicode
        encoding issues in the identifier field.
        Display names (labels) CAN contain Unicode - Chinese, etc. is fine.
        Only the identifier must be ASCII-safe.
        
        Items are cached in _LIBRARY_ENUM_CACHE to prevent garbage collection
        before Blender can display them (known Blender API issue).

    Returns:
        list: List of tuples in format (identifier, name, description, icon, index)
              Returns error item if no libraries are configured
    """
    global _LIBRARY_ENUM_CACHE
    
    items = []
    try:
        prefs = bpy.context.preferences

        if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
            asset_libs = prefs.filepaths.asset_libraries
            for idx, lib in enumerate(asset_libs):
                try:
                    if hasattr(lib, "name") and hasattr(lib, "path") and lib.path:
                        # Get library name - handle potential encoding issues gracefully
                        try:
                            lib_name = lib.name if lib.name else f"Library {idx + 1}"
                        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError):
                            lib_name = f"Library {idx + 1}"
                        
                        try:
                            lib_path = lib.path if lib.path else "<unknown>"
                        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError):
                            lib_path = "<unknown>"
                        
                        # Use the actual library name as display name
                        # EnumProperty labels fully support Unicode (Chinese, etc.)
                        # Only the identifier needs to be ASCII-safe
                        display_name = lib_name
                        
                        debug_print(f"[QAS Enum Debug] Adding library {idx}: id=LIB_{idx}, name={display_name}, path={lib_path}")
                        
                        items.append(
                            (
                                f"LIB_{idx}",      # ASCII-safe identifier (required)
                                display_name,      # Display name - Unicode OK!
                                f"Save to: {lib_path}",  # Full path in tooltip
                                "ASSET_MANAGER",
                                idx,
                            )
                        )
                except (AttributeError, UnicodeDecodeError, TypeError) as e:
                    debug_print(f"Error processing library {idx}: {e}")
                    continue
    except Exception as e:
        print(f"Error building library enum items: {e}")

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

    # Cache items to prevent garbage collection before Blender displays them
    _LIBRARY_ENUM_CACHE = items
    debug_print(f"[QAS Enum Debug] Cached {len(_LIBRARY_ENUM_CACHE)} library items")
    return _LIBRARY_ENUM_CACHE


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
            # Get the actual library name and path from identifier
            library_name, library_path = get_library_by_identifier(self.selected_library)
            if library_path:
                row = layout.row()
                display_text = f"{library_name}: {library_path}" if library_name else library_path
                row.label(text=display_text, icon="FILE_FOLDER")

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
        Handles errors gracefully to prevent UI crashes.

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
            debug_print(f"Warning: Could not import get_catalogs_from_cdf: {e}")
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

        try:
            # Get the actual library path from the identifier
            library_identifier = (
                self.selected_library
                if self.selected_library != NONE_LIBRARY_IDENTIFIER
                else None
            )
            if not library_identifier:
                return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

            library_name, library_path = get_library_by_identifier(library_identifier)
            if not library_path:
                return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

            catalogs, enum_items = get_catalogs_from_cdf(library_path)
            return (
                enum_items
                if enum_items
                else [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]
            )
        except (UnicodeDecodeError, UnicodeEncodeError) as e:
            debug_print(f"Unicode error loading catalogs: {e}")
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]
        except Exception as e:
            debug_print(f"Error loading catalogs: {e}")
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
        name="Name",
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
        name="Overwrite",
        description="What to do if a file with the same name already exists",
        items=[
            ("INCREMENT", "Increment", "Save as Name_001.blend, etc.", "DUPLICATE", 0),
            ("OVERWRITE", "Overwrite", "Replace the existing file", "FILE_REFRESH", 1),
            ("CANCEL", "Cancel", "Don't save if file exists", "CANCEL", 2),
        ],
        default="INCREMENT",
    )

    show_success_message: BoolProperty(
        name="Show Success Message",
        description="Internal flag to show thank you message after save",
        default=False,
        options={"SKIP_SAVE", "HIDDEN"},
    )

    success_message_time: bpy.props.FloatProperty(
        name="Success Message Time",
        description="Timestamp when success message was shown",
        default=0.0,
        options={"SKIP_SAVE", "HIDDEN"},
    )


def _migrate_old_library_format(addon_prefs, preferences):
    """
    Migrate old path-based or name-based library settings to new identifier format.

    Old versions stored library paths or names directly in selected_library.
    New versions store ASCII-safe identifiers (LIB_0, LIB_1) to avoid Unicode issues.
    This function detects and converts old format to new format.

    Args:
        addon_prefs: QuickAssetSaverPreferences instance
        preferences: Blender preferences object
    """
    try:
        current_value = addon_prefs.selected_library
        
        # Check if current value is already in new format
        if current_value and current_value.startswith("LIB_"):
            return  # Already migrated
        
        # Check if current value is a built-in identifier
        if current_value in (NONE_LIBRARY_IDENTIFIER, "LOCAL", "CURRENT", "ALL", "ESSENTIALS"):
            return
        
        if current_value:
            # Try to find matching library by name or path
            if hasattr(preferences, "filepaths") and hasattr(
                preferences.filepaths, "asset_libraries"
            ):
                asset_libs = preferences.filepaths.asset_libraries
                
                # First try to match by name
                for idx, lib in enumerate(asset_libs):
                    try:
                        if hasattr(lib, "name") and lib.name == current_value:
                            # Found by name
                            addon_prefs.selected_library = f"LIB_{idx}"
                            print(f"Migrated library setting to: LIB_{idx} ({lib.name})")
                            return
                    except (AttributeError, UnicodeDecodeError):
                        continue
                
                # Then try to match by path
                for idx, lib in enumerate(asset_libs):
                    try:
                        if hasattr(lib, "path") and lib.path:
                            from pathlib import Path
                            old_path = Path(current_value).resolve()
                            lib_path = Path(lib.path).resolve()
                            if old_path == lib_path:
                                addon_prefs.selected_library = f"LIB_{idx}"
                                print(f"Migrated library setting to: LIB_{idx} ({lib.name})")
                                return
                    except (OSError, ValueError, TypeError, UnicodeDecodeError):
                        continue
                
                # If we couldn't migrate, use default
                print("Warning: Could not migrate old library format. Using default library.")
                _initialize_default_library(addon_prefs, preferences)
    except Exception as e:
        print(f"Warning during library format migration: {e}")
        # Continue anyway - we'll use default library


def get_addon_preferences(context=None):
    """
    Get the addon preferences instance.

    Retrieves the Quick Asset Saver addon preferences from Blender's
    addon system. Automatically initializes default library if none selected.
    Handles migration from old path-based format to new identifier-based format.

    Args:
        context: Blender context (optional, uses bpy.context if None)

    Returns:
        QuickAssetSaverPreferences: The addon preferences instance

    Note:
        Side effect: Sets selected_library to first available library
        if none is currently selected. This ensures a valid default.
        Also performs automatic migration from old storage formats.
    """
    if context is None:
        context = bpy.context

    preferences = context.preferences
    addon_prefs = preferences.addons[__package__].preferences

    # Try to migrate old format if needed
    _migrate_old_library_format(addon_prefs, preferences)

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
    library if no library is currently selected. Uses ASCII-safe identifier.

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
                and hasattr(asset_libs[0], "name")
                and asset_libs[0].name
            ):
                # Use ASCII-safe identifier instead of name/path
                addon_prefs.selected_library = "LIB_0"
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

    show_success_message: BoolProperty(
        name="Show Success Message",
        description="Internal flag to show thank you message after bundle",
        default=False,
        options={"SKIP_SAVE", "HIDDEN"},
    )

    success_message_time: bpy.props.FloatProperty(
        name="Success Message Time",
        description="Timestamp when success message was shown",
        default=0.0,
        options={"SKIP_SAVE", "HIDDEN"},
    )


class QAS_ManageProperties(PropertyGroup):
    """
    Property group for managing existing assets in libraries.

    Supports moving selected assets between libraries/catalogs,
    renaming assets, updating tags, and swapping scene objects.
    """

    def get_target_libraries(self, context):
        return build_library_enum_items()

    def get_target_catalogs(self, context):
        try:
            from .operators import get_catalogs_from_cdf
        except ImportError:
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

        try:
            identifier = (
                self.move_target_library
                if self.move_target_library and self.move_target_library != NONE_LIBRARY_IDENTIFIER
                else None
            )
            if not identifier:
                return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

            library_name, library_path = get_library_by_identifier(identifier)
            if not library_path:
                return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

            _, enum_items = get_catalogs_from_cdf(library_path)
            return enum_items if enum_items else [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]
        except (RuntimeError, OSError, UnicodeDecodeError):
            return [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

    # Edit properties (top of panel)
    edit_asset_name: StringProperty(
        name="Name",
        description="New name for the selected asset (leave empty to keep current)",
        default="",
    )

    edit_asset_tags: StringProperty(
        name="Tags",
        description="Comma-separated tags (replaces existing tags, leave empty to keep current)",
        default="",
    )

    # Move properties (middle of panel)
    move_target_library: EnumProperty(
        name="Target Library",
        description="Library to move the selected assets into",
        items=get_target_libraries,
    )

    move_target_catalog: EnumProperty(
        name="Target Catalog",
        description="Catalog to assign to moved assets",
        items=get_target_catalogs,
    )

    move_conflict_resolution: EnumProperty(
        name="If File Exists",
        description="What to do if a file with the same name exists at destination",
        items=[
            ("INCREMENT", "Increment", "Save as Name_001.blend, etc.", "DUPLICATE", 0),
            ("OVERWRITE", "Overwrite", "Replace the existing file", "FILE_REFRESH", 1),
            ("CANCEL", "Skip", "Skip files that already exist", "CANCEL", 2),
        ],
        default="INCREMENT",
    )

    # Swap properties
    swap_link_mode: EnumProperty(
        name="Import Mode",
        description="How to import the swapped asset",
        items=[
            ("APPEND", "Append", "Copy the asset data into the file", "APPEND_BLEND", 0),
            ("LINK", "Link", "Link to the original asset file", "LINK_BLEND", 1),
        ],
        default="APPEND",
    )

    # Internal tracking for edit field auto-population
    edit_last_selection: StringProperty(
        name="",
        description="Internal: tracks last selected asset for edit auto-fill",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'},
    )


classes = (
    QuickAssetSaverPreferences,
    QASSaveProperties,
    QAS_BundlerProperties,
    QAS_ManageProperties,
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
    bpy.types.WindowManager.qas_manage_props = bpy.props.PointerProperty(
        type=QAS_ManageProperties
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
    if hasattr(bpy.types.WindowManager, "qas_manage_props"):
        del bpy.types.WindowManager.qas_manage_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
