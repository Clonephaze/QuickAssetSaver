Blender’s Asset Library is powerful, but managing your own assets is unnecessarily tedious. Saving assets takes too many steps, and once they’re saved, Blender offers no easy way to rename, edit metadata, reorganize catalogs, or delete assets without manually opening files.

**Quick Asset Manager** fixes that.

It lets you save assets directly to your configured libraries with full metadata support, then manage those assets in place. Rename them, edit metadata and tags, move them between catalogs or libraries, swap them into scenes, or delete them entirely. No file hunting. No opening .blend files just to make a small change.

## Features

- **Direct Save**: Save selected assets to any configured Blender library with one click, including optional catalog assignment.
- **Editable Saved Assets**: Edit any metadata fields or tags you desire in your saved assets
- **Move & Organize**: Move assets between catalogs or entire libraries without touching the filesystem
- **Swap Assets**: Replace selected scene objects by right-clicking any object or collection asset.
- **Bulk Operations**: Move multiple assets at once, or bundle them into a single .blend file for easy sharing.

## Usage

### Saving Assets

1. Open the Asset Browser and switch to **Current File** view 
2. Select an asset you want to save
3. Open your tool panel (N by default)
4. Configure the asset name, catalog, and metadata as needed
5. Choose your target library and optional catalog from the dropdowns
6. Click **Save to Asset Library**

### Editing Assets 

1. Open the Asset Browser and select any already saved asset
2. Open your tool panel (N by default)
3. Change any metadata field as needed
4. Choose Apply Changes

### Moving Assets

1. Open the Asset Browser and select any already saved asset
2. Open your tool panel (N by default)
3. At the bottom of the panel choose a new library and/or catalog destination
4. Choose Move

### Swapping Assets

1. Ensure an item is selected in your scene
2. Open the Asset Browser and find any already saved asset
3. Right Click your desired asset and choose "Swap with active objects" 
(Note: Only works for collection and object assets)

### Bundling Assets

1. Open the Asset Browser and switch to a configured library
2. Select the assets you want to save
3. Continue from the **Quick Asset Bundler** panel in the sidebar to the left
4. Choose your target save directory
5. Configure the bundle name, catalog copy, and overwrite settings
6. Click Bundle and wait for your bundle to complete!

The addon will:
- Create a bundled`.blend` file with all your selected
- Automatically pack all required images and dependencies
- Apply all metadata and catalog assignments
- Save to your chosen directory with proper file naming
- Optionally save a copy of your catalog (categories) file

## Support me

If you would like to help fund development (and the replacement of my dead GPU 😅), or just give me a tip, I have a [Buy me a Coffee page here](https://buymeacoffee.com/Clonephaze)