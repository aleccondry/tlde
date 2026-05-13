# Skill: Renode Peripheral Catalogue

## Purpose

Reference of existing Renode stock peripheral models. Use this skill when deciding whether to reuse an upstream model or build a custom one, and when identifying the correct C# class name and namespace to reference in a `.repl` file.

## When to Reuse vs Build Custom

| Signal | Recommendation |
|---|---|
| Peripheral is a well-known ARM or ST/NXP/Nordic standard | Check catalogue first; a stock model likely exists |
| Firmware only reads status bits or does minimal config | Stock model usually sufficient |
| Firmware uses DMA, FIFO, or precise interrupt timing | Audit the stock model for missing behaviour before reusing |
| Peripheral is vendor-unique (custom radio, proprietary codec) | Build custom |
| Stock model exists but has known gaps for your MCU revision | Subclass the stock model and override only what differs |

## Namespace Conventions

```
Antmicro.Renode.Peripherals.<Category>.<ClassName>
```

Common categories:

| Category | Example class |
|---|---|
| `UART` | `STM32_UART`, `Nordic_UART`, `PL011` |
| `Timers` | `STM32_Timer`, `NRF52840_RTC`, `Cortex_A_GenericTimer` |
| `IRQControllers` | `NVIC`, `GIC`, `PLIC`, `CLINT` |
| `GPIOPort` | `STM32_GPIOPort`, `NRF52840_GPIO` |
| `SPI` | `STM32SPI`, `NRF52840_SPI` |
| `I2C` | `STM32F7_I2C`, `NRF52840_TWI` |
| `DMA` | `STM32DMA`, `STM32GPDMA` |
| `Miscellaneous` | `LED`, `Button`, `CombinedInput`, `ArmPowerControl` |
| `Sensors` | `LSM6DSO`, `BME280` |
| `Memory` | `MappedMemory`, `ArrayMemory`, `FlashStorage` |
| `MTD` | `MT25Q`, `S25FL` (SPI NOR flash) |
| `Network` | `Quectel_BC660K`, `ENC28J60` |
| `Wireless` | `NRF52840_Radio`, `ESP_WiFi_Model` |

## ARM Core Infrastructure (Always Available)

These are built into Renode; never need a custom implementation:

| Renode type | Use for |
|---|---|
| `CPU.CortexM` | ARM Cortex-M0/M0+/M3/M4/M7/M33 |
| `CPU.ARMv8A` | ARM Cortex-A series (64-bit) |
| `CPU.RiscV32` / `CPU.RiscV64` | RISC-V 32/64-bit cores |
| `IRQControllers.NVIC` | ARM Cortex-M NVIC (nested vector interrupt controller) |
| `Timers.ARM_GenericTimer` | ARMv7/v8 generic timer |
| `Miscellaneous.ArmPowerControl` | Cortex-M power management registers (`0xE000ED00`) |

## Commonly Reused Stock Models by MCU Family

### STM32 (ST Microelectronics)
Models live under `Antmicro.Renode.Peripherals.*` in the `renode-infrastructure` repo.

| Peripheral | Class | Notes |
|---|---|---|
| UART/USART | `UART.STM32_UART` | Covers F0–F7, L0–L5; check baud rate support |
| SPI | `SPI.STM32SPI` | Basic TX/RX; DMA mode not modelled |
| I2C | `I2C.STM32F7_I2C` | F7/H7 variant; older F1/F4 use `STM32F4_I2C` |
| GPIO | `GPIOPort.STM32_GPIOPort` | Full MODER/OTYPER/OSPEEDR register set |
| General-purpose timer | `Timers.STM32_Timer` | Basic + advanced timers |
| DMA | `DMA.STM32DMA` | Stream-based (F2/F4); GPDMA for G0/G4/H5/U5 |
| RCC | `Miscellaneous.STM32F4_RCC` | Clock gating registers; coarse model |
| Watchdog (IWDG) | `Timers.STM32_IndependentWatchdog` | Key register sequence modelled |
| Flash interface | `MTD.STM32F4_FlashController` | Lock/unlock + program emulation |
| USB FS | `USB.STM32_USB` | Enumeration only; no full protocol stack |

### Nordic nRF52 / nRF53 series

| Peripheral | Class | Notes |
|---|---|---|
| UART (UARTE) | `UART.Nordic_UART` | EasyDMA-based; nRF52840 and nRF5340 |
| SPI (SPIM) | `SPI.NRF52840_SPI` | Master mode; SPIS not modelled |
| I2C (TWIM) | `I2C.NRF52840_TWI` | Master mode only |
| GPIO | `GPIOPort.NRF52840_GPIO` | Full DIR/OUT/IN register set |
| GPIOTE | `GPIOPort.NRF52840_GPIOTE` | Event/task wiring |
| RTC | `Timers.NRF52840_RTC` | 24-bit, PRESCALER, COMPARE events |
| Timer | `Timers.NRF52840_Timer` | Configurable width (8/16/24/32-bit) |
| RADIO | `Wireless.NRF52840_Radio` | BLE physical layer; limited protocol |
| NVMC (flash) | `MTD.NRF52840_NVMC` | Erase/write protection registers |
| WDT | `Timers.NRF52840_Watchdog` | Run/pause behaviour in sleep |
| POWER | `Miscellaneous.NRF52840_POWER` | Reset reason + REGULATORS |
| CLOCK | `Miscellaneous.NRF52840_CLOCK` | HFCLK/LFCLK start events |

### Raspberry Pi RP2040

| Peripheral | Class | Notes |
|---|---|---|
| UART | `UART.PL011` | ARM PL011 compatible |
| SPI | `SPI.RP2040SPI` | |
| I2C | `I2C.RP2040I2C` | |
| GPIO | `GPIOPort.RP2040GPIO` | |
| Timer | `Timers.RP2040Timer` | 64-bit µs counter |
| PIO | Not modelled | Custom state machine; must build custom or stub |

### ESP32 / ESP32-C3

| Peripheral | Class | Notes |
|---|---|---|
| UART | `UART.ESP32_UART` | |
| SPI | `SPI.ESP32_SPI` | |
| GPIO | `GPIOPort.ESP32_GPIO` | |
| WiFi | `Network.ESP_WiFi_Model` | Stub only; no actual packet routing |

## Sensor Models (I²C / SPI)

| Sensor | Class | Interface |
|---|---|---|
| LSM6DSO (IMU) | `Sensors.LSM6DSO` | I²C / SPI |
| BME280 (env) | `Sensors.BME280` | I²C / SPI |
| MAX30208 (temp) | `Sensors.MAX30208` | I²C |
| TMP108 (temp) | `Sensors.TMP108` | I²C |
| VL53L1X (ToF) | `Sensors.VL53L1X` | I²C |

## Key Decision Rules

1. **Check the renode-infrastructure repo first.** The catalogue above is representative, not exhaustive. Search `src/Infrastructure/src/Emulator/Peripherals/` for `<VendorPrefix>` before concluding a model doesn't exist.
2. **Read the model before reusing it.** Verify it implements the registers your firmware touches. A model that stubs a critical register with `Tag` (log-only) will appear to work but silently drop writes.
3. **Subclassing is preferred over copy-paste.** Override only the register fields that differ from the stock model.
4. **Note the model in `notes` of the work unit.** State the class name, the commit/version it was verified against, and any gaps found.
5. **`MappedMemory` is always the right type for plain RAM/ROM regions.** Use `ArrayMemory` only when you need byte-level access hooks.
