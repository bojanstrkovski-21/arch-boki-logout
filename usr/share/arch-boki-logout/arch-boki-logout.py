#!/usr/bin/env python3
"""
arch-boki-logout — minimal session-end overlay
Buttons: cancel · shutdown · restart · lock · logout
Settings gear: opacity slider + theme picker
Keyboard shortcuts: Escape · S · R · K · L
"""

import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os
import io
import configparser
from PIL import Image, ImageTk

# ── lock file — prevent double launch ────────────────────────────────────────
LOCK_FILE = "/tmp/arch-boki-logout.lock"

if os.path.isfile(LOCK_FILE):
    print("[arch-boki-logout] already running. Remove /tmp/arch-boki-logout.lock if stuck.")
    sys.exit(1)

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

def _cleanup():
    try:
        os.unlink(LOCK_FILE)
    except FileNotFoundError:
        pass

# ── wayland check ─────────────────────────────────────────────────────────────
IS_WAYLAND = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

# ── artix uses loginctl instead of systemctl ─────────────────────────────────
try:
    from distro import id as distro_id
    _distro = distro_id()
except ImportError:
    _distro = ""

if _distro == "artix" and os.path.isfile("/usr/bin/loginctl"):
    CMD_SHUTDOWN  = "loginctl poweroff"
    CMD_RESTART   = "loginctl reboot"
else:
    CMD_SHUTDOWN  = "systemctl poweroff"
    CMD_RESTART   = "systemctl reboot"

# ── lock command ──────────────────────────────────────────────────────────────
if os.path.isfile("/usr/bin/arch-boki-lock"):
    CMD_LOCK = "arch-boki-lock"
elif IS_WAYLAND:
    if os.path.isfile("/usr/bin/hyprlock"):
        CMD_LOCK = "hyprlock"
    elif os.path.isfile("/usr/bin/gtklock"):
        CMD_LOCK = "gtklock"
    elif os.path.isfile("/usr/bin/swaylock"):
        CMD_LOCK = "swaylock"
    else:
        CMD_LOCK = "loginctl lock-session"
else:
    if os.path.isfile("/usr/bin/betterlockscreen"):
        CMD_LOCK = "betterlockscreen -l"
    elif os.path.isfile("/usr/bin/i3lock"):
        CMD_LOCK = "i3lock"
    else:
        CMD_LOCK = "xdg-screensaver lock"

# ── session detection ─────────────────────────────────────────────────────────
def _detect_desktop():
    desktop = "unknown"
    try:
        desktop = (
            os.environ.get("DESKTOP_SESSION")
            or os.environ.get("XDG_CURRENT_DESKTOP")
            or os.environ.get("XDG_SESSION_DESKTOP")
            or "unknown"
        )
        desktop = desktop.split(":")[0].strip().lower()
    except Exception:
        desktop = "unknown"

    if os.system("systemctl is-active --quiet ly") == 0:
        try:
            out = subprocess.run(
                ["sh", "-c", "env | grep XDG_CURRENT_DESKTOP"],
                shell=False, stdout=subprocess.PIPE,
            )
            desktop = out.stdout.decode().split("=")[1].strip().split(":")[0].lower()
        except Exception:
            desktop = "unknown"

    if desktop == "unknown":
        for wm in ("ohmychadwm", "chadwm"):
            try:
                if subprocess.run(
                    ["pgrep", "-x", wm],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode == 0:
                    desktop = wm
                    break
            except Exception:
                pass

    return desktop


def _get_logout_cmd():
    desktop = _detect_desktop()
    print(f"[arch-boki-logout] detected session: {desktop}")

    if desktop in ("herbstluftwm", "/usr/share/xsessions/herbstluftwm"):
        return "herbstclient quit"
    elif desktop in ("xfce", "/usr/share/xsessions/xfce"):
        return "xfce4-session-logout -f -l"
    elif desktop in ("ohmychadwm", "/usr/share/xsessions/ohmychadwm"):
        script = os.path.expanduser("~/.config/ohmychadwm/scripts/shutdown_ohmychadwm.sh")
        return script if os.path.isfile(script) else "pkill ohmychadwm"
    elif desktop in ("hypr", "/usr/share/xsessions/hypr"):
        return "pkill Hypr"
    elif desktop in ("dk", "/usr/share/xsessions/dk"):
        return "dkcmd exit"
    elif desktop in ("gnome", "gnome-xorg", "gnome-classic",
                     "/usr/share/xsessions/gnome",
                     "/usr/share/xsessions/gnome-xorg",
                     "/usr/share/xsessions/gnome-classic"):
        return "gnome-session-quit --logout --no-prompt"
    elif desktop in ("hyprland", "hyprland-uwsm",
                     "/usr/share/wayland-sessions/hyprland",
                     "/usr/share/wayland-sessions/hyprland-uwsm"):
        return "hyprctl dispatch exit"

    pkill_x11 = [
        "bspwm", "jwm", "openbox", "awesome", "qtile", "xmonad",
        "worm", "berry", "dwm", "chadwm", "flexi", "sunset",
        "i3", "i3-with-shmlog", "lxqt", "spectrwm", "icewm",
        "icewm-session", "cwm", "fvwm3", "stumpwm", "leftwm",
        "dusk", "wmderland", "nimdow", "oxwm",
    ]
    pkill_wayland = ["sway", "river", "wayfire", "newm", "niri", "oxwm"]

    for s in pkill_x11:
        if desktop in (s, f"/usr/share/xsessions/{s}"):
            return f"pkill {s}"

    for s in pkill_wayland:
        if desktop in (s, f"/usr/share/wayland-sessions/{s}"):
            return f"pkill {s}"

    if desktop and desktop != "unknown":
        name = desktop.split("/")[-1]
        print(f"[arch-boki-logout] unknown session, falling back to: pkill {name}")
        return f"pkill {name}"

    return f"pkill -KILL -u {os.environ.get('USER', '')}"


LOGOUT_CMD = _get_logout_cmd()

COMMANDS = {
    "logout":   LOGOUT_CMD.split(),
    "shutdown": CMD_SHUTDOWN.split(),
    "restart":  CMD_RESTART.split(),
    "lock":     CMD_LOCK.split(),
}

# ── config persistence ────────────────────────────────────────────────────────
CONFIG_DIR  = os.path.expanduser("~/.config/arch-boki-logout")
CONFIG_FILE = os.path.join(CONFIG_DIR, "arch-boki-logout.conf")

def _load_config():
    parser = configparser.RawConfigParser()
    opacity     = 0.82
    theme       = "handy"
    icon_size   = 80
    colorscheme = "default"
    if os.path.isfile(CONFIG_FILE):
        parser.read(CONFIG_FILE)
        try:
            opacity = int(parser.get("settings", "opacity")) / 100
        except Exception:
            pass
        try:
            theme = parser.get("settings", "theme")
        except Exception:
            pass
        try:
            icon_size = int(parser.get("settings", "icon_size"))
        except Exception:
            pass
        try:
            colorscheme = parser.get("settings", "colorscheme")
        except Exception:
            pass
    return opacity, theme, icon_size, colorscheme

def _save_settings(opacity, theme, icon_size, colorscheme):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    parser = configparser.RawConfigParser()
    if os.path.isfile(CONFIG_FILE):
        parser.read(CONFIG_FILE)
    if not parser.has_section("settings"):
        parser.add_section("settings")
    parser.set("settings", "opacity",     str(int(round(opacity * 100))))
    parser.set("settings", "theme",       theme)
    parser.set("settings", "icon_size",   str(int(icon_size)))
    parser.set("settings", "colorscheme", colorscheme)
    with open(CONFIG_FILE, "w") as f:
        parser.write(f)

# ── themes ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
THEMES_DIR = os.path.join(SCRIPT_DIR, "themes")
ICON_SIZE  = 80

# ── colorscheme ────────────────────────────────────────────────────────────────
COLORS_DIR = os.path.join(SCRIPT_DIR, "colors")
CS = {}  # current colorscheme — populated before widget creation

_CS_DEFAULTS = {
    "bg":            "#141414",
    "label":         "#cccccc",
    "hint":          "#555555",
    "gear_normal":   "#555555",
    "gear_hover":    "#aaaaaa",
    "circle_hover":  "#2a2a2a",
    "circle_click":  "#3d3d3d",
    "popover_bg":    "#1e1e1e",
    "popover_field": "#2a2a2a",
    "popover_fg":    "#aaaaaa",
}

def _get_colorschemes():
    if not os.path.isdir(COLORS_DIR):
        return ["default"]
    schemes = sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(COLORS_DIR)
        if f.endswith(".conf")
    )
    return schemes if schemes else ["default"]

def _load_colorscheme(name):
    """Populate CS from a colorscheme file; falls back to defaults."""
    colors = dict(_CS_DEFAULTS)
    path = os.path.join(COLORS_DIR, f"{name}.conf")
    parser = configparser.RawConfigParser()
    if os.path.isfile(path):
        parser.read(path)
        if parser.has_section("colors"):
            for key in colors:
                try:
                    colors[key] = parser.get("colors", key)
                except Exception:
                    pass
    CS.clear()
    CS.update(colors)

def _get_themes():
    if not os.path.isdir(THEMES_DIR):
        return ["(no themes)"]
    themes = sorted(
        d for d in os.listdir(THEMES_DIR)
        if os.path.isdir(os.path.join(THEMES_DIR, d))
    )
    return themes if themes else ["(no themes)"]

def _svg_to_photoimage(svg_path, size=ICON_SIZE):
    try:
        result = subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size), svg_path],
            capture_output=True, timeout=3,
        )
        img = Image.open(io.BytesIO(result.stdout))
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"[arch-boki-logout] icon load failed: {svg_path}: {e}", file=sys.stderr)
        return None

def _load_icon(action, theme, size):
    path = os.path.join(THEMES_DIR, theme, f"{action}.svg")
    if os.path.isfile(path):
        return _svg_to_photoimage(path, size)
    return None

# ── constants ─────────────────────────────────────────────────────────────────
DEFAULT_OPACITY, DEFAULT_THEME, DEFAULT_ICON_SIZE, DEFAULT_COLORSCHEME = _load_config()

FONT_LABEL   = ("Inter", 11, "bold italic")
FONT_HINT    = ("Inter", 9, "bold italic")
FONT_SESSION = ("MesloLGS Nerd Font", 32, "bold italic")

ACTIONS = ["cancel", "shutdown", "restart", "lock", "logout"]

LABELS = {
    "cancel":   "Cancel",
    "shutdown": "Shutdown",
    "restart":  "Reboot",
    "lock":     "Lock",
    "logout":   "Logout",
}

SHORTCUTS = {
    "cancel":   "Esc",
    "shutdown": "S",
    "restart":  "R",
    "lock":     "K",
    "logout":   "L",
}

# ── run action ────────────────────────────────────────────────────────────────
def run(action):
    if action == "cancel":
        _cleanup()
        root.destroy()
        return
    _cleanup()
    cmd = COMMANDS[action]
    try:
        subprocess.Popen(cmd)
    except FileNotFoundError as e:
        print(f"[arch-boki-logout] command not found: {e}", file=sys.stderr)
    root.destroy()

# ── button registry ───────────────────────────────────────────────────────────────────
_btn_refs   = {}  # action -> {canvas, circle, img, frame, text, hint}
_photo_refs = {}  # action -> PhotoImage (keeps refs alive)

def _apply_theme(theme):
    for action in ACTIONS:
        refs = _btn_refs.get(action)
        if refs is None:
            continue
        ph = _load_icon(action, theme, current_icon_size)
        if ph:
            _photo_refs[action] = ph
            refs["canvas"].itemconfig(refs["img"], image=ph)
        else:
            _photo_refs.pop(action, None)
            refs["canvas"].itemconfig(refs["img"], image="")

def _apply_icon_size(new_size):
    global current_icon_size
    current_icon_size = new_size
    c = new_size + 28
    for action in ACTIONS:
        refs = _btn_refs.get(action)
        if refs is None:
            continue
        refs["canvas"].config(width=c, height=c)
        refs["canvas"].coords(refs["circle"], 0, 0, c, c)
        refs["canvas"].coords(refs["img"], c // 2, c // 2)
        ph = _load_icon(action, current_theme, new_size)
        if ph:
            _photo_refs[action] = ph
            refs["canvas"].itemconfig(refs["img"], image=ph)

def _apply_colorscheme(name):
    """Load colorscheme and refresh all main-window widgets."""
    _load_colorscheme(name)
    try:
        root.configure(bg=CS["bg"])
        wrapper.configure(bg=CS["bg"])
        btn_row.configure(bg=CS["bg"])
        gear.configure(bg=CS["bg"], fg=CS["hint"])
        top_bar.configure(bg=CS["bg"])
        session_lbl.configure(bg=CS["bg"], fg=CS["label"])
        taskman_btn.configure(bg=CS["bg"], fg=CS["label"])
    except Exception:
        pass
    for refs in _btn_refs.values():
        refs["frame"].configure(bg=CS["bg"])
        refs["canvas"].configure(bg=CS["bg"])
        refs["canvas"].itemconfig(refs["circle"], fill=CS["bg"])
        refs["text"].configure(bg=CS["bg"], fg=CS["label"])
        refs["hint"].configure(bg=CS["bg"], fg=CS["hint"])

# ── button widget ─────────────────────────────────────────────────────────────
def make_button(parent, action, theme, icon_size):
    c = icon_size + 44   # canvas size: icon + padding so circle has breathing room

    frame = tk.Frame(parent, bg=CS["bg"], cursor="hand2",
                     relief="flat", bd=0, highlightthickness=0)

    canvas = tk.Canvas(frame, width=c, height=c,
                       bg=CS["bg"], highlightthickness=0, bd=0)
    circle_id = canvas.create_oval(0, 0, c, c, fill=CS["bg"], outline="")

    ph = _load_icon(action, theme, icon_size)
    if ph:
        _photo_refs[action] = ph
    img_id = canvas.create_image(c // 2, c // 2, anchor="center",
                                 image=ph if ph else "")
    canvas.pack(pady=(14, 4))

    text_lbl = tk.Label(frame, text=LABELS[action],
                        bg=CS["bg"], fg=CS["label"], font=FONT_LABEL)
    text_lbl.pack(pady=(0, 2))

    hint_lbl = tk.Label(frame, text=f"[{SHORTCUTS[action]}]",
                        bg=CS["bg"], fg=CS["hint"], font=FONT_HINT)
    hint_lbl.pack(pady=(0, 12))

    _btn_refs[action] = {
        "canvas": canvas, "circle": circle_id, "img": img_id,
        "frame": frame, "text": text_lbl, "hint": hint_lbl,
    }

    def on_enter(_):
        canvas.itemconfig(circle_id, fill=CS["circle_hover"])

    def on_leave(_):
        canvas.itemconfig(circle_id, fill=CS["bg"])

    def on_click(_):
        canvas.itemconfig(circle_id, fill=CS["circle_click"])
        root.after(120, lambda: run(action))

    for w in (frame, canvas, text_lbl, hint_lbl):
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
        w.bind("<Button-1>", on_click)

    return frame

# ── settings popover ──────────────────────────────────────────────────────────
def open_settings(gear_btn):
    win = tk.Toplevel(root)
    win.title("settings")
    win.configure(bg=CS["popover_bg"])
    win.resizable(False, False)
    win.overrideredirect(True)

    root.update_idletasks()
    gx = gear_btn.winfo_rootx()
    gy = gear_btn.winfo_rooty()
    win.geometry(f"+{gx}+{gy + gear_btn.winfo_height() + 4}")

    pb       = CS["popover_bg"]
    pf       = CS["popover_field"]
    pg       = CS["popover_fg"]
    ph_color = CS["hint"]

    pad = dict(padx=14, pady=6)

    # ── opacity
    tk.Label(win, text="opacity", bg=pb, fg=ph_color,
             font=FONT_HINT).pack(anchor="w", **pad)

    slider_row = tk.Frame(win, bg=pb)
    slider_row.pack(fill="x", padx=14, pady=(0, 8))

    pct = tk.Label(slider_row, text=f"{int(root.attributes('-alpha') * 100)}%",
                   bg=pb, fg=pg, font=FONT_HINT, width=4)

    def on_slide(val):
        v = round(float(val), 2)
        root.attributes("-alpha", v)
        pct.configure(text=f"{int(v * 100)}%")

    sl = tk.Scale(
        slider_row,
        from_=0.20, to=1.0, resolution=0.01,
        orient="horizontal", length=160,
        command=on_slide,
        bg=pb, fg=ph_color,
        troughcolor="#333333",
        activebackground=pg,
        highlightthickness=0,
        bd=0, showvalue=False,
    )
    sl.set(root.attributes("-alpha"))
    sl.pack(side="left")
    pct.pack(side="left", padx=(6, 0))

    # ── icon size
    tk.Label(win, text="icon size", bg=pb, fg=ph_color,
             font=FONT_HINT).pack(anchor="w", padx=14, pady=(10, 2))

    icon_row = tk.Frame(win, bg=pb)
    icon_row.pack(fill="x", padx=14, pady=(0, 8))

    icon_px = tk.Label(icon_row, text=f"{current_icon_size}px",
                       bg=pb, fg=pg, font=FONT_HINT, width=5)

    def on_icon_slide(val):
        new_size = int(float(val))
        _apply_icon_size(new_size)
        icon_px.configure(text=f"{new_size}px")

    icon_sl = tk.Scale(
        icon_row,
        from_=40, to=140, resolution=4,
        orient="horizontal", length=160,
        command=on_icon_slide,
        bg=pb, fg=ph_color,
        troughcolor="#333333",
        activebackground=pg,
        highlightthickness=0,
        bd=0, showvalue=False,
    )
    icon_sl.set(current_icon_size)
    icon_sl.pack(side="left")
    icon_px.pack(side="left", padx=(6, 0))

    # ── colorscheme
    colorschemes = _get_colorschemes()
    tk.Label(win, text="colorscheme", bg=pb, fg=ph_color,
             font=FONT_HINT).pack(anchor="w", padx=14, pady=(10, 2))

    cs_var = tk.StringVar(value=current_colorscheme)

    cs_btn = tk.Button(
        win, text=f"{current_colorscheme}  ▾",
        bg=pf, fg=pg, font=FONT_HINT,
        activebackground=CS["circle_hover"], activeforeground=pg,
        highlightthickness=0, relief="flat",
        anchor="w", padx=8, pady=5,
    )
    cs_btn.pack(fill="x", padx=14, pady=(0, 8))

    _cs_popup_ref = [None]

    def _close_cs_popup():
        if _cs_popup_ref[0] and _cs_popup_ref[0].winfo_exists():
            _cs_popup_ref[0].destroy()
        _cs_popup_ref[0] = None
        win.focus_force()

    def _open_cs_popup():
        if _cs_popup_ref[0] and _cs_popup_ref[0].winfo_exists():
            _close_cs_popup()
            return

        popup = tk.Toplevel(win)
        popup.overrideredirect(True)
        popup.configure(bg=pf)
        _cs_popup_ref[0] = popup

        # position below the button
        win.update_idletasks()
        bx = cs_btn.winfo_rootx()
        by = cs_btn.winfo_rooty() + cs_btn.winfo_height()
        bw = cs_btn.winfo_width()
        row_h = 22
        visible = min(12, len(colorschemes))
        popup.geometry(f"{bw}x{visible * row_h}+{bx}+{by}")

        style_name = f"Popup.Vertical.TScrollbar"
        sb_style = ttk.Style(popup)
        sb_style.theme_use("clam")
        sb_style.configure(style_name,
            troughcolor=pf, background=CS["circle_click"],
            darkcolor=pf, lightcolor=pf,
            bordercolor=pf, arrowcolor=pg,
            relief="flat", arrowsize=10)
        sb_style.map(style_name, background=[("active", CS["circle_hover"])])

        sb = ttk.Scrollbar(popup, orient="vertical", style=style_name)
        lb = tk.Listbox(
            popup,
            yscrollcommand=sb.set,
            bg=pf, fg=pg, font=FONT_HINT,
            selectbackground=CS["circle_click"], selectforeground=pg,
            highlightthickness=0, relief="flat",
            activestyle="none", bd=0,
        )
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        for s in colorschemes:
            lb.insert("end", s)

        # pre-select current
        if current_colorscheme in colorschemes:
            idx = colorschemes.index(cs_var.get())
            lb.selection_set(idx)
            lb.see(idx)

        def _pick(event=None):
            idx = lb.nearest(event.y) if event else (lb.curselection() or [None])[0]
            if idx is not None and 0 <= idx < len(colorschemes):
                name = colorschemes[idx]
                cs_var.set(name)
                cs_btn.configure(text=f"{name}  ▾")
                _apply_colorscheme(name)
            _close_cs_popup()

        def _cs_focus_out(e=None):
            focused = win.focus_get()
            w = focused
            while w is not None:
                if w == popup:
                    return
                w = getattr(w, "master", None)
            _close_cs_popup()

        lb.bind("<ButtonPress-1>", _pick)
        lb.bind("<Return>", _pick)
        lb.bind("<Escape>", lambda e: _close_cs_popup())
        lb.bind("<MouseWheel>", lambda e: lb.yview_scroll(int(-1*(e.delta/120)), "units"))
        lb.bind("<Button-4>", lambda e: lb.yview_scroll(-1, "units"))
        lb.bind("<Button-5>", lambda e: lb.yview_scroll(1, "units"))
        lb.bind("<FocusOut>", _cs_focus_out)
        popup.after(50, lb.focus_set)

    cs_btn.configure(command=_open_cs_popup)

    def on_cs_change(*_):
        pass  # handled directly in _pick

    # ── theme
    themes = _get_themes()
    tk.Label(win, text="theme", bg=pb, fg=ph_color,
             font=FONT_HINT).pack(anchor="w", padx=14, pady=(10, 2))

    theme_var = tk.StringVar(value=current_theme)

    theme_btn = tk.Button(
        win, text=f"{current_theme}  ▾",
        bg=pf, fg=pg, font=FONT_HINT,
        activebackground=CS["circle_hover"], activeforeground=pg,
        highlightthickness=0, relief="flat",
        anchor="w", padx=8, pady=5,
    )
    theme_btn.pack(fill="x", padx=14, pady=(0, 8))

    _th_popup_ref = [None]

    def _close_th_popup():
        if _th_popup_ref[0] and _th_popup_ref[0].winfo_exists():
            _th_popup_ref[0].destroy()
        _th_popup_ref[0] = None
        win.focus_force()

    def _open_th_popup():
        if _th_popup_ref[0] and _th_popup_ref[0].winfo_exists():
            _close_th_popup()
            return

        popup = tk.Toplevel(win)
        popup.overrideredirect(True)
        popup.configure(bg=pf)
        _th_popup_ref[0] = popup

        win.update_idletasks()
        bx = theme_btn.winfo_rootx()
        by = theme_btn.winfo_rooty() + theme_btn.winfo_height()
        bw = theme_btn.winfo_width()
        row_h = 22
        visible = min(12, len(themes))
        popup.geometry(f"{bw}x{visible * row_h}+{bx}+{by}")

        th_style = ttk.Style(popup)
        th_style.theme_use("clam")
        th_style.configure("Th.Vertical.TScrollbar",
            troughcolor=pf, background=CS["circle_click"],
            darkcolor=pf, lightcolor=pf,
            bordercolor=pf, arrowcolor=pg,
            relief="flat", arrowsize=10)
        th_style.map("Th.Vertical.TScrollbar", background=[("active", CS["circle_hover"])])

        sb = ttk.Scrollbar(popup, orient="vertical", style="Th.Vertical.TScrollbar")
        lb = tk.Listbox(
            popup,
            yscrollcommand=sb.set,
            bg=pf, fg=pg, font=FONT_HINT,
            selectbackground=CS["circle_click"], selectforeground=pg,
            highlightthickness=0, relief="flat",
            activestyle="none", bd=0,
        )
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        for t in themes:
            lb.insert("end", t)

        if current_theme in themes:
            idx = themes.index(theme_var.get())
            lb.selection_set(idx)
            lb.see(idx)

        def _pick_theme(event=None):
            idx = lb.nearest(event.y) if event else (lb.curselection() or [None])[0]
            if idx is not None and 0 <= idx < len(themes):
                name = themes[idx]
                theme_var.set(name)
                theme_btn.configure(text=f"{name}  ▾")
                _apply_theme(name)
            _close_th_popup()

        def _th_focus_out(e=None):
            focused = win.focus_get()
            w = focused
            while w is not None:
                if w == popup:
                    return
                w = getattr(w, "master", None)
            _close_th_popup()

        lb.bind("<ButtonPress-1>", _pick_theme)
        lb.bind("<Return>", _pick_theme)
        lb.bind("<Escape>", lambda e: _close_th_popup())
        lb.bind("<MouseWheel>", lambda e: lb.yview_scroll(int(-1*(e.delta/120)), "units"))
        lb.bind("<Button-4>", lambda e: lb.yview_scroll(-1, "units"))
        lb.bind("<Button-5>", lambda e: lb.yview_scroll(1, "units"))
        lb.bind("<FocusOut>", _th_focus_out)
        popup.after(50, lb.focus_set)

    theme_btn.configure(command=_open_th_popup)

    def on_theme_change(*_):
        pass  # handled directly in _pick_theme

    # ── session info
    tk.Label(win, text=f"session: {_detect_desktop()}",
             bg=pb, fg=ph_color,
             font=FONT_HINT).pack(anchor="w", padx=14, pady=(0, 10))

    def close_popover(e=None):
        win.destroy()
        root.focus_force()

    def on_save():
        global current_theme, current_icon_size, current_colorscheme
        current_theme       = theme_var.get()
        current_icon_size   = int(icon_sl.get())
        current_colorscheme = cs_var.get()
        _save_settings(root.attributes("-alpha"), current_theme,
                       current_icon_size, current_colorscheme)
        close_popover()

    save_btn = tk.Button(
        win, text="save", command=on_save,
        bg=pf, fg=pg,
        font=FONT_HINT, relief="flat",
        cursor="hand2", activebackground=CS["circle_hover"],
        activeforeground=pg, bd=0,
        padx=10, pady=4,
    )
    save_btn.pack(anchor="e", padx=14, pady=(0, 10))

    def _on_escape(e=None):
        if _cs_popup_ref[0] and _cs_popup_ref[0].winfo_exists():
            _close_cs_popup()
        elif _th_popup_ref[0] and _th_popup_ref[0].winfo_exists():
            _close_th_popup()
        else:
            close_popover()

    win.bind_all("<Escape>", _on_escape)
    # NOTE: no <FocusOut> binding — it would fire when dropdowns open
    win.grab_set()
    win.focus_force()

# ── build main window ─────────────────────────────────────────────────────────
current_theme       = DEFAULT_THEME
current_icon_size   = DEFAULT_ICON_SIZE
current_colorscheme = DEFAULT_COLORSCHEME
_load_colorscheme(current_colorscheme)  # populate CS before any widget is created

root = tk.Tk()
root.title("arch-boki-logout")
root.attributes("-fullscreen", True)
root.configure(bg=CS["bg"])
root.update_idletasks()
root.attributes("-alpha", DEFAULT_OPACITY)

def _quit(_=None):
    _cleanup()
    root.destroy()

root.bind("<Escape>", _quit)
root.bind_all("<s>", lambda e: run("shutdown"))
root.bind_all("<S>", lambda e: run("shutdown"))
root.bind_all("<r>", lambda e: run("restart"))
root.bind_all("<R>", lambda e: run("restart"))
root.bind_all("<k>", lambda e: run("lock"))
root.bind_all("<K>", lambda e: run("lock"))
root.bind_all("<l>", lambda e: run("logout"))
root.bind_all("<L>", lambda e: run("logout"))
root.focus_force()

# top bar — session name + task manager
_session_name = _detect_desktop()

def _launch_taskmanager(_=None):
    for cmd in ("xfce4-taskmanager", "gnome-system-monitor", "lxtask",
                "mate-system-monitor", "ksysguard", "plasma-systemmonitor"):
        if subprocess.run(["which", cmd], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0:
            subprocess.Popen([cmd])
            return
    # fallback: htop in a terminal
    for term in ("xterm", "alacritty", "kitty", "foot", "gnome-terminal"):
        if subprocess.run(["which", term], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0:
            subprocess.Popen([term, "-e", "htop"])
            return

top_bar = tk.Frame(root, bg=CS["bg"])
top_bar.place(relx=0.5, rely=0, anchor="n", y=110)

session_lbl = tk.Label(top_bar, text=_session_name,
                        bg=CS["bg"], fg=CS["label"],
                        font=FONT_SESSION)
session_lbl.pack(side="left")

taskman_btn = tk.Label(top_bar, text="→ power manager",
                        bg=CS["bg"], fg=CS["label"],
                        font=FONT_SESSION)
taskman_btn.pack(side="left", padx=(12, 0))

# gear button — top left
gear = tk.Label(root, text="⚙", bg=CS["bg"], fg=CS["gear_normal"],
                font=("Inter", 16, "bold italic"), cursor="hand2")
gear.place(x=18, y=14)
gear.bind("<Button-1>", lambda e: open_settings(gear))
gear.bind("<Enter>", lambda e: gear.configure(fg=CS["gear_hover"]))
gear.bind("<Leave>", lambda e: gear.configure(fg=CS["hint"]))

# center wrapper
wrapper = tk.Frame(root, bg=CS["bg"])
wrapper.place(relx=0.5, rely=0.5, anchor="center")

btn_row = tk.Frame(wrapper, bg=CS["bg"])
btn_row.pack()

for action in ACTIONS:
    btn = make_button(btn_row, action, current_theme, current_icon_size)
    btn.pack(side="left", padx=30)

root.mainloop()
_cleanup()
