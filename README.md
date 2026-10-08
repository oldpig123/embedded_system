# Embedded Systems Labs

Coursework for an embedded systems course, on the STM32 **B-L475E-IOT01A**
Discovery kit (STM32L475VG, Cortex-M4F). Projects are generated with
STM32CubeMX and built with CMake + Ninja + `arm-none-eabi-gcc`.

Each lab's design and write-up live in its own report; this page is just an
index.

## Labs

| Lab | Topic | Report |
| --- | --- | --- |
| [`lab1/`](lab1/) | FreeRTOS task synchronisation — two tasks sharing one LED under a mutex, plus button long-press detection via a message queue | [report.pdf](lab1/report/report.pdf) |
| [`lab2/`](lab2/) | Wi-Fi sensor streaming — LSM6DSL accelerometer and gyroscope sent over TCP (ES-WiFi) to a Python live plot; optional: significant-motion interrupt forwarded to the host | [README](lab2/README.md) |
| [`lab3/`](lab3/) | BLE central in Python (`bluepy`) on a Raspberry Pi, writing a CCCD on a GATT server; optional: building GATTLIB in C | [report.pdf](lab3/report/report.pdf) |

## Building

```sh
cd lab1
cmake --preset Debug          # or Release
cmake --build --preset Debug
```

Output is `build/<preset>/<lab>.elf`. Flash with STM32CubeProgrammer, or open
the project in STM32CubeIDE and run from there.

### lab2 (Wi-Fi)

The firmware is the STM32CubeL4 `WiFi_Client_Server` example converted to CMake.
Set `SSID`, `PASSWORD` and `RemoteIP[]` in `lab2/WiFi_Client_Server/Src/main.c`
(they are placeholders in the repo), build as above from `lab2/WiFi_Client_Server`,
then start the host before resetting the board:

```sh
cd lab2/host
uv run visualize.py           # listens on port 8002
```

See [`lab2/README.md`](lab2/README.md) for the wire format and the
significant-motion setup.

### lab3 (BLE, no STM32 build)

Two machines are used: a Windows laptop standing in for the phone, and a
Raspberry Pi as the BLE central.

```sh
# laptop: GATT server advertising service 0xFFF0 (needs uv)
cd lab3
uv run server.py

# Raspberry Pi: BLE central (bluepy installed in a venv; root is needed for scanning)
sudo ~/blenv/bin/python central.py
```

See [`lab3/report/report.tex`](lab3/report/report.tex) for the Pi setup, and
build it with `pdflatex report.tex` (twice) from `lab3/report`.

> Regenerating from a `.ioc` in CubeMX overwrites everything outside the
> `/* USER CODE BEGIN ... */` … `/* USER CODE END ... */` markers.
