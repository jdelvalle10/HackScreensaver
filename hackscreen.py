#!/usr/bin/env python3
"""
hackscreen.py - Terminal "hacking console" screensaver.

Purely cosmetic: this program performs NO network activity. Every IP address
comes from the RFC 5737 documentation ranges, and all "data" is random.

Usage:     python3 hackscreen.py          (press any key to exit)
Requires:  Python 3.8+. On Windows: pip install windows-curses
"""

import curses
import datetime
import locale
import os
import random
import textwrap
import time
from collections import deque

FPS = 20
FRAME_TIME = 1.0 / FPS
MIN_H, MIN_W = 20, 70

DOC_NETS = ("192.0.2.", "198.51.100.", "203.0.113.")  # RFC 5737 - never real hosts

# Half-width katakana + hex digits. Set USE_KATAKANA = False if your font
# renders them poorly.
USE_KATAKANA = True
RAIN_CHARS = ([chr(c) for c in range(0xFF66, 0xFF9E)] if USE_KATAKANA else []) \
    + list("0123456789ABCDEF")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def fake_ip():
    return random.choice(DOC_NETS) + str(random.randint(1, 254))


def fake_port():
    return random.choice([21, 22, 23, 25, 53, 80, 110, 139, 143, 443,
                          445, 3306, 3389, 5432, 8080, 8443])


def fake_hash(n_hex=32):
    return os.urandom(n_hex // 2).hex()


C_GREEN, C_BRIGHT, C_RED, C_CYAN, C_YELLOW = range(1, 6)


def init_colors():
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    curses.init_pair(C_GREEN, curses.COLOR_GREEN, bg)
    curses.init_pair(C_BRIGHT, curses.COLOR_WHITE, bg)
    curses.init_pair(C_RED, curses.COLOR_RED, bg)
    curses.init_pair(C_CYAN, curses.COLOR_CYAN, bg)
    curses.init_pair(C_YELLOW, curses.COLOR_YELLOW, bg)


def color(cid, extra=0):
    return curses.color_pair(cid) | extra


def put(scr, y, x, text, attr=0):
    """addstr that clips to the screen and never crashes."""
    h, w = scr.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    try:
        scr.addstr(y, x, text[: w - x], attr)
    except curses.error:
        pass  # writing the bottom-right cell raises; the text is still drawn


def draw_box(scr, y, x, h, w, title, attr):
    if h < 2 or w < 2:
        return
    put(scr, y, x, "┌" + "─" * (w - 2) + "┐", attr)
    for r in range(y + 1, y + h - 1):
        put(scr, r, x, "│", attr)
        put(scr, r, x + w - 1, "│", attr)
    put(scr, y + h - 1, x, "└" + "─" * (w - 2) + "┘", attr)
    if title and w > 8:
        put(scr, y, x + 2, f"[ {title} ]"[: w - 4], attr | curses.A_BOLD)


def line_points(y0, x0, y1, x1):
    """Bresenham line between two cells."""
    pts = []
    dy, dx = abs(y1 - y0), abs(x1 - x0)
    sy, sx = (1 if y0 < y1 else -1), (1 if x0 < x1 else -1)
    err = dx - dy
    while True:
        pts.append((y0, x0))
        if (y0, x0) == (y1, x1):
            return pts
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


# --------------------------------------------------------------------------- #
# Panels: each has update() (advance state) and draw_inner() (render)
# --------------------------------------------------------------------------- #
class Panel:
    title = ""

    def __init__(self, y, x, h, w):
        self.y, self.x, self.h, self.w = y, x, h, w
        self.iy, self.ix = y + 1, x + 1
        self.ih, self.iw = max(1, h - 2), max(1, w - 2)

    def update(self):
        pass

    def draw(self, scr):
        draw_box(scr, self.y, self.x, self.h, self.w, self.title, color(C_GREEN))
        self.draw_inner(scr)

    def draw_inner(self, scr):
        pass


# Recognizable Windows file names that occasionally fall through the rain.
WINDOWS_FILES = [
    "explorer.exe", "svchost.exe", "notepad.exe", "cmd.exe", "powershell.exe",
    "regedit.exe", "taskmgr.exe", "winlogon.exe", "lsass.exe", "ntoskrnl.exe",
    "kernel32.dll", "user32.dll", "NTUSER.DAT", "pagefile.sys", "hiberfil.sys",
    "desktop.ini", "bootmgr", "hosts", "SAM", "calc.exe", "mspaint.exe",
    "System32", "autoexec.bat", "boot.ini", "win.ini", "thumbs.db",
]


class MatrixRain(Panel):
    title = "SIGINT"

    def __init__(self, *a):
        super().__init__(*a)
        # Filenames are drawn vertically, so only those that fit the panel height.
        self.files = [f for f in WINDOWS_FILES if len(f) <= self.ih - 2]
        self.blink_rows = max(3, self.ih // 4)       # blink zone above the ground
        self.max_files = max(1, self.iw // 6)        # cap simultaneous filenames
        self.drops = [self._new_drop(initial=True) for _ in range(self.iw)]

    def _active_files(self):
        return sum(1 for d in self.drops if d.get("name"))

    def _new_drop(self, initial=False):
        d = {"head": random.uniform(-self.ih, 0) if initial else random.uniform(-self.ih / 2, 0),
             "speed": random.uniform(0.3, 1.2),
             "len": random.randint(4, max(5, self.ih)),
             "name": None}
        if (not initial and self.files and random.random() < 0.10
                and self._active_files() < self.max_files):
            name = random.choice(self.files)
            # Slower fall so the name is readable and the blink phase lasts ~1-2 s.
            d.update(name=name, len=len(name), head=-1.0, speed=random.uniform(0.18, 0.3))
        return d

    def update(self):
        for i, d in enumerate(self.drops):
            d["head"] += d["speed"]
            if d["name"]:
                if d["head"] >= self.ih:              # last letter touched the ground
                    self.drops[i] = self._new_drop()
            elif d["head"] - d["len"] > self.ih:
                self.drops[i] = self._new_drop()

    def draw_inner(self, scr):
        blink_on = int(time.monotonic() * 6) % 2 == 0
        for col, d in enumerate(self.drops):
            head = int(d["head"])
            if d["name"]:
                self._draw_filename(scr, col, head, d["name"], blink_on)
                continue
            for k in range(d["len"]):
                row = head - k
                if 0 <= row < self.ih:
                    if k == 0:
                        attr = color(C_BRIGHT, curses.A_BOLD)
                    elif k < d["len"] // 3:
                        attr = color(C_GREEN, curses.A_BOLD)
                    else:
                        attr = color(C_GREEN, curses.A_DIM)
                    put(scr, self.iy + row, self.ix + col, random.choice(RAIN_CHARS), attr)

    def _draw_filename(self, scr, col, head, name, blink_on):
        """Name reads top-to-bottom; its last character is the falling head."""
        near_ground = head >= self.ih - self.blink_rows
        if near_ground:
            # Whole filename flashes in reverse video just before impact.
            base = color(C_YELLOW, curses.A_BOLD | (curses.A_REVERSE if blink_on else 0))
        else:
            base = color(C_YELLOW, curses.A_BOLD)
        n = len(name)
        for k, ch in enumerate(name):
            row = head - (n - 1 - k)
            if 0 <= row < self.ih:
                attr = base
                if k == n - 1 and not near_ground:
                    attr = color(C_BRIGHT, curses.A_BOLD)   # bright leading edge
                put(scr, self.iy + row, self.ix + col, ch, attr)


# School locations used as "targets" in the operations log.
SCHOOL_TARGETS = [
    "Cafeteria", "Test Room", "Video Game Arena", "Principal's Office", "Main Office",
    "Library", "Media Center", "Gymnasium", "Nurse's Office", "Guidance Office",
    "Science Lab", "Computer Lab", "Robotics Lab", "Teachers' Lounge", "Auditorium",
    "Band Room", "Art Room", "Front Desk", "Attendance Office", "Athletics Office",
    "Bus Loop Cameras", "Parking Lot Cameras", "Vending Machines", "Bell System",
    "PA System", "Hallway Cameras", "Chemistry Lab", "Locker Room", "Book Room",
]

LOG_TEMPLATES = [
    ("[*] Scanning {target} ({ip}) ports 1-65535...", C_CYAN),
    ("[+] Port {port}/tcp open on {target} ({ip})", C_GREEN),
    ("[+] Handshake established with {target} @ {ip}:{port}", C_GREEN),
    ("[*] Enumerating devices in {target} subnet...", C_CYAN),
    ("[*] Injecting payload 0x{h8} into {target} controller", C_YELLOW),
    ("[!] IDS signature evaded at {target} ({n} rules)", C_YELLOW),
    ("[!] Firewall rule #{n} bypassed at {target}", C_YELLOW),
    ("[+] Credential hash recovered from {target}: {h32}", C_GREEN),
    ("[-] Connection reset by {target} ({ip}), retrying...", C_RED),
    ("[*] Routing via proxy chain {ip} -> {ip2} -> {target}", C_CYAN),
    ("[+] Root shell spawned on {target} (uid=0)", C_BRIGHT),
    ("[*] Transferring block {n}/{m} from {target}...", C_CYAN),
    ("[-] Honeypot detected in {target}, aborting route", C_RED),
    ("[*] Rotating TLS fingerprint -> JA3 {h8}", C_CYAN),
    ("[+] {target} camera feed intercepted", C_GREEN),
    ("[!] {target} admin panel reached - default password", C_YELLOW),
]

TS_INDENT = 9   # width of "HH:MM:SS " so wrapped lines align under the message


class LogPanel(Panel):
    title = "OPERATIONS LOG"

    def __init__(self, *a):
        super().__init__(*a)
        self.lines = deque(maxlen=self.ih)       # completed lines, each pre-wrapped
        self.pause = 0
        self._next_line()

    def _wrap(self, text):
        return textwrap.wrap(text, width=max(12, self.iw - 1),
                             subsequent_indent=" " * TS_INDENT,
                             break_long_words=True, break_on_hyphens=False) or [""]

    def _next_line(self):
        tmpl, cid = random.choice(LOG_TEMPLATES)
        n = random.randint(2, 999)
        text = tmpl.format(ip=fake_ip(), ip2=fake_ip(), port=fake_port(),
                           h8=fake_hash(8), h32=fake_hash(32),
                           n=n, m=n + random.randint(1, 500),
                           target=random.choice(SCHOOL_TARGETS))
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.cur_rows = self._wrap(f"{ts} {text}")
        self.cur_cid, self.typed = cid, 0
        # Characters to "type" = wrapped content without the alignment indent.
        self.cur_total = sum(len(r) - (TS_INDENT if i else 0) for i, r in enumerate(self.cur_rows))

    def update(self):
        if self.pause > 0:
            self.pause -= 1
            return
        self.typed += random.randint(1, 4)
        if self.typed >= self.cur_total:
            self.lines.append((self.cur_rows, self.cur_cid))
            self._next_line()
            self.pause = random.randint(0, 12)

    def _partial_rows(self):
        """Reveal self.typed characters across the pre-wrapped rows."""
        out, left = [], self.typed
        for i, row in enumerate(self.cur_rows):
            indent = TS_INDENT if i else 0
            body = row[indent:]
            if left <= 0 and i:
                break
            out.append(row[:indent] + body[:max(0, left)])
            left -= len(body)
        return out

    def draw_inner(self, scr):
        rows = [(r, cid, 0) for rws, cid in self.lines for r in rws]
        rows += [(r, self.cur_cid, curses.A_BOLD) for r in self._partial_rows()]
        rows = rows[-self.ih:]
        for i, (text, cid, extra) in enumerate(rows):
            put(scr, self.iy + i, self.ix, text[: self.iw], color(cid, extra))
        last_text = rows[-1][0] if rows else ""
        if int(time.monotonic() * 2) % 2 == 0 and len(last_text) < self.iw:
            put(scr, self.iy + len(rows) - 1, self.ix + len(last_text), "█", color(C_GREEN))

class HexDump(Panel):
    title = "MEMORY DUMP // PID 4471"
    STRINGS = [b"password", b"admin:", b"BEGIN RSA", b"session=", b"token", b"root:x:0"]

    def __init__(self, *a):
        super().__init__(*a)
        self.offset = random.randrange(0, 0x7FFF0000, 16)
        self.lines = deque(maxlen=self.ih)
        self.tick = 0

    def update(self):
        self.tick += 1
        if self.tick % 2:
            return
        data = os.urandom(16)
        hot = random.random() < 0.12
        if hot:
            data = (random.choice(self.STRINGS) + data)[:16]
        hexpart = " ".join(f"{b:02x}" for b in data[:8]) + "  " + \
                  " ".join(f"{b:02x}" for b in data[8:])
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
        self.lines.append((f"{self.offset:08x}: {hexpart}  |{asc}|", hot))
        self.offset += 16

    def draw_inner(self, scr):
        for i, (text, hot) in enumerate(self.lines):
            attr = color(C_YELLOW, curses.A_BOLD) if hot else color(C_GREEN, curses.A_DIM)
            put(scr, self.iy + i, self.ix, text[: self.iw], attr)


TASKS = ["Decrypting payload", "Brute-forcing SHA-256", "Cracking WPA2 handshake",
         "Deploying implant", "Bypassing 2FA", "Compiling exploit",
         "Mapping subnet", "Spoofing MAC table", "Escalating privileges"]


class ProgressPanel(Panel):
    title = "ACTIVE JOBS"

    def __init__(self, *a):
        super().__init__(*a)
        self.jobs = [self._new_job() for _ in range(max(1, self.ih // 2))]

    @staticmethod
    def _new_job():
        return {"name": random.choice(TASKS), "pct": 0.0,
                "speed": random.uniform(0.2, 1.5), "stall": 0, "done": 0}

    def update(self):
        for i, j in enumerate(self.jobs):
            if j["done"]:
                j["done"] -= 1
                if j["done"] == 0:
                    self.jobs[i] = self._new_job()
                continue
            if j["stall"]:
                j["stall"] -= 1
                continue
            j["pct"] = min(100.0, j["pct"] + j["speed"] * random.random())
            if 96 <= j["pct"] < 99 and random.random() < 0.05:
                j["stall"] = random.randint(20, 60)      # the dramatic 97% pause
            if j["pct"] >= 100:
                j["done"] = FPS * 2

    def draw_inner(self, scr):
        barw = max(5, self.iw - 7)
        for i, j in enumerate(self.jobs):
            r = self.iy + i * 2
            if r + 1 >= self.iy + self.ih + 1:
                break
            if j["done"]:
                attr, status = color(C_BRIGHT, curses.A_BOLD), "  DONE"
            elif j["stall"]:
                attr, status = color(C_YELLOW), f"{j['pct']:5.1f}%"
            else:
                attr, status = color(C_GREEN), f"{j['pct']:5.1f}%"
            filled = int(barw * j["pct"] / 100)
            put(scr, r, self.ix, j["name"][: self.iw], color(C_CYAN))
            put(scr, r + 1, self.ix, "█" * filled + "░" * (barw - filled), attr)
            put(scr, r + 1, self.ix + barw + 1, status, attr)


class NodeMap(Panel):
    title = "NETWORK TOPOLOGY"

    def __init__(self, *a):
        super().__init__(*a)
        n = max(4, min(10, (self.ih * self.iw) // 40))
        span_x = max(1, self.iw - 4)          # leave room for the node label
        self.nodes = [(random.randrange(self.ih), random.randrange(span_x)) for _ in range(n)]
        self.labels = ["." + fake_ip().rsplit(".", 1)[1] for _ in range(n)]
        edges = {(i, random.randrange(i)) for i in range(1, n)}   # spanning tree
        for _ in range(n // 2):
            a, b = random.sample(range(n), 2)
            edges.add((a, b))
        self.edges = [(a, b, line_points(*self.nodes[a], *self.nodes[b])) for a, b in edges]
        self.packets = []
        self.owned = {0}

    def update(self):
        if random.random() < 0.25 and len(self.packets) < 6:
            a, b, path = random.choice(self.edges)
            if random.random() < 0.5:
                a, b, path = b, a, path[::-1]
            self.packets.append({"path": path, "pos": 0, "dst": b})
        for p in self.packets:
            p["pos"] += 1
        for p in [p for p in self.packets if p["pos"] >= len(p["path"])]:
            if random.random() < 0.3:
                self.owned.add(p["dst"])
            self.packets.remove(p)
        if len(self.owned) == len(self.nodes) and random.random() < 0.01:
            self.owned = {0}                  # network "re-secures", start over

    def draw_inner(self, scr):
        for _, _, path in self.edges:
            for y, x in path[1:-1]:
                put(scr, self.iy + y, self.ix + x, "·", color(C_GREEN, curses.A_DIM))
        for p in self.packets:
            y, x = p["path"][p["pos"]]
            put(scr, self.iy + y, self.ix + x, "●", color(C_YELLOW, curses.A_BOLD))
        for i, (y, x) in enumerate(self.nodes):
            attr = color(C_RED, curses.A_BOLD) if i in self.owned else color(C_CYAN, curses.A_BOLD)
            put(scr, self.iy + y, self.ix + x, "■" + self.labels[i], attr)


# --------------------------------------------------------------------------- #
# Overlay, header, layout, main loop
# --------------------------------------------------------------------------- #
class Alert:
    MESSAGES = [("ACCESS GRANTED", C_GREEN), ("ROOT PRIVILEGES ACQUIRED", C_GREEN),
                ("INTRUSION DETECTED", C_RED), ("TRACE INITIATED - REROUTING", C_RED)]

    def __init__(self):
        self._schedule()

    def _schedule(self):
        self.next_at = time.monotonic() + random.uniform(20, 45)
        self.msg, self.until = None, 0

    def update(self):
        now = time.monotonic()
        if self.msg is None and now >= self.next_at:
            self.msg, self.until = random.choice(self.MESSAGES), now + 3
        elif self.msg and now >= self.until:
            self._schedule()

    def draw(self, scr, h, w):
        if not self.msg or int(time.monotonic() * 4) % 2:   # blink
            return
        text, cid = self.msg
        spaced = " ".join(text)
        bw, bh = len(spaced) + 8, 5
        y, x = (h - bh) // 2, (w - bw) // 2
        attr = color(cid, curses.A_REVERSE | curses.A_BOLD)
        for r in range(bh):
            put(scr, y + r, x, " " * bw, attr)
        put(scr, y + 2, x + 4, spaced, attr)


def draw_header(scr, w, start):
    up = int(time.monotonic() - start)
    jitter = random.Random(int(time.time()))           # changes once per second
    left = " ◢ NEXUS//OPS CONSOLE v4.2 ◣"
    right = (f"UPLINK {jitter.uniform(2.1, 2.6):.2f} Gbps | "
             f"UP {up // 3600:02d}:{up // 60 % 60:02d}:{up % 60:02d} | "
             f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ")
    bar = color(C_GREEN, curses.A_REVERSE)
    put(scr, 0, 0, " " * w, bar)
    put(scr, 0, 0, left, bar | curses.A_BOLD)
    put(scr, 0, max(len(left) + 1, w - len(right)), right, bar)


def build_layout(h, w):
    top, body_h = 1, h - 2                # row 0 header, last row footer
    rain_w = max(14, w // 5)
    rx, rw = rain_w, w - rain_w
    top_h = body_h // 2
    bot_h = body_h - top_h
    left_w = int(rw * 0.6)
    right_w = rw - left_w
    return [MatrixRain(top, 0, body_h, rain_w),
            LogPanel(top, rx, top_h, left_w),
            NodeMap(top, rx + left_w, top_h, right_w),
            HexDump(top + top_h, rx, bot_h, left_w),
            ProgressPanel(top + top_h, rx + left_w, bot_h, right_w)]


def main(stdscr):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.nodelay(True)
    stdscr.keypad(True)
    init_colors()

    start = time.monotonic()
    size, panels, alert = None, [], Alert()

    while True:
        t0 = time.monotonic()
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            size = None
        elif key != -1:
            break                            # any key exits

        h, w = stdscr.getmaxyx()
        if (h, w) != size:
            size = (h, w)
            panels = build_layout(h, w) if h >= MIN_H and w >= MIN_W else []

        stdscr.erase()
        if not panels:
            put(stdscr, h // 2, 0, f"Enlarge terminal to {MIN_W}x{MIN_H} (now {w}x{h})".center(w),
                color(C_RED, curses.A_BOLD))
        else:
            for p in panels:
                p.update()
                p.draw(stdscr)
            alert.update()
            alert.draw(stdscr, h, w)
            draw_header(stdscr, w, start)
            put(stdscr, h - 1, 0, " press any key to exit ".rjust(w - 1), color(C_GREEN, curses.A_DIM))
        stdscr.refresh()

        elapsed = time.monotonic() - t0
        if elapsed < FRAME_TIME:
            time.sleep(FRAME_TIME - elapsed)


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
