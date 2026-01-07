# Quick Asset Saver — Changes

## Overview
- Reworked UI to feel native to Blender’s Asset Browser.
- Consolidated left-side tools and moved saving into Blender’s right-side Asset panel.
- Added robust support for multi-asset .blend files and metadata editing for external assets.

## Panels
- Left Side (TOOLS):
  - Added Quick Asset Manager panel to bundle and move assets in user libraries. See [QuickAssetSaver/panels.py](QuickAssetSaver/panels.py).
  - Added Current File save hint panel (QAS_PT_save_hint) that explains the new location of the save workflow and shows your keybind to open the right-side panel.
- Right Side (TOOL_PROPS):
  - Asset Metadata (QAS_PT_asset_metadata): Editable fields for external assets; preserves native behavior for local assets.
  - Asset Tags (QAS_PT_asset_tags): Custom UIList tag editor for external assets; uses Blender’s native tag editor for local assets.
  - Actions (QAS_PT_asset_actions): Apply Changes, Move, and Remove Asset actions for external assets.
  - Save to Library (QAS_PT_save_to_library): Library + Catalog selector and Copy button for local assets.

## Operators
- Added QAS_OT_apply_metadata_changes: Safely writes metadata back to the source .blend for a specific asset.
- Added QAS_OT_tag_add / QAS_OT_tag_remove: Manage tag rows in the custom UIList.
- Updated QAS_OT_save_asset_to_library_direct: Uses native `asset_data.tags`; smart conflict handling with dialog when needed.
- Updated QAS_OT_move_selected_to_library: Bulk move selected assets with Library/Catalog targeting.
- Updated QAS_OT_delete_selected_assets: Safe delete across multi-asset files.
- Updated QAS_OT_swap_selected_with_asset: Replaces selected scene objects using Blender’s Import Settings.
- Removed QAS_OT_edit_selected_asset (legacy left-panel edit path).

## Properties
- Added QAS_MetadataEditProperties: Tracks editable name/description/license/copyright/author + CollectionProperty tags.
- Added QAS_TagItem: Single-tag property group used by the UIList editor.
- Trimmed QAS_ManageProperties: Removed legacy edit fields; retained move-target properties and conflict policy.
- Continued QASSaveProperties for local asset save workflow (name, author, license, description, catalog, library, etc.).

## Behavior & Fixes
- Multi-asset file safety: All edit/move/delete operations target the specific asset within multi-asset .blend files.
- Tag editing parity: Local assets use Blender’s native tag editor; external assets use the custom UIList stored in `qas_metadata_edit`.
- "All Libraries" support: Panels decide between Save vs Edit based on `asset.local_id` (local → Save panel, external → Actions panel), independent of library filter.
- Source path resolution fix: Extracts only the `.blend` path when Blender returns a full internal path (e.g., `file.blend/Material/Asset`), preventing "Source file not found" errors. Implemented in `_get_asset_source_path()`.
- Asset library identifiers: UI uses ASCII-safe identifiers (e.g., `LIB_0`); always resolve via `get_library_by_identifier`.
- Catalogs: Enumerated via `get_catalogs_from_cdf` reading `blender_assets.cats.txt`; optional subfolder creation per preferences.
- Conflict strategy: Prefer auto-incremented filenames; overwrite/cancel only when explicitly chosen or confirmed.

## UX Notes
- Save workflow moved: Use the right-side Asset panel (TOOL_PROPS). The left-side hint panel shows your keybind to open it (default often "N").
- Path previews: Long paths truncated gracefully in the Save panel; invalid inputs handled without crashes.
- Success messages: Optional "thank you" messages gated behind preferences.

## Safety & I/O
- Pre-write checks: Operators verify target directories exist and are writable.
- Atomic writes: Use temp files then move; restore packed assets on error.
- Dependency packing: Images/fonts/sounds/movie clips temporarily packed and remapped; volumes warned when not packable.

## Packaging
- Built extension artifact confirmed via Blender’s `extension build` command.

## Files Touched (high-level)
- Panels: [QuickAssetSaver/panels.py](QuickAssetSaver/panels.py)
- Operators: [QuickAssetSaver/operators.py](QuickAssetSaver/operators.py)
- Properties: [QuickAssetSaver/properties.py](QuickAssetSaver/properties.py)
- Manifest: [QuickAssetSaver/blender_manifest.toml](QuickAssetSaver/blender_manifest.toml)

## Migration Guidance
- For existing users: Look for the "Quick Asset Save" hint in Current File to open the new right-side Save panel.
- External assets: Edit metadata and tags in the right-side panels, then Apply Changes to persist to the source file.
- Bulk operations: Use the left-side Quick Asset Manager to bundle or move many assets at once.
