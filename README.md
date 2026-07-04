Blender's Asset Library is powerful, but managing your own assets is unnecessarily tedious. Saving assets takes too many steps, and once they're saved, Blender offers no easy way to rename, edit metadata, reorganize catalogs, or delete assets without manually opening files.

**Quick Asset Manager** fixes that.

It lets you save assets directly to your configured libraries with full metadata support, then manage those assets in place. Rename them, edit metadata and tags, move them between catalogs or libraries, swap them into scenes, or delete them entirely. No file hunting. No opening .blend files just to make a small change.

Requires Blender 4.2 or newer.

## Features

- **Direct Save**: Save selected assets to any configured Blender library with one click, including optional catalog assignment and automatic dependency packing (images, fonts, sounds, movie clips).
- **Copy Catalog from Current File**: Reuse an asset's existing catalog when saving — if it doesn't exist yet in the target library, it's created automatically.
- **Editable Saved Assets**: Edit any metadata fields or tags on assets you've already saved, right from the Asset Browser sidebar.
- **Move & Organize**: Move assets between catalogs or entire libraries without touching the filesystem. Choose how conflicts are handled — increment the filename, overwrite, or skip.
- **Swap Assets**: Replace selected scene objects by right-clicking any object or collection asset.
- **Delete Assets**: Remove assets straight from the Asset Browser. Files (and their thumbnails/companion folders) go to your system's recycle bin, not permanent deletion.
- **Bulk Operations**: Select multiple assets — in a library or directly in your Current File — to Move or Bundle them all at once.
- **Bundling**: Package selected assets into a single, shareable `.blend` file, with automatic duplicate handling and optional catalog file copying.

## Usage

### Saving Assets

1. Open the Asset Browser and switch to **Current File** view
2. Select an asset you want to save
3. Open your tool panel (N by default)
4. Configure the asset name, catalog, and metadata as needed (or enable **Copy Catalog from Current File** to reuse its existing catalog)
5. Choose your target library from the dropdown
6. Click **Copy to Asset Library**

### Editing Assets

1. Open the Asset Browser and select any already saved asset
2. Open your tool panel (N by default)
3. Click **Edit Metadata/Tags**, make your changes, then click **Apply Changes**

### Moving Assets

1. Open the Asset Browser and select one or more already saved assets
2. Open your tool panel (N by default)
3. Choose a new library and/or catalog destination, and how to handle filename conflicts (Increment, Overwrite, or Skip)
4. Click **Move Asset** (or **Move N Assets** for a multi-selection)

### Deleting Assets

1. Open the Asset Browser and select an already saved asset
2. Open your tool panel (N by default) and click **Remove Asset from Library**, or right-click the asset and choose **Remove Asset from Library**
3. The asset's file and any companion thumbnails/folders are sent to your system's recycle bin

### Swapping Assets

1. Ensure an item is selected in your scene
2. Open the Asset Browser and find any already saved asset
3. Right-click your desired asset and choose **Replace Selected Objects**
(Note: Only works for collection and object assets)

### Bundling Assets

1. Select two or more assets — either in a configured library, or directly in your **Current File**
2. Continue from the **Bulk Operations** panel in the sidebar
3. Set a bundle name and target save directory
4. Configure duplicate handling and whether to copy the catalog file
5. Click **Bundle N Assets** and wait for it to complete

   The addon will:
     - Create a bundled `.blend` file with all your selected assets
     - Automatically pack all required images and dependencies
     - Apply all metadata and catalog assignments
     - Save to your chosen directory with proper file naming
     - Optionally save a copy of your catalog (categories) file

### Bulk Moving from Current File

Selecting two or more unsaved assets in your **Current File** view brings up the same **Bulk Operations** panel, letting you Move or Bundle them straight to a library without saving them one at a time first.

## Preferences

Configure these under **Edit > Preferences > Add-ons > Quick Asset Manager**:

- **Default Asset Library**: The library pre-selected when saving new assets.
- **Organize by Catalog**: Automatically create subfolders matching your catalog structure (e.g. `Materials/Metal`).
- **Filename Conventions**: Optional prefix, suffix, and date stamp applied to every saved asset's filename.
- **Default Metadata**: Default author, description, license, and copyright applied to new assets.
- **Auto-Refresh Asset Browser**: Automatically refresh the Asset Browser after saving.
- **Max Bundle Size**: Safety limit (in MB) to warn before importing too many assets into one bundle.

## Support me

If you would like to help fund development (and the replacement of my dead GPU 😅), or just give me a tip, I have a [Buy me a Coffee page here](https://buymeacoffee.com/Clonephaze)