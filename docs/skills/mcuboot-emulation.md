# Skill: MCUboot Firmware Emulation in Renode

## Purpose

Configure Renode to emulate firmware using MCUboot, the secure bootloader for 32-bit microcontrollers. This skill covers partition layouts, binary loading, signature verification behavior, and common MCUboot-specific emulation patterns.

## Context

MCUboot is a secure bootloader that provides firmware update capabilities including image signature verification, rollback protection, and multiple slot management. Emulating MCUboot-based firmware requires correct memory layout, binary placement, and understanding of the boot sequence.

## MCUboot Overview

### Boot Sequence

```
Reset → MCUboot (slot 0 or slot 1) → Image Validation → Jump to Application
                                    ↓
                              (if validation fails)
                                    ↓
                              Try alternate slot / Recovery
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Slot** | Flash region containing a firmware image |
| **Image Header** | Metadata at start of each image (magic, size, version) |
| **TLV (Type-Length-Value)** | Trailer with signatures, hashes |
| **Swap Mode** | A/B swap update mechanism |
| **Direct XIP** | Execute in place without swap |
| **Signature Verification** | ECDSA/Ed25519/RSA verification of images |

## Partition Layouts

### Standard Single Slot Layout

```
Flash Memory Map:
┌─────────────────────────────────────┐ 0x00000000
│           MCUboot Bootloader        │ 64KB
├─────────────────────────────────────┤ 0x00010000
│           Primary Slot              │ 256KB
│           (Application Image)       │
├─────────────────────────────────────┤ 0x00050000
│           Secondary Slot            │ 256KB
│           (Update Image)            │
├─────────────────────────────────────┤ 0x00090000
│           Scratch Area              │ (optional)
├─────────────────────────────────────┤
│           Storage / NVS             │
└─────────────────────────────────────┘
```

### Zephyr DTS Partition Definition

```dts
/ {
    soc {
        flash0: flash@8000000 {
            reg = <0x08000000 0x100000>;
            
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
                
                scratch_partition: partition@90000 {
                    label = "image-scratch";
                    reg = <0x00090000 0x00020000>;
                };
            };
        };
    };
};
```

## Binary Loading in Renode

### RESC Script for MCUboot

```resc
:name: MCUboot Firmware Emulation
:description: Loads MCUboot bootloader and signed application

$mcuboot_bin?=@build/mcuboot/zephyr/zephyr.bin
$app_bin?=@build/zephyr/zephyr.signed.bin

using sysbus
mach create "mcuboot_device"
machine LoadPlatformDescription @platforms/cpus/nrf52840.repl

showAnalyzer uart0

# Load bootloader at flash base
sysbus LoadBinary $mcuboot_bin 0x00000000

# Load signed application in primary slot
sysbus LoadBinary $app_bin 0x00010000

macro reset
"""
    sysbus LoadBinary $mcuboot_bin 0x00000000
    sysbus LoadBinary $app_bin 0x00010000
"""

runMacro $reset
```

### ELF Loading (Preferred When Available)

```resc
# If bootloader ELF is available (contains debug symbols)
sysbus LoadELF $mcuboot_elf

# Application must still be raw binary at correct offset
sysbus LoadBinary $app_signed_bin 0x00010000
```

### Address Calculation

From DTS partition table:
```python
# Flash base address
flash_base = 0x08000000

# Partition offsets (from DTS)
mcuboot_offset = 0x00000000
slot0_offset = 0x00010000
slot1_offset = 0x00050000

# Renode load addresses
mcuboot_load_addr = flash_base + mcuboot_offset  # 0x08000000
slot0_load_addr = flash_base + slot0_offset      # 0x08010000
slot1_load_addr = flash_base + slot1_offset      # 0x08050000
```

## MCUboot Image Format

### Image Header Structure

```c
struct image_header {
    uint32_t ih_magic;      /* Image magic: 0x96f3b83c */
    uint32_t ih_load_addr;  /* Load address */
    uint16_t ih_hdr_size;   /* Header size */
    uint16_t ih_pad1;
    uint32_t ih_img_size;   /* Image size (without header) */
    uint32_t ih_flags;      /* Image flags */
    uint16_t ih_ver_major;  /* Version: major */
    uint16_t ih_ver_minor;  /* Version: minor */
    uint16_t ih_ver_rev;    /* Version: revision */
    uint16_t ih_ver_build;  /* Version: build */
    uint32_t ih_pad2;
};
/* Total: 32 bytes */
```

### Image Trailer

```
┌─────────────────────────────────────┐
│           Application Code          │
├─────────────────────────────────────┤
│           Padding                   │
├─────────────────────────────────────┤
│           TLV Area                  │
│  ┌─────────────────────────────┐    │
│  │ SHA256 Hash (32 bytes)      │    │
│  ├─────────────────────────────┤    │
│  │ Signature (64-256 bytes)    │    │
│  └─────────────────────────────┘    │
├─────────────────────────────────────┤
│           Swap Status               │
│           (for A/B updates)         │
└─────────────────────────────────────┘
```

## Signature Verification in Emulation

### Verification Behavior

MCUboot verifies image signatures at boot. In emulation:

1. **Real signature**: MCUboot validates against embedded public key
2. **Emulation choice**: Can either:
   - Use properly signed images (full verification)
   - Disable signature verification in MCUboot config
   - Stub verification in peripheral model (for testing)

### Building MCUboot Without Signature Check

For emulation testing, build MCUboot with verification disabled:

```conf
# prj.conf for MCUboot
CONFIG_BOOT_SIGNATURE_TYPE_NONE=y
CONFIG_BOOT_VALIDATE_SLOT0=n
```

### Console Markers for Boot Sequence

```resc
# Expected UART output for successful MCUboot boot
# "*** Booting Zephyr OS build xxx ***"    ← Zephyr boot (from MCUboot)
# "I: Starting bootloader"                  ← MCUboot start
# "I: Primary image: magic=good, swap_type=0x3, copy_done=0x1"  ← Image check
# "I: Jumping to the first image slot"     ← Handoff
# "*** Booting Zephyr OS build xxx ***"    ← Application boot
# "uart:~$"                                 ← Shell prompt
```

## Flash Persistence Patterns

### The Flash Persistence Problem

In Renode, the `reset` macro typically reloads binaries:

```resc
# PROBLEM: This overwrites flash changes on every reset
macro reset
"""
    sysbus LoadBinary $mcuboot_bin 0x00000000
    sysbus LoadBinary $app_bin 0x00010000
"""
```

For MCUboot testing (swap updates, persistent state), this is wrong.

### Solution 1: Snapshot Pattern

```resc
macro reset
"""
    # Load only once at first boot
    sysbus LoadBinary $mcuboot_bin 0x00000000
    sysbus LoadBinary $app_bin 0x00010000
    sysbus Save initial_state
"""

# After first boot, use snapshot for reset
macro soft_reset
"""
    sysbus Load initial_state
"""
```

### Solution 2: Flash Model with Persistence

In the flash peripheral C# model:

```csharp
public class MCUFlash : BasicDoubleWordPeripheral, IKnownSize
{
    private readonly byte[] flashStorage;
    
    public MCUFlash(IMachine machine, long size) : base(machine)
    {
        flashStorage = new byte[size];
        // ... register definitions ...
    }
    
    public override void Reset()
    {
        // DON'T clear flashStorage on reset!
        // Only reset peripheral registers
        base.Reset();
        RegistersCollection.Reset();
    }
    
    // Write persists flashStorage array
}
```

### Solution 3: Initial Load Only

```resc
# Load binaries OUTSIDE the reset macro
sysbus LoadBinary $mcuboot_bin 0x00000000
sysbus LoadBinary $app_bin 0x00010000

# Reset only resets CPU and peripherals, not flash
macro reset
"""
    cpu PC 0x08000000
    cpu SetRegister "SP" `sysbus ReadWord 0x08000000`
    # Reset peripherals but not flash
"""
```

## Common MCUboot Emulation Issues

### Issue 1: Boot Hangs at "Starting bootloader"

**Cause:** Flash not loaded correctly or wrong address.

**Fix:**
```resc
# Verify bootloader is at correct address
sysbus ReadWord 0x08000000   # Should be valid stack pointer
sysbus ReadWord 0x08000004   # Should be valid reset handler

# Check vector table
cpu PC `sysbus ReadDoubleWord 0x08000004`
```

### Issue 2: "Image verification failed"

**Cause:** Signature mismatch or missing public key.

**Fix:**
- Use unsigned MCUboot build (`CONFIG_BOOT_SIGNATURE_TYPE_NONE=y`)
- Or ensure correct signing key was used:
```bash
# Sign the image with correct key
imgtool sign --key signing_key.pem --pad \
    --align 4 --version 1.0.0 \
    --header-size 0x200 --slot-size 0x40000 \
    build/zephyr/zephyr.bin \
    build/zephyr/zephyr.signed.bin
```

### Issue 3: Flash Overwritten on Reset

**Cause:** Reset macro reloads binaries.

**Fix:** Use snapshot pattern or move binary loading outside reset macro.

### Issue 4: Swap Update Testing

For A/B swap update testing:

```resc
# Load both slots
sysbus LoadBinary $mcuboot_bin 0x00000000
sysbus LoadBinary $app_v1_bin 0x00010000    # Slot 0: v1
sysbus LoadBinary $app_v2_bin 0x00050000    # Slot 1: v2 (update)

# MCUboot will swap on boot if configured for swap mode
# After swap, slot 0 contains v2, slot 1 contains v1
```

## Robot Test Patterns for MCUboot

### Basic MCUboot Boot Test

```robot
*** Settings ***
Resource    renode_keywords.robot

*** Variables ***
${MCUBOOT_BIN}    @build/mcuboot/zephyr/zephyr.bin
${APP_BIN}        @build/zephyr/zephyr.signed.bin

*** Test Cases ***
MCUboot Boots Application
    Create Machine    nrf52840.repl
    Execute Command    sysbus LoadBinary ${MCUBOOT_BIN} 0x00000000
    Execute Command    sysbus LoadBinary ${APP_BIN} 0x00010000
    
    Create Log Tester    30
    Start Emulation
    
    Wait For Line On Uart    Starting bootloader
    Wait For Line On Uart    Jumping to the first image slot
    Wait For Line On Uart    Booting Zephyr OS
    Wait For Line On Uart    uart:~$
```

### MCUboot Version Check Test

```robot
Verify Application Version
    Create Machine    nrf52840.repl
    Execute Command    sysbus LoadBinary ${MCUBOOT_BIN} 0x00000000
    Execute Command    sysbus LoadBinary ${APP_BIN} 0x00010000
    
    Create Log Tester    30
    Start Emulation
    
    Wait For Line On Uart    regexp=.*version 1\\.0\\.0.*
```

### Firmware Update Test

```robot
Firmware Update Swap
    Create Machine    nrf52840.repl
    Execute Command    sysbus LoadBinary ${MCUBOOT_BIN} 0x00000000
    Execute Command    sysbus LoadBinary ${APP_V1_BIN} 0x00010000
    Execute Command    sysbus LoadBinary ${APP_V2_BIN} 0x00050000
    
    Create Log Tester    60
    Start Emulation
    
    # First boot - should run v1, detect v2, and swap
    Wait For Line On Uart    Swap type: test
    Wait For Line On Uart    regexp=.*version 1\\.0\\.0.*
    
    # Reset to complete swap
    Execute Command    machine Reset
    Wait For Line On Uart    regexp=.*version 2\\.0\\.0.*
```

## MCUboot Configuration Analysis

### Key Kconfig Options

```ini
# From .config
CONFIG_BOOTLOADER_MCUBOOT=y          # MCUboot enabled
CONFIG_BOOT_SIGNATURE_TYPE_ECDSA256=y # Signature type
CONFIG_BOOT_VALIDATE_SLOT0=y         # Validate primary slot
CONFIG_BOOT_UPGRADE_ONLY=n           # Allow rollback
CONFIG_BOOT_SWAP_USING_MOVE=n        # Swap mode
CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION="1.0.0"  # Version
```

### Determining Slot Layout

```bash
# Extract from zephyr.dts
grep -A2 "slot0_partition\|slot1_partition" build/zephyr/zephyr.dts

# From .config (if using fixed sizes)
grep "CONFIG_FLASH_BASE_ADDRESS\|CONFIG_FLASH_SIZE" build/zephyr/.config
```

## Debugging MCUboot in Renode

### Enable MCUboot Logging

```resc
# MCUboot uses Zephyr logging
logLevel 4

# Or in DTS, ensure logging is enabled:
# CONFIG_LOG=y
# CONFIG_LOG_BACKEND_UART=y
```

### Check Flash Contents

```resc
# Read image header magic at slot 0
sysbus ReadDoubleWord 0x08010000
# Should return 0x96f3b83c (MCUboot magic)

# Read image version (offset 0x14 in header)
sysbus ReadHalfWord 0x08010014   # Major
sysbus ReadHalfWord 0x08010016   # Minor
```

### Step Through MCUboot

```resc
# Set breakpoint at MCUboot entry
cpu ExecutionBlockedAtAddress `sysbus GetSymbolAddress "main"`

# Or use GDB
machine StartGdbServer 3333
# Connect with: arm-none-eabi-gdb -ex "target remote :3333"
```

## Summary Table

| Task | RESC Command |
|------|-------------|
| Load bootloader | `sysbus LoadBinary $mcuboot 0x08000000` |
| Load app in slot 0 | `sysbus LoadBinary $app 0x08010000` |
| Load app in slot 1 | `sysbus LoadBinary $app 0x08050000` |
| Check image magic | `sysbus ReadDoubleWord 0x08010000` |
| Save state | `sysbus Save mcuboot_state` |
| Restore state | `sysbus Load mcuboot_state` |
| Soft reset (no flash reload) | `cpu PC 0x08000000` |

## Output Format

When generating MCUboot emulation setup:

```markdown
## MCUboot Emulation Configuration

### Partition Layout
| Partition | Address | Size | Content |
|-----------|---------|------|---------|
| MCUboot | 0x08000000 | 64KB | Bootloader |
| Slot 0 | 0x08010000 | 256KB | Application v1.0 |
| Slot 1 | 0x08050000 | 256KB | (empty/update) |

### Binary Files
- Bootloader: `build/mcuboot/zephyr/zephyr.bin`
- Application: `build/zephyr/zephyr.signed.bin`

### Console Markers (Golden Path)
1. "Starting bootloader"
2. "Primary image: magic=good"
3. "Jumping to the first image slot"
4. "Booting Zephyr OS"
5. "uart:~$"
```
