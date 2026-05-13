# Skill: Renode Debugging and Troubleshooting

## Purpose

Diagnose and fix common emulation failures in Renode. This skill provides systematic approaches to identify root causes from log output, peripheral access traces, and runtime behavior, along with concrete fixes for each failure pattern.

## Context

Renode emulation failures often manifest as boot hangs, unexpected peripheral behavior, or test assertion failures. The diagnostic process relies on Renode's logging infrastructure, peripheral access tracing, and monitor commands. Understanding the failure taxonomy enables faster iteration during bring-up.

## Diagnostic Tools

### Log Levels

```resc
logLevel 3                           # Global: 0=Silent, 1=Error, 2=Warning, 3=Info, 4=Debug, 5=Noisy
logLevel -1 sysbus.uart0            # Per-peripheral: -1 inherits global
```

### Peripheral Access Logging

```resc
# Enable access logging for specific peripheral
sysbus LogPeripheralAccess uart0 true

# Enable for all peripherals (verbose)
sysbus LogAllPeripheralsAccess true

# In Robot tests
Execute Command  sysbus LogPeripheralAccess uart0 true
```

### Monitor Commands

```resc
# Check CPU state
cpu IsHalted

# Read memory directly
sysbus ReadWord 0x20000000
sysbus ReadDoubleWord 0x40011000

# Check peripheral properties
sysbus.uart0 BaudRate

# List all peripherals
sysbus What

# Get CPU registers
cpu PC
cpu GetRegister "SP"
```

### Snapshot Debugging

```resc
# Save state at known point
sysbus Save snapshot_m2

# Restore for faster iteration
sysbus Load snapshot_m2

# In Robot tests
Execute Command  sysbus Save snapshot_before_issue
```

## Failure Taxonomy

### 1. Unmapped Access

**Symptom:**
```
[WARNING] sysbus: Unmapped access to 0x40023800 (length 4) at PC=0x08001234
```

**Root Cause:** Peripheral not defined in `.repl` file or registered at wrong address.

**Diagnosis:**
1. Note the address from the warning (e.g., `0x40023800`)
2. Cross-reference with MCU reference manual to identify peripheral
3. Check `.repl` file for missing registration

**Fix:**

```repl
# Add peripheral registration (even as stub if not fully modeled)
sysbus:
    init:
        Tag <0x40023800, 0x400> "RCC"

# Or full peripheral
rcc: Miscellaneous.StM32RCC @ sysbus <0x40023800, +0x400>
```

**Verification:**
```resc
# Run again and check for unmapped access warnings
sysbus LogAllPeripheralsAccess true
```

---

### 2. CPU Halted / Stuck in Loop

**Symptom:**
- No UART output
- CPU reports `IsHalted true`
- Repeated reads to same address

**Root Cause:** Driver waiting on peripheral status bit that never changes.

**Diagnosis:**
```resc
# Check if CPU is actually halted
cpu IsHalted

# If not halted, check what it's doing
sysbus LogPeripheralAccess my_peripheral true
emulation RunFor "0.1"

# Check PC to see where code is stuck
cpu PC
```

**Fix:**

The peripheral model needs to return correct status values. Common patterns:

```csharp
// STATUS register must indicate "ready" or "not busy"
Registers.Status.Define(this)
    .WithFlag(0, FieldMode.Read, name: "READY",
        valueProviderCallback: _ => true)  // Always ready in emulation
    .WithFlag(1, FieldMode.Read, name: "BUSY",
        valueProviderCallback: _ => false);  // Never busy
```

---

### 3. Missing Interrupt

**Symptom:**
- Driver waiting for interrupt that never fires
- Code stuck in `WFI` (Wait For Interrupt) loop

**Root Cause:** Peripheral raises interrupt but IRQ line not wired, or IRQ number incorrect.

**Diagnosis:**
```resc
# Check interrupt controller state
sysbus.nvic GetState

# Manually trigger interrupt to verify wiring
sysbus.my_peripheral IRQ Set true
```

**Fix:**

Check `.repl` IRQ wiring:
```repl
# Verify IRQ connection
uart0: UART.STM32_UART @ sysbus <0x40011000, +0x400>
    -> nvic@37                    # Must match datasheet IRQ number
```

Check C# model triggers IRQ:
```csharp
private void OnDataReceived()
{
    rxNotEmpty.Value = true;
    rxInterruptPending.Value = true;  // Set pending flag
    UpdateInterrupts();                // Trigger IRQ line
}

private void UpdateInterrupts()
{
    var pending = rxInterruptEnabled.Value && rxInterruptPending.Value;
    IRQ.Set(pending);
}
```

---

### 4. Wrong Register Value

**Symptom:**
```
[WARNING] uart0: Unexpected value written to register
```
Or firmware behaves incorrectly after reading peripheral.

**Root Cause:** Register reset value doesn't match hardware, or field at wrong bit position.

**Diagnosis:**
```resc
# Read register directly
sysbus.ReadDoubleWord 0x40011000

# Compare with datasheet reset value
```

**Fix:**

Verify reset values match datasheet:
```csharp
// In Reset() method, set correct defaults
public override void Reset()
{
    base.Reset();
    controlRegister.Value = 0x00000000;  // Match datasheet
    baudRateRegister.Value = 0x00003412; // Default baud rate
}
```

Use register field `valueProviderCallback` for dynamic values:
```csharp
.WithValueField(0, 16, FieldMode.Read, name: "CLOCK_FREQ",
    valueProviderCallback: _ => currentClockFrequency)
```

---

### 5. Flash Persistence Issue (MCUboot)

**Symptom:**
- Firmware boots correctly first time
- Subsequent resets show corrupted flash
- MCUboot fails validation after first boot

**Root Cause:** The `reset` macro re-loads the binary, overwriting flash changes. Or flash peripheral doesn't persist writes across reset.

**Diagnosis:**
```resc
# Check if flash is being reloaded
# Look for LoadELF or LoadBinary in reset macro
```

**Fix:**

```resc
# For MCUboot, don't reload the entire binary on reset
# Instead, save/restore flash state

macro reset
"""
    # Only load binary once, use snapshot for subsequent resets
    sysbus LoadELF $mcuboot_bin
    sysbus LoadBinary $app_bin 0x00020000
    sysbus Save clean_boot_state
"""

# After boot, for testing reset scenarios:
sysbus Load clean_boot_state
```

In C# flash model:
```csharp
public override void Reset()
{
    // DON'T clear flash contents on reset
    // Only reset peripheral registers, not the storage array
    base.Reset();
    // flashStorage remains intact
}
```

---

### 6. Timing / Timeout Too Short

**Symptom:**
```
[ERROR] Robot test failed: Timeout waiting for line "uart:~$"
```

**Root Cause:** Robot test timeout shorter than actual boot time, or virtual time not advancing correctly.

**Diagnosis:**
```resc
# Check how much virtual time elapsed
emulation RunFor "10"

# In Robot test, add timing
Execute Command  emulation RunFor "5"
```

**Fix:**

Increase Robot test timeout:
```robot
Wait For Line On Uart    uart:~$    timeout=30    # Virtual seconds
```

Ensure emulation is running:
```robot
Start Emulation
# Not just: Execute Command  start
```

---

### 7. Binary Load Address Wrong

**Symptom:**
- CPU executes garbage or immediately faults
- PC at unexpected location after boot

**Root Cause:** Binary loaded at wrong address, or using wrong load command.

**Diagnosis:**
```resc
# Check PC after boot
cpu PC

# Verify binary is at correct address
sysbus ReadWord 0x08000000
```

**Fix:**

Use correct load command for binary type:
```resc
# ELF (preferred - contains addresses)
sysbus LoadELF $bin

# Intel HEX (addresses embedded)
sysbus LoadHEX $bin

# Raw binary (MUST specify address)
sysbus LoadBinary $bin 0x08000000
```

Verify vector table location:
```resc
# ARM Cortex-M: Vector table at start of flash
# First word = stack pointer, second word = reset handler
sysbus ReadWord 0x08000000   # Should be valid SRAM address
sysbus ReadWord 0x08000004   # Should be valid code address

cpu PC `sysbus ReadDoubleWord 0x08000004`
```

---

### 8. SVD Not Applied

**Symptom:**
- Logs show numeric addresses instead of register names
- Hard to debug which register is being accessed

**Root Cause:** SVD file not loaded or incorrect SVD.

**Fix:**
```repl
sysbus:
    init:
        ApplySVD @https://dl.antmicro.com/projects/renode/svd/STM32F4xx.svd
```

Or in RESC:
```resc
sysbus ApplySVD $svd_file
```

---

### 9. Endianness Issues

**Symptom:**
- Garbage data in UART or sensor readings
- Values shifted or byte-swapped

**Root Cause:** Multi-byte registers read in wrong order, or sensor data not properly formatted.

**Fix:**

```csharp
// For 16-bit values split across two 8-bit registers
private ushort GetSensorValue()
{
    return (ushort)((regs[Register.DataHigh] << 8) | regs[Register.DataLow]);
}

// For left-justified values (e.g., 10-bit in 16-bit register)
private int GetLeftJustifiedValue()
{
    // Datasheet: 10-bit value left-justified in bits [15:6]
    return (int)(rawValue >> 6);
}
```

---

### 10. Renode C# Compilation Failure

**Symptom:**
```
[ERROR] Failed to compile peripheral: CS0103: The name 'GPIO' does not exist
```

**Root Cause:** Missing `using` directive or wrong namespace.

**Fix:**

Add required namespaces:
```csharp
using Antmicro.Renode.Core;                      // GPIO, IMachine
using Antmicro.Renode.Core.Structure.Registers;  // Register framework
using Antmicro.Renode.Logging;                   // this.Log()
using Antmicro.Renode.Peripherals.Bus;           // IDoubleWordPeripheral
using Antmicro.Renode.Time;                      // LimitTimer
```

---

## Robot Test Debugging

### Debugging Test Failures

```robot
*** Settings ***
Resource    renode_keywords.robot

*** Test Cases ***
Debug Boot
    Create Machine    stm32f4.repl
    Execute Command    sysbus LogAllPeripheralsAccess true
    Execute Command    sysbus LoadELF $bin
    
    # Add debug output
    Create Log Tester    10
    Start Emulation
    
    # Check what happened
    ${output}=    Read From Uart    timeout=5
    Log    UART output: ${output}
    
    # Check CPU state
    ${halted}=    Execute Command    cpu IsHalted    pause_on_failure=true
    Log    CPU halted: ${halted}
```

### Stepping Through Code

```robot
# Single-step execution
Execute Command    cpu Step
${pc}=    Execute Command    cpu PC
Log    PC is at ${pc}

# Run until specific address
Execute Command    cpu ExecutionBlockedAtAddress 0x08001234
Start Emulation
```

---

## Systematic Debugging Workflow

1. **Enable logging** — `logLevel 4` and peripheral access logging
2. **Check CPU state** — `cpu IsHalted`, `cpu PC`
3. **Look for unmapped accesses** — Search logs for `WARNING` and `Unmapped`
4. **Verify peripheral registration** — `sysbus What` to list all peripherals
5. **Check IRQ wiring** — `sysbus.nvic GetState`
6. **Compare with datasheet** — Verify addresses, reset values, IRQ numbers
7. **Isolate the issue** — Create minimal test case
8. **Use snapshots** — Save state before issue to iterate faster

---

## Common Quick Fixes

| Symptom | Quick Fix |
|---------|-----------|
| No UART output | Add `showAnalyzer uart0` |
| Boot hangs | Check `READY`/`BUSY` status flags return correct values |
| Unmapped access | Add `Tag` stub or peripheral registration |
| Test timeout | Increase `timeout=` in Robot test |
| Wrong register value | Verify reset value matches datasheet |
| Interrupt not firing | Check `-> nvic@N` wiring and `IRQ.Set()` call |

---

## Output Format

When diagnosing an issue, provide:

1. **Classification** — Which failure pattern from the taxonomy
2. **Evidence** — Relevant log lines or monitor command output
3. **Root cause** — Specific register, address, or wiring issue
4. **Fix** — Concrete code or RESC/REPL changes
5. **Verification** — Commands to run to confirm the fix
