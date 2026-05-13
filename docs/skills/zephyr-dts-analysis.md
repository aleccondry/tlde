# Skill: Zephyr Device Tree Analysis

## Purpose

Extract peripheral configuration information from Zephyr RTOS build artifacts (`.dts`, `.dts.pre`, `devicetree.h`, `.config`) to inform Renode platform model generation. This skill provides patterns for reading Zephyr's device tree format and mapping nodes to Renode artifacts.

## Context

Zephyr RTOS uses Device Tree (DTS) to describe hardware. The build system processes DTS files and generates resolved artifacts that contain the actual addresses, interrupts, and configuration used by firmware. These artifacts are authoritative sources for peripheral configuration when generating Renode models.

## Key Build Artifacts

| File | Description | When to Use |
|------|-------------|-------------|
| `zephyr.dts` | Final resolved DTS after preprocessing | Primary source for peripheral info |
| `zephyr.dts.pre` | Preprocessed DTS before final resolution | Debugging DTS issues |
| `devicetree.h` | Generated C headers with macros | Verifying what firmware sees |
| `.config` | Final Kconfig with all symbols resolved | Check feature enablement |
| `zephyr.dts.compiled` | Binary DTS blob (rarely used) | Advanced debugging |

## DTS File Location

```
<build_dir>/zephyr/
├── zephyr.dts              # Primary: resolved device tree
├── zephyr.dts.pre          # Preprocessed DTS
├── devicetree.h            # Generated C header
├── include/generated/      # Additional generated headers
│   └── devicetree_unfixed.h
└── .config                  # Kconfig output
```

## DTS Syntax Overview

### Basic Node Structure

```dts
/ {
    soc {
        uart0: uart@40011000 {
            compatible = "st,stm32-usart", "st,stm32-uart";
            reg = <0x40011000 0x400>;
            reg-names = "regs";
            interrupts = <37 0>;
            clocks = <&rcc STM32_CLOCK_BUS_APB2 0x00000010>;
            status = "okay";
            current-speed = <115200>;
            label = "UART_0";
        };
    };
};
```

### Key Properties

| Property | Description | Renode Mapping |
|----------|-------------|----------------|
| `reg = <addr size>` | Base address and size | `.repl` registration address |
| `interrupts = <irq flags>` | IRQ number and flags | `.repl` IRQ wiring |
| `compatible` | Driver binding string | Identifies peripheral type |
| `status` | "okay" or "disabled" | Whether peripheral is used |
| `label` | Zephyr device name | Firmware reference |
| `clocks` | Clock source reference | Clock configuration |
| `pinctrl-*` | Pin mux configuration | GPIO pin assignments |

## Extracting Peripheral Information

### Peripheral Address Map

```bash
# Extract all peripherals with addresses
grep -E "^\s+[a-z0-9_]+@[0-9a-f]+" build/zephyr/zephyr.dts

# Or more detailed extraction
awk '/[a-z_]+@[0-9a-f]+/ {print}' build/zephyr/zephyr.dts
```

### UART Extraction Pattern

```dts
# Example UART nodes to find:
uart1: usart@40011000 {
    compatible = "st,stm32-usart";
    reg = <0x40011000 0x400>;
    interrupts = <37 0>;
    status = "okay";
    current-speed = <115200>;
};

uart2: lpuart@40008000 {
    compatible = "st,stm32-lpuart";
    reg = <0x40008000 0x400>;
    interrupts = <38 0>;
    status = "okay";
};
```

Extracted values:
- Base address: `0x40011000`
- Size: `0x400`
- IRQ: `37`
- Baud rate: `115200`

### GPIO Extraction Pattern

```dts
gpiob: gpio@48000400 {
    compatible = "st,stm32-gpio";
    reg = <0x48000400 0x400>;
    clocks = <&rcc STM32_CLOCK_BUS_AHB2 0x00000002>;
    gpio-controller;
    #gpio-cells = <2>;
    status = "okay";
    label = "GPIOB";
};

gpioc: gpio@48000800 {
    compatible = "st,stm32-gpio";
    reg = <0x48000800 0x400>;
    status = "okay";
    label = "GPIOC";
};
```

### I2C Extraction Pattern

```dts
i2c0: i2c@40005400 {
    compatible = "st,stm32-i2c-v2";
    reg = <0x40005400 0x400>;
    interrupts = <31 0>, <32 0>;
    clocks = <&rcc STM32_CLOCK_BUS_APB1 0x00000001>;
    status = "okay";
    
    bme280: bme280@76 {
        compatible = "bosch,bme280";
        reg = <0x76>;
    };
};
```

Extracted values:
- I2C controller address: `0x40005400`
- IRQs: `31` (event), `32` (error)
- Device on bus: `bme280` at address `0x76`

### SPI Extraction Pattern

```dts
spi1: spi@40013000 {
    compatible = "st,stm32-spi";
    reg = <0x40013000 0x400>;
    interrupts = <35 0>;
    clocks = <&rcc STM32_CLOCK_BUS_APB2 0x00001000>;
    status = "okay";
    
    accelerometer: lis2dw12@0 {
        compatible = "st,lis2dw12";
        reg = <0>;
        spi-max-frequency = <1000000>;
    };
};
```

### Timer Extraction Pattern

```dts
timers2: timers@40000000 {
    compatible = "st,stm32-timers";
    reg = <0x40000000 0x400>;
    clocks = <&rcc STM32_CLOCK_BUS_APB1 0x00000001>;
    interrupts = <28 0>;
    status = "okay";
    label = "TIMERS_2";
    
    pwm {
        compatible = "st,stm32-pwm";
        status = "okay";
        #pwm-cells = <3>;
    };
};
```

### Flash Memory Map

```dts
flash0: flash@8000000 {
    compatible = "soc-nv-flash";
    reg = <0x08000000 0x100000>;
    label = "FLASH_0";
    
    partitions {
        compatible = "fixed-partitions";
        #address-cells = <1>;
        #size-cells = <1>;
        
        boot_partition: partition@0 {
            label = "mcuboot";
            reg = <0x00000000 0x00010000>;
        };
        
        slot0_partition: partition@10000 {
            label = "image-0";
            reg = <0x00010000 0x00040000>;
        };
        
        slot1_partition: partition@50000 {
            label = "image-1";
            reg = <0x00050000 0x00040000>;
        };
    };
};

sram0: memory@20000000 {
    compatible = "mmio-sram";
    reg = <0x20000000 0x40000>;
};
```

## Mapping to Renode

### Address to REPL Registration

```dts
/* DTS */
uart0: uart@40011000 {
    reg = <0x40011000 0x400>;
};
```

```repl
/* Renode REPL */
uart0: UART.STM32_UART @ sysbus <0x40011000, +0x400>
```

### Interrupts to IRQ Wiring

```dts
/* DTS */
interrupts = <37 0>;
```

```repl
/* Renode REPL */
uart0: UART.STM32_UART @ sysbus <0x40011000, +0x400>
    -> nvic@37
```

For multiple interrupts:
```dts
interrupts = <31 0>, <32 0>;
```

```repl
i2c0: I2C.STM32F4_I2C @ sysbus <0x40005400, +0x400>
    EventInterrupt -> nvic@31
    ErrorInterrupt -> nvic@32
```

### Clock Configuration

Clock information from DTS helps determine peripheral frequency but doesn't directly map to Renode. Use the clock configuration to set correct frequencies:

```dts
clocks = <&rcc STM32_CLOCK_BUS_APB2 0x00000010>;
```

This indicates the UART is on APB2. Check the system clock configuration:

```dts
clk_hse: clk-hse {
    clock-frequency = <DT_FREQ_M(8)>;
};

pll: pll {
    clocks = <&clk_hse>;
    div-m = <8>;
    mul-n = <336>;
    div-p = <2>;
    div-q = <7>;
    /* VCO = 8MHz * 336/8 = 336MHz */
    /* SYSCLK = 336MHz / 2 = 168MHz */
    /* APB2 = 168MHz / 2 = 84MHz */
};
```

Then in Renode:
```repl
uart0: UART.STM32_UART @ sysbus <0x40011000, +0x400>
    frequency: 84000000
```

## Device Status Analysis

### Enabled vs Disabled Peripherals

```dts
/* Enabled - used by firmware */
uart0: uart@40011000 {
    status = "okay";
};

/* Disabled - not used, can be stubbed or omitted */
uart1: uart@40011400 {
    status = "disabled";
};
```

**Tier strategy:**
- `status = "okay"` → Tier 1 or 2 (must model)
- `status = "disabled"` → Tier 3 (stub or omit)

## .config Analysis

The `.config` file shows which features are actually compiled in:

```ini
# UART is enabled
CONFIG_SERIAL=y
CONFIG_UART_STM32=y

# Shell on UART0
CONFIG_SHELL=y
CONFIG_SHELL_BACKEND_UART=y
CONFIG_SHELL_BACKEND_SERIAL_INDEX=0

# MCUboot enabled
CONFIG_BOOTLOADER_MCUBOOT=y

# Networking disabled
CONFIG_NETWORKING=n

# Bluetooth disabled
CONFIG_BT=n
```

### Feature Extraction

```bash
# Check for MCUboot
grep "CONFIG_BOOTLOADER_MCUBOOT=y" build/zephyr/.config

# Check for shell
grep "CONFIG_SHELL=y" build/zephyr/.config

# Check for networking
grep "CONFIG_NETWORKING=y" build/zephyr/.config

# Check for Bluetooth
grep "CONFIG_BT=y" build/zephyr/.config
```

## devicetree.h Analysis

The generated header shows how firmware accesses devices:

```c
/* Node identifier for UART_0 */
#define DT_NODELABEL_UART_0 DT_N_S_soc_S_uart_40011000

/* Base address */
#define DT_REG_ADDR(DT_NODELABEL(uart_0)) 0x40011000

/* Interrupt number */
#define DT_IRQN(DT_NODELABEL(uart_0)) 37

/* Label string */
#define DT_LABEL(DT_NODELABEL(uart_0)) "UART_0"

/* Baud rate */
#define DT_PROP(DT_NODELABEL(uart_0), current_speed) 115200
```

Use this to verify the DTS extraction matches what firmware expects.

## Common Patterns

### Extracting All Enabled Peripherals

```python
# Example Python script to parse DTS
import re

def parse_dts(dts_content):
    peripherals = []
    
    # Find all peripheral nodes
    pattern = r'(\w+): (\w+)@([0-9a-fA-F]+)\s*\{([^}]+)\}'
    
    for match in re.finditer(pattern, dts_content):
        label, name, addr, body = match.groups()
        
        # Check if enabled
        if 'status = "okay"' in body or 'status = "disabled"' not in body:
            # Extract reg
            reg_match = re.search(r'reg = <(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)>', body)
            # Extract interrupts
            irq_match = re.search(r'interrupts = <(\d+)', body)
            
            peripherals.append({
                'label': label,
                'name': name,
                'address': reg_match.group(1) if reg_match else addr,
                'size': reg_match.group(2) if reg_match else None,
                'irq': int(irq_match.group(1)) if irq_match else None,
            })
    
    return peripherals
```

### Generating REPL from DTS

```python
def generate_repl(peripherals):
    lines = []
    for p in peripherals:
        if p['name'].startswith('uart'):
            typename = 'UART.STM32_UART'
        elif p['name'].startswith('i2c'):
            typename = 'I2C.STM32F4_I2C'
        elif p['name'].startswith('spi'):
            typename = 'SPI.STM32SPI'
        elif p['name'].startswith('gpio'):
            typename = 'GPIOPort.STM32_GPIOPort'
        elif p['name'].startswith('timer'):
            typename = 'Timers.STM32_Timer'
        else:
            typename = 'Miscellaneous.Unknown'
        
        reg = f"<{p['address']}, {p['size']}>" if p['size'] else p['address']
        irq = f"    -> nvic@{p['irq']}" if p['irq'] else ""
        
        lines.append(f"{p['label']}: {typename} @ sysbus {reg}")
        if irq:
            lines.append(irq)
        lines.append("")
    
    return '\n'.join(lines)
```

## MCUboot Partition Analysis

```dts
/boot_partition: partition@0 {
    label = "mcuboot";
    reg = <0x00000000 0x00010000>;
};

slot0_partition: partition@10000 {
    label = "image-0";
    reg = <0x00010000 0x00040000>;
};
```

**Renode binary loading:**
```resc
# MCUboot bootloader
sysbus LoadBinary $mcuboot_bin 0x08000000

# Application in slot 0
sysbus LoadBinary $app_bin 0x08010000
```

## Validation Checklist

When extracting from DTS:

1. **Use `zephyr.dts`** (resolved), not source `.dts` files
2. **Check `status`** — "okay" means firmware uses it
3. **Verify with `.config`** — CONFIG_ options confirm feature enablement
4. **Cross-reference labels** — `DT_NODELABEL(x)` in firmware matches `label = "X"` in DTS
5. **Check pin mux** — `pinctrl-*` properties show actual pin assignments
6. **Note clock domains** — Required for correct peripheral frequencies
7. **Extract partition layout** — Critical for MCUboot firmware loading

## Output Format

When providing DTS analysis:

```markdown
## Peripheral Summary from zephyr.dts

### UART
| Label | Address | Size | IRQ | Status |
|-------|---------|------|-----|--------|
| uart0 | 0x40011000 | 0x400 | 37 | okay |

### GPIO
| Label | Address | Size | Status |
|-------|---------|------|--------|
| gpioa | 0x48000000 | 0x400 | okay |
| gpiob | 0x48000400 | 0x400 | okay |

### Memory
| Region | Address | Size |
|--------|---------|------|
| Flash | 0x08000000 | 0x100000 |
| SRAM | 0x20000000 | 0x40000 |

### Partitions
| Name | Address | Size |
|------|---------|------|
| mcuboot | 0x08000000 | 0x10000 |
| image-0 | 0x08010000 | 0x40000 |
```
