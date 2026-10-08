# lab2 — Wi-Fi sensor streaming and significant motion

The B-L475E-IOT01A reads its on-board LSM6DSL (3-axis accelerometer + gyroscope)
and streams the samples over Wi-Fi (ES-WiFi module, TCP client) to a Python
server on a laptop, which plots them live. For option problem 1 the LSM6DSL's
significant-motion detector raises an interrupt that the board forwards to the
host as an event.

## Layout

| Path | What it is |
| --- | --- |
| [`WiFi_Client_Server/`](WiFi_Client_Server/) | Firmware. The `WiFi_Client_Server` example from STM32Cube FW L4, converted to CMake with the STM32Cube VS Code extension and modified (`Src/main.c`, `Src/stm32l4xx_it.c`). |
| [`host/`](host/) | Python receiver and live plot (`visualize.py`), plus `fake_board.py` to test it without the board. Managed with `uv`. |

## Wire format

One TCP line per sample, accelerometer in mg and gyroscope in mdps:

```
ax,ay,az,gx,gy,gz\n
```

and one line per significant-motion event:

```
EVENT,SIGMOT\n
```

## Running it

Firmware (tools come from the STM32Cube VS Code extension's bundle manager):

```sh
cd WiFi_Client_Server
cmake --preset Debug
cmake --build --preset Debug
```

Set `SSID`, `PASSWORD` and `RemoteIP[]` in `Src/main.c` first (the laptop's
IPv4 address on the same 2.4 GHz network), then flash
`build/Debug/WiFi_Client_Server.elf` with STM32CubeProgrammer or the extension.
Serial console (ST-LINK virtual COM port): 115200 baud.

Host, started before the board is reset:

```sh
cd host
uv run visualize.py                 # listens on port 8002
uv run fake_board.py                # optional: synthetic data instead of the board
```

## Design notes

- **Sample rate.** The BSP runs the LSM6DSL at 52 Hz, so sending faster only
  repeats values. The loop sleeps 10 ms between sends. 2-50 ms ran stably; 1 ms
  stalled intermittently and recovered; with no delay the stream stopped after
  about 2 s. The cause (probably the ES-WiFi SPI/AT send path backing up) was
  not investigated further.
- **Significant motion** (`MotionInt_Init` in `main.c`). The BSP has no helper
  for it, so the registers are written directly through `SENSOR_IO_*`:
  - `CTRL10_C |= 0x05`: `FUNC_EN` and `SIGN_MOTION_EN`.
  - `INT1_CTRL |= 0x40`: route `INT1_SIGN_MOT` to the INT1 pin.
  - INT1 is wired to **PD11** (taken from Zephyr's device tree for this board,
    not from ST's user manual). It is an EXTI rising-edge input on
    `EXTI15_10_IRQn`; the ISR only sets a flag and the main loop sends the event.
  - Embedded-function Bank A (`FUNC_CFG_ACCESS = 0x80`, restored to `0x00`
    afterwards): `SM_STEP_THS` (0x13) is the significant-motion threshold,
    `PEDO_DEB_REG` (0x14) holds the step debounce (`deb_step` in bits 2:0,
    `deb_time` in bits 7:3). Both are `#define`s at the top of `main.c`
    (`SIGMOT_THRESHOLD`, `SIGMOT_DEBOUNCE`).
  - The sensor keeps these registers across an MCU reset; only a power cycle
    clears them.

## Significant-motion sensitivity

Steady shaking at about 3 steps per second. Gap between repeat events:

| `SM_THR` | `DEB_STEP` | events | mean gap |
| --- | --- | --- | --- |
| 3 | default | 13 | 0.94 s |
| 6 | default | 7 | 1.93 s |
| 12 | default | 4 | 3.78 s |
| 12 | 2 | 3 runs x 4 | 3.96 s, 4.49 s, 3.78 s |

The gap is proportional to `SM_THR` (gap / `SM_THR` is about 0.31-0.34 s), so a
repeat event fires roughly every `SM_THR` steps: a smaller threshold re-triggers
more often while you keep moving. `DEB_STEP` did not change the gap. Numbers are
from hand shaking, so expect 10-20 % spread between runs.

Not measured: the delay from the start of shaking to the *first* event as a
function of `DEB_STEP`. Informally it took about 6 shakes with the default
debounce, whatever `SM_THR` was.

## Known limits

- The firmware leaves its send loop on the first failed send and does not
  reconnect, so stopping the host script ends the stream until the board is reset.
- Significant motion is step-based: a single shake or tap does not trigger it.
