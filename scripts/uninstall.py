"""Uninstall a Hermes memory provider plugin."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PLUGINS_DIR = Path.home() / ".hermes" / "plugins" / "memory"


def main() -> None:
    parser = argparse.ArgumentParser(description="Uninstall a Hermes memory provider plugin")
    parser.add_argument("plugin", help="Plugin name to uninstall")
    parser.add_argument("--purge", action="store_true", help="Remove plugin config files too")
    args = parser.parse_args()

    plugin_path = PLUGINS_DIR / args.plugin

    if not plugin_path.exists():
        print(f"Plugin '{args.plugin}' is not installed.", file=sys.stderr)
        sys.exit(1)

    if args.purge:
        config_paths = [
            Path.home() / ".hermes" / f"{args.plugin}.json",
            Path.home() / ".hermes" / f"{args.plugin}.yaml",
        ]
        for cfg in config_paths:
            if cfg.exists():
                cfg.unlink()
                print(f"Removed config: {cfg}")

    shutil.rmtree(plugin_path)
    print(f"Uninstalled '{args.plugin}'")


if __name__ == "__main__":
    main()
