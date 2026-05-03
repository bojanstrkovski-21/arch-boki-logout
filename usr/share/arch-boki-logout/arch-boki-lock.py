#!/usr/bin/env python3
"""
arch-boki-lock — minimal lock screen
Works on X11 (full input grab) and Wayland (fullscreen best-effort)
Requires: python-pam  (Arch: python-pam)
"""

import tkinter as tk
from tkinter import ttk
import configparser
import subprocess
import os
import sys
import time
import threading

# ── wayland check ─────────────────────────────────────────────────────────────
IS_WAYLAND = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
COLORS_DIR  = os.path.join(SCRIPT_DIR, "colors")
CONFIG_DIR  = os.path.expanduser("~/.config/arch-boki-logout")
CONFIG_FILE = os.path.join(CONFIG_DIR, "arch-boki-lock.conf")

FONT_HINT = ("Inter", 9, "bold italic")

# ── colorscheme defaults ──────────────────────────────────────────────────────
_CS_DEFAULTS = {
    # standard keys (shared with logout)
    "bg":            "#0d0d0d",
    "label":         "#cdd6f4",
    "hint":          "#6c7086",
    "gear_normal":   "#585b70",
    "gear_hover":    "#cdd6f4",
    "circle_hover":  "#1e1e2e",
    "circle_click":  "#313244",
    "popover_bg":    "#1e1e2e",
    "popover_field": "#313244",
    "popover_fg":    "#cdd6f4",
    # lock-specific keys (fall back to standard keys if absent)
    "clock_fg":      None,   # → label
    "date_fg":       None,   # → hint
    "user_fg":       None,   # → hint
    "error_fg":      "#f38ba8",
    "entry_bg":      None,   # → popover_field
    "entry_fg":      None,   # → label
    "entry_hl":      None,   # → hint
}

CS = {}

def _load_colorscheme(name: str):
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
    # resolve fallbacks for lock-specific keys
    if not colors["clock_fg"]:  colors["clock_fg"]  = colors["label"]
    if not colors["date_fg"]:   colors["date_fg"]   = colors["hint"]
    if not colors["user_fg"]:   colors["user_fg"]   = colors["hint"]
    if not colors["entry_bg"]:  colors["entry_bg"]  = colors["popover_field"]
    if not colors["entry_fg"]:  colors["entry_fg"]  = colors["label"]
    if not colors["entry_hl"]:  colors["entry_hl"]  = colors["hint"]
    CS.clear()
    CS.update(colors)

def _get_colorschemes():
    if not os.path.isdir(COLORS_DIR):
        return ["default-lock"]
    schemes = sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(COLORS_DIR)
        if f.endswith(".conf")
    )
    return schemes if schemes else ["default-lock"]

# ── config persistence ────────────────────────────────────────────────────────
def _load_config():
    parser = configparser.RawConfigParser()
    opacity     = 1.0
    colorscheme = "default-lock"
    if os.path.isfile(CONFIG_FILE):
        parser.read(CONFIG_FILE)
        try:
            opacity = int(parser.get("settings", "opacity")) / 100
        except Exception:
            pass
        try:
            colorscheme = parser.get("settings", "colorscheme")
        except Exception:
            pass
    return opacity, colorscheme

def _save_config(opacity: float, colorscheme: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    parser = configparser.RawConfigParser()
    if os.path.isfile(CONFIG_FILE):
        parser.read(CONFIG_FILE)
    if not parser.has_section("settings"):
        parser.add_section("settings")
    parser.set("settings", "opacity",     str(int(round(opacity * 100))))
    parser.set("settings", "colorscheme", colorscheme)
    with open(CONFIG_FILE, "w") as f:
        parser.write(f)

# ── PAM authentication ────────────────────────────────────────────────────────
def _authenticate(username: str, password: str) -> bool:
    try:
        import pam
        p = pam.pam()
        return p.authenticate(username, password)
    except ImportError:
        pass
    try:
        proc = subprocess.run(
            ["unix_chkpwd", username, "nullok"],
            input=password.encode() + b"\x00",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


# ── lock screen ───────────────────────────────────────────────────────────────
class LockScreen:

    def __init__(self):
        self.username = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        self.opacity, self.colorscheme = _load_config()
        _load_colorscheme(self.colorscheme)

        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()
        self._update_clock()
        self.root.attributes("-alpha", self.opacity)
        if not IS_WAYLAND:
            self.root.after(200, self._grab_input)
        self.root.mainloop()

    # ── window setup ─────────────────────────────────────────────────────────
    def _setup_window(self):
        r = self.root
        r.title("")
        r.configure(bg=CS["bg"])
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        r.geometry(f"{sw}x{sh}+0+0")
        r.attributes("-fullscreen", True)
        r.protocol("WM_DELETE_WINDOW", lambda: None)
        for seq in ("<Alt-F4>", "<Control-c>", "<Control-z>",
                    "<Super_L>", "<Super_R>"):
            r.bind(seq, lambda e: None)

    def _grab_input(self):
        try:
            self.root.grab_set_global()
        except tk.TclError:
            self.root.grab_set()
        self.pw_entry.focus_force()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        r = self.root

        # Gear button — top right
        self.gear_btn = tk.Label(
            r, text="⚙", font=("monospace", 18),
            bg=CS["bg"], fg=CS["gear_normal"],
            cursor="hand2",
        )
        self.gear_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-18, y=14)
        self.gear_btn.bind("<Enter>",    lambda e: self.gear_btn.config(fg=CS["gear_hover"]))
        self.gear_btn.bind("<Leave>",    lambda e: self.gear_btn.config(fg=CS["gear_normal"]))
        self.gear_btn.bind("<Button-1>", lambda e: self._open_settings())

        # Clock
        self.clock_var = tk.StringVar()
        self.clock_lbl = tk.Label(
            r, textvariable=self.clock_var,
            font=("monospace", 64, "bold"),
            bg=CS["bg"], fg=CS["clock_fg"],
        )
        self.clock_lbl.place(relx=0.5, rely=0.33, anchor="center")

        # Date
        self.date_var = tk.StringVar()
        self.date_lbl = tk.Label(
            r, textvariable=self.date_var,
            font=("monospace", 18),
            bg=CS["bg"], fg=CS["date_fg"],
        )
        self.date_lbl.place(relx=0.5, rely=0.42, anchor="center")

        # Username
        self.user_lbl = tk.Label(
            r, text=self.username,
            font=("monospace", 12),
            bg=CS["bg"], fg=CS["user_fg"],
        )
        self.user_lbl.place(relx=0.5, rely=0.52, anchor="center")

        # Password entry
        self.pw_var = tk.StringVar()
        self.pw_entry = tk.Entry(
            r, textvariable=self.pw_var,
            show="●", font=("monospace", 16),
            bg=CS["entry_bg"], fg=CS["entry_fg"],
            insertbackground=CS["entry_fg"],
            relief="flat", width=24,
            highlightthickness=1,
            highlightcolor=CS["entry_hl"],
            highlightbackground=CS["entry_hl"],
        )
        self.pw_entry.place(relx=0.5, rely=0.58, anchor="center")
        self.pw_entry.focus_force()
        self.pw_entry.bind("<Return>", self._try_unlock)

        # Status / error
        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(
            r, textvariable=self.status_var,
            font=("monospace", 12),
            bg=CS["bg"], fg=CS["error_fg"],
        )
        self.status_lbl.place(relx=0.5, rely=0.64, anchor="center")

    # ── apply colorscheme live ────────────────────────────────────────────────
    def _apply_colorscheme(self, name: str):
        self.colorscheme = name
        _load_colorscheme(name)
        r = self.root
        r.configure(bg=CS["bg"])
        self.gear_btn.configure(bg=CS["bg"], fg=CS["gear_normal"])
        self.clock_lbl.configure(bg=CS["bg"], fg=CS["clock_fg"])
        self.date_lbl.configure(bg=CS["bg"], fg=CS["date_fg"])
        self.user_lbl.configure(bg=CS["bg"], fg=CS["user_fg"])
        self.status_lbl.configure(bg=CS["bg"], fg=CS["error_fg"])
        self.pw_entry.configure(
            bg=CS["entry_bg"], fg=CS["entry_fg"],
            insertbackground=CS["entry_fg"],
            highlightcolor=CS["entry_hl"],
            highlightbackground=CS["entry_hl"],
        )

    # ── settings popover ─────────────────────────────────────────────────────
    def _open_settings(self):
        if not IS_WAYLAND:
            try:
                self.root.grab_release()
            except tk.TclError:
                pass

        win = tk.Toplevel(self.root)
        win.title("")
        win.configure(bg=CS["popover_bg"])
        win.resizable(False, False)
        win.overrideredirect(True)

        self.root.update_idletasks()
        gx = self.gear_btn.winfo_rootx()
        gy = self.gear_btn.winfo_rooty()
        win.geometry(f"+{gx - 160}+{gy + self.gear_btn.winfo_height() + 4}")

        pb = CS["popover_bg"]
        pf = CS["popover_field"]
        pg = CS["popover_fg"]
        ph = CS["hint"]

        pad = dict(padx=14, pady=6)

        # ── opacity
        tk.Label(win, text="opacity", bg=pb, fg=ph,
                 font=FONT_HINT).pack(anchor="w", **pad)

        slider_row = tk.Frame(win, bg=pb)
        slider_row.pack(fill="x", padx=14, pady=(0, 8))

        pct_lbl = tk.Label(slider_row,
                           text=f"{int(self.root.attributes('-alpha') * 100)}%",
                           bg=pb, fg=pg, font=FONT_HINT, width=4)

        def on_slide(val):
            v = round(float(val), 2)
            self.root.attributes("-alpha", v)
            pct_lbl.configure(text=f"{int(v * 100)}%")

        sl = tk.Scale(
            slider_row, from_=0.20, to=1.0, resolution=0.01,
            orient="horizontal", length=160,
            command=on_slide,
            bg=pb, fg=ph, troughcolor="#333333",
            activebackground=pg, highlightthickness=0,
            bd=0, showvalue=False,
        )
        sl.set(self.root.attributes("-alpha"))
        sl.pack(side="left")
        pct_lbl.pack(side="left", padx=(6, 0))

        # ── colorscheme
        colorschemes = _get_colorschemes()
        tk.Label(win, text="colorscheme", bg=pb, fg=ph,
                 font=FONT_HINT).pack(anchor="w", padx=14, pady=(10, 2))

        cs_var = tk.StringVar(value=self.colorscheme)
        cs_btn = tk.Button(
            win, text=f"{self.colorscheme}  ▾",
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

            win.update_idletasks()
            bx = cs_btn.winfo_rootx()
            by = cs_btn.winfo_rooty() + cs_btn.winfo_height()
            bw = cs_btn.winfo_width()
            row_h = 22
            visible = min(12, len(colorschemes))
            popup.geometry(f"{bw}x{visible * row_h}+{bx}+{by}")

            sb_style = ttk.Style(popup)
            sb_style.theme_use("clam")
            sb_style.configure("Lock.Vertical.TScrollbar",
                troughcolor=pf, background=CS["circle_click"],
                darkcolor=pf, lightcolor=pf,
                bordercolor=pf, arrowcolor=pg,
                relief="flat", arrowsize=10)
            sb_style.map("Lock.Vertical.TScrollbar",
                background=[("active", CS["circle_hover"])])

            sb = ttk.Scrollbar(popup, orient="vertical",
                               style="Lock.Vertical.TScrollbar")
            lb = tk.Listbox(
                popup, yscrollcommand=sb.set,
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
            if self.colorscheme in colorschemes:
                idx = colorschemes.index(cs_var.get())
                lb.selection_set(idx)
                lb.see(idx)

            def _pick(event=None):
                idx = lb.nearest(event.y) if event else (lb.curselection() or [None])[0]
                if idx is not None and 0 <= idx < len(colorschemes):
                    name = colorschemes[idx]
                    cs_var.set(name)
                    cs_btn.configure(text=f"{name}  ▾")
                    self._apply_colorscheme(name)
                    # refresh popover colors
                    win.configure(bg=CS["popover_bg"])
                _close_cs_popup()

            lb.bind("<ButtonPress-1>", _pick)
            lb.bind("<Return>",        _pick)
            lb.bind("<Escape>",        lambda e: _close_cs_popup())
            lb.bind("<Button-4>",      lambda e: lb.yview_scroll(-1, "units"))
            lb.bind("<Button-5>",      lambda e: lb.yview_scroll( 1, "units"))
            popup.after(50, lb.focus_set)

        cs_btn.configure(command=_open_cs_popup)

        # ── save / close
        def _on_save():
            self.opacity     = round(float(sl.get()), 2)
            self.colorscheme = cs_var.get()
            _save_config(self.opacity, self.colorscheme)
            _close_popover()

        def _close_popover(e=None):
            win.destroy()
            if not IS_WAYLAND:
                self.root.after(100, self._grab_input)
            else:
                self.pw_entry.focus_force()

        save_btn = tk.Button(
            win, text="save", command=_on_save,
            bg=pf, fg=pg, font=FONT_HINT,
            relief="flat", cursor="hand2",
            activebackground=CS["circle_hover"],
            activeforeground=pg, bd=0, padx=10, pady=4,
        )
        save_btn.pack(anchor="e", padx=14, pady=(0, 10))

        def _on_escape(e=None):
            if _cs_popup_ref[0] and _cs_popup_ref[0].winfo_exists():
                _close_cs_popup()
            else:
                _close_popover()

        win.bind_all("<Escape>", _on_escape)
        win.grab_set()
        win.focus_force()

    # ── clock ────────────────────────────────────────────────────────────────
    def _update_clock(self):
        now = time.localtime()
        self.clock_var.set(time.strftime("%H:%M", now))
        self.date_var.set(time.strftime("%A, %d %B %Y", now))
        self.root.after(1000, self._update_clock)

    # ── unlock ───────────────────────────────────────────────────────────────
    def _try_unlock(self, _event=None):
        password = self.pw_var.get()
        self.pw_var.set("")
        self.status_var.set("·  ·  ·")
        self.pw_entry.config(state="disabled")
        self.root.update()

        def _check():
            ok = _authenticate(self.username, password)
            self.root.after(0, self._on_result, ok)

        threading.Thread(target=_check, daemon=True).start()

    def _on_result(self, success: bool):
        if success:
            if not IS_WAYLAND:
                try:
                    self.root.grab_release()
                except tk.TclError:
                    pass
            self.root.destroy()
        else:
            self.status_var.set("incorrect password")
            self.pw_entry.config(state="normal")
            self.pw_entry.focus_force()
            self.root.after(1800, lambda: self.status_var.set(""))


if __name__ == "__main__":
    LockScreen()
