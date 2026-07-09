import os, sys, json, termios, tty

outfile = sys.argv[1] if len(sys.argv) > 1 else None

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

results = {}
try:
    w(f"\r\n  \033[1m\033[36mAI Status\033[39m\033[22m — Configuration Wizard\r\n\r\n")

    results["ICON_MODE"] = "logo" if yesno("Show the provider logo as an image next to the text?", True) else "off"
    results["SHOW_PROVIDER"] = "true" if yesno("Show provider name in the status text? (e.g. 'Claude')", True) else "false"
    results["SHOW_MODEL"] = "true" if yesno("Show model/plan name in parens? (e.g. '(Pro)')", True) else "false"
    results["SHOW_METRIC"] = "true" if yesno("Show metric type name? (e.g. 'Rolling Usage')", False) else "false"
    results["SHOW_PCT"] = "true" if yesno("Show percentage? (e.g. '4%')", True) else "false"
    results["CONFIGURE_WAYBAR"] = "true" if yesno("Add AI Status modules to your Waybar config automatically?", True) else "false"
finally:
    cleanup()

if outfile and results:
    with open(outfile, "w") as f:
        json.dump(results, f)
