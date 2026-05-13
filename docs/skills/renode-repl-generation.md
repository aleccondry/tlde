# Skill: Renode REPL Platform Description File Generation

## Purpose

Generate Renode `.repl` (REnode PLatform) files that describe hardware platform configurations for firmware emulation. REPL files define the complete hardware topology including CPUs, memory regions, peripherals, interrupt connections, and bus registrations.

## Context

Renode uses a YAML-like text-based format for platform descriptions. These files define the hardware structure that the emulator instantiates. The format supports inheritance via `using`, property overrides, and complex interrupt routing topologies.

## Format Specification

### File Extension
- `.repl` (REnode PLatform)

### Indentation Rules
- **Only spaces** (no tabs)
- **4 spaces** per indentation level
- Indentation inside braces `{}` is NOT meaningful
- Semicolons separate statements in non-indent (brace) mode

### Comments
- Line comments: `// comment`
- Multiline comments: `/* comment */`

### Basic Entry Structure

```repl
variableName: TypeName @ registrationInfo
    attribute1: value1
    attribute2: value2
    -> interruptDestination@irqNumber
```

All of `TypeName`, `registrationInfo`, and `attributes` are optional, but at least one must be present.

- **Creating entry**: Contains a `TypeName` (declares the variable)
- **Updating entry**: No `TypeName` (modifies an existing variable)

### Value Types
- **Strings**: `"hello"` (escape: `\"`)
- **Multiline strings**: `'''content'''` (escape: `\'''`)
- **Booleans**: `true`, `false`
- **Numbers**: decimal (`42`) or hexadecimal (`0x2A`)
- **Ranges**: `<begin, end>` or `<begin, +size>` (e.g., `<0x40000000, +0x400>`)
- **References**: variable name (e.g., `gic`, `cpu`)
- **Inline objects**: `new Type { attr1: val1; attr2: val2 }`
- **Lists**: `[value1, value2, value3]`
- **Keywords**: `none` (cancel/unset), `empty` (default value)

### Registration Info

```repl
// Single registration on sysbus at address
peripheral: Type @ sysbus 0x40000000

// Registration with range (address + size)
peripheral: Type @ sysbus <0x40000000, +0x400>

// Registration on another bus (e.g., I2C)
sensor: Sensors.SI70xx @ i2c0 0x44

// Multiple registrations
ram: Memory.MappedMemory @ { sysbus 0x800000; sysbus 0x20000000 }
    size: 0x40000

// Complex multi-region registration (e.g., GIC)
gic: IRQControllers.ARM_GenericInterruptController @ {
        sysbus new Bus.BusMultiRegistration { address: 0x8000000; size: 0x10000; region: "distributor" };
        sysbus new Bus.BusMultiRegistration { address: 0x8010000; size: 0x10000; region: "cpuInterface" }
    }

// Core-specific registration (visible only to one CPU)
nvic: IRQControllers.NVIC @ sysbus new Bus.BusPointRegistration {
        address: 0xE000E000;
        cpu: cpu_m33
    }

// Alias
peripheral: Type @ sysbus 0x1000 as "customName"

// Cancel registration
variable: @ none
```

### Type Namespaces
- Default namespace `Antmicro.Renode.Peripherals` can be omitted
- Example: `UART.PL011` instead of `Antmicro.Renode.Peripherals.UART.PL011`

Common namespace prefixes:
- `CPU.` — Processors (ARMv7A, ARMv8A, CortexM, RiscV32, RiscV64, etc.)
- `UART.` — Serial ports
- `Timers.` — Timer peripherals
- `IRQControllers.` — Interrupt controllers (NVIC, GIC, PLIC, etc.)
- `GPIOPort.` — GPIO controllers
- `Memory.` — Memory regions (MappedMemory, ArrayMemory)
- `SPI.` — SPI controllers
- `I2C.` — I2C controllers
- `DMA.` — DMA controllers
- `Sensors.` — I2C/SPI sensors
- `Miscellaneous.` — LEDs, Buttons, CombinedInput, etc.
- `Network.` — Network controllers
- `SD.` — SD card controllers

### Attributes

#### Constructor/Property Attributes
```repl
// Constructor parameter (lowercase initial)
peripheral: Type @ sysbus 0x0
    frequency: 48000000

// Property (uppercase initial)
peripheral: Type @ sysbus 0x0
    Frequency: 48000000
```

#### Interrupt Attributes
```repl
// Default (single GPIO property)
timer: Timers.SomeTimer @ sysbus 0x1000
    -> nvic@15

// Named source
uart: UART.SomeUART @ sysbus 0x2000
    TxInterrupt -> nvic@10
    RxInterrupt -> nvic@11

// Numbered source (INumberedGPIOOutput)
dma: DMA.SomeDMA @ sysbus 0x3000
    0 -> nvic@5
    1 -> nvic@6

// Range mapping
gpioPort: GPIOPort.STM32_GPIOPort @ sysbus <0x50000000, +0x400>
    [0-15] -> exti@[0-15]

// Multiple destinations (OR)
exti:
    0 -> gpioPortA#0@2 | gpioPortB#0@2

// Local interrupt receiver (#index)
timer: Timers.ARM_GenericTimer @ cpu
    EL1PhysicalTimerIRQ -> gic#0@30
    NonSecureEL2PhysicalTimerIRQ -> gic#0@26

// Cancel connection
source -> none
```

#### Init/Preinit/Reset Attributes
```repl
// Init: commands executed after peripheral creation (prepended with peripheral name)
sysbus:
    init:
        Tag <0x40080000, 0x400> "RADIO"
        Tag <0x40026000, 0x3FF> "AES"
        ApplySVD @https://path/to/file.svd

// Preinit: commands executed before creation (global context)
peripheral: MyPeripheral @ sysbus 0x0
    preinit:
        include @MyPeripheral.cs

// Reset: commands executed when peripheral is reset
peripheral:
    reset:
        SomeCommand

// Append mode (instead of override)
peripheral:
    init add:
        AdditionalCommand
```

### Using (File Inheritance)

```repl
// Must appear before all other entries
using "platforms/cpus/stm32f4.repl"
using "./relative_path.repl"
using "/absolute/path.repl"

// With prefix (prepends to all variable names from included file)
using "platforms/cpus/cortex-r52.repl" prefixed "core0_"
```

### Local Variables
```repl
// Only visible within current file
local myHelper: SomeType @ sysbus 0x0
    property: value
```

## Common Patterns

### Pattern 1: Cortex-M Microcontroller

```repl
// STM32-style Cortex-M platform
nvic: IRQControllers.NVIC @ sysbus 0xE000E000
    priorityMask: 0xF0
    systickFrequency: 72000000
    IRQ -> cpu@0

cpu: CPU.CortexM @ sysbus
    cpuType: "cortex-m4f"
    nvic: nvic

flash: Memory.MappedMemory @ sysbus 0x08000000
    size: 0x100000

sram: Memory.MappedMemory @ sysbus 0x20000000
    size: 0x20000

uart1: UART.STM32_UART @ sysbus <0x40011000, +0x400>
    -> nvic@37

timer2: Timers.STM32_Timer @ sysbus <0x40000000, +0x400>
    frequency: 72000000
    initialLimit: 0xFFFF
    -> nvic@28

gpioPortA: GPIOPort.STM32_GPIOPort @ sysbus <0x40020000, +0x400>
    modeResetValue: 0xA8000000
    [0-15] -> exti@[0-15]
```

### Pattern 2: RISC-V SoC

```repl
cpu: CPU.RiscV32 @ sysbus
    cpuType: "rv32imac_zicsr_zifencei"
    privilegedArchitecture: PrivilegedArchitecture.Priv1_10
    timeProvider: clint
    hartId: 0

clint: IRQControllers.CoreLevelInterruptor @ sysbus 0x02000000
    frequency: 66000000
    numberOfTargets: 1
    [0, 1] -> cpu@[3, 7]

plic: IRQControllers.PlatformLevelInterruptController @ sysbus 0x0C000000
    numberOfSources: 128
    numberOfContexts: 2
    prioritiesEnabled: false
    [0, 1] -> cpu@[11, 9]

ram: Memory.MappedMemory @ sysbus 0x80000000
    size: 0x4000000

uart0: UART.SiFive_UART @ sysbus 0x10010000
    -> plic@4
```

### Pattern 3: ARMv8-A with GIC

```repl
cpu0: CPU.ARMv8A @ sysbus
    cpuType: "cortex-a53"
    cpuId: 0
    genericInterruptController: gic

gic: IRQControllers.ARM_GenericInterruptController @ {
        sysbus new Bus.BusMultiRegistration { address: 0x8000000; size: 0x10000; region: "distributor" };
        sysbus new Bus.BusMultiRegistration { address: 0x8010000; size: 0x10000; region: "cpuInterface" }
    }
    architectureVersion: IRQControllers.ARM_GenericInterruptControllerVersion.GICv2
    supportsTwoSecurityStates: false
    [0] -> cpu0@0
    [1] -> cpu0@1

timer: Timers.ARM_GenericTimer @ cpu0
    frequency: 62500000
    EL1PhysicalTimerIRQ -> gic#0@30
    EL1VirtualTimerIRQ -> gic#0@27
    NonSecureEL2PhysicalTimerIRQ -> gic#0@26

ddr: Memory.MappedMemory @ sysbus 0x40000000
    size: 0x40000000

uart0: UART.PL011 @ sysbus 0x09000000
    -> gic@33
```

### Pattern 4: Multi-Core SMP

```repl
// Base single-core file: cortex-r52.repl
using "./cortex-r52.repl"

// Add second core
cpu1: CPU.ARMv8R @ sysbus
    cpuType: "cortex-r52"
    genericInterruptController: gic
    cpuId: 1

// Update GIC for multi-core support
gic: @ {
        sysbus new IRQControllers.ArmGicRedistributorRegistration { attachedCPU: cpu; address: 0xAF100000 };
        sysbus new IRQControllers.ArmGicRedistributorRegistration { attachedCPU: cpu1; address: 0xAF120000 }
    }

timer1: Timers.ARM_GenericTimer @ cpu1
    frequency: 62500000
    EL1PhysicalTimerIRQ -> gic#1@30
```

### Pattern 5: Board with External Peripherals

```repl
// Board file inherits from CPU platform
using "platforms/cpus/stm32f4.repl"

// Add board-specific peripherals
UserButton: Miscellaneous.Button @ gpioPortA
    -> gpioPortA@0

led0: Miscellaneous.LED @ gpioPortD 12
led1: Miscellaneous.LED @ gpioPortD 13
led2: Miscellaneous.LED @ gpioPortD 14
led3: Miscellaneous.LED @ gpioPortD 15
```

### Pattern 6: Platform with I2C/SPI Sensors

```repl
i2c1: I2C.STM32F4_I2C @ sysbus <0x40005400, +0x400>
    -> nvic@31

temperatureSensor: Sensors.SI70xx @ i2c1 0x44

spi1: SPI.STM32SPI @ sysbus <0x40013000, +0x400>
    -> nvic@35

accelerometer: Sensors.LIS2DW12 @ spi1 0
```

### Pattern 7: Memory-Mapped Peripheral with Tags (Stubs)

```repl
sysbus:
    init:
        Tag <0x40080000, 0x400> "RADIO"
        Tag <0x40026000, 0x3FF> "AES"
        Tag <0x400FF000, 0xFFF> "GPIO_TASK_EVENT"
        ApplySVD @https://dl.antmicro.com/projects/renode/svd/STM32F4xx.svd
```

### Pattern 8: CombinedInput for Shared IRQ Lines

```repl
// Multiple peripheral interrupts merged into single NVIC input
nvicInput5: Miscellaneous.CombinedInput
    numberOfInputs: 2
    -> nvic@5

timer6: Timers.STM32_Timer @ sysbus <0x40001000, +0x400>
    -> nvicInput5@0

dac: Analog.STM32_DAC @ sysbus <0x40007400, +0x400>
    -> nvicInput5@1
```

## Validation Checklist

When generating a REPL file, verify:

1. **`using` entries appear first** (before any peripheral entries)
2. **Each variable is created (typed) only once** across all files in hierarchy
3. **Addresses don't overlap** between peripherals (unless intentional mirror)
4. **IRQ numbers are unique per destination** (no two sources to same destination@number without CombinedInput)
5. **CPU type string matches available models** (e.g., "cortex-m4f", "cortex-a53", "rv32imac_zicsr_zifencei")
6. **Memory sizes are power-of-2 aligned** where required by architecture
7. **Interrupt controller is connected to CPU** (nvic->cpu for Cortex-M, gic->[N]->cpuN for A-profile)
8. **Required constructor parameters are provided** (e.g., `frequency` for timers, `cpuType` for CPUs)
9. **Registration size matches peripheral's IKnownSize** or is explicitly provided via range syntax
10. **Namespace prefixes are correct** for all peripheral types

## Output Format

Generate complete, syntactically valid `.repl` files. Include comments explaining non-obvious configurations. Use the standard Renode peripheral type names exactly as they appear in the renode-infrastructure source.
