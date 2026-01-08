# Quick Asset Saver

Blender add-on that aims to help you Work *with* Blender's Asset Browser, not around it. Quickly save assets from your current file into any user asset library, and manage assets inside libraries with editing, moving, replacing, deleting, and bundling tools.

## Core Features

- **Quick Save from Current File**
	- Save the active asset from **Current File** directly into any user asset library
	- Writes a lightweight `.blend` that packs external dependencies (images, fonts, etc.)
	- Applies full metadata: name, description, author, license, copyright, tags, catalog
	- Optional auto-refresh of the Asset Browser after saving

- **Library Asset Management Panel**
	- Works when browsing a user asset library in the Asset Browser
	- **Edit**: change asset name and tags, and update them inside the `.blend` file
	- **Move**: move selected assets to another library and/or catalog (including Unassigned)
		- Respects Blender's catalog file and updates catalog IDs inside the asset files
		- Handles name conflicts with Increment / Overwrite / Skip options
	- **Replace**: swap selected scene objects with the selected asset (append or link)
	- **Delete**: send selected asset `.blend` files to the system Recycle Bin / Trash (Windows, macOS, Linux) using `send2trash`

- **Quick Asset Bundler**
	- When browsing a user library, bundle multiple selected assets into a single shareable `.blend`
	- Choose bundle name and output folder
	- Control how duplicate datablocks are handled (Overwrite / Increment)
	- Optionally copy the catalog file alongside the bundle
	- Guardrails for large selections and maximum bundle size to avoid memory issues

All tools build on Blender's native asset libraries and catalogs – no custom database, no forced folder structure, and no custom file suffixes.

## Panels & Workflows

### 1. Quick Asset Saver (Current File)

1. Open the Asset Browser and switch to **Current File**.
2. Select an asset you want to save.
3. In the left sidebar, open the **Quick Asset Saver** panel.
4. Choose the target asset library.
5. Adjust:
	 - Asset display name and catalog
	 - Description, tags, author, license, copyright
	 - Conflict behavior (Increment / Overwrite / Cancel).
6. Review the preview path.
7. Click **Copy to Asset Library**.

The add-on will write a new `.blend` into the chosen library (optionally into catalog-based subfolders), pack dependencies, apply metadata, and refresh the Asset Browser if auto-refresh is enabled.

### 2. Quick Asset Manager (Library View)

1. In the Asset Browser, browse a user-configured asset library.
2. Open the **Quick Asset Manager** panel in the sidebar.

Sections:

- **Edit**
	- Select exactly one asset in the Asset Browser.
	- The panel auto-fills its name and tags.
	- Change the fields and click **Apply** to update tags/metadata inside the asset file (and optionally rename the file itself).

- **Move**
	- Select one or more assets.
	- Choose a target library and catalog (or Unassigned).
	- Pick a conflict mode (Increment / Overwrite / Skip).
	- Click **Move** to move the `.blend` files and update their catalog assignments.

- **Replace**
	- In your scene, select one or more objects.
	- In the Asset Browser, select a single asset.
	- Choose **Append** or **Link** mode.
	- Click **Replace** to swap the scene objects with instances of the chosen asset, preserving placement.

- **Delete**
	- Select one or more assets in the Asset Browser.
	- Click **Delete Selected Files** to move their `.blend` files to the system Recycle Bin / Trash.

All management operations automatically refresh the Asset Browser so thumbnails update immediately.

### 3. Quick Asset Bundler (Library View)

1. In the Asset Browser, browse a user asset library and select multiple assets.
2. Open the **Quick Asset Bundler** panel.
3. Set bundle name, output folder, duplicate handling mode, and whether to copy the catalog file.
4. Click **Bundle Selected Assets** to generate a single `.blend` containing all chosen assets.

The bundler enforces a configurable maximum total size and warns about very large selections to help avoid memory issues.

## Preferences

Add-on preferences are under **Edit → Preferences → Add-ons → Quick Asset Saver**:

- **Default Asset Library**: initial target library for saving assets.
- **Organization**: option to create subfolders that mirror catalog paths inside libraries.
- **Filename Conventions**:
	- Prefix / suffix for saved asset filenames.
	- Optional date stamp appended to filenames.
- **Default Metadata**:
	- Author, description, license, copyright.
- **Auto-Refresh Asset Browser**: toggle automatic refresh after saving assets from Current File.
- **Asset Bundling**:
	- Maximum allowed bundle size in MB.

## Requirements & Compatibility

- Blender 4.2.0 or newer.
- At least one asset library configured in **Preferences → File Paths → Asset Libraries**.
- File access permission (used only for reading library paths, writing asset `.blend` files, and sending deleted assets to the system trash).

Tested on Windows, macOS, and Linux using Blender's native asset system and cross-platform-safe file handling.