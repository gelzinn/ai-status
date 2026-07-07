import curses
import os
from . import config
from . import state

def get_selectable_items():
    cache = state.load_cache()
    items = []
    if cache:
        for p in cache:
            dir_name = p.get("_dir")
            idx = p.get("_idx", 0)
            p_name = p.get("provider", dir_name)
            metrics = p.get("metrics", [])
            for m in metrics:
                mtype = m.get("type", "rolling")
                items.append({
                    "provider": dir_name,
                    "idx": idx,
                    "metric": mtype,
                    "label": f"{p_name} ({mtype})"
                })
    if not items:
        for p in config.available_providers():
            for mtype in ["rolling", "weekly", "monthly"]:
                items.append({
                    "provider": p,
                    "idx": 0,
                    "metric": mtype,
                    "label": f"{p} ({mtype})"
                })
    return items

def run():
    all_providers = sorted(config.available_providers())
    if not all_providers:
        return

    enabled = config.enabled_order()
    enabled_set = set(enabled)
    order = [p for p in enabled if p in all_providers]
    for p in all_providers:
        if p not in order:
            order.append(p)

    selectable_items = get_selectable_items()
    if not selectable_items:
        return

    current_selected = state.load_selected() or {}
    
    # Selected provider index
    selected_item_idx = 0
    for idx, item in enumerate(selectable_items):
        if (item["provider"] == current_selected.get("provider") and 
            item["idx"] == current_selected.get("idx", 0) and 
            item["metric"] == current_selected.get("metric")):
            selected_item_idx = idx
            break

    # Display flags
    show_provider = current_selected.get("show_provider", True)
    show_model = current_selected.get("show_model", True)
    show_metric = current_selected.get("show_metric", False)
    show_pct = current_selected.get("show_pct", True)

    selected_idx = 0
    scroll_offset = 0
    config_changed = False
    selected_changed = False

    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    try:
        curses.curs_set(0)
    except Exception:
        pass

    def draw():
        nonlocal scroll_offset
        h, w = stdscr.getmaxyx()
        list_height = max(1, h - 11)

        if selected_idx >= 5:
            prov_idx = selected_idx - 5
            if prov_idx < scroll_offset:
                scroll_offset = prov_idx
            if prov_idx >= scroll_offset + list_height:
                scroll_offset = prov_idx - list_height + 1
        else:
            scroll_offset = 0

        stdscr.clear()

        title = " AI Status Config "
        stdscr.addstr(0, max(0, (w - len(title)) // 2), title,
                       curses.A_REVERSE | curses.A_BOLD)

        # 1. Active Provider
        prov_label = selectable_items[selected_item_idx]["label"]
        prov_text = f"  Active Provider: < {prov_label} >"
        if len(prov_text) > w:
            prov_text = prov_text[:w]
        attr = curses.A_REVERSE if selected_idx == 0 else curses.A_NORMAL
        stdscr.addstr(2, 0, prov_text, attr)

        # Display Options
        opt_header = "--- Display Settings (SPACE to toggle) ---"
        if len(opt_header) > w:
            opt_header = opt_header[:w]
        stdscr.addstr(4, 0, opt_header, curses.A_DIM)

        # 2. Show Provider
        flag_p = "[x]" if show_provider else "[ ]"
        p_text = f"   {flag_p} Show Provider (e.g. Gemini)"
        attr = curses.A_REVERSE if selected_idx == 1 else curses.A_NORMAL
        stdscr.addstr(5, 0, p_text, attr)

        # 3. Show Plan/Origin
        flag_m = "[x]" if show_model else "[ ]"
        m_text = f"   {flag_m} Show Plan/Origin (e.g. Antigravity)"
        attr = curses.A_REVERSE if selected_idx == 2 else curses.A_NORMAL
        stdscr.addstr(6, 0, m_text, attr)

        # 4. Show Metric
        flag_mt = "[x]" if show_metric else "[ ]"
        mt_text = f"   {flag_mt} Show Metric Name (e.g. Rolling Usage)"
        attr = curses.A_REVERSE if selected_idx == 3 else curses.A_NORMAL
        stdscr.addstr(7, 0, mt_text, attr)

        # 5. Show Percentage
        flag_pct = "[x]" if show_pct else "[ ]"
        pct_text = f"   {flag_pct} Show Percentage (e.g. 4%)"
        attr = curses.A_REVERSE if selected_idx == 4 else curses.A_NORMAL
        stdscr.addstr(8, 0, pct_text, attr)
        
        # 6. Show Text Icon
        show_icon = current_selected.get("show_icon", True)
        flag_icon = "[x]" if show_icon else "[ ]"
        icon_text = f"   {flag_icon} Show Text Icon (e.g. 󰚩)"
        attr = curses.A_REVERSE if selected_idx == 5 else curses.A_NORMAL
        stdscr.addstr(9, 0, icon_text, attr)

        # Header for providers
        header_text = "--- Providers List (SPACE to toggle, Shift+J/K to reorder) ---"
        if len(header_text) > w:
            header_text = header_text[:w]
        stdscr.addstr(11, 0, header_text, curses.A_DIM)

        # Draw providers list
        visible = order[scroll_offset:scroll_offset + list_height]
        for i, prov in enumerate(visible):
            y = 12 + i
            if y >= h - 1:
                break
            enabled_flag = prov in enabled_set
            checkbox = "[x]" if enabled_flag else "[ ]"
            prefix = " > " if scroll_offset + i + 6 == selected_idx else "   "
            text = f"{prefix}{checkbox} {prov}"
            if len(text) > w:
                text = text[:w]
            attr = curses.A_REVERSE if scroll_offset + i + 6 == selected_idx else curses.A_NORMAL
            stdscr.addstr(y, 0, text, attr)

        help_text = (
            "\u2191\u2193 navigate  \u2190\u2192 change active  "
            "SPACE toggle  Shift+J/K move  ENTER save  ESC cancel"
        )
        stdscr.addstr(h - 1, max(0, (w - len(help_text)) // 2), help_text)

        stdscr.refresh()

    max_idx = 6 + len(order) - 1 if order else 5

    while True:
        draw()
        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        elif key == ord("\n"):
            if config_changed or selected_changed:
                if config_changed:
                    cfg = [p for p in order if p in enabled_set]
                    config.save_config(cfg)
                
                sel_item = selectable_items[selected_item_idx]
                
                # Safeguard: if all options are disabled, force defaults (provider & percentage)
                final_show_provider = show_provider
                final_show_pct = show_pct
                if not (show_provider or show_model or show_metric or show_pct):
                    final_show_provider = True
                    final_show_pct = True
                    
                new_selected = {
                    "provider": sel_item["provider"],
                    "idx": sel_item["idx"],
                    "metric": sel_item["metric"],
                    "show_provider": final_show_provider,
                    "show_model": show_model,
                    "show_metric": show_metric,
                    "show_pct": final_show_pct,
                    "show_icon": show_icon
                }
                state.save_selected(new_selected)
                
                # If only display settings changed, no need to trigger_refresh!
                # The daemon will detect selected_mtime change and instantly re-render.
                if config_changed:
                    state.trigger_refresh()
            break
        elif key in (curses.KEY_UP, ord("k")) and selected_idx > 0:
            selected_idx -= 1
        elif key in (curses.KEY_DOWN, ord("j")) and selected_idx < max_idx:
            selected_idx += 1
        elif key in (curses.KEY_LEFT,):
            if selected_idx == 0:
                selected_item_idx = (selected_item_idx - 1) % len(selectable_items)
                selected_changed = True
        elif key in (curses.KEY_RIGHT,):
            if selected_idx == 0:
                selected_item_idx = (selected_item_idx + 1) % len(selectable_items)
                selected_changed = True
        elif key == ord(" "):
            if selected_idx == 0:
                selected_item_idx = (selected_item_idx + 1) % len(selectable_items)
                selected_changed = True
            elif selected_idx == 1:
                show_provider = not show_provider
                selected_changed = True
            elif selected_idx == 2:
                show_model = not show_model
                selected_changed = True
            elif selected_idx == 3:
                show_metric = not show_metric
                selected_changed = True
            elif selected_idx == 4:
                show_pct = not show_pct
                selected_changed = True
            elif selected_idx == 5:
                show_icon = not show_icon
                selected_changed = True
            elif selected_idx >= 6:
                prov = order[selected_idx - 6]
                if prov in enabled_set:
                    enabled_set.remove(prov)
                else:
                    enabled_set.add(prov)
                config_changed = True
        elif key in (curses.KEY_PPAGE,):
            if selected_idx >= 6:
                selected_idx = max(6, selected_idx - 10)
            else:
                selected_idx = 0
        elif key in (curses.KEY_NPAGE,):
            if selected_idx >= 6:
                selected_idx = min(max_idx, selected_idx + 10)
            else:
                selected_idx = max_idx
        elif key == ord("K"):
            if selected_idx > 6:
                idx1 = selected_idx - 6
                idx2 = idx1 - 1
                order[idx1], order[idx2] = order[idx2], order[idx1]
                selected_idx -= 1
                config_changed = True
        elif key == ord("J"):
            if selected_idx >= 6 and selected_idx < max_idx:
                idx1 = selected_idx - 6
                idx2 = idx1 + 1
                order[idx1], order[idx2] = order[idx2], order[idx1]
                selected_idx += 1
                config_changed = True

    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    try:
        curses.curs_set(1)
    except Exception:
        pass
    curses.endwin()
