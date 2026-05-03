"""Install a Hermes plugin (categorized or isolated)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

HERMES_PLUGINS_DIR = Path.home() / ".hermes" / "plugins"
REPO_ROOT = Path(__file__).parent.parent
PLUGINS_SOURCE_DIR = REPO_ROOT / "plugins"


def discover_plugins() -> dict[str, dict]:
    """Return plugin structure found in the repo (supports nested structure)."""
    if not PLUGINS_SOURCE_DIR.exists():
        return {}
    
    plugins = {}
    
    for item in PLUGINS_SOURCE_DIR.iterdir():
        if not item.is_dir():
            continue
            
        # Direct plugin: plugins/{plugin}/
        if (item / "plugin.yaml").exists():
            plugins[item.name] = {
                "path": item,
                "type": "isolated",
                "category": None
            }
        else:
            # Category directory: plugins/{category}/
            # Look for nested plugins: plugins/{category}/{plugin}/
            for plugin_dir in item.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.yaml").exists():
                    full_name = f"{item.name}/{plugin_dir.name}"
                    plugins[full_name] = {
                        "path": plugin_dir,
                        "type": "categorized", 
                        "category": item.name
                    }
    
    return plugins


def main() -> None:
    parser = argparse.ArgumentParser(description="Install a Hermes plugin")
    parser.add_argument("plugin", nargs="?", help="Plugin name (e.g. engram or memory/engram)")
    parser.add_argument("--list", action="store_true", help="List available plugins")
    parser.add_argument("--source", default=str(REPO_ROOT), help="Source directory (default: repo root)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip reinstall confirmation")
    args = parser.parse_args()

    available = discover_plugins()

    if args.list or not args.plugin:
        print("Available plugins:")
        print("\n📦 Isolated plugins:")
        for name, info in available.items():
            if info["type"] == "isolated":
                print(f"  - {name}")
        
        print("\n📂 Categorized plugins:")
        for name, info in available.items():
            if info["type"] == "categorized":
                print(f"  - {name}")
        
        print(f"\n✅ Installed plugins:")
        if HERMES_PLUGINS_DIR.exists():
            # Show all installed plugins with their structure
            for category_or_plugin in sorted(HERMES_PLUGINS_DIR.iterdir()):
                if category_or_plugin.is_dir():
                    # Check if it's a category or direct plugin
                    if any((category_or_plugin / item).is_dir() and (category_or_plugin / item / "plugin.yaml").exists() 
                          for item in category_or_plugin.iterdir() if item.is_dir()):
                        # It's a category
                        print(f"  📂 {category_or_plugin.name}/")
                        for plugin in category_or_plugin.iterdir():
                            if plugin.is_dir() and (plugin / "plugin.yaml").exists():
                                print(f"    - {plugin.name}")
                    elif (category_or_plugin / "plugin.yaml").exists():
                        # It's a direct plugin
                        print(f"  📦 {category_or_plugin.name}")
        else:
            print("  (none)")
        
        if not args.list:
            sys.exit(1)
        return

    if args.plugin not in available:
        print(f"❌ Plugin '{args.plugin}' not found in repo.", file=sys.stderr)
        print(f"📋 Run with --list to see available plugins.", file=sys.stderr)
        sys.exit(1)

    plugin_info = available[args.plugin]
    source = plugin_info["path"]
    
    # Determine destination based on plugin type
    if plugin_info["type"] == "isolated":
        # Install directly: ~/.hermes/plugins/{plugin}/
        plugin_name = args.plugin
        dest = HERMES_PLUGINS_DIR / plugin_name
    else:
        # Install in category: ~/.hermes/plugins/{category}/{plugin}/
        category, plugin_name = args.plugin.split("/")
        dest = HERMES_PLUGINS_DIR / category / plugin_name

    if dest.exists():
        print(f"⚠️  Plugin '{args.plugin}' is already installed at {dest}")
        response = input("🔄 Reinstall? [y/N] ") if not args.yes else "y"
        if response.lower() != "y":
            print("❌ Aborted.")
            return
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    print(f"✅ Installed '{args.plugin}' → {dest}")


if __name__ == "__main__":
    main()
