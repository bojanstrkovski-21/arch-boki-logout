#!/usr/bin/env python3
"""
arch-boki-lock — minimal lock screen
Works on X11 (full input grab) and Wayland (fullscreen best-effort)
Requires: python-pam  (Arch: python-pam)
"""

import tkinter as tk
import subprocess
import os
import sys
import time
import threading

# ── wayland check ─────────────────────────────────────────────────────────────
IS_WAYLAND = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

# ── PAM authentication ────────────────────────────────────────────────────────
def _authenticate(username: str, password: str) -> bool:
    # Primary: python-pam
    try:
        import pam
        p = pam.pam()
        return p.authenticate(username, password)
    except ImportError:
        pass

    # Fallback: unix_chkpwd (setuid helper, available on most distros)
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
    BG       = "#0d0d0d"
    FG_CLOCK = "#cdd6f4"
    FG_DATE  = "#6c7086"
    FG_USER  = "#45475a"
    FG_ERR   = "#f38ba8"
    FG_HINT  = "#585b70"
    ENTRY_BG = "#1e1e2e"
    ENTRY_FG = "#cdd6f4"
    ENTRY_HL = "#585b70"

    def __init__(self):
        self.username = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()
        self._update_clock()
        if not IS_WAYLAND:
            self.root.after(200, self._grab_input)
        self.root.mainloop()

    # ── window setup ─────────────────────────────────────────────────────────
    def _setup_window(self):
        r = self.root
        r.title("")
        r.configure(bg=self.BG)
        r.attributes("-fullscreen", True)
        r.attributes("-topmost", True)
        r.overrideredirect(True)
        # Block all exit shortcuts
        r.protocol("WM_DELETE_WINDOW", lambda: None)
        for seq in ("<Escape>", "<Alt-F4>", "<Control-c>",
                    "<Control-z>", "<Super-l>", "<Super-r>"):
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

        # Clock
        self.clock_var = tk.StringVar()
        tk.Label(
            r, textvariable=self.clock_var,
            font=("monospace", 64, "bold"),
            bg=self.BG, fg=self.FG_CLOCK,
        ).place(relx=0.5, rely=0.33, anchor="center")

        # Date
        self.date_var = tk.StringVar()
        tk.Label(
            r, textvariable=self.date_var,
            font=("monospace", 18),
            bg=self.BG, fg=self.FG_DATE,
        ).place(relx=0.5, rely=0.42, anchor="center")

        # Username hint
        tk.Label(
            r, text=self.username,
            font=("monospace", 12),
            bg=self.BG, fg=self.FG_USER,
        ).place(relx=0.5, rely=0.52, anchor="center")

        # Password entry
        self.pw_var = tk.StringVar()
        self.pw_entry = tk.Entry(
            r, textvariable=self.pw_var,
            show="●", font=("monospace", 16),
            bg=self.ENTRY_BG, fg=self.ENTRY_FG,
            insertbackground=self.ENTRY_FG,
            relief="flat", width=24,
            highlightthickness=1,
            highlightcolor=self.ENTRY_HL,
            highlightbackground="#313244",
        )
        self.pw_entry.place(relx=0.5, rely=0.58, anchor="center", ipady=8)
        self.pw_entry.focus_force()
        self.pw_entry.bind("<Return>", self._try_unlock)

        # Status / error
        self.status_var = tk.StringVar(value="")
        tk.Label(
            r, textvariable=self.status_var,
            font=("monospace", 12),
            bg=self.BG, fg=self.FG_ERR,
        ).place(relx=0.5, rely=0.64, anchor="center")

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
