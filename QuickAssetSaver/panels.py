"""
Panels Module - Quick Asset Saver
==================================
UI integration for panels in the Asset Browser.
Provides a side panel for saving assets to libraries.
"""

import bpy

from .properties import DEBUG_MODE

# UI Constants
MAX_PATH_DISPLAY_LENGTH = 40  # Characters before splitting path display
LARGE_SELECTION_THRESHOLD = 10  # Show warning when selecting more than this many assets

# Excluded library references (built-in libraries)
EXCLUDED_LIBRARY_REFS = ["LOCAL", "CURRENT", "ALL", "ESSENTIALS"]

def debug_print(*args, **kwargs):
    """Print debug messages only when DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)

def is_user_library(context, asset_lib_ref):
    """
    Check if the given library reference is a user-configured library.

    Args:
        context: Blender context
        asset_lib_ref: Library reference string to check

    Returns:
        bool: True if this is a user-configured library
    """
    if not asset_lib_ref or asset_lib_ref in EXCLUDED_LIBRARY_REFS:
        return False

    prefs = context.preferences
    if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
        for lib in prefs.filepaths.asset_libraries:
            if hasattr(lib, "name") and lib.name == asset_lib_ref:
                return True

    return False


class QAS_PT_asset_tools_panel(bpy.types.Panel):
    """Side panel in Asset Browser for Quick Asset Saver."""

    bl_label = "Quick Asset Saver"
    bl_idname = "QAS_PT_asset_tools"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Assets"

    @classmethod
    def poll(cls, context):
        """
        Determine if this panel should be visible.

        Only shows when:
        - In Asset Browser (FILE_BROWSER with ASSETS browse mode)
        - Browsing the Current File library (LOCAL/CURRENT)

        Args:
            context: Blender context

        Returns:
            bool: True if panel should be visible
        """
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False

        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False

        params = space.params
        if not hasattr(params, "asset_library_reference"):
            return False

        asset_lib_ref = params.asset_library_reference
        is_current_file = (
            asset_lib_ref == "LOCAL"
            or asset_lib_ref == "CURRENT"
            or getattr(params, "asset_library_ref", None) == "LOCAL"
        )

        return is_current_file

    def draw(self, context):
        """
        Draw the Quick Asset Saver panel UI.

        Displays:
        - Library selection dropdown
        - Asset metadata fields (name, author, description, etc.)
        - Catalog selection
        - File naming options
        - Target path preview
        - Save button

        Args:
            context: Blender context with selected asset
        """
        layout = self.layout

        from . import properties
        from .properties import get_library_by_identifier
        from .operators import sanitize_name

        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qas_save_props

        box = layout.box()
        box.label(text="Target", icon="ASSET_MANAGER")
        box.prop(props, "selected_library", text="")
        box.label(
            text="Add other libraries in the File Paths tab in Blender Preferences."
        )

        # Get the actual library name and path from identifier
        library_name, library_path_str = (None, None)
        if props.selected_library and props.selected_library != "NONE":
            library_name, library_path_str = get_library_by_identifier(props.selected_library)
            # Debug output
            debug_print(f"[QAS Panel Debug] selected_library: {props.selected_library}")
            debug_print(f"[QAS Panel Debug] library_name: {library_name}")
            debug_print(f"[QAS Panel Debug] library_path_str: {library_path_str}")

        if library_path_str:
            row = box.row()
            # Display the library name and path
            row.label(text=library_path_str)
            row.operator("qas.open_library_folder", text="", icon="FOLDER_REDIRECT")

        layout.separator()

        # Check for timeout on success message (15 seconds)
        import time
        if props.show_success_message and props.success_message_time > 0:
            if time.time() - props.success_message_time > 15.0:
                props.show_success_message = False
                props.success_message_time = 0.0

        if context.asset and hasattr(context, "asset"):
            asset_name = getattr(context.asset, "name", "Unknown")

            if props.last_asset_name != asset_name:
                props.last_asset_name = asset_name
                props.asset_display_name = asset_name
                props.asset_author = prefs.default_author
                props.asset_description = prefs.default_description
                props.asset_license = prefs.default_license
                props.asset_copyright = prefs.default_copyright
                # Clear success message when user selects a different asset
                props.show_success_message = False
                props.success_message_time = 0.0

            if props.asset_display_name:
                props.asset_file_name = sanitize_name(props.asset_display_name)

            outer_box = layout.box()
            outer_box.label(text="Asset Data", icon="ASSET_MANAGER")
            outer_box.label(text=f"  {asset_name}")

            inner_box = outer_box.box()
            inner_box.label(text="Options", icon="SETTINGS")

            inner_box.prop(props, "asset_display_name")
            inner_box.prop(props, "catalog")
            inner_box.prop(props, "asset_author")
            inner_box.prop(props, "asset_description")
            inner_box.prop(props, "asset_license")
            inner_box.prop(props, "asset_copyright")
            inner_box.prop(props, "asset_tags")
            inner_box.prop(props, "conflict_resolution")

            # Show target path preview
            if (
                props.selected_library
                and props.selected_library != "NONE"
                and props.asset_file_name
                and library_path_str
            ):
                from pathlib import Path
                from .operators import get_catalog_path_from_uuid, build_asset_filename

                preview_box = layout.box()
                preview_box.label(text="Path", icon="FILE_FOLDER")

                # Build the preview path with validation to handle invalid inputs gracefully
                try:
                    library_path = Path(library_path_str)
                    target_path = library_path

                    # Add catalog subfolder if enabled
                    if (
                        prefs.use_catalog_subfolders
                        and props.catalog
                        and props.catalog != "UNASSIGNED"
                    ):
                        catalog_path = get_catalog_path_from_uuid(
                            library_path_str, props.catalog
                        )
                        if catalog_path:
                            path_parts = catalog_path.split("/")
                            sanitized_parts = [
                                sanitize_name(part, max_length=64)
                                for part in path_parts
                                if part
                            ]
                            for part in sanitized_parts:
                                target_path = target_path / part

                    # Build the final filename with naming conventions
                    final_filename = build_asset_filename(props.asset_file_name, prefs)
                    full_path = target_path / f"{final_filename}.blend"
                except (OSError, ValueError):
                    # If path construction fails, show error
                    preview_box.label(text="  Error: Invalid path", icon="ERROR")
                    return

                # Display relative path if it fits, otherwise show just the filename with ellipsis
                try:
                    relative_path = full_path.relative_to(library_path)
                    path_str = str(relative_path)
                except (ValueError, OSError):
                    # Path is not relative or other path error
                    path_str = full_path.name

                # Path display in a nested box for visual emphasis
                path_display_box = preview_box.box()
                
                # Split long paths across multiple lines
                if len(path_str) > MAX_PATH_DISPLAY_LENGTH:
                    col = path_display_box.column(align=True)
                    col.scale_y = 0.8
                    # Show library name
                    col.label(text=f"{library_path.name}/", icon="BLANK1")
                    # Show subdirectories
                    if target_path != library_path:
                        try:
                            subpath = target_path.relative_to(library_path)
                            col.label(text=f"  {subpath}/", icon="BLANK1")
                        except ValueError:
                            pass
                    # Show filename
                    col.label(text=f"  {final_filename}.blend", icon="BLANK1")
                else:
                    path_display_box.label(text=path_str, icon="BLANK1")

            layout.separator()
            layout.operator(
                "qas.save_asset_to_library_direct",
                text="Copy to Asset Library",
                icon="EXPORT",
            )
        else:
            box = layout.box()
            box.label(text="No asset selected", icon="INFO")
            box.label(text="Select an asset")
            box.label(text="to save it to your library")
        
        # Show success message after save (outside asset check so it shows when deselected)
        if props.show_success_message:
            layout.separator()
            success_box = layout.box()
            success_box.label(text="Asset saved successfully!", icon="CHECKMARK")
            col = success_box.column(align=True)
            col.label(text="Enjoying Quick Asset Saver?", icon="FUND")
            col.label(text="Consider leaving a rating! It really helps!", icon="BLANK1")


# ============================================================================
# QUICK ASSET BUNDLER PANEL
# ============================================================================


class QAS_PT_asset_bundler(bpy.types.Panel):
    """Panel for bundling multiple assets from a user library."""

    bl_label = "Quick Asset Bundler"
    bl_idname = "QAS_PT_asset_bundler"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Assets"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        """
        Determine if the bundler panel should be visible.

        Only shows when:
        - In Asset Browser (FILE_BROWSER with ASSETS browse mode)
        - Browsing a user-configured library (not LOCAL, CURRENT, ALL, or ESSENTIALS)
        - Library exists in user preferences

        Args:
            context: Blender context

        Returns:
            bool: True if panel should be visible
        """
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False

        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False

        params = space.params
        if not hasattr(params, "asset_library_reference"):
            return False

        asset_lib_ref = params.asset_library_reference

        # Check if this is a user-configured library (not built-in)
        if not is_user_library(context, asset_lib_ref):
            return False

        # Also check the newer API attribute if it exists
        if hasattr(params, "asset_library_ref"):
            newer_ref = params.asset_library_ref
            if not is_user_library(context, newer_ref):
                return False

        return True

    def draw(self, context):
        """
        Draw the Asset Bundler panel UI.

        Displays:
        - Bundle name input
        - Save path selection
        - Duplicate handling mode
        - Catalog copy option
        - Selected assets count
        - Warnings for large selections or problematic paths
        - Bundle button

        Args:
            context: Blender context
        """
        layout = self.layout
        wm = context.window_manager
        props = wm.qas_bundler_props

        # Output name
        layout.label(text="Bundle", icon="PACKAGE")
        row = layout.row()
        row.prop(props, "output_name", text="Name", icon="FILE_BLEND")

        # Save path
        row = layout.row()
        row.prop(props, "save_path", text="File Path", icon="FOLDER_REDIRECT")

        # Duplicate handling
        row = layout.row()
        row.prop(props, "duplicate_mode", text="Overwrite", icon="DUPLICATE")

        layout.prop(props, "copy_catalog")

        # Count selected assets
        selected_count = 0
        if (
            hasattr(context, "selected_asset_files")
            and context.selected_asset_files is not None
        ):
            selected_count = len(context.selected_asset_files)
        elif (
            hasattr(context, "selected_assets") and context.selected_assets is not None
        ):
            selected_count = len(context.selected_assets)
        elif hasattr(context.space_data, "activate_operator_properties"):
            # Fallback: try to get selection from file browser
            try:
                selected_files = [f for f in context.space_data.files if f.select]
                selected_count = len(selected_files)
            except (AttributeError, TypeError):
                selected_count = 0

        # Check for timeout on success message (15 seconds)
        import time
        if props.show_success_message and props.success_message_time > 0:
            if time.time() - props.success_message_time > 15.0:
                props.show_success_message = False
                props.success_message_time = 0.0

        # Clear success message when selection changes
        if selected_count > 0 and props.show_success_message:
            # User has made a new selection, clear the message
            props.show_success_message = False
            props.success_message_time = 0.0

        # Red warning: saving inside library directory
        if props.save_path:
            from pathlib import Path

            try:
                save_path = Path(props.save_path)
            except (OSError, ValueError):
                # Invalid path, skip warning
                save_path = None

            # Get active library path
            if save_path:
                prefs = context.preferences
                if hasattr(prefs, "filepaths") and hasattr(
                    prefs.filepaths, "asset_libraries"
                ):
                    # Safely get params with proper null checks
                    if context.area and hasattr(context.area, "spaces"):
                        active_space = context.area.spaces.active
                        if active_space and hasattr(active_space, "params"):
                            params = active_space.params
                            asset_lib_ref = getattr(params, "asset_library_ref", None)
                            
                            # Also try the older API
                            if not asset_lib_ref and hasattr(params, "asset_library_reference"):
                                asset_lib_ref = params.asset_library_reference

                            if asset_lib_ref:
                                for lib in prefs.filepaths.asset_libraries:
                                    if hasattr(lib, "name") and lib.name == asset_lib_ref:
                                        try:
                                            library_path = Path(lib.path)
                                            if save_path.resolve().is_relative_to(
                                                library_path.resolve()
                                            ):
                                                warning_box = layout.box()
                                                warning_box.alert = True
                                                warning_box.label(
                                                    text="Warning: Save location is inside your configured asset library",
                                                    icon="ERROR",
                                                )
                                                warning_box.label(
                                                    text="This may cause issues with asset management"
                                                )
                                        except (ValueError, OSError):
                                            # Path comparison failed, skip warning
                                            pass
                                        # Found the library, no need to continue
                                        break

        if selected_count > LARGE_SELECTION_THRESHOLD:
            layout.separator()
            warning_box = layout.box()
            row = warning_box.row()
            row.label(text=f"{selected_count} assets selected", icon="INFO")
            warning_box.label(text="Bundling may take a moment,", icon="BLANK1")
            warning_box.label(text="blender will hang until complete.", icon="BLANK1")
            warning_box.scale_y = 0.7

        layout.separator()

        if selected_count > 0:
            row = layout.row(align=True)
            row.scale_y = 1.2
            row.operator(
                "qas.bundle_assets",
                text=f"Bundle {selected_count} Selected Asset{'s' if selected_count != 1 else ''}",
                icon="PACKAGE",
            )
            row.operator("qas.open_bundle_folder", text="", icon="FILE_FOLDER")
        else:
            row = layout.row()
            row.enabled = False
            row.scale_y = 1.2
            row.operator(
                "qas.bundle_assets", text="Bundle Selected Assets", icon="PACKAGE"
            )

            box = layout.box()
            box.label(text="No assets selected", icon="INFO")
            box.label(text="Select assets from the browser", icon="BLANK1")
            box.label(text="to bundle them into one file", icon="BLANK1")
        
        # Show success message after bundle (outside selection check so it shows when deselected)
        if props.show_success_message:
            layout.separator()
            success_box = layout.box()
            success_box.label(text="Bundle created successfully!", icon="CHECKMARK")
            col = success_box.column(align=True)
            col.label(text="Enjoying Quick Asset Saver?", icon="FUND")
            col.label(text="Consider leaving a rating! It really helps!", icon="BLANK1")


class QAS_PT_asset_manage(bpy.types.Panel):
    """Panel for managing assets inside user libraries (move/delete/catalog)."""

    bl_label = "Quick Asset Manager"
    bl_idname = "QAS_PT_asset_manage"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Assets"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False

        params = space.params
        if not hasattr(params, "asset_library_reference"):
            return False

        # Visible when browsing a user-configured library (not LOCAL/CURRENT/ALL/ESSENTIALS)
        asset_lib_ref = params.asset_library_reference
        if not is_user_library(context, asset_lib_ref):
            return False

        if hasattr(params, "asset_library_ref"):
            newer_ref = params.asset_library_ref
            if not is_user_library(context, newer_ref):
                return False

        return True

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        manage = getattr(wm, "qas_manage_props", None)

        # Get selected asset files
        asset_files = None
        if hasattr(context, "selected_asset_files") and context.selected_asset_files is not None:
            asset_files = context.selected_asset_files
        elif hasattr(context, "selected_assets") and context.selected_assets is not None:
            asset_files = context.selected_assets
        elif hasattr(context.space_data, "files"):
            try:
                asset_files = [f for f in context.space_data.files if getattr(f, "select", False)]
            except (AttributeError, TypeError, RuntimeError):
                asset_files = None

        selected_count = len(asset_files) if asset_files else 0

        # ============ EDIT SECTION (top) ============
        if manage:
            layout.label(text="Edit", icon="GREASEPENCIL")
            box = layout.box()
            
            # Auto-populate edit fields when exactly one asset is selected
            if selected_count == 1 and asset_files:
                asset_file = asset_files[0]
                asset_name = getattr(asset_file, "name", "")
                
                # Get current selection identifier to track changes
                current_selection_id = asset_name
                
                # Only update if selection changed (check via a simple tracking attribute)
                last_selection = manage.edit_last_selection
                if last_selection != current_selection_id:
                    # Update the fields with selected asset info
                    manage.edit_asset_name = asset_name
                    
                    # Try to get tags from the asset's metadata
                    tags_str = ""
                    if hasattr(asset_file, "asset_data") and asset_file.asset_data:
                        try:
                            tags = asset_file.asset_data.tags
                            tags_str = ", ".join(tag.name for tag in tags)
                        except (AttributeError, TypeError):
                            pass
                    elif hasattr(asset_file, "metadata") and asset_file.metadata:
                        try:
                            tags = getattr(asset_file.metadata, "tags", None)
                            if tags:
                                tags_str = ", ".join(tag.name for tag in tags)
                        except (AttributeError, TypeError):
                            pass
                    
                    manage.edit_asset_tags = tags_str
                    manage.edit_last_selection = current_selection_id
            elif selected_count != 1:
                # Clear tracking when not exactly one selected
                if manage.edit_last_selection:
                    manage.edit_last_selection = ""
            
            box.prop(manage, "edit_asset_name", text="Name")
            box.prop(manage, "edit_asset_tags", text="Tags")
            edit_row = box.row()
            edit_row.enabled = selected_count == 1
            edit_row.operator("qas.edit_selected_asset", text="Apply", icon="CHECKMARK")

        layout.separator()

        # ============ MOVE SECTION (middle) ============
        if manage:
            layout.label(text="Move", icon="ASSET_MANAGER")
            box = layout.box()
            box.prop(manage, "move_target_library", text="Library")
            box.prop(manage, "move_target_catalog", text="Catalog")
            box.prop(manage, "move_conflict_resolution", text="Overwrite")

            # Move button
            move_row = box.row()
            move_row.scale_y = 1.2
            move_row.enabled = selected_count > 0
            move_row.operator("qas.move_selected_to_library", text="Move", icon="EXPORT")


class QAS_MT_asset_context_menu(bpy.types.Menu):
    """Quick Asset Saver context menu items for the Asset Browser."""
    bl_idname = "QAS_MT_asset_context_menu"
    bl_label = "Quick Asset Saver"

    def draw(self, context):
        layout = self.layout
        layout.operator("qas.delete_selected_assets", text="Remove Asset from Library", icon="TRASH")


def draw_asset_context_menu(self, context):
    """Append Quick Asset Saver options to the Asset Browser context menu."""
    # Only show in Asset Browser
    if not hasattr(context, "space_data") or context.space_data.type != "FILE_BROWSER":
        return
    if getattr(context.space_data, "browse_mode", None) != "ASSETS":
        return
    
    layout = self.layout
    layout.separator()
    layout.operator("qas.swap_selected_with_asset", text="Replace Selected Objects", icon="FILE_REFRESH")
    layout.operator("qas.delete_selected_assets", text="Remove Asset from Library", icon="TRASH")


classes = (
    QAS_PT_asset_tools_panel,
    QAS_PT_asset_manage,
    QAS_PT_asset_bundler,
    QAS_MT_asset_context_menu,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Append to Asset Browser context menu
    bpy.types.ASSETBROWSER_MT_context_menu.append(draw_asset_context_menu)


def unregister():
    # Remove from Asset Browser context menu
    bpy.types.ASSETBROWSER_MT_context_menu.remove(draw_asset_context_menu)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
