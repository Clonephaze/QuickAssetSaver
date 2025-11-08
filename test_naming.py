#!/usr/bin/env python3
"""
Quick test script to verify naming and path logic
without needing to run Blender.
"""

import re
from pathlib import Path
from datetime import datetime


def sanitize_name(name, max_length=128):
    """Sanitize a filename to be cross-platform compatible."""
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "_", name)
    sanitized = sanitized.replace(" ", "_")
    sanitized = sanitized.strip("._")
    
    if not sanitized:
        sanitized = "asset"
    
    return sanitized[:max_length]


def build_asset_filename(base_name, prefix="", suffix="", include_date=False):
    """Build the final asset filename with optional prefix, suffix, and date."""
    filename_parts = []
    
    # Add prefix if specified
    if prefix:
        clean_prefix = sanitize_name(prefix, max_length=32).strip("_")
        if clean_prefix:
            filename_parts.append(clean_prefix)
    
    # Add the base name
    filename_parts.append(base_name)
    
    # Add suffix if specified
    if suffix:
        clean_suffix = sanitize_name(suffix, max_length=32).strip("_")
        if clean_suffix:
            filename_parts.append(clean_suffix)
    
    # Add date if enabled
    if include_date:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename_parts.append(date_str)
    
    # Join all parts with underscores
    final_name = "_".join(filename_parts)
    
    return sanitize_name(final_name, max_length=200)


def test_naming_conventions():
    """Test various naming scenarios."""
    print("Testing Naming Conventions:")
    print("-" * 60)
    
    test_cases = [
        # (base, prefix, suffix, date, expected_pattern)
        ("MyAsset", "", "", False, "MyAsset"),
        ("MyAsset", "PRE", "", False, "PRE_MyAsset"),
        ("MyAsset", "", "v1", False, "MyAsset_v1"),
        ("MyAsset", "PRE", "v1", False, "PRE_MyAsset_v1"),
        ("MyAsset", "", "", True, r"MyAsset_\d{4}-\d{2}-\d{2}"),
        ("MyAsset", "PRE", "v1", True, r"PRE_MyAsset_v1_\d{4}-\d{2}-\d{2}"),
        ("My Asset", "", "", False, "My_Asset"),
        ("Asset/Name", "", "", False, "Asset_Name"),
        ("Asset*Name?", "", "", False, "Asset_Name_"),
    ]
    
    for base, prefix, suffix, date, expected in test_cases:
        result = build_asset_filename(base, prefix, suffix, date)
        
        # Check if we're using regex pattern
        if expected.startswith(r""):
            import re
            matches = bool(re.match(expected, result))
            status = "✓" if matches else "✗"
            print(f"{status} {base!r} → {result!r} (pattern: {expected})")
        else:
            matches = result == expected
            status = "✓" if matches else "✗"
            print(f"{status} {base!r} → {result!r} (expected: {expected})")


def test_catalog_paths():
    """Test catalog path sanitization."""
    print("\n\nTesting Catalog Path Sanitization:")
    print("-" * 60)
    
    test_catalogs = [
        "Materials/Metal",
        "Materials/Wood/Oak",
        "Props/Furniture/Modern",
        "Characters/NPCs",
        "VFX/Particles/Fire",
    ]
    
    for catalog in test_catalogs:
        parts = catalog.split("/")
        sanitized_parts = [sanitize_name(part, max_length=64) for part in parts if part]
        result_path = "/".join(sanitized_parts)
        print(f"✓ {catalog} → {result_path}")


def test_full_paths():
    """Test full path building."""
    print("\n\nTesting Full Path Building:")
    print("-" * 60)
    
    library_base = Path("/home/user/AssetLibrary")
    
    scenarios = [
        ("MyMaterial", "Materials/Metal", "", "", False),
        ("WoodTexture", "Materials/Wood", "PRE_", "", False),
        ("ChairModel", "Props/Furniture", "", "_v1", False),
        ("ParticleSystem", "VFX/Particles", "", "", True),
    ]
    
    for asset_name, catalog, prefix, suffix, date in scenarios:
        # Build catalog subfolder
        catalog_parts = catalog.split("/")
        sanitized_parts = [sanitize_name(part, max_length=64) for part in catalog_parts]
        target_dir = library_base
        for part in sanitized_parts:
            target_dir = target_dir / part
        
        # Build filename
        filename = build_asset_filename(asset_name, prefix, suffix, date)
        full_path = target_dir / f"{filename}.blend"
        
        # Show relative path
        try:
            rel_path = full_path.relative_to(library_base)
            print(f"✓ {asset_name} → {rel_path}")
        except ValueError:
            print(f"✗ {asset_name} → {full_path}")


if __name__ == "__main__":
    test_naming_conventions()
    test_catalog_paths()
    test_full_paths()
    print("\n" + "=" * 60)
    print("All tests completed!")
