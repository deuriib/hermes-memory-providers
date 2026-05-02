"""List installed and available plugins."""
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="List Hermes memory provider plugins")
    parser.add_argument("--installed", action="store_true", help="Show only installed")
    parser.add_argument("--available", action="store_true", help="Show only available")
    parser.add_argument("rest", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # mise passes 'sh' as $0 when no args given; drop it
    _ = [a for a in args.rest if a != "sh"]

    available = discover_plugins()
    installed = {p.name for p in PLUGINS_DIR.iterdir()} if PLUGINS_DIR.is_dir() else set()

    if not args.installed:
        print("Available plugins:")
        for name in sorted(available):
            status = "[installed]" if name in installed else ""
            print(f"  - {name} {status}")

    if not args.available:
        print("Installed plugins:")
        if installed:
            for name in sorted(installed):
                available_tag = "[available]" if name in available else ""
                print(f"  - {name} {available_tag}")
        else:
            print("  (none)")


if __name__ == "__main__":
    main()
