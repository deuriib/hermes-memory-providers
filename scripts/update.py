"""Update installed plugins from the repo."""
from __future__ import annotations

import argparse
import shutil
import subprocess
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

def git_update(repo: Path) -> None:
    """Pull latest changes from origin master."""
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"git pull failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout.strip() or "Already up to date.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Hermes memory provider plugins")
    parser.add_argument("plugin", nargs="?", help="Plugin to update (default: all installed)")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="Repo path (default: local repo)")
    parser.add_argument("--no-git", action="store_true", help="Skip git pull")
    args = parser.parse_args()

    repo = Path(args.repo)

    if not args.no_git:
        if not repo.is_dir():
            print(f"error: repo not found at {repo}", file=sys.stderr)
            print("Clone first or use --no-git", file=sys.stderr)
            sys.exit(1)
        print(f"Updating repo at {repo}...")
        git_update(repo)

    available = discover_plugins()
    installed = [p.name for p in PLUGINS_DIR.iterdir() if p.is_dir()] if PLUGINS_DIR.is_dir() else []

    if args.plugin:
        targets = [args.plugin] if args.plugin in available else []
        if not targets:
            print(f"error: plugin '{args.plugin}' not in repo.", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [p for p in installed if p in available]

    if not targets:
        print("Nothing to update.")
        return

    for name in targets:
        # Handle nested plugin structure
        if "/" in name:
            src = repo / "plugins" / name
            # For nested plugins, use just the plugin name as destination
            plugin_name = name.split("/")[-1]
            dst = PLUGINS_DIR / plugin_name
        else:
            src = repo / "plugins" / name
            dst = PLUGINS_DIR / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"Updated '{name}'")


if __name__ == "__main__":
    main()
