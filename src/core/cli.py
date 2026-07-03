import sys
from . import daemon
from . import state
from . import tui

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        state.trigger_refresh()
    elif len(sys.argv) > 1 and sys.argv[1] == "daemon":
        sys.stderr = open('/tmp/waybar-ai-status-error.log', 'w')
        daemon.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "config":
        tui.run()
    else:
        print("Usage: waybar-ai-status [daemon|refresh|config]")
        sys.exit(1)
