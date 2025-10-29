# Quick Asset Saver - Blender Addon

**Version:** 1.0.0  
**Blender Version:** 5.0+  
**Category:** Asset Management

## Overview

Quick Asset Saver enables you to save assets from the Current File Asset Browser directly to a user asset library folder as individual .blend files. Each asset is saved with full metadata support including catalogs, descriptions, tags, and author information.

## Features

- **One-Click Asset Export**: Right-click any asset in Current File and save it to your library
- **Full Metadata Support**: Preserve author, description, tags, and catalog assignments
- **Smart File Handling**: Automatic filename sanitization and conflict resolution (increment/overwrite)
- **Catalog Integration**: Parse and use existing `blender_assets.cats.txt` catalog definitions
- **Atomic File Writes**: Safe saving with temporary files to prevent corruption
- **Auto-Refresh**: Automatically refresh Asset Browser after saving (configurable)
- **Cross-Platform**: Works on Windows, macOS, and Linux with proper path handling
- **One File Per Asset**: Keeps asset files granular for fast indexing and easy management

## Installation

### Method 1: Standard Addon Installation

1. Download or clone this repository
2. If downloaded as ZIP, extract it to get the `QuickSave` folder
3. Open Blender 5.0+
4. Go to `Edit > Preferences > Add-ons`
5. Click `Install...` at the top right
6. Navigate to the `QuickSave` folder and select it (or select the ZIP file)
7. Enable the addon by checking the checkbox next to "Asset Management: Quick Asset Saver"

### Method 2: Manual Installation

1. Locate your Blender scripts folder:
   - **Windows**: `C:\Users\[YourName]\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\`
   - **macOS**: `~/Library/Application Support/Blender/5.0/scripts/addons/`
   - **Linux**: `~/.config/blender/5.0/scripts/addons/`

2. Copy the entire `QuickSave` folder into the `addons` directory
3. Restart Blender
4. Go to `Edit > Preferences > Add-ons`
5. Search for "Quick Asset Saver" and enable it

## Configuration

After installation, configure the addon in preferences:

1. Go to `Edit > Preferences > Add-ons`
2. Find "Quick Asset Saver" and expand it
3. Set the following:
   - **Asset Library Path**: Folder where assets will be saved (auto-detected or defaults to "Easy Add Assets" in your home folder)
   - **Default Author**: Your name to embed in asset metadata
   - **Auto-Refresh Asset Browser**: Toggle automatic refresh after saving
   - **Pack Images by Default**: Pack external images into .blend files

## Usage

### Basic Workflow

1. **Create an Asset** in your current blend file:
   - Create a material, object, node group, etc.
   - Mark it as an asset (Outliner or Properties panel)
   - Optionally add preview and metadata

2. **Open Asset Browser**:
   - Switch an area to Asset Browser
   - Select "Current File" from the library dropdown

3. **Save to Library**:
   - Right-click the asset you want to save
   - Select "Save to Library"
   - A dialog appears with options:
     - **Asset Name**: Pre-filled, edit if needed
     - **Catalog**: Choose from existing catalogs or "Unassigned"
     - **Author**: Your name (from preferences)
     - **Description**: Optional description
     - **Tags**: Comma-separated tags
     - **If File Exists**: Choose to increment, overwrite, or cancel

4. **Confirm**: Click OK to save the asset as `AssetName.blend` in your library

5. **Verify**: Open a new Blender file, browse your asset library, and the new asset should appear

### Conflict Resolution

If a file with the same name exists:
- **Increment**: Saves as `Name_001.blend`, `Name_002.blend`, etc.
- **Overwrite**: Replaces the existing file
- **Cancel**: Aborts if file exists

### Catalog Management

The addon reads your library's `blender_assets.cats.txt` file to populate the catalog dropdown. To use catalogs:

1. Create a `blender_assets.cats.txt` file in your asset library folder (if not exists)
2. Format: `UUID:catalog/path:CatalogName` (one per line)
3. Example:
   ```
   VERSION 1
   # UUID:catalog_path:catalog_name
   a1b2c3d4-e5f6-7890-abcd-ef1234567890:Materials/Metal:Metal Materials
   b2c3d4e5-f6a7-8901-bcde-f12345678901:Materials/Wood:Wood Materials
   ```

## Manual QA Checklist

Follow these steps to verify the addon works correctly:

### Test 1: Basic Asset Save

1. ✓ Open Blender 5.0 or higher
2. ✓ Create a new material
3. ✓ Assign it to the default cube
4. ✓ In the Shader Editor or Outliner, mark the material as an asset
5. ✓ Open Asset Browser and select "Current File"
6. ✓ Verify the material appears
7. ✓ Right-click the material → Select "Save to Library"
8. ✓ Dialog appears with pre-filled name
9. ✓ Edit name to "TestMaterial"
10. ✓ Set author and description
11. ✓ Click OK
12. ✓ Check for success message in status bar
13. ✓ Navigate to your asset library folder
14. ✓ Verify `TestMaterial.blend` file exists

### Test 2: Asset Import in New File

1. ✓ Close Blender (or File > New)
2. ✓ Open a fresh Blender file
3. ✓ Open Asset Browser
4. ✓ Select your configured asset library
5. ✓ Verify "TestMaterial" appears in the browser
6. ✓ Check that preview thumbnail is visible (if you set one)
7. ✓ Drag material onto an object
8. ✓ Verify material applies correctly with all nodes intact

### Test 3: Conflict Resolution

1. ✓ Go back to your original file with the asset
2. ✓ Right-click the same material → "Save to Library"
3. ✓ Use the same name "TestMaterial"
4. ✓ Set "If File Exists" to "Increment"
5. ✓ Click OK
6. ✓ Verify `TestMaterial_001.blend` is created
7. ✓ Repeat and verify `TestMaterial_002.blend` is created

### Test 4: Catalog Assignment

1. ✓ Create a `blender_assets.cats.txt` in your library folder with at least one catalog
2. ✓ Restart Blender (or reload addon)
3. ✓ Create a new asset
4. ✓ Right-click → "Save to Library"
5. ✓ Open the "Catalog" dropdown
6. ✓ Verify your catalog appears in the list
7. ✓ Select a catalog
8. ✓ Save the asset
9. ✓ In Asset Browser (in your library), verify the asset appears in the chosen catalog

### Test 5: Metadata Preservation

1. ✓ Create an asset with custom preview
2. ✓ Save to library with author, description, and tags
3. ✓ In a new file, open Asset Browser
4. ✓ Select the asset (don't import)
5. ✓ Check the asset details panel
6. ✓ Verify author, description, and tags are preserved

### Test 6: Preferences

1. ✓ Go to Edit > Preferences > Add-ons
2. ✓ Find Quick Asset Saver
3. ✓ Click "Open Library Folder" button
4. ✓ Verify file browser opens to your library
5. ✓ Change settings (auto-refresh, pack images)
6. ✓ Verify settings are saved after Blender restart

### Test 7: Edge Cases

1. ✓ Try saving an asset with special characters in name (`Test/Asset*Name`)
2. ✓ Verify filename is sanitized (`Test_Asset_Name.blend`)
3. ✓ Try with very long asset name (>128 chars)
4. ✓ Verify truncation works
5. ✓ Try saving with empty name - should default to "asset"

## Known Limitations / TODO

### Current Limitations

1. **Single Asset Save Only**: Currently saves one asset at a time. Batch saving multiple selected assets would require UI changes and iteration logic.

2. **Metadata Application**: Due to `bpy.data.libraries.write()` limitations, metadata (author, description, tags) is set on the source asset before writing. A more robust approach would be to load the written file, apply metadata, and re-save, but this adds complexity.

3. **Preview Thumbnail Preservation**: While the addon attempts to preserve preview thumbnails by writing the asset with its existing metadata, custom previews may not always transfer perfectly. Additional work with `AssetMetaData.render` may be needed.

4. **Asset Type Detection**: The addon relies on context to find the asset datablock. Some edge cases with linked or instanced assets may not be handled optimally.

5. **Catalog File Format Validation**: Minimal validation of `blender_assets.cats.txt` format. Malformed catalog files might cause issues. Could add more robust parsing with error reporting.

### Future Improvements

1. **Batch Processing**: Add support for saving multiple selected assets in one operation with progress indicator.

2. **Asset Browser Integration**: Add a custom Asset Browser sidebar panel with more features like:
   - Quick view of saved assets count
   - Recent saves history
   - Library statistics

3. **Advanced Metadata Editor**: Inline editor for complex metadata without opening dialog, similar to native Blender asset editing.

4. **Dependency Report**: Before saving, show a list of indirect dependencies (textures, node groups) that will be included.

5. **Library Synchronization**: Add ability to update an existing library asset with new changes from current file (versioning).

6. **Auto-Categorization**: ML or rule-based suggestions for catalog assignment based on asset type and naming.

7. **Export Presets**: Save and reuse common export configurations (author, tags, catalog preferences).

8. **Undo Support**: Better undo integration for the save operation (currently limited by file I/O nature).

9. **Network/Cloud Storage**: Support for saving to network drives or cloud-synced folders with proper locking.

10. **Asset Comparison**: Before overwriting, show a diff/comparison view of what would change.

## Troubleshooting

### "Asset library path not set in preferences"
- Go to Preferences > Add-ons > Quick Asset Saver and set the Asset Library Path

### "Library path is not writable"
- Check folder permissions
- On Windows, run Blender as administrator (not recommended) or choose a different folder
- On macOS/Linux, use `chmod` to grant write permissions

### "Could not identify asset to save"
- Ensure you're right-clicking an actual asset marked in Current File
- Verify you're in the Asset Browser (not regular File Browser)
- Make sure the asset is from "Current File" library, not an external library

### Asset doesn't appear after saving
- Check if Auto-Refresh is enabled in preferences
- Manually refresh Asset Browser (F5 or refresh button)
- Verify the .blend file exists in your library folder
- Restart Blender to force library re-scan

### Catalogs don't appear
- Check that `blender_assets.cats.txt` exists in library folder
- Verify file format (UTF-8, proper UUID:path:name format)
- Check console for parsing errors
- Restart Blender or reload addon after editing catalog file

## Development

### File Structure

```
QuickSave/
├── __init__.py          # Main addon entry point, bl_info, register/unregister
├── operators.py         # Core operators and helper functions
├── properties.py        # Preferences and property groups
├── panels.py           # UI integration (context menus, panels)
└── README.md           # This file
```

### Helper Functions

Key functions for testing and reuse:

- `sanitize_name(name, max_length=128)`: Sanitize filenames for cross-platform use
- `increment_filename(base_path, name, extension=".blend")`: Generate numbered filenames
- `get_catalogs_from_cdf(library_path)`: Parse catalog definition file
- `write_blend_file(filepath, datablocks, pack_images)`: Atomic .blend file writing

### API Requirements

- Blender 5.0+ Python API
- No external dependencies
- Uses: `bpy`, `bpy.types`, `bpy.props`, `os`, `pathlib`, `re`, `uuid`, `shutil`

## License

GPL (GNU General Public License) - Compatible with Blender's licensing

## Support

For issues, suggestions, or contributions, please refer to the project repository or contact the addon author.

---

**Note**: This addon is designed for Blender 5.0+. API calls and context behavior may differ in earlier Blender versions.
