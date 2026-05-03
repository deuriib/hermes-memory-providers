"""Uninstall a Hermes plugin."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERMES_PLUGINS_DIR = Path.home() / ".hermes" / "plugins"


def find_installed_plugin(plugin_name: str) -> tuple[Path, str] | None:
    """Find an installed plugin by name and return (path, type)."""
    if not HERMES_PLUGINS_DIR.exists():
        return None
    
    # Try to find as isolated plugin first
    isolated_path = HERMES_PLUGINS_DIR / plugin_name
    if isolated_path.exists() and (isolated_path / "plugin.yaml").exists():
        return (isolated_path, "isolated")
    
    # Try to find as categorized plugin (category/plugin)
    if "/" in plugin_name:
        category, plugin = plugin_name.split("/")
        categorized_path = HERMES_PLUGINS_DIR / category / plugin
        if categorized_path.exists() and (categorized_path / "plugin.yaml").exists():
            return (categorized_path, "categorized")
    
    # Try to find by plugin name in any category
    for category_dir in HERMES_PLUGINS_DIR.iterdir():
        if category_dir.is_dir():
            plugin_path = category_dir / plugin_name
            if plugin_path.exists() and (plugin_path / "plugin.yaml").exists():
                return (plugin_path, "categorized")
    
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Uninstall a Hermes plugin")
    parser.add_argument("plugin", help="Plugin name to uninstall (e.g. engram or memory/engram)")
    parser.add_argument("--purge", action="store_true", help="Remove plugin config files too")
    args = parser.parse_args()

    found = find_installed_plugin(args.plugin)
    
    if not found:
        print(f"❌ Plugin '{args.plugin}' is not installed.", file=sys.stderr)
        print("📋 Use 'bin/hm-list' to see installed plugins.", file=sys.stderr)
        sys.exit(1)
    
    plugin_path, plugin_type = found

    if args.purge:
        # Clean up config files using just the plugin name (without category)
        plugin_name = args.plugin.split("/")[-1] if "/" in args.plugin else args.plugin
        config_paths = [
            Path.home() / ".hermes" / f"{plugin_name}.json",
            Path.home() / ".hermes" / f"{plugin_name}.yaml",
        ]
        for cfg in config_paths:
            if cfg.exists():
                cfg.unlink()
                print(f"🧹 Removed config: {cfg}")

    shutil.rmtree(plugin_path)
    
    # Clean up empty category directories
    if plugin_type == "categorized" and plugin_path.parent != HERMES_PLUGINS_DIR:
        try:
            if not any(plugin_path.parent.iterdir()):  # If category is empty
                plugin_path.parent.rmdir()
                print(f"🧹 Removed empty category: {plugin_path.parent}")
        except OSError:
            pass  # Directory not empty, that's fine
    
    print(f"✅ Uninstalled '{args.plugin}'")


if __name__ == "__main__":
    main()
