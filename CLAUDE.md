# arch-boki-logout

Personal Python project: a minimal, themeable session-end overlay
(`usr/share/arch-boki-logout/arch-boki-logout.py`) and lock screen
(`usr/share/arch-boki-logout/arch-boki-lock.py`) for Linux, built with
Tkinter. Works across X11/Wayland and many WMs/DEs (Hyprland, i3, GNOME,
XFCE, sway, etc). No build system — it's a flat tree mirroring an installed
system (`/usr/...`, `/etc/skel/...`).

Full architecture notes live in [memory/](memory/) — see the session
workflow below for how to load it.

## Session workflow

This project uses a memory-backed session convention, backed by the
[memory/](memory/) folder in this repo (see [memory/README.md](memory/README.md)):

- When the user types **"start session"**: read `memory/overview.md` and the
  top entries of `memory/session-log.md` to re-orient, then briefly state
  where things stand before doing anything else.
- When the user types **"end session"**: append a summary of what was done
  in this conversation to `memory/session-log.md` (newest entry on top), and
  update `memory/overview.md` / `memory/repo-setup.md` if the
  architecture/setup changed, then confirm memory is updated.

## Publishing

Do not run `push.sh` or `set-git-cred.sh` non-interactively — they are the
user's own manual git helper scripts (`push.sh` prompts for a commit message
on stdin; `set-git-cred.sh` changes *global* git config). Use normal `git`
commands instead unless the user explicitly asks to run those scripts.
