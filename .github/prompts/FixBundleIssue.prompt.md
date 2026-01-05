---
agent: agent
---

## Project Context

This add-on is currently named **Quick Asset Saver**.

It has grown beyond simple asset saving, and *may* be renamed to **Quick Asset Manager** in the future, but that rename has **not** happened yet and should not be assumed in code or architecture.

Current features include:
- Quickly saving Blender assets
- Bundling multiple assets into a single `.blend` file (QuickAssetBundler)
- Post-save asset operations:
  - Renaming assets
  - Editing asset tags
  - Editing asset catalog assignment
  - Changing asset library location
  - Deleting assets

## Observed Problem

Multiple assets can exist inside a single `.blend` file.

When attempting to operate on **one asset** inside such a file, current behavior often results in:
- All assets in the file being modified together
- Or the entire `.blend` file being deleted
- Or unintended metadata changes propagating to other assets

This is unacceptable when:
- A file contains many assets
- The user explicitly targets only one

## Important Clarification

It is **not yet proven** that this limitation is caused by Blender’s API itself.

It is very possible that:
- The Blender API *does* support safe asset-level operations
- But the **current add-on implementation is operating too coarsely** (file-level logic instead of asset-level logic)

This investigation must determine **where the real boundary is**.

## Constraints

- Assets may intentionally be bundled together
- Bundled assets may:
  - Share textures
  - Share node groups
  - Reference each other
- Automatically separating assets into individual files is often destructive

## Attempted Solution (Rejected)

### Automatic Unbundling

**Approach:**
- Detect when an asset shares a `.blend` with others
- Extract it into its own `.blend` file
- Move it to the appropriate asset library

**Result:**
- Broke shared textures
- Broke shared data-block references
- Broke assets that depended on other bundled assets

This approach is not viable.

## Actual Goal

Determine whether it is possible to safely perform **asset-scoped operations** inside a multi-asset `.blend` file, including:
- Renaming a single asset
- Editing only that asset’s tags
- Changing only that asset’s catalog
- Deleting only that asset

Without:
- Modifying other assets
- Breaking shared data
- Destroying the `.blend` file

## Investigation Strategy

Do not immediately refactor the add-on.

Instead, treat this as an **experimental API investigation**.

### Required Method

1. Use Blender in **headless / command-line mode**
2. Operate on **controlled test `.blend` files** containing multiple assets
3. Perform **one asset-level change at a time**
4. Observe and verify results

### Test Operations

Each test should attempt exactly one of the following:
- Rename a single asset
- Modify tags for a single asset
- Change catalog assignment for a single asset
- Delete a single asset

### Verification Criteria

After each operation, confirm:
- Other assets are unchanged
- Shared textures and data-blocks still function
- The `.blend` file remains valid and intact

## Expected Outcomes

This investigation should result in one of the following:
- A safe, repeatable sequence of Blender API calls for asset-level editing
- Identification of API calls that appear asset-scoped but are actually file-scoped
- Clear proof that certain operations are not safely possible, requiring UX-level constraints

## Non-Goals

- Do not assume assets must be stored one-per-file
- Do not rely on destructive duplication
- Do not suggest manual workflows for users as a primary solution

This is an engineering investigation, not a workaround hunt.

## Summary

The purpose of this document is to:
- Untangle asset-level intent vs file-level behavior
- Experiment rather than speculate
- Determine whether the limitation is:
  - Add-on architecture
  - Blender API design
  - Or a combination of both
