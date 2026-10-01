"""Stand-in for the STM32 board: sends synthetic samples to visualize.py.

    uv run fake_board.py [--host 127.0.0.1] [--port 8002] [--seconds 5]

It mimics the firmware's line format, sends one EVENT line, and also splits one line
across two sends and sends one garbage line, to exercise the receiver.
"""

import argparse
import math
import socket
import time

RATE_HZ = 20


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8002)
    p.add_argument("--seconds", type=float, default=5.0)
    args = p.parse_args()

    with socket.create_connection((args.host, args.port)) as s:
        t0 = time.monotonic()
        i = 0
        while (t := time.monotonic() - t0) < args.seconds:
            ax = 300 * math.sin(2 * math.pi * 0.5 * t)
            ay = 300 * math.cos(2 * math.pi * 0.5 * t)
            az = 1000 + 20 * math.sin(2 * math.pi * 3 * t)
            gx = 20000 * math.sin(2 * math.pi * 0.25 * t)
            gy = 10000 * math.cos(2 * math.pi * 0.25 * t)
            gz = 5000 * math.sin(2 * math.pi * 1 * t)
            line = b"%d,%d,%d,%d,%d,%d\n" % (ax, ay, az, gx, gy, gz)
            if i == 10:
                s.sendall(b"not,a,sample\n")
            if i == 40:
                s.sendall(b"EVENT,SIGMOT\n")
            if i == 20:  # split mid-line, as TCP is free to do
                s.sendall(line[:7])
                time.sleep(0.02)
                s.sendall(line[7:])
            else:
                s.sendall(line)
            i += 1
            time.sleep(1 / RATE_HZ)
    print("sent", i, "lines")


if __name__ == "__main__":
    main()
