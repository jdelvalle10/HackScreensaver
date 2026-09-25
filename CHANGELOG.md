# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-25

### Added
- Multi-panel curses screensaver:
  - Matrix rain (SIGINT)
  - Operations log
  - Network topology map
  - Memory dump
  - Active jobs progress bars
  - Blinking alert overlay
  - Header bar with uptime and clock
- Recognizable Windows filenames falling through the Matrix rain, highlighted in yellow, that blink before reaching the ground.
- School locations as log targets: Cafeteria, Test Room, Video Game Arena, Principal's Office, Main Office, and 24 more.
- Word-wrapped Operations Log with continuation lines aligned under the message.
- Responsive layout with live resize handling and a minimum-size (70x20) notice.
- All IP addresses restricted to RFC 5737 documentation ranges. No network activity.
- `install.py`, a cross-platform installer that:
  - Detects the OS, Linux distribution, and WSL.
  - Verifies Python and `curses`, and installs `windows-curses` on Windows.
  - Installs `tmux` with apt-get, dnf, yum, pacman, zypper, apk, brew, or pkg.
  - Creates a `hackscreen` launcher.
  - Optionally configures tmux screensaver mode, with a backup of the existing config and no duplicate entries on re-runs.
  - Asks permission before every change and offers a `--check` mode.
- `requirements.txt` with a platform marker, so it installs nothing on Linux or macOS.

### Fixed (during pre-release testing)
- The installer no longer aborts when `apt-get update` fails because of an unrelated unreachable third-party repository.
