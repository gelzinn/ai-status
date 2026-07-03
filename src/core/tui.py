import curses
import os
from . import config


def run():
    all_providers = config.available_providers()
    if not all_providers:
        return

    enabled = config.enabled_order()
    enabled_set = set(enabled)
    order = [p for p in enabled if p in all_providers]
    for p in all_providers:
        if p not in order:
            order.append(p)

    selected_idx = 0
    scroll_offset = 0

    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    try:
        curses.curs_set(0)
    except Exception:
        pass

    changed = False

    def draw():
        nonlocal scroll_offset
        h, w = stdscr.getmaxyx()
        list_height = h - 4

        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        if selected_idx >= scroll_offset + list_height:
            scroll_offset = selected_idx - list_height + 1

        stdscr.clear()

        title = " AI Provider Config "
        stdscr.addstr(0, max(0, (w - len(title)) // 2), title,
                       curses.A_REVERSE | curses.A_BOLD)

        help_text = (
            "\u2191\u2193 navigate  SPACE toggle  "
            "K/J move  ENTER save  ESC cancel"
        )
        stdscr.addstr(h - 1, max(0, (w - len(help_text)) // 2), help_text)

        visible = order[scroll_offset:scroll_offset + list_height]
        for i, prov in enumerate(visible):
            y = i + 1
            enabled_flag = prov in enabled_set
            checkbox = "[x]" if enabled_flag else "[ ]"
            prefix = " > " if scroll_offset + i == selected_idx else "   "
            text = f"{prefix}{checkbox} {prov}"
            if len(text) > w:
                text = text[:w]
            attr = curses.A_REVERSE if scroll_offset + i == selected_idx else curses.A_NORMAL
            stdscr.addstr(y, 0, text, attr)

        stdscr.refresh()

    while True:
        draw()
        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        elif key == ord("\n"):
            if changed:
                cfg = [p for p in order if p in enabled_set]
                config.save_config(cfg)
                from . import state
                state.trigger_refresh()
            break
        elif key == curses.KEY_UP:
            selected_idx = max(0, selected_idx - 1)
        elif key == curses.KEY_DOWN:
            selected_idx = min(len(order) - 1, selected_idx + 1)
        elif key == ord(" "):
            prov = order[selected_idx]
            if prov in enabled_set:
                enabled_set.remove(prov)
            else:
                enabled_set.add(prov)
            changed = True
        elif key in (curses.KEY_PPAGE,):
            selected_idx = max(0, selected_idx - 10)
        elif key in (curses.KEY_NPAGE,):
            selected_idx = min(len(order) - 1, selected_idx + 10)
        elif key == ord("K"):
            if selected_idx > 0:
                order[selected_idx], order[selected_idx - 1] = \
                    order[selected_idx - 1], order[selected_idx]
                selected_idx -= 1
                changed = True
        elif key == ord("J"):
            if selected_idx < len(order) - 1:
                order[selected_idx], order[selected_idx + 1] = \
                    order[selected_idx + 1], order[selected_idx]
                selected_idx += 1
                changed = True

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    try:
        curses.curs_set(1)
    except Exception:
        pass
    curses.endwin()
