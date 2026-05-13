# Skill: Zephyr Build System

## Purpose

Reference for building Zephyr RTOS firmware binaries with `west`. Covers board target naming, build flags, output artefact locations, and common failure modes. Use this skill when building samples, resolving build errors, or determining the correct binary to load into Renode.

## Core Build Command

```bash
west build -b <board_target> [<app_dir>] [-- -D<cmake_var>=<value> ...]
```

| Flag | Purpose |
|---|---|
| `-b <board>` | Target board (see naming below) |
| `-p always` | Pristine build — delete `build/` before building. Always use this when changing board or config |
| `-p auto` | Pristine only if board/app changed (default) |
| `-- -DCONFIG_FOO=y` | Override a Kconfig option without editing `prj.conf` |
| `-- -DDTC_OVERLAY_FILE=foo.overlay` | Apply an additional devicetree overlay |

## Board Target Naming

Zephyr board targets follow this pattern:

```
<board_name>[/<soc_variant>][/<core>]
```

Examples:

| Board | Target string |
|---|---|
| BBC micro:bit v2 | `bbc_microbit_v2` |
| STM32 Nucleo H753ZI | `nucleo_h753zi` |
| Nordic nRF52840 DK | `nrf52840dk/nrf52840` |
| Nordic nRF5340 DK (app core) | `nrf5340dk/nrf5340/cpuapp` |
| Raspberry Pi Pico | `rpi_pico/rp2040` |
| ESP32-C3 DevKit | `esp32c3_devkitm` |
| QEMU Cortex-M0 | `qemu_cortex_m0` |

To list all boards Zephyr knows about:
```bash
west boards
west boards | grep <keyword>
```

## Output Artefacts

All outputs land under `<app_dir>/build/zephyr/`:

| File | When present | Notes |
|---|---|---|
| `zephyr.elf` | Always | Use with `sysbus LoadELF` in Renode — includes symbols |
| `zephyr.hex` | Most boards | Intel HEX; use with `sysbus LoadHEX` |
| `zephyr.bin` | Most boards | Raw binary; use with `sysbus LoadBinary <addr>` — verify address |
| `zephyr.map` | Always | Linker map; useful for symbol/address lookup |
| `zephyr.dts` | Always | **Resolved** devicetree — ground truth for peripheral addresses and aliases |
| `zephyr_final.dts` | Always | Same as `zephyr.dts` in recent Zephyr versions |
| `boards/<board>.conf` | Sometimes | Merged Kconfig output |

**Prefer `zephyr.elf` for Renode** — it carries DWARF symbols, which Renode uses for function-level tracing and breakpoints.

## Project Configuration (`prj.conf`)

Kconfig options that commonly matter for emulation:

```kconfig
# Enable logging (required for LOG_INF / LOG_DBG output over UART)
CONFIG_LOG=y
CONFIG_LOG_DEFAULT_LEVEL=3     # 0=off 1=err 2=warn 3=inf 4=dbg

# Serial shell / console
CONFIG_SERIAL=y
CONFIG_UART_CONSOLE=y

# Sensor subsystem
CONFIG_SENSOR=y
CONFIG_I2C=y

# Disable features that panic in emulation
CONFIG_WATCHDOG=n              # WDT often triggers before Renode virtual time catches up
CONFIG_ENTROPY_NRF_RNG=n       # Hardware RNG may block indefinitely in emulation
```

## Makefile Wrapper Pattern

Samples in this project use a `Makefile` that wraps `west build`:

```makefile
TARGET_BOARD_ZEPHYR ?= bbc_microbit_v2

build:
    west build -b $(TARGET_BOARD_ZEPHYR) .

clean:
    rm -rf build/
```

Invoke as:
```bash
make -C samples/<name> TARGET_BOARD_ZEPHYR=<board> build
# Force pristine:
make -C samples/<name> TARGET_BOARD_ZEPHYR=<board> EXTRA_CFG="-p always" build
```

## Resolved Devicetree (`zephyr.dts`)

The resolved DTS is the most reliable source for:
- Peripheral base addresses (`reg = <0x40000000 0x1000>`)
- IRQ numbers (`interrupts = <37 0>`)
- Console UART alias (`chosen { zephyr,console = &usart1; }`)
- I²C / SPI bus assignments and device addresses

```bash
# Find the console UART
grep -A2 "zephyr,console" build/zephyr/zephyr.dts

# Find all I2C devices
grep -B2 "reg = " build/zephyr/zephyr.dts | grep -A1 "i2c"
```

## Common Build Failures

| Error | Cause | Fix |
|---|---|---|
| `Board <name> not found` | Wrong board target string | Run `west boards \| grep <keyword>` |
| `west: command not found` | west not on PATH | `pip install west` or activate the venv |
| `CMake Error: toolchain not found` | Zephyr SDK not set up | Set `ZEPHYR_SDK_INSTALL_DIR` or `ZEPHYR_TOOLCHAIN_VARIANT` |
| `fatal error: zephyr/kernel.h: No such file` | `ZEPHYR_BASE` not set | Run `. ~/zephyrproject/.venv/bin/activate && source ~/zephyrproject/zephyr/zephyr-env.sh` |
| `west update` errors | Workspace out of sync | Run `west update` in the workspace root |
| Stale CMakeCache mismatch | Board changed without pristine | Add `-p always` |

## Binary Selection for Renode

| Scenario | Load command |
|---|---|
| Standard Zephyr app | `sysbus LoadELF @build/zephyr/zephyr.elf` |
| MCUboot bootloader | `sysbus LoadELF @build/zephyr/zephyr.elf` (load bootloader first) |
| Signed app image | `sysbus LoadBinary @build/zephyr/zephyr.signed.bin <slot0_offset>` |
| Raw binary at known address | `sysbus LoadBinary @build/zephyr/zephyr.bin <flash_base_addr>` |

Get `<slot0_offset>` from `build/zephyr/zephyr.dts`:
```
&flash0 {
    partitions {
        slot0_partition: partition@<offset> { ... }
    }
}
```

## Quick Reference Checklist

Before referencing a binary in a Robot test:
1. `[ ]` Build succeeded (exit code 0)
2. `[ ]` `build/zephyr/zephyr.elf` exists (or `.hex` / `.bin` as appropriate)
3. `[ ]` Board target matches the `.repl` platform being tested
4. `[ ]` Used `-p always` if board or `prj.conf` changed since last build
5. `[ ]` `CONFIG_LOG=y` in `prj.conf` if test asserts on `LOG_INF` output
