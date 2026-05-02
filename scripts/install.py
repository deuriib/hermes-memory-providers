"""Install a Hermes memory provider plugin."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PLUGINS_DIR = Path.home() / ".hermes" / "plugins" / "memory"
REPO_ROOT = Path(__file__).parent.parent
PLUGINS_SOURCE_DIR = REPO_ROOT / "plugins"


def discover_plugins() -> list[str]:
    """Return plugin directories found in the repo (supports nested structure)."""
    if not PLUGINS_SOURCE_DIR.exists():
        return []
    
    plugins = []
    
    for item in PLUGINS_SOURCE_DIR.iterdir():
        if not item.is_dir():
            continue
            
        # Direct plugin: plugins/{plugin}/
        if (item / "plugin.yaml").exists():
            plugins.append(item.name)
        else:
            # Category directory: plugins/{category}/
            # Look for nested plugins: plugins/{category}/{plugin}/
            for plugin_dir in item.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.yaml").exists():
                    plugins.append(f"{item.name}/{plugin_dir.name}")
    
    return plugins


def main() -> None:
    parser = argparse.ArgumentParser(description="Install a Hermes memory provider plugin")
    parser.add_argument("plugin", nargs="?", help="Plugin name (e.g. engram)")
    parser.add_argument("--list", action="store_true", help="List available plugins")
    parser.add_argument("--source", default=str(REPO_ROOT), help="Source directory (default: repo root)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip reinstall confirmation")
    args = parser.parse_args()

    available = discover_plugins()

    if args.list or not args.plugin:
        print("Available plugins:")
        for p in available:
            print(f"  - {p}")
        print(f"\nInstalled plugins:")
        for p in sorted((PLUGINS_DIR).iterdir()) if PLUGINS_DIR.is_dir() else []:
            print(f"  - {p.name}")
        if not args.list:
            sys.exit(1)
        return

    if args.plugin not in available:
        print(f"error: plugin '{args.plugin}' not found in repo.", file=sys.stderr)
        print(f"Run with --list to see available plugins.", file=sys.stderr)
        sys.exit(1)

    # Handle nested plugin structure
    source = Path(args.source) / "plugins" / args.plugin
    
    # For nested plugins, use just the plugin name as destination
    if "/" in args.plugin:
        plugin_name = args.plugin.split("/")[-1]
        dest = PLUGINS_DIR / plugin_name
    else:
        dest = PLUGINS_DIR / args.plugin

    if dest.exists():
        print(f"Plugin '{args.plugin}' is already installed.")
        response = input("Reinstall? [y/N] ") if not args.yes else "y"
        if response.lower() != "y":
            print("Aborted.")
            return
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    print(f"Installed '{args.plugin}' → {dest}")


if __name__ == "__main__":
    main()
