#!/usr/bin/env python3
"""
install.py - Installer for hackscreen.py

Detects the operating system, verifies dependencies, and asks for permission
before every change it makes. Nothing is installed or modified without a "y".

Usage:
    python3 install.py            interactive install
    python3 install.py --check    verify only; change nothing

Dependencies handled:
    Required  Python 3.8+                     (all platforms)
    Required  curses module                   (stdlib on Linux/macOS/BSD;
                                               windows-curses from PyPI on Windows)
    Optional  tmux, for idle-triggered        (Linux, macOS, BSD; not native on
              screensaver mode                 Windows - use WSL there)
"""

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP = "hackscreen"
SCRIPT_NAME = "hackscreen.py"
MIN_PY = (3, 8)
TMUX_MARKER = "# >>> hackscreen screensaver >>>"
TMUX_MARKER_END = "# <<< hackscreen screensaver <<<"

CHECK_ONLY = False


# --------------------------------------------------------------------------- #
# Console helpers
# --------------------------------------------------------------------------- #
def _ansi_ok():
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        os.system("")          # enables VT processing on Windows 10+ consoles
    return True


_C = _ansi_ok()


def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _C else text


def ok(msg):    print(_c("32", "  [ OK ] ") + msg)
def warn(msg):  print(_c("33", "  [WARN] ") + msg)
def fail(msg):  print(_c("31", "  [FAIL] ") + msg)
def info(msg):  print(_c("36", "  [INFO] ") + msg)
def head(msg):  print("\n" + _c("1", msg))


def ask(question, default_no=True):
    """Ask a yes/no question. Default is NO. In --check mode, never asks."""
    if CHECK_ONLY:
        info(f"(check mode) would ask: {question}")
        return False
    suffix = " [y/N] " if default_no else " [Y/n] "
    try:
        ans = input(_c("1", "  >> ") + question + suffix).strip().lower()
    except EOFError:
        return False
    if not ans:
        return not default_no
    return ans in ("y", "yes")


def run(cmd):
    """Show the exact command, run it, return True on success."""
    print(_c("2", "     $ " + " ".join(cmd)))
    try:
        return subprocess.run(cmd).returncode == 0
    except FileNotFoundError:
        fail(f"Command not found: {cmd[0]}")
        return False


# --------------------------------------------------------------------------- #
# OS detection
# --------------------------------------------------------------------------- #
def read_os_release():
    data = {}
    for p in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.rstrip("\n").split("=", 1)
                        data[k] = v.strip().strip('"')
            break
        except OSError:
            continue
    return data


def detect_os():
    system = platform.system()
    osinfo = {"system": system, "pretty": system, "distro_ids": [], "wsl": False}
    if system == "Linux":
        rel = read_os_release()
        osinfo["pretty"] = rel.get("PRETTY_NAME", "Linux")
        osinfo["distro_ids"] = [rel.get("ID", "")] + rel.get("ID_LIKE", "").split()
        osinfo["wsl"] = "microsoft" in platform.release().lower()
    elif system == "Darwin":
        osinfo["pretty"] = f"macOS {platform.mac_ver()[0]}"
    elif system == "Windows":
        osinfo["pretty"] = f"Windows {platform.release()} ({platform.version()})"
    else:
        osinfo["pretty"] = f"{system} {platform.release()}"
    return osinfo


def sudo_prefix():
    """[] if root, ['sudo'] if sudo exists, None if elevation is impossible."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    return ["sudo"] if shutil.which("sudo") else None


def package_manager(osinfo):
    """Return (name, [install-command list for tmux]) or (None, None)."""
    system = osinfo["system"]
    if system == "Darwin":
        return ("brew", [["brew", "install", "tmux"]]) if shutil.which("brew") else (None, None)
    if system == "FreeBSD" and shutil.which("pkg"):
        return "pkg", [["pkg", "install", "-y", "tmux"]]
    if system != "Linux":
        return None, None
    # Linux: pick by what's actually installed; distro ID is only a tiebreaker.
    candidates = [
        ("apt-get", [["apt-get", "update"], ["apt-get", "install", "-y", "tmux"]]),
        ("dnf",     [["dnf", "install", "-y", "tmux"]]),
        ("yum",     [["yum", "install", "-y", "tmux"]]),
        ("pacman",  [["pacman", "-S", "--needed", "--noconfirm", "tmux"]]),
        ("zypper",  [["zypper", "--non-interactive", "install", "tmux"]]),
        ("apk",     [["apk", "add", "tmux"]]),
    ]
    for name, cmds in candidates:
        if shutil.which(name):
            return name, cmds
    return None, None


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def in_virtualenv():
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def check_python():
    v = sys.version_info
    if v[:2] >= MIN_PY:
        ok(f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")
        return True
    fail(f"Python {v.major}.{v.minor} found; {MIN_PY[0]}.{MIN_PY[1]}+ is required.")
    info("Install a newer Python from https://www.python.org/downloads/ or your package manager.")
    return False


def curses_available():
    try:
        import curses  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_pip():
    if subprocess.run([sys.executable, "-m", "pip", "--version"],
                      capture_output=True).returncode == 0:
        return True
    warn("pip is not available for this Python.")
    if ask("Bootstrap pip using Python's built-in 'ensurepip' module?"):
        return run([sys.executable, "-m", "ensurepip", "--upgrade"])
    return False


def check_curses(osinfo):
    if curses_available():
        ok("curses module available")
        return True

    system = osinfo["system"]
    if system == "Windows":
        warn("curses is not bundled with Python on Windows; the 'windows-curses' package provides it.")
        if not ensure_pip():
            fail("Cannot install windows-curses without pip.")
            return False
        cmd = [sys.executable, "-m", "pip", "install"]
        if not in_virtualenv():
            cmd.append("--user")
        cmd.append("windows-curses")
        if ask("Install 'windows-curses' from PyPI now?"):
            if run(cmd) and _reimport_curses():
                ok("windows-curses installed; curses now available")
                return True
            fail("windows-curses installation failed.")
        else:
            info("Skipped. Install later with: " + " ".join(cmd))
        return False

    # Linux/macOS/BSD: curses is part of the standard library; if it's missing,
    # this Python was built without ncurses. There is no single safe fix.
    fail("curses is missing - this Python build was compiled without ncurses support.")
    if system == "Linux":
        info("Use your distribution's own python3 package (it includes curses),")
        info("or rebuild Python after installing the ncurses development headers.")
    elif system == "Darwin":
        info("Use Python from python.org or Homebrew; both include curses.")
    return False


def _reimport_curses():
    import importlib
    import site
    importlib.invalidate_caches()
    # A fresh --user install may not be on sys.path yet in this process.
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
    return curses_available()


def check_locale(osinfo):
    if osinfo["system"] == "Windows":
        info("Windows: use Windows Terminal for best Unicode rendering (legacy console may show '?').")
        return
    import locale
    enc = locale.getpreferredencoding(False).upper().replace("-", "")
    if enc == "UTF8":
        ok("UTF-8 locale")
    else:
        warn(f"Locale encoding is {enc}; box-drawing and katakana characters may not render.")
        info("Set a UTF-8 locale (e.g. export LANG=en_US.UTF-8) or set USE_KATAKANA = False in the script.")


def check_tmux(osinfo):
    """Optional dependency. Returns True if tmux is (now) installed."""
    if osinfo["system"] == "Windows":
        info("tmux (screensaver auto-launch) is not available natively on Windows.")
        info("Run hackscreen manually, or install it inside WSL to use tmux locking.")
        return False
    if shutil.which("tmux"):
        ok("tmux installed (optional; enables idle-triggered screensaver)")
        return True

    warn("tmux not found (optional; needed only for idle-triggered screensaver mode).")
    pm, cmds = package_manager(osinfo)
    if pm is None:
        if osinfo["system"] == "Darwin":
            info("Homebrew not found. Install tmux via Homebrew (https://brew.sh) or MacPorts, then re-run.")
        else:
            info("No supported package manager found; install tmux manually if you want it.")
        return False

    needs_root = pm != "brew"
    prefix = sudo_prefix() if needs_root else []
    if prefix is None:
        warn(f"Installing with {pm} requires root, and sudo is not available. Skipping.")
        return False
    full = [prefix + c for c in cmds]
    detail = " && ".join(" ".join(c) for c in full)
    if ask(f"Install tmux using {pm}? This will run: {detail}"):
        if pm == "apt-get":
            # A single broken third-party repo makes 'apt-get update' exit non-zero
            # even when the distro repos refreshed fine, so treat it as a warning.
            if not run(full[0]):
                warn("'apt-get update' reported errors (often an unrelated third-party repo); "
                     "attempting the install anyway.")
            full = full[1:]
        if all(run(c) for c in full) and shutil.which("tmux"):
            ok("tmux installed")
            return True
        fail("tmux installation failed.")
    else:
        info("Skipped tmux.")
    return False


# --------------------------------------------------------------------------- #
# Install steps
# --------------------------------------------------------------------------- #
def install_dir(osinfo):
    if osinfo["system"] == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP
    return Path.home() / ".local" / "share" / APP


def bin_dir(osinfo):
    if osinfo["system"] == "Windows":
        return install_dir(osinfo)
    return Path.home() / ".local" / "bin"


def path_contains(d):
    parts = os.environ.get("PATH", "").split(os.pathsep)
    return any(Path(p).resolve() == d.resolve() for p in parts if p)


def install_script(osinfo, src):
    dest_dir = install_dir(osinfo)
    dest = dest_dir / SCRIPT_NAME
    bdir = bin_dir(osinfo)
    launcher = bdir / (APP + ".cmd" if osinfo["system"] == "Windows" else APP)

    info(f"Script destination:   {dest}")
    info(f"Launcher destination: {launcher}")
    if not ask("Copy hackscreen and create the launcher?"):
        info("Skipped. You can always run it directly: python3 " + SCRIPT_NAME)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

    if osinfo["system"] == "Windows":
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{dest}" %*\r\n', encoding="utf-8")
    else:
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{dest}" "$@"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    ok(f"Installed. Launcher: {launcher}")

    if not path_contains(bdir):
        warn(f"{bdir} is not on your PATH.")
        if osinfo["system"] == "Windows":
            info(f'Add it via System Properties > Environment Variables, or run: "{launcher}"')
        else:
            info(f'Add to your shell profile:  export PATH="{bdir}:$PATH"')
    return launcher


def configure_tmux(launcher):
    conf = Path.home() / ".tmux.conf"
    existing = conf.read_text(encoding="utf-8") if conf.exists() else ""
    if TMUX_MARKER in existing:
        ok(f"{conf} already contains a hackscreen block; leaving it unchanged.")
        return
    try:
        minutes = input(_c("1", "  >> ") + "Idle minutes before the screensaver starts? [5] ").strip()
    except EOFError:
        minutes = ""
    minutes = int(minutes) if minutes.isdigit() and int(minutes) > 0 else 5

    block = (f"\n{TMUX_MARKER}\n"
             f"set -g lock-after-time {minutes * 60}\n"
             f'set -g lock-command "{launcher}"\n'
             f"{TMUX_MARKER_END}\n")
    print(_c("2", block))
    if not ask(f"Append the block above to {conf}?" +
               (" (a timestamped backup will be made first)" if existing else "")):
        info("Skipped tmux configuration.")
        return
    if existing:
        backup = conf.with_name(f".tmux.conf.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(conf, backup)
        ok(f"Backup saved: {backup}")
    with open(conf, "a", encoding="utf-8") as f:
        f.write(block)
    ok(f"tmux configured. Reload inside tmux with:  tmux source-file {conf}")
    info("Note: lock-after-time applies to sessions running inside tmux only.")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    global CHECK_ONLY
    ap = argparse.ArgumentParser(description="Install hackscreen, the terminal hacker screensaver.")
    ap.add_argument("--check", action="store_true", help="verify dependencies only; change nothing")
    CHECK_ONLY = ap.parse_args().check

    print(_c("32;1", "\n  hackscreen installer") + (_c("33", "  (check mode)") if CHECK_ONLY else ""))

    head("1. Operating system")
    osinfo = detect_os()
    ok(f"{osinfo['pretty']}  [{platform.machine()}]")
    if osinfo["wsl"]:
        info("Running under WSL; Linux dependencies apply.")

    src = Path(__file__).resolve().parent / SCRIPT_NAME
    if not src.exists():
        fail(f"{SCRIPT_NAME} not found next to the installer ({src.parent}).")
        return 1

    head("2. Required dependencies")
    if not check_python():
        return 1
    curses_ok = check_curses(osinfo)

    head("3. Terminal environment")
    check_locale(osinfo)
    if not sys.stdout.isatty():
        warn("Not running in an interactive terminal; hackscreen needs one.")

    head("4. Optional dependencies")
    tmux_ok = check_tmux(osinfo)

    if CHECK_ONLY:
        head("Summary")
        (ok if curses_ok else fail)("Required dependencies " + ("satisfied" if curses_ok else "MISSING"))
        (ok if tmux_ok else info)("tmux " + ("available" if tmux_ok else "not available (optional)"))
        return 0 if curses_ok else 1

    if not curses_ok:
        fail("Required dependency missing; installation stopped. Nothing else was changed.")
        return 1

    head("5. Install")
    launcher = install_script(osinfo, src)

    if launcher and tmux_ok:
        head("6. Screensaver mode (tmux)")
        if ask("Configure tmux to launch hackscreen after a period of inactivity?"):
            configure_tmux(launcher)
        else:
            info("Skipped.")

    head("Done")
    info("Run it with: " + (str(launcher) if launcher else f"python3 {src}"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Aborted by user. Anything already completed was reported above.")
        sys.exit(130)
