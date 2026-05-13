# Skill: Renode RESC Script File Generation

## Purpose

Generate Renode `.resc` (REnode SCript) files that configure and launch emulation scenarios. RESC files are monitor scripts that create machines, load platform descriptions, configure peripherals, load firmware binaries, and set up the emulation environment.

## Context

RESC files are executed by the Renode Monitor (command-line interface). They orchestrate the complete setup of an emulation scenario: from machine creation through platform loading, binary loading, peripheral configuration, and defining the reset behavior. They support variables, macros, multi-machine setups, and integration with communication mediums.

## Format Specification

### File Extension
- `.resc` (REnode SCript)

### Execution Model
- Lines are executed sequentially, top-to-bottom
- Each line is a Monitor command with space-separated arguments
- Scripts can include other scripts and define reusable macros

### Comments
- Line comments: `#` (only at start of meaningful content)
- Metadata headers: `:name:`, `:description:` (documentation, not executed)

### Variables

```resc
# Direct assignment (always sets)
$variable = "value"
$variable = @https://dl.antmicro.com/projects/renode/binary.elf

# Default assignment (only sets if not already defined)
$variable?="default_value"
$variable?=@path/to/default/binary.elf

# Alternative syntax
set variable "value"

# Multiline variable
set variable
"""
line 1
line 2
"""

# Special path variables
$ORIGIN         # Relative to current script file location
$CWD            # Current working directory
$global.name    # Global variable accessible across machines
```

### Variable Types
- **Strings**: `"hello"`
- **Paths**: `@platforms/cpus/name.repl`, `@https://url/to/binary.elf`
- **Integers**: `1`, `0xFFFF`, `0b1010`
- **Floats**: `1.1`
- **Ranges**: `<0xDEAD, 0xBEEF>`
- **Booleans**: `true`, `false`
- **Command substitution**: `` `command` `` (backticks execute and return result)

### Macros

```resc
# Define a macro (multiline)
# Use the appropriate load command for the binary format:
#   LoadELF for .elf files
#   LoadBinary for raw .bin files (requires load address)
#   LoadHEX for Intel .hex files (address embedded in file)
macro reset
"""
    sysbus LoadELF $bin
    cpu PC 0x80000000
"""

# Execute a macro
runMacro $reset

# Named custom macros
macro my_setup
"""
    sysbus LoadHEX $firmware
    sysbus.uart0 BaudRate 115200
"""
runMacro $my_setup
```

The `reset` macro is special — it runs automatically when `machine Reset` is called.

## Core Commands

### Machine Lifecycle

```resc
mach create                         # Create unnamed machine (machine-0, machine-1, ...)
mach create "my_machine"            # Create named machine
mach set "my_machine"               # Switch monitor context to machine
mach set 0                          # Switch by index
```

### Platform Loading

```resc
machine LoadPlatformDescription @platforms/cpus/stm32f4.repl
machine LoadPlatformDescription $platform
machine LoadPlatformDescriptionFromString "sensor: Sensors.SI70xx @ i2c1 0x44"
```

### Binary Loading

```resc
# ELF files (contains code + entry point + debug symbols)
sysbus LoadELF @path/to/firmware.elf
sysbus LoadELF $bin
sysbus LoadELF $bin cpu=cpu0             # Multi-core: target specific CPU

# Raw binary files (requires explicit load address)
sysbus LoadBinary $binary 0x80000000
sysbus LoadBinary $binary 0x80000000 cpu=apu0

# Intel HEX files (addresses embedded in file, no load address needed)
sysbus LoadHEX @firmware.hex

# U-Boot images
sysbus LoadUImage @uImage

# Device Tree Blob
sysbus LoadFdt $dtb 0x100000 "console=ttyS0,115200 root=/dev/ram0 rw"
sysbus LoadFdt $dtb 0x100000 "bootargs" false context=apu0

# Symbol loading (debug symbols separate from code)
sysbus LoadSymbolsFrom $vmlinux
sysbus LoadSymbolsFrom $uboot_elf context=apu0

# Inline assembly
cpu AssembleBlock 0x80000000 """
li sp, 0x80004000
li t0, 0x10013000
j main
"""
```

### Using Namespace

```resc
using sysbus                         # Shorthand: uart0 instead of sysbus.uart0
```

### Peripheral Configuration

```resc
# Set properties
sysbus.uart0 BaudRate 115200
sysbus.timer0 Frequency 48000000

# Execute methods
sysbus.memory ZeroAll
cpu PC 0x08000000
cpu VectorTableOffset `sysbus GetSymbolAddress "__Vectors"`

# Set CPU registers
cpu SetRegister "X0" 0xABC
cpu IsHalted true
cpu IsHalted false
```

### Analyzers and Output

```resc
# Show UART output window (GUI mode)
showAnalyzer sysbus.uart0
showAnalyzer uart0                   # If "using sysbus" is active

# Server socket terminal (headless mode)
emulation CreateServerSocketTerminal 3456 "terminal_name"
connector Connect sysbus.uart0 terminal_name

# Virtual console
machine CreateVirtualConsole "segger_rtt"
```

### Memory Operations

```resc
# Tag memory regions (logging stubs)
sysbus Tag <0x40080000, 0x400> "RADIO"
sysbus Tag <0x40026000, 0x3FF> "AES" 0xDEADBEEF

# Redirect memory access
sysbus Redirect 0xC0000000 0x0 0x10000000

# Apply SVD for register names in logs
sysbus ApplySVD @https://dl.antmicro.com/projects/renode/svd/STM32F4xx.svd
```

### Execution Control

```resc
start                                # Begin emulation
pause                                # Pause emulation
machine Reset                        # Reset (runs $reset macro)
emulation RunFor "3.2"               # Run for N seconds (virtual time)
```

### Logging

```resc
logLevel 3                           # Set global log level
logLevel -1 sysbus.uart0            # Set per-peripheral log level
sysbus LogPeripheralAccess uart0 True
sysbus LogAllPeripheralsAccess false
```

### GDB Server

```resc
machine StartGdbServer 3333
machine StartGdbServer 3333 false cpu0  # Specific CPU
```

### Emulation Settings

```resc
emulation SetGlobalQuantum "0.00001"
emulation SetGlobalSerialExecution true
machine SetSerialExecution True
```

## Multi-Node Commands

### Communication Mediums

```resc
# Bluetooth Low Energy
emulation CreateBLEMedium "wireless"

# IEEE 802.15.4 (Zigbee, Thread)
emulation CreateIEEE802_15_4Medium "wireless"

# WiFi (DA16200-specific)
emulation CreateDA16200Network "wifi"

# CAN Bus
emulation CreateCANHub "canHub"

# UART Hub (for HCI-UART bridging)
emulation CreateUARTHub "hci_uart_hub"
```

### Connecting to Mediums

```resc
connector Connect sysbus.radio wireless
connector Connect sysbus.fdcan1 canHub
connector Connect sysbus.uart1 hci_uart_hub
```

### Socket Bridges

```resc
machine CreateSocketCANBridge "socketcan"
connector Connect socketcan canHub
```

## Common Patterns

### Pattern 1: Simple Single-Node Script

```resc
:name: STM32F4 Discovery
:description: Runs firmware on STM32F4 Discovery board

$bin?=@https://dl.antmicro.com/projects/renode/stm32f4-demo.elf-s_123456-abc123

using sysbus
mach create "stm32f4"
machine LoadPlatformDescription @platforms/boards/stm32f4_discovery.repl

showAnalyzer uart1

macro reset
"""
    sysbus LoadELF $bin
"""

runMacro $reset
```

### Pattern 2: Single-Node with Custom Configuration

```resc
:name: Murax SoC Demo
:description: Runs VexRiscv Murax SoC demo

$bin?=@https://dl.antmicro.com/projects/renode/murax--demo.elf-s_26952-abc123

using sysbus
mach create "murax"
machine LoadPlatformDescription @platforms/cpus/murax_vexriscv.repl

showAnalyzer uart

macro reset
"""
    sysbus LoadELF $bin
    cpu MTVEC 0x80000020
    cpu SetMachineIrqMask 0xffffffff
"""

runMacro $reset
```

### Pattern 3: Multi-Node BLE

```resc
:name: nRF52840 BLE Demo
:description: Two nRF52840 nodes communicating via BLE

$central_bin?=@https://dl.antmicro.com/projects/renode/central.elf
$peripheral_bin?=@https://dl.antmicro.com/projects/renode/peripheral.elf

using sysbus
emulation CreateBLEMedium "wireless"

mach create "central"
machine LoadPlatformDescription @platforms/cpus/nrf52840.repl
connector Connect sysbus.radio wireless
showAnalyzer uart0

mach create "peripheral"
machine LoadPlatformDescription @platforms/cpus/nrf52840.repl
connector Connect sysbus.radio wireless
showAnalyzer uart0

macro reset
"""
    mach set "central"
    sysbus LoadELF $central_bin

    mach set "peripheral"
    sysbus LoadELF $peripheral_bin
"""

runMacro $reset
```

### Pattern 4: Complex Linux Boot (Multi-Stage)

```resc
:name: Zynq UltraScale+ Linux
:description: Boots Linux on Zynq UltraScale+ with ATF and U-Boot

$atf?=@https://dl.antmicro.com/projects/renode/zynqmp-atf.elf
$uboot?=@https://dl.antmicro.com/projects/renode/u-boot.bin
$linux?=@https://dl.antmicro.com/projects/renode/Image
$dtb?=@https://dl.antmicro.com/projects/renode/zynqmp.dtb
$rootfs?=@https://dl.antmicro.com/projects/renode/rootfs.cpio

using sysbus
mach create "zynqmp"
machine LoadPlatformDescription @platforms/cpus/zynqmp.repl

showAnalyzer uart1

macro reset
"""
    sysbus LoadELF $atf cpu=apu0
    sysbus LoadBinary $uboot 0x8000000 cpu=apu0
    sysbus LoadBinary $linux 0x10000000 cpu=apu0
    sysbus LoadBinary $rootfs 0x20000000 cpu=apu0
    sysbus LoadFdt $dtb 0x100000 "earlycon console=ttyPS1,115200 root=/dev/ram0 rw" false context=apu0
    sysbus LoadSymbolsFrom $atf context=apu0
"""

runMacro $reset
```

### Pattern 5: Multi-Node CAN Bus

```resc
:name: CAN Bus Network
:description: Multiple ECUs connected via CAN

using sysbus
emulation CreateCANHub "canHub"

# ECU A
mach create "ecu_a"
machine LoadPlatformDescription @platforms/cpus/stm32h747.repl
connector Connect sysbus.fdcan1 canHub
showAnalyzer uart1

# ECU B
mach create "ecu_b"
machine LoadPlatformDescription @platforms/cpus/stm32h747.repl
connector Connect sysbus.fdcan1 canHub
showAnalyzer uart1

macro reset
"""
    mach set "ecu_a"
    sysbus LoadELF $ecu_a_bin

    mach set "ecu_b"
    sysbus LoadELF $ecu_b_bin
"""

runMacro $reset
```

### Pattern 6: Including Sub-Scripts

```resc
:name: Multi-ECU CAN Network
:description: Reuses per-node script via include

using sysbus
emulation CreateCANHub "canHub"

set global.name "ECU_A"
$bin = @path/to/ecu_a.elf
include @scripts/single-node/ecu_node.resc
connector Connect sysbus.fdcan1 canHub

set global.name "ECU_B"
$bin = @path/to/ecu_b.elf
include @scripts/single-node/ecu_node.resc
connector Connect sysbus.fdcan1 canHub

start
```

### Pattern 7: With Inline Platform Extension

```resc
:name: STM32 with External Sensor
:description: Adds I2C sensor not in base platform

$bin?=@firmware.elf

using sysbus
mach create
machine LoadPlatformDescription @platforms/cpus/stm32l072.repl
machine LoadPlatformDescriptionFromString "bme280: Sensors.BME280 @ i2c1 0x76"
machine LoadPlatformDescriptionFromString "led: Miscellaneous.LED @ gpioPortB 5"

showAnalyzer usart2

macro reset
"""
    sysbus LoadELF $bin
"""

runMacro $reset
```

## Script Documentation Headers

Always include metadata at the top of scripts:

```resc
:name: Human Readable Name
:description: Brief description of what this script sets up and runs
```

## Validation Checklist

When generating a RESC file, verify:

1. **`using sysbus` appears before unqualified peripheral names** (or use full `sysbus.` prefix)
2. **`mach create` before any machine-specific commands**
3. **Platform description loaded before binary** (peripherals must exist first)
4. **`$variable?=` for user-overridable defaults** (allows CLI override)
5. **`macro reset` contains all binary loading** (enables `machine Reset`)
6. **Multi-machine: `mach set` before each machine's commands**
7. **Medium created before `connector Connect`** calls
8. **`runMacro $reset` at script end** (performs initial load)
9. **Binary URLs use full hash-suffixed paths** for reproducibility
10. **`showAnalyzer` or terminal setup for any UART** the user needs to observe

## Output Format

Generate complete, executable `.resc` files. Include `:name:` and `:description:` headers. Use `$variable?=` for any user-configurable paths (binaries, scripts). Structure the script in the standard order: metadata → variables → machine creation → platform → analyzers → macro reset → runMacro.
