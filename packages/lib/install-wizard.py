import os, sys, json, termios, tty
import shutil

outfile = sys.argv[1] if len(sys.argv) > 1 else None
bar = sys.argv[2] if len(sys.argv) > 2 else "waybar"
bar_explicit = len(sys.argv) > 3 and sys.argv[3] == "true"
usage_display = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] in ("used", "remaining") else "used"

STYLE_SELECTED = "\033[4m\033[36m"
STYLE_INACTIVE = "\033[2m"
STYLE_RESET = "\033[24m\033[22m\033[39m"

fd = os.open("/dev/tty", os.O_RDWR)
old_attrs = termios.tcgetattr(fd)
tty.setraw(fd)
os.write(fd, b"\x1b[?25l")

cleaned = False

def w(s):
    os.write(fd, s.encode())

def cleanup():
    global cleaned
    if cleaned:
        return
    cleaned = True
    w("\x1b[?25h")
    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
    os.close(fd)
    sys.stdout.flush()

def abort():
    w("\033[G\033[K")
    cleanup()
    print("  \033[31mAborted.\033[0m")
    sys.exit(1)

def yesno(prompt, default=True):
    idx = 1 if default else 0
    labels = ["No", "Yes"]
    while True:
        parts = []
        for i in range(2):
            parts.append(f"{STYLE_SELECTED}{labels[i]}{STYLE_RESET}" if i == idx else f"{STYLE_INACTIVE}{labels[i]}{STYLE_RESET}")
        w(f"\033[G\033[K  \033[96m?\033[39m {prompt} \033[2m\u203a\033[22m {' / '.join(parts)}")
        ch = os.read(fd, 1).decode()
        if ch == "\x03":
            abort()
        elif ch == "\x1b":
            seq = os.read(fd, 2).decode()
            if len(seq) == 1:
                seq += os.read(fd, 1).decode()
            if seq in ("[C", "[D", "[A", "[B"):
                idx = 1 - idx
        elif ch in "yY": idx = 1; break
        elif ch in "nN": idx = 0; break
        elif ch in "\r\n": break
    chosen = labels[idx]
    w(f"\033[G\033[K  \033[96m?\033[39m {prompt} \033[2m\u203a\033[22m {STYLE_SELECTED}{chosen}{STYLE_RESET}\r\n")
    return idx == 1

def choose_usage_display(default="used"):
    values = ["used", "remaining"]
    labels = ["Used", "Remaining"]
    idx = values.index(default)
    prompt = "Show quota as"
    while True:
        parts = [f"{STYLE_SELECTED}{label}{STYLE_RESET}" if i == idx
                 else f"{STYLE_INACTIVE}{label}{STYLE_RESET}" for i, label in enumerate(labels)]
        w(f"\033[G\033[K  \033[96m?\033[39m {prompt} \033[2m\u203a\033[22m {' / '.join(parts)}")
        ch = os.read(fd, 1).decode()
        if ch == "\x03":
            abort()
        elif ch == "\x1b":
            seq = os.read(fd, 2).decode()
            if len(seq) == 1:
                seq += os.read(fd, 1).decode()
            if seq in ("[C", "[D", "[A", "[B"):
                idx = 1 - idx
        elif ch in "uU": idx = 0; break
        elif ch in "rR": idx = 1; break
        elif ch in "\r\n": break
    w(f"\033[G\033[K  \033[96m?\033[39m {prompt} \033[2m\u203a\033[22m {STYLE_SELECTED}{labels[idx]}{STYLE_RESET}\r\n")
    return values[idx]

results = {}
try:
    w(f"\r\n  \033[1m\033[36mAI Status\033[39m\033[22m — Configuration Wizard\r\n\r\n")

    if not bar_explicit and shutil.which("waybar") and shutil.which("omarchy") and shutil.which("omarchy-shell") and (shutil.which("qs") or shutil.which("quickshell")):
        bar = "quickshell" if yesno("Use the Omarchy Quickshell bar instead of Waybar?", bar == "quickshell") else "waybar"
    results["BAR"] = bar
    results["ICON_MODE"] = "logo" if yesno("Show the provider logo as an image next to the text?", True) else "off"
    results["SHOW_PROVIDER"] = "true" if yesno("Show provider name in the status text? (e.g. 'Claude')", True) else "false"
    results["SHOW_MODEL"] = "true" if yesno("Show model/plan name in parens? (e.g. '(Pro)')", True) else "false"
    results["SHOW_METRIC"] = "true" if yesno("Show metric type name? (e.g. 'Rolling Usage')", False) else "false"
    results["SHOW_PCT"] = "true" if yesno("Show percentage? (e.g. '4%')", True) else "false"
    results["USAGE_DISPLAY"] = choose_usage_display(usage_display)
    label = "Omarchy Quickshell bar" if bar == "quickshell" else "Waybar config"
    results["CONFIGURE_BAR"] = "true" if yesno(f"Add AI Status to your {label} automatically?", True) else "false"
finally:
    cleanup()

if outfile and results:
    with open(outfile, "w") as f:
        json.dump(results, f)
