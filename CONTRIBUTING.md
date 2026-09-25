# Contributing

Thanks for your interest in improving hackscreen.

## Ground rules

- **Keep it cosmetic.** Pull requests that add real network activity, scanning, or file access won't be accepted. Every displayed IP address must come from the RFC 5737 documentation ranges.
- **Standard library only** on Linux and macOS. `windows-curses` is the single allowed dependency, and only on Windows.
- **Draw with `put()`**, never with `addstr()` directly, so the program stays crash-free at every terminal size.

## Reporting a bug or testing a platform

macOS, native Windows, and the non-apt Linux package managers have not been tested on real systems yet, so reports from those platforms are especially valuable. Please include:

1. The output of `python3 install.py --check`
2. Your terminal application and its size (for example, `tput cols; tput lines`)
3. What you expected, what happened, and any traceback

## Submitting changes

1. Fork the repo and create a branch: `git checkout -b my-feature`
2. Test at the minimum size (70x20), at a large size, and while resizing the window.
3. Update `CHANGELOG.md` under an `[Unreleased]` heading.
4. Open a pull request describing the change and how you tested it.

See [docs/CUSTOMIZATION.md](docs/CUSTOMIZATION.md) for how the panels work.
