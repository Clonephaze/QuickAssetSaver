# Changelog

All notable user-facing changes to Quick Asset Manager are documented here.

## 2.1.0

This release brings a couple of highly requested features, several bug fixes, and a round of general polish.

### New Features

- **Bulk Move & Bundle from Current File**: You can now select multiple unsaved assets directly in your Current File and Move or Bundle them straight to a library, instead of saving them one at a time.
- **Copy Catalog from Current File**: When saving an asset, enable this checkbox to automatically reuse the asset's existing catalog. If that catalog doesn't exist yet in the target library, it's created for you — no need to pick it manually from the dropdown.

### Improvements

- Moving assets now shows a clear confirmation message, so you know right away it worked.
- The Catalog dropdown has a refresh button, so newly created catalogs show up immediately without restarting Blender.
- Disabled asset libraries no longer show up in your library dropdowns. #11
- Added a heads-up on the Bundle panel that opening the save-path picker will deselect your assets (a quirk of Blender's file browser).

### Bug Fixes

- Saving an asset to a library no longer removes its catalog from the Current File. 
- Fixed an issue on Blender 5.1+ where the protected Essentials library could accidentally be modified.
- Fixed "Overwrite" mode for Bundling so it actually replaces the existing file instead of always creating a new one.
- Fixed Bulk Move from the Current File incorrectly reporting "no assets selected."
- Fixed the "Saved!" confirmation message appearing in red as if it were an error.
- If your system's recycle bin/trash feature isn't available, you'll now get a clear warning instead of a silent failure.
- Fixed Compositor node group assets copying the entire project into the library file instead of just the node group itself.
- Fixed saving Scene assets with sound/video sequences potentially failing on the newest Blender 5.2 builds.

### Notes
- Blender 5.2 added online asset libraries, which at least for now will not be supported by Quick Asset Manager. All QAM features will not work to or from online asset libraries. This was a conscious decision to avoid the complexity of dealing with online asset libraries, which are not yet fully documented and may change in future Blender releases. Additionally, I'm not entirely sure how licensing and copyright issues will be handled with online asset libraries, so for now QAM will only support local asset libraries.

- While the user-facing changes are relatively minor, the underlying code has had a large refactor to improve maintainability and future feature development. Because of this, testing has been incredibly thorough (including creating over 150 tests to ensure no regressions), but if you notice any issues, please report them on GitHub.
