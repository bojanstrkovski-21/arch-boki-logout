# Project overview

arch-boki-logout is a minimal, themeable session-end overlay and lock screen
for Linux (built for Arch/Artix, works across X11 and Wayland window
managers/desktop environments like Hyprland, i3, GNOME, XFCE, sway, etc).

## Components

- [usr/share/arch-boki-logout/arch-boki-logout.py](../usr/share/arch-boki-logout/arch-boki-logout.py)
  — main logout overlay. Tkinter fullscreen UI with 5 actions: cancel, shutdown,
  restart, lock, logout. Auto-detects the running desktop/WM (env vars, pgrep,
  Hyprland signature, ly display manager) and picks the right shutdown/restart/
  logout/lock command per desktop (systemctl vs loginctl on Artix, pkill for WM
  fallback, hyprctl for Hyprland, etc). Has a settings gear popover: opacity
  slider, icon size slider, colorscheme picker, theme (icon set) picker. Single-
  instance guarded via `/tmp/arch-boki-logout.lock`. Keyboard shortcuts:
  Esc/S/R/K/L.
- [usr/share/arch-boki-logout/arch-boki-lock.py](../usr/share/arch-boki-logout/arch-boki-lock.py)
  — standalone lock screen. Tkinter fullscreen, PAM authentication (via
  python-pam, falling back to `unix_chkpwd`), clock/date/username display,
  password entry, same colorscheme/opacity settings popover pattern as the
  logout screen. Grabs input globally on X11; best-effort fullscreen on
  Wayland (no global grab available).
- [usr/bin/arch-boki-logout](../usr/bin/arch-boki-logout) and
  [usr/bin/arch-boki-lock](../usr/bin/arch-boki-lock) — thin shell wrappers that
  exec the corresponding Python script (these are what get installed to PATH).
- [usr/share/arch-boki-logout/themes/](../usr/share/arch-boki-logout/themes/) —
  icon theme packs (svg/png per action: cancel, shutdown, restart, lock,
  logout, hibernate, switch). ~20 themes (beauty, blue, breeze, candy, sardi-*,
  sweet, white, yellow, etc).
- [usr/share/arch-boki-logout/colors/](../usr/share/arch-boki-logout/colors/) —
  colorscheme `.conf` files (background/label/hint/popover colors etc, shared
  key format between logout and lock screens, with lock-specific keys like
  clock_fg/date_fg/entry_fg falling back to the shared keys when absent).
  ~30 colorschemes (catppuccin variants, dracula, gruvbox, kanagawa, monokai,
  nightfox, everforest, etc) plus an `archboki` custom scheme that is the
  user's current default.
- [etc/skel/.config/arch-boki-logout/](../etc/skel/.config/arch-boki-logout/) —
  default user config skeleton (`arch-boki-logout.conf`,
  `arch-boki-lock.conf`) installed to new users' home dirs. Live user config
  is read/written at `~/.config/arch-boki-logout/*.conf` via Python's
  configparser.
- [usr/share/applications/arch-boki-logout.desktop](../usr/share/applications/arch-boki-logout.desktop)
  — desktop entry so the logout overlay shows up as a launchable app.

## Conventions / notable design points

- No build system / package manager — it's a flat filesystem tree mirroring
  an installed system (`/usr/...`, `/etc/skel/...`) meant to be packaged or
  rsynced into place (likely as an Arch package or manual install script,
  though no PKGBUILD exists yet in the repo).
- Desktop/session detection logic in `arch-boki-logout.py` (`_detect_desktop`,
  `_get_logout_cmd`) is the most complex/fragile part — handles many WMs by
  name, with pkill fallback lists for X11 and Wayland compositors.

See [repo-setup.md](repo-setup.md) for how changes get published, and
[session-log.md](session-log.md) for a history of what's been done.
