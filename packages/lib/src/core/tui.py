import curses
import os
from . import config
from . import state, render

ICON_MODE_LABELS = {
    "off": "Off",
    "bot": "Bot Icon (e.g. 󰚩)",
    "logo": "Provider Logo (image)",
}
USAGE_DISPLAY_LABELS = {"used": "Used", "remaining": "Remaining"}
# Rows 0-7 are settings; providers start here.
FIRST_PROVIDER = 8

def get_selectable_items():
    cache = state.load_cache()
    items = []
    if cache:
        for p in cache:
            dir_name = render.connection_key(p)
            idx = p.get("_idx", 0)
            p_name = render.entry_name(p)
            metrics = render.usable_metrics(p)
            for m in sorted(metrics, key=render.metric_sort_key):
                mtype = render.metric_key(m)
                title = render.metric_title(m)
                if not m.get("name") and ":" in mtype:
                    title += f" ({mtype.split(':', 1)[1]})"
                items.append({
                    "provider": dir_name,
                    "idx": idx,
                    "metric": mtype,
                    "label": f"{p_name} · {title}"
                })
    if not items:
        for p in config.available_connections():
            for mtype in ["rolling", "weekly", "monthly"]:
                items.append({
                    "provider": p,
                    "idx": 0,
                    "metric": mtype,
                    "label": f"{p} ({mtype})"
                })
    return items

def run():
    all_providers = sorted(config.available_connections())
    if not all_providers:
        return

    enabled = config.enabled_connection_order()
    enabled_set = set(enabled)
    order = [p for p in enabled if p in all_providers]
    for p in all_providers:
        if p not in order:
            order.append(p)

    selectable_items = get_selectable_items()
    if not selectable_items:
        return

    current_selected = state.load_selected() or {}
    bar_items = state.get_selected_items(current_selected)
    if not bar_items:
        bar_items = state.get_selected_items(selectable_items[0])
    
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
    icon_mode_idx = state.ICON_MODES.index(state.get_icon_mode(current_selected))
    usage_display_idx = state.USAGE_DISPLAY_MODES.index(state.get_usage_display(current_selected))
    show_total = state.get_show_total(current_selected)

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

    def safe_addstr(y, x, text, attr=curses.A_NORMAL):
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def draw():
        nonlocal scroll_offset
        h, w = stdscr.getmaxyx()
        list_height = max(1, h - 15)

        if selected_idx >= FIRST_PROVIDER:
            prov_idx = selected_idx - FIRST_PROVIDER
            if prov_idx < scroll_offset:
                scroll_offset = prov_idx
            if prov_idx >= scroll_offset + list_height:
                scroll_offset = prov_idx - list_height + 1
        else:
            scroll_offset = 0

        stdscr.clear()

        title = " AI Status Config "
        safe_addstr(0, max(0, (w - len(title)) // 2), title,
                       curses.A_REVERSE | curses.A_BOLD)

        # 1. Active Provider
        primary = bar_items[0]
        prov_label = next((item["label"] for item in selectable_items if state.get_selected_items(item)[0] == primary),
                          f"{primary['provider']} · {primary['metric']} (unavailable)")
        prov_text = f"  Bar items ({len(bar_items)}): < {prov_label} >  SPACE to select items"
        if len(prov_text) > w:
            prov_text = prov_text[:w]
        attr = curses.A_REVERSE if selected_idx == 0 else curses.A_NORMAL
        safe_addstr(2, 0, prov_text, attr)

        # Display Options
        opt_header = "--- Display Settings (SPACE to toggle) ---"
        if len(opt_header) > w:
            opt_header = opt_header[:w]
        safe_addstr(4, 0, opt_header, curses.A_DIM)

        # 2. Show Provider
        flag_p = "[x]" if show_provider else "[ ]"
        p_text = f"   {flag_p} Show Provider (e.g. Gemini)"
        attr = curses.A_REVERSE if selected_idx == 1 else curses.A_NORMAL
        safe_addstr(5, 0, p_text, attr)

        # 3. Show Plan/Origin
        flag_m = "[x]" if show_model else "[ ]"
        m_text = f"   {flag_m} Show Plan/Origin (e.g. Antigravity)"
        attr = curses.A_REVERSE if selected_idx == 2 else curses.A_NORMAL
        safe_addstr(6, 0, m_text, attr)

        # 4. Show Metric
        flag_mt = "[x]" if show_metric else "[ ]"
        mt_text = f"   {flag_mt} Show Metric Name (e.g. Rolling Usage)"
        attr = curses.A_REVERSE if selected_idx == 3 else curses.A_NORMAL
        safe_addstr(7, 0, mt_text, attr)

        # 5. Show Percentage
        flag_pct = "[x]" if show_pct else "[ ]"
        pct_text = f"   {flag_pct} Show Percentage (e.g. 4%)"
        attr = curses.A_REVERSE if selected_idx == 4 else curses.A_NORMAL
        safe_addstr(8, 0, pct_text, attr)
        
        # 6. Provider Icon
        icon_label = ICON_MODE_LABELS[state.ICON_MODES[icon_mode_idx]]
        icon_text = f"   Provider Icon: < {icon_label} >"
        if len(icon_text) > w:
            icon_text = icon_text[:w]
        attr = curses.A_REVERSE if selected_idx == 5 else curses.A_NORMAL
        safe_addstr(9, 0, icon_text, attr)

        usage_label = USAGE_DISPLAY_LABELS[state.USAGE_DISPLAY_MODES[usage_display_idx]]
        usage_text = f"   Usage display: < {usage_label} >"
        attr = curses.A_REVERSE if selected_idx == 6 else curses.A_NORMAL
        safe_addstr(10, 0, usage_text[:w], attr)

        total_text = f"   [{'x' if show_total else ' '}] Show total"
        attr = curses.A_REVERSE if selected_idx == 7 else curses.A_NORMAL
        safe_addstr(11, 0, total_text[:w], attr)

        # Header for providers
        header_text = "--- Providers List (SPACE to toggle, Shift+J/K to reorder) ---"
        if len(header_text) > w:
            header_text = header_text[:w]
        safe_addstr(13, 0, header_text, curses.A_DIM)

        # Draw providers list
        visible = order[scroll_offset:scroll_offset + list_height]
        for i, prov in enumerate(visible):
            y = 14 + i
            if y >= h - 1:
                break
            enabled_flag = prov in enabled_set
            checkbox = "[x]" if enabled_flag else "[ ]"
            prefix = " > " if scroll_offset + i + FIRST_PROVIDER == selected_idx else "   "
            text = f"{prefix}{checkbox} {prov}"
            if len(text) > w:
                text = text[:w]
            attr = curses.A_REVERSE if scroll_offset + i + FIRST_PROVIDER == selected_idx else curses.A_NORMAL
            safe_addstr(y, 0, text, attr)

        help_text = (
            "\u2191\u2193 navigate  \u2190\u2192 change first  "
            "SPACE toggle  Shift+J/K move  ENTER save  ESC cancel"
        )
        if len(help_text) > w:
            help_text = help_text[:w]
        safe_addstr(h - 1, max(0, (w - len(help_text)) // 2), help_text)

        stdscr.refresh()

    max_idx = FIRST_PROVIDER + len(order) - 1 if order else FIRST_PROVIDER - 1

    while True:
        draw()
        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        elif key == ord("\n"):
            if not enabled_set:
                continue
            if config_changed or selected_changed:
                if config_changed:
                    cfg = [p for p in order if p in enabled_set]
                    config.save_connection_order(cfg)
                
                chosen = [item for item in bar_items if item["provider"] in enabled_set]
                if not chosen:
                    chosen = state.get_selected_items(next((item for item in selectable_items if item["provider"] in enabled_set),
                                                          {"provider": next(iter(enabled_set), order[0]), "idx": 0, "metric": "rolling"}))
                
                # Safeguard: if all options are disabled, force defaults (provider & percentage)
                final_show_provider = show_provider
                final_show_pct = show_pct
                if not (show_provider or show_model or show_metric or show_pct):
                    final_show_provider = True
                    final_show_pct = True
                    
                new_selected = {
                    **current_selected,
                    "show_provider": final_show_provider,
                    "show_model": show_model,
                    "show_metric": show_metric,
                    "show_pct": final_show_pct,
                    "icon_mode": state.ICON_MODES[icon_mode_idx],
                    "usage_display": state.USAGE_DISPLAY_MODES[usage_display_idx],
                    "show_total": show_total,
                }
                state.set_selected_items(new_selected, chosen)
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
                draft = state.select_primary({"items": bar_items}, selectable_items[selected_item_idx])
                bar_items = state.get_selected_items(draft)
                selected_changed = True
            elif selected_idx == 5:
                icon_mode_idx = (icon_mode_idx - 1) % len(state.ICON_MODES)
                selected_changed = True
            elif selected_idx == 6:
                usage_display_idx = (usage_display_idx - 1) % len(state.USAGE_DISPLAY_MODES)
                selected_changed = True
        elif key in (curses.KEY_RIGHT,):
            if selected_idx == 0:
                selected_item_idx = (selected_item_idx + 1) % len(selectable_items)
                draft = state.select_primary({"items": bar_items}, selectable_items[selected_item_idx])
                bar_items = state.get_selected_items(draft)
                selected_changed = True
            elif selected_idx == 5:
                icon_mode_idx = (icon_mode_idx + 1) % len(state.ICON_MODES)
                selected_changed = True
            elif selected_idx == 6:
                usage_display_idx = (usage_display_idx + 1) % len(state.USAGE_DISPLAY_MODES)
                selected_changed = True
        elif key == ord(" "):
            if selected_idx == 0:
                choices = [item for item in selectable_items if item["provider"] in enabled_set]
                for item in bar_items:
                    if item["provider"] in enabled_set and not any(state.get_selected_items(choice)[0] == item for choice in choices):
                        choices.append(dict(item, label=f"{item['provider']} · {item['metric']} (unavailable)"))
                if not choices:
                    continue
                draft_items = list(bar_items)
                cursor = 0
                applied = False
                while True:
                    h, w = stdscr.getmaxyx()
                    stdscr.clear()
                    safe_addstr(0, 0, " Bar items — select as many limits as you want ", curses.A_REVERSE | curses.A_BOLD)
                    height = max(1, h - 3)
                    start = max(0, cursor - height + 1)
                    for row, item in enumerate(choices[start:start + height]):
                        identity = state.get_selected_items(item)[0]
                        checked = identity in draft_items
                        text = f" {'[x]' if checked else '[ ]'} {item['label']}"
                        safe_addstr(row + 1, 0, text[:w], curses.A_REVERSE if row + start == cursor else curses.A_NORMAL)
                    safe_addstr(h - 1, 0, "↑↓ navigate  SPACE toggle  ENTER apply  ESC cancel"[:w])
                    stdscr.refresh()
                    item_key = stdscr.getch()
                    if item_key in (27, ord("q")):
                        break
                    if item_key == ord("\n"):
                        if not draft_items:
                            continue
                        applied = bar_items != draft_items
                        bar_items = draft_items
                        selected_item_idx = next((index for index, item in enumerate(selectable_items)
                                                  if state.get_selected_items(item)[0] == bar_items[0]), selected_item_idx)
                        break
                    if item_key in (curses.KEY_UP, ord("k")):
                        cursor = max(0, cursor - 1)
                    elif item_key in (curses.KEY_DOWN, ord("j")):
                        cursor = min(len(choices) - 1, cursor + 1)
                    elif item_key == ord(" "):
                        identity = state.get_selected_items(choices[cursor])[0]
                        draft_items = [item for item in draft_items if item != identity] if identity in draft_items else draft_items + [identity]
                selected_changed = selected_changed or applied
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
                icon_mode_idx = (icon_mode_idx + 1) % len(state.ICON_MODES)
                selected_changed = True
            elif selected_idx == 6:
                usage_display_idx = (usage_display_idx + 1) % len(state.USAGE_DISPLAY_MODES)
                selected_changed = True
            elif selected_idx == 7:
                show_total = not show_total
                selected_changed = True
            elif selected_idx >= FIRST_PROVIDER:
                prov = order[selected_idx - FIRST_PROVIDER]
                if prov in enabled_set:
                    enabled_set.remove(prov)
                else:
                    enabled_set.add(prov)
                config_changed = True
        elif key in (curses.KEY_PPAGE,):
            if selected_idx >= FIRST_PROVIDER:
                selected_idx = max(FIRST_PROVIDER, selected_idx - 10)
            else:
                selected_idx = 0
        elif key in (curses.KEY_NPAGE,):
            if selected_idx >= FIRST_PROVIDER:
                selected_idx = min(max_idx, selected_idx + 10)
            else:
                selected_idx = max_idx
        elif key == ord("K"):
            if selected_idx > FIRST_PROVIDER:
                idx1 = selected_idx - FIRST_PROVIDER
                idx2 = idx1 - 1
                order[idx1], order[idx2] = order[idx2], order[idx1]
                selected_idx -= 1
                config_changed = True
        elif key == ord("J"):
            if selected_idx >= FIRST_PROVIDER and selected_idx < max_idx:
                idx1 = selected_idx - FIRST_PROVIDER
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
