"""Update installed plugins from the repo."""
from __future__ import annotations

import argparse
import shutil
import subprocess
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


def get_installed_plugins() -> dict[str, tuple[Path, str]]:
    """Return installed plugins with their paths and types."""
    installed = {}
    
    if not HERMES_PLUGINS_DIR.exists():
        return installed
    
    for item in HERMES_PLUGINS_DIR.iterdir():
        if not item.is_dir():
            continue
            
        # Check if it's a direct plugin
        if (item / "plugin.yaml").exists():
            installed[item.name] = (item, "isolated")
        else:
            # Check if it's a category with plugins inside
            for plugin_dir in item.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.yaml").exists():
                    full_name = f"{item.name}/{plugin_dir.name}"
                    installed[full_name] = (plugin_dir, "categorized")
    
    return installed


def git_update(repo: Path) -> None:
    """Pull latest changes from origin master."""
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"🔴 git pull failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    print(f"📥 {result.stdout.strip() or 'Already up to date.'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Hermes plugins")
    parser.add_argument("plugin", nargs="?", help="Plugin to update (default: all installed)")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="Repo path (default: local repo)")
    parser.add_argument("--no-git", action="store_true", help="Skip git pull")
    args = parser.parse_args()

    repo = Path(args.repo)

    if not args.no_git:
        if not repo.is_dir():
            print(f"❌ Repo not found at {repo}", file=sys.stderr)
            print("📥 Clone first or use --no-git", file=sys.stderr)
            sys.exit(1)
        print(f"📦 Updating repo at {repo}...")
        git_update(repo)

    available = discover_plugins()
    installed = get_installed_plugins()

    if args.plugin:
        targets = [args.plugin] if args.plugin in available else []
        if not targets:
            print(f"❌ Plugin '{args.plugin}' not in repo.", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [p for p in installed.keys() if p in available]

    if not targets:
        print("✅ Nothing to update.")
        return

    for name in targets:
        plugin_info = available[name]
        src = plugin_info["path"]
        installed_path, _ = installed[name]
        
        # Remove and replace
        if installed_path.exists():
            shutil.rmtree(installed_path)
        shutil.copytree(src, installed_path)
        print(f"🔄 Updated '{name}'")


if __name__ == "__main__":
    main()
