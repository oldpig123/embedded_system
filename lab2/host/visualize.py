"""Live receiver and plotter for the STM32 IoT node.

The board connects to this program as a TCP client and sends one line per
sample:

    ax,ay,az,gx,gy,gz\\n

ax/ay/az are accelerometer values (mg) and gx/gy/gz are gyroscope values
(mdps), exactly as the firmware sends them. The board may also send an
event line, e.g. "EVENT,SIGMOT\n", which is drawn as a vertical marker and a
banner. Other lines that do not parse are skipped and counted.

    uv run visualize.py                      # live window on port 8002
    uv run visualize.py --duration 5 --save out.png   # headless, for testing
"""

import argparse
import socket
import threading
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

NUM_FIELDS = 6
AXES = ("x", "y", "z")
COLORS = ("tab:red", "tab:green", "tab:blue")
BANNER_SECONDS = 2.0


class Receiver:
    """Accepts board connections on a background thread and stores samples."""

    def __init__(self, host, port, maxlen):
        self.t = deque(maxlen=maxlen)
        self.data = [deque(maxlen=maxlen) for _ in range(NUM_FIELDS)]
        self.peer = None
        self.bad_lines = 0
        self.total = 0
        self.events = []  # (seconds since start, name)
        self._t0 = time.monotonic()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.listen(1)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            conn, addr = self._server.accept()
            self.peer = "%s:%d" % addr
            print("connected:", self.peer)
            try:
                self._read(conn)
            except OSError as e:
                print("connection error:", e)
            finally:
                conn.close()
                print("disconnected:", self.peer)
                self.peer = None

    def _read(self, conn):
        buf = b""
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                return
            buf += chunk
            # TCP is a byte stream: a read may hold half a line or several.
            *lines, buf = buf.split(b"\n")
            for line in lines:
                self._parse(line)

    def _parse(self, line):
        if line.startswith(b"EVENT"):
            name = line.decode("ascii", "replace").strip().partition(",")[2] or "event"
            now = time.monotonic() - self._t0
            self.events.append((now, name))
            print("%8.2fs  EVENT: %s" % (now, name))
            return
        try:
            values = [float(v) for v in line.decode("ascii").strip().split(",")]
            if len(values) != NUM_FIELDS:
                raise ValueError
        except ValueError:
            if line.strip():
                self.bad_lines += 1
            return
        self.t.append(time.monotonic() - self._t0)
        for series, v in zip(self.data, values):
            series.append(v)
        self.total += 1


def build_figure():
    fig, (ax_acc, ax_gyr) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))
    ax_acc.set_ylabel("accelerometer (mg)")
    ax_gyr.set_ylabel("gyroscope (mdps)")
    ax_gyr.set_xlabel("time (s)")
    # Set a title now so tight_layout reserves room for the status line.
    ax_acc.set_title("waiting for board...")
    lines = []
    for ax in (ax_acc, ax_gyr):
        for name, color in zip(AXES, COLORS):
            (line,) = ax.plot([], [], color=color, label=name)
            lines.append(line)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
    banner = fig.text(
        0.5, 0.5, "", ha="center", va="center", fontsize=28, color="tab:red",
        fontweight="bold", alpha=0.8,
    )
    fig.tight_layout()
    return fig, (ax_acc, ax_gyr), lines, banner


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8002)
    p.add_argument("--window", type=float, default=10.0, help="seconds shown")
    p.add_argument("--duration", type=float, help="headless: run N seconds then exit")
    p.add_argument("--save", help="headless: write a PNG of the plot at exit")
    args = p.parse_args()

    if args.duration is not None:
        plt.switch_backend("Agg")

    rx = Receiver(args.host, args.port, maxlen=5000)
    fig, axes, lines, banner = build_figure()
    print("listening on %s:%d" % (args.host, args.port))

    marks = []  # (time, artists) for events already drawn

    def update(_frame=None):
        t = list(rx.t)
        n = len(t)
        for line, series in zip(lines, rx.data):
            line.set_data(t, list(series)[:n])
        if t:
            axes[0].set_xlim(max(0.0, t[-1] - args.window), max(t[-1], args.window))
        for ax in axes:
            ax.relim()
            ax.autoscale_view(scalex=False)
        now = time.monotonic() - rx._t0
        for ev_t, name in rx.events[len(marks):]:
            artists = [ax.axvline(ev_t, color="k", linestyle="--") for ax in axes]
            artists.append(axes[0].text(ev_t, 1.0, name, transform=axes[0].get_xaxis_transform(),
                                        ha="right", va="top", rotation=90, fontsize=8))
            marks.append((ev_t, artists))
        xmin = axes[0].get_xlim()[0]
        for ev_t, artists in marks:
            for a in artists:
                a.set_visible(ev_t >= xmin)
        recent = [name for ev_t, name in rx.events if now - ev_t < BANNER_SECONDS]
        banner.set_text(("MOTION: " + recent[-1]) if recent else "")
        state = "connected: " + rx.peer if rx.peer else "waiting for board..."
        axes[0].set_title(
            "%s | samples: %d | bad lines: %d" % (state, rx.total, rx.bad_lines)
        )
        return lines

    if args.duration is None:
        _anim = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
        plt.show()
        return

    end = time.monotonic() + args.duration
    while time.monotonic() < end:
        time.sleep(0.1)
    update()
    print("samples: %d, events: %d, bad lines: %d" % (rx.total, len(rx.events), rx.bad_lines))
    if args.save:
        fig.savefig(args.save, dpi=100)
        print("saved", args.save)


if __name__ == "__main__":
    main()
