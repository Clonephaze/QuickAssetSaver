# Quick Asset Saver

A Blender addon that simplifies saving assets from your current file to your asset libraries as standalone `.blend` files.

## Purpose

Quick Asset Saver streamlines the asset library workflow by letting you save selected assets directly to your configured libraries with full metadata support. No manual file management required.

## Features

- **Direct Save**: Save assets to any configured Blender library with one click
- **Full Metadata**: Set name, description, author, license, copyright, tags, and catalog
- **Smart Defaults**: Configure default metadata in preferences to speed up your workflow
- **Catalog Support**: Automatically reads and assigns assets to library catalogs
- **Conflict Handling**: Choose to increment, overwrite, or cancel when files already exist
- **Auto-Refresh**: Optionally refresh the asset browser after saving
- **Cross-Platform**: Uses Blender's native path handling for Windows, Mac, and Linux

## Usage

### Setup

1. Install the addon in Blender (Edit > Preferences > Add-ons)
2. Configure your default library and metadata in addon preferences
3. Ensure you have at least one asset library configured in Blender (Preferences > File Paths > Asset Libraries)

### Saving Assets

1. Open the Asset Browser and switch to **Current File** view
2. Select an asset you want to save
3. Continue from the the **Quick Asset Saver** panel in the sidebar to the left
4. Choose your target library from the dropdown
5. Configure the asset name, catalog, and metadata as needed
6. Click **Save to Asset Library**

The addon will:
- Create a standalone lightweight `.blend` file with your asset
- Automatically pack all required images and dependencies
- Apply all metadata and catalog assignments
- Save to your chosen library with proper file naming

### Preferences

Set default values that will auto-populate when selecting assets:
- **Default Asset Library**: Your preferred library for saving
- **Default Author**: Your name or organization
- **Default Description**: Standard description text
- **Default License**: License for your assets
- **Default Copyright**: Copyright notice
- **Auto-Refresh**: Toggle automatic asset browser refresh

## Requirements

- File access
- At least one configured asset library