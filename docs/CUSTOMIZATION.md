# Customizing hackscreen

Everything is in one file, `hackscreen.py`, and needs nothing beyond the Python standard library (plus `windows-curses` on Windows). After editing, run `python3 hackscreen.py` to see the result. If you used the installer, run `install.py` again to copy the updated file into place.

## Quick settings

| Setting | Location | Default | Notes |
|---|---|---|---|
| `FPS` | top of file | `20` | Higher is smoother but uses more CPU |
| `MIN_H`, `MIN_W` | top of file | `20`, `70` | Below this size, a "please enlarge" message is shown instead |
| `USE_KATAKANA` | top of file | `True` | `False` switches the rain to hex digits only |
| `DOC_NETS` | top of file | RFC 5737 ranges | **Keep these as documentation ranges** so the screensaver never displays a real host's address |
| `WINDOWS_FILES` | before `MatrixRain` | 26 names | Names longer than the panel height minus 2 are skipped automatically |
| `SCHOOL_TARGETS` | before `LOG_TEMPLATES` | 29 locations | Used for the `{target}` placeholder |
| `LOG_TEMPLATES` | before `LogPanel` | 16 templates | See placeholders below |
| `TASKS` | before `ProgressPanel` | 9 tasks | Names shown in ACTIVE JOBS |
| `HexDump.STRINGS` | `HexDump` class | 6 byte strings | Occasionally inserted and highlighted in the dump |
| `Alert.MESSAGES` | `Alert` class | 4 messages | Keep them under about 30 characters so they fit at the minimum width |
| Alert interval | `Alert._schedule` | 20-45 s | `random.uniform(20, 45)` |
| Header text | `draw_header` | `NEXUS//OPS CONSOLE v4.2` | Change it to your own class or lab name |

### Falling filenames

These values are in `MatrixRain`:

| Value | Default | Effect |
|---|---|---|
| Spawn chance | `0.10` in `_new_drop` | Probability that a new drop carries a filename (subject to the cap below) |
| Fall speed | `random.uniform(0.18, 0.3)` | Rows per frame. Slower speeds are easier to read and lengthen the blink. |
| `blink_rows` | `max(3, ih // 4)` | How far above the ground the blinking starts |
| `max_files` | `max(1, iw // 6)` | Maximum number of filenames falling at the same time |

### Log template placeholders

| Placeholder | Replaced with |
|---|---|
| `{target}` | A random entry from `SCHOOL_TARGETS` |
| `{ip}`, `{ip2}` | Random RFC 5737 addresses |
| `{port}` | A common service port |
| `{h8}`, `{h32}` | Random hex strings of 8 and 32 characters |
| `{n}`, `{m}` | Random integers, where `m` is greater than `n` |

Available colors: `C_GREEN`, `C_BRIGHT` (white), `C_RED`, `C_CYAN`, `C_YELLOW`.

Example:

```python
LOG_TEMPLATES.append(("[+] {target} smartboard hijacked via port {port}", C_YELLOW))
```

## Writing your own panel

Every panel subclasses `Panel` and implements two methods:

```python
class ClockPanel(Panel):
    title = "UTC CLOCK"

    def update(self):
        # Advance state once per frame. Keep this fast.
        self.now = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")

    def draw_inner(self, scr):
        # Draw inside the border. The drawable area starts at (self.iy, self.ix)
        # and is self.ih rows by self.iw columns.
        put(scr, self.iy + self.ih // 2, self.ix + (self.iw - 8) // 2,
            self.now, color(C_CYAN, curses.A_BOLD))
```

Rules to follow:

1. **Always draw with `put()`, never with `scr.addstr()` directly.** `put()` clips text to the screen, which is what keeps hackscreen crash-free at every window size.
2. **Stay inside your area.** Rows run from `self.iy` to `self.iy + self.ih - 1`, and columns from `self.ix` to `self.ix + self.iw - 1`.
3. **Don't block.** Anything slow in `update()` freezes every panel, because they all share one loop.
4. **Size things in `__init__` from `self.ih` and `self.iw`.** A panel is rebuilt from scratch whenever the terminal is resized.

To show the new panel, add it to the list returned by `build_layout()`. For example, give it part of the rain column:

```python
rain_h = body_h - 5
return [MatrixRain(top, 0, rain_h, rain_w),
        ClockPanel(top + rain_h, 0, 5, rain_w),
        ...]
```

## Classroom exercises

Suggested extensions, roughly in order of difficulty:

1. **Personalize it.** Change the header text, add ten new locations to `SCHOOL_TARGETS`, and write three new log templates. *(Lists, string formatting.)*
2. **Themes.** Add a `THEME` setting that switches every color at once, for example from green "Matrix" to amber "retro". *(Constants, refactoring.)*
3. **New panel: CPU/RAM gauges.** Draw fake meters that drift smoothly toward random targets instead of jumping. *(Classes, interpolation.)*
4. **Real data, safely.** Make a panel that displays the *local* machine's real hostname, uptime, or CPU count using only the standard library (`platform`, `os`). Discuss why the program should never scan or connect to other machines. *(Ethics, the standard library.)*
5. **Command-line options.** Add `--fps`, `--no-katakana`, and `--targets FILE` using `argparse`. *(CLI design, file I/O.)*
6. **Pathfinding packets.** In `NodeMap`, send packets along multi-hop routes computed with breadth-first search instead of single edges. *(Graphs, BFS.)*
7. **Discussion topic.** Compare three things the screensaver shows (port scanning, credential hash recovery, IDS evasion) with how those activities really look, and what makes them legal or illegal. *(Cybersecurity ethics and law.)*
