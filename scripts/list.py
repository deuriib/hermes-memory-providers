"""List installed and available plugins."""
from __future__ import annotations

import argparse
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


def get_installed_plugins() -> dict[str, str]:
    """Return installed plugins with their type."""
    installed = {}
    
    if not HERMES_PLUGINS_DIR.exists():
        return installed
    
    for item in HERMES_PLUGINS_DIR.iterdir():
        if not item.is_dir():
            continue
            
        # Check if it's a direct plugin
        if (item / "plugin.yaml").exists():
            installed[item.name] = "isolated"
        else:
            # Check if it's a category with plugins inside
            for plugin_dir in item.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.yaml").exists():
                    full_name = f"{item.name}/{plugin_dir.name}"
                    installed[full_name] = "categorized"
    
    return installed


def main() -> None:
    parser = argparse.ArgumentParser(description="List Hermes plugins")
    parser.add_argument("--installed", action="store_true", help="Show only installed")
    parser.add_argument("--available", action="store_true", help="Show only available")
    parser.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # mise passes 'sh' as $0 when no args given; drop it
    _ = [a for a in args.rest if a != "sh"]

    available = discover_plugins()
    installed = get_installed_plugins()

    if not args.installed:
        print("📋 Available plugins:")
        
        print("\n📦 Isolated plugins:")
        for name, info in available.items():
            if info["type"] == "isolated":
                status = "✅ [installed]" if name in installed else ""
                print(f"  - {name} {status}")
        
        print("\n📂 Categorized plugins:")
        for name, info in available.items():
            if info["type"] == "categorized":
                status = "✅ [installed]" if name in installed else ""
                print(f"  - {name} {status}")

    if not args.available:
        print("\n✅ Installed plugins:")
        if installed:
            isolated_installed = {k: v for k, v in installed.items() if v == "isolated"}
            categorized_installed = {k: v for k, v in installed.items() if v == "categorized"}
            
            if isolated_installed:
                print("  📦 Isolated:")
                for name in sorted(isolated_installed.keys()):
                    available_tag = "📋 [available]" if name in available else "⚠️  [not in repo]"
                    print(f"    - {name} {available_tag}")
            
            if categorized_installed:
                print("  📂 Categorized:")
                for name in sorted(categorized_installed.keys()):
                    available_tag = "📋 [available]" if name in available else "⚠️  [not in repo]"
                    print(f"    - {name} {available_tag}")
        else:
            print("  (none)")


if __name__ == "__main__":
    main()
