"""CLI commands for Engram memory provider plugin."""

import json
import logging
from pathlib import Path
from . import tools

logger = logging.getLogger(__name__)


def _get_config_path():
    """Get the config file path from HERMES_HOME."""
    from hermes_constants import get_hermes_home
    return get_hermes_home() / "engram.json"


def engram_command(args):
    """Handler dispatched by argparse."""
    sub = getattr(args, "engram_command", None)
    
    if sub == "status":
        # Check if engram server is running
        if tools._is_engram_running():
            print("✓ Engram server is running")
            # Get current project info
            project = tools._current_project or "unknown"
            print(f"  Current project: {project}")
        else:
            print("✗ Engram server is not running")
            print("  Run 'engram serve' to start the server")
    
    elif sub == "config":
        # Show current configuration
        config_path = _get_config_path()
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                print("Current Engram configuration:")
                for key, value in config.items():
                    print(f"  {key}: {value}")
            except Exception as e:
                print(f"Error reading config: {e}")
        else:
            print("No Engram configuration found")
            print(f"Config would be stored at: {config_path}")
    
    elif sub == "server":
        # Try to start engram server
        print("Starting Engram server...")
        if tools._ensure_server():
            print("✓ Engram server started successfully")
        else:
            print("✗ Failed to start Engram server")
            print("  Make sure 'engram' is installed and in PATH")
    
    elif sub == "test":
        # Test connection and basic functionality
        print("Testing Engram connection...")
        
        # Test server connection
        if not tools._is_engram_running():
            print("✗ Server not running")
            return
        
        print("✓ Server connection OK")
        
        # Test current project detection
        project = tools._current_project or "unknown"
        print(f"✓ Current project: {project}")
        
        # Test basic API call
        try:
            result = tools._engram_fetch("/context", params={"project": project})
            if result:
                print("✓ API communication OK")
            else:
                print("✗ API communication failed")
        except Exception as e:
            print(f"✗ API error: {e}")
    
    else:
        print("Usage: hermes engram <status|config|server|test>")


def register_cli(subparser) -> None:
    """Build the hermes engram argparse tree.
    
    Called by discover_plugin_cli_commands() at argparse setup time.
    """
    subs = subparser.add_subparsers(dest="engram_command")
    
    subs.add_parser("status", help="Show Engram server status and current project")
    subs.add_parser("config", help="Show Engram configuration")  
    subs.add_parser("server", help="Start Engram server")
    subs.add_parser("test", help="Test Engram connection and functionality")
    
    subparser.set_defaults(func=engram_command)