# Session log

Newest entries on top.

## 2026-06-30 — Hyprland logout/lock fixes

Fixed three real bugs in `arch-boki-logout.py`/`arch-boki-lock.py`, all
confirmed working by the user on their actual Hyprland machine:

1. **Hyprland exit not working**: `hyprctl dispatch exit` errored with a Lua
   syntax error on the user's Hyprland build (`hl.dispatch: expected a
   dispatcher`). Fixed by switching to the new Lua-style dispatcher syntax:
   `hyprctl dispatch hl.dsp.exit()`. Confirmed by the user testing the raw
   command in their terminal before the script was changed.
2. **uwsm-managed Hyprland logout**: switched from running `uwsm stop`
   directly as a subprocess to routing it through Hyprland's own exec
   dispatcher: `hyprctl eval 'hl.dsp.exec("uwsm stop")'`, per the user's
   request. This required switching `COMMANDS` dict construction from naive
   `.split()` to `shlex.split()` (added `import shlex`) so the quoted Lua
   string with an embedded space (`"uwsm stop"`) doesn't get torn apart.
3. **Lock screen only locking the current workspace**: root cause is that
   Tkinter has no native Wayland backend — `arch-boki-lock` runs via
   XWayland and so can never get a real compositor-wide input grab on
   Wayland (no `ext-session-lock-v1` support). Fixed by reordering
   `CMD_LOCK` selection so Wayland prefers real lockers first: hyprlock →
   swaylock → gtklock → waylock → `arch-boki-lock` (last resort) →
   `loginctl lock-session`. X11 still prefers `arch-boki-lock` first since
   its `grab_set_global()` genuinely works there.

Also fixed, earlier in the same session: lock screen password field not
auto-focusing on Wayland (added a `_focus_password()` helper called via a
200ms-delayed `root.after`, mirroring the existing X11 delay — focusing
before the window was actually mapped was the bug).

See [overview.md](overview.md) for the updated architecture notes on both
the Hyprland dispatch syntax and the Wayland lock priority.

## 2026-06-30 — memory system setup

Set up a project-local memory folder (this folder) so notes travel with the
repo instead of living only in Claude's internal config: read through the
full codebase (both Python scripts, shell wrappers, push/cred helper
scripts, desktop entry, config skeletons) and wrote
[overview.md](overview.md), [repo-setup.md](repo-setup.md), and this log.
Added `CLAUDE.md` at the repo root documenting the "start session"/"end
session" convention so it loads automatically. No code changes made.

Repo state at the time: branch `master`, clean working tree, latest commit
`4c4f571 upd`. Recent history: hyprland logout support added
(`f324545`), sardi-candi theme fix (`cbea40f`), lock screen added earlier
(`fbe1c04`).
