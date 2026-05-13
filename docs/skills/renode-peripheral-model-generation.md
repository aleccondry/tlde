# Skill: Renode Peripheral Model Generation (C# Infrastructure)

## Purpose

Generate C# peripheral models for the Renode emulation framework. These models implement hardware peripheral behavior at register level, enabling accurate firmware emulation without real hardware. Models are built on the `renode-infrastructure` framework using the Register Framework fluent API.

## Context

Renode peripheral models are C# classes in the `Antmicro.Renode.Peripherals` namespace. They implement bus access interfaces, define register layouts with bit-level precision, handle interrupts via GPIO signals, and model peripheral-specific logic (FIFOs, timers, state machines). The Register Framework provides a declarative, fluent API for defining registers and their fields.

For simpler peripherals or rapid prototyping, Renode also supports Python peripherals defined directly in REPL files:

```repl
myPeripheral: PythonPeripheral @ sysbus 0x1000
    init: |
        def read(offset, size):
            return 0
        def write(offset, value, size):
            pass
```

Python peripherals are useful for trivial logic but C# models are required for advanced peripheral behavior and interconnect.

## Architecture Overview

```
IPeripheral (Reset)
    ├── IBytePeripheral (8-bit bus access)
    ├── IWordPeripheral (16-bit bus access)
    ├── IDoubleWordPeripheral (32-bit bus access)  ← Most common
    └── IQuadWordPeripheral (64-bit bus access)

BasicDoubleWordPeripheral (abstract base class)
    ├── Provides RegistersCollection
    ├── Implements Read/Write dispatching
    └── Implements Reset pattern

UARTBase (abstract base for UARTs)
    ├── Character queue management
    ├── TransmitCharacter() / TryGetCharacter()
    └── CharWritten() / QueueEmptied() callbacks
```

## Required Namespaces

```csharp
using System;
using System.Collections.Generic;
using Antmicro.Renode.Core;                          // IMachine, GPIO
using Antmicro.Renode.Core.Structure.Registers;      // Register framework
using Antmicro.Renode.Logging;                       // this.Log()
using Antmicro.Renode.Peripherals.Bus;               // IDoubleWordPeripheral, IKnownSize
using Antmicro.Renode.Utilities;                     // BitHelper
using Antmicro.Renode.Time;                          // ClockEntry, LimitTimer
using Antmicro.Renode.Exceptions;                    // ConstructionException
```

## Core Interfaces

### Bus Access Interfaces

| Interface | Width | Methods |
|-----------|-------|---------|
| `IBytePeripheral` | 8-bit | `ReadByte(long)` / `WriteByte(long, byte)` |
| `IWordPeripheral` | 16-bit | `ReadWord(long)` / `WriteWord(long, ushort)` |
| `IDoubleWordPeripheral` | 32-bit | `ReadDoubleWord(long)` / `WriteDoubleWord(long, uint)` |
| `IQuadWordPeripheral` | 64-bit | `ReadQuadWord(long)` / `WriteQuadWord(long, ulong)` |

### Key Additional Interfaces

| Interface | Purpose |
|-----------|---------|
| `IKnownSize` | Declares peripheral size on bus (`long Size { get; }`) |
| `IProvidesRegisterCollection<T>` | Exposes register collection for framework |
| `IGPIOReceiver` | Can receive GPIO/interrupt signals |
| `INumberedGPIOOutput` | Provides numbered GPIO outputs |
| `IIRQController` | Interrupt controller interface |
| `II2CPeripheral` | I2C slave device |
| `ISPIPeripheral` | SPI slave device |
| `IUART` | UART interface |

### AllowedTranslations Attribute

Placed on class to allow bus width translation (e.g., byte access to double-word peripheral):

```csharp
[AllowedTranslations(AllowedTranslation.ByteToDoubleWord)]
[AllowedTranslations(AllowedTranslation.ByteToDoubleWord | AllowedTranslation.WordToDoubleWord)]
```

Note: Automatic translation might generate more accesses on the bus (e.g., 4 byte reads per one double word read). This might have unintended side effects for some registers (e.g., automatically incrementing FIFO data register, read-to-clear behavior). Verify that automatic translation is safe for your peripheral.

## Memory Types Performance Note

When defining memory in REPL files, prefer `Memory.MappedMemory` over `Memory.ArrayMemory` for performance reasons. `MappedMemory` handles operations at the C level, while `ArrayMemory` processes everything at C# level, which can cause significant performance degradation. Only use `ArrayMemory` when you need to intercept all memory operations at C# level.

## Register Framework

### Register Definition (Fluent API)

Registers are defined using a private enum and the fluent builder pattern:

```csharp
private enum Registers : long
{
    Control = 0x00,
    Status = 0x04,
    Data = 0x08,
    InterruptStatus = 0x0C,
    InterruptEnable = 0x10,
}
```

### Field Types

#### 1. Flag Fields (Single Bit)

```csharp
// Basic flag
.WithFlag(0, name: "ENABLE")

// With out reference (for programmatic access)
.WithFlag(0, out enableFlag, name: "ENABLE")

// With access mode
.WithFlag(0, out irqPending, FieldMode.Read | FieldMode.WriteOneToClear, name: "IRQ_PENDING")

// With callback on write
.WithFlag(0, out txEnable, name: "TX_EN",
    writeCallback: (_, val) => { if(val) StartTransmission(); })

// With callback on change
.WithFlag(0, out enableFlag, name: "ENABLE",
    changeCallback: (_, __) => UpdateInterrupts())

// With value provider (dynamic read value)
.WithFlag(0, FieldMode.Read, name: "BUSY",
    valueProviderCallback: _ => isBusy)
```

#### 2. Value Fields (Multi-Bit Numeric)

```csharp
// Basic value field
.WithValueField(0, 8, name: "DATA")

// With out reference
.WithValueField(0, 16, out baudRateDiv, name: "BAUD_DIV")

// With write callback (e.g., UART TX data)
.WithValueField(0, 8, name: "TX_DATA",
    writeCallback: (_, value) => TransmitCharacter((byte)value),
    valueProviderCallback: _ => ReadFromFifo())

// Read-only value
.WithValueField(0, 8, FieldMode.Read, name: "RX_DATA",
    valueProviderCallback: _ => GetReceivedByte())
```

#### 3. Enum Fields

```csharp
// Enum field
.WithEnumField<DoubleWordRegister, ClockSource>(4, 2, out clockSource, name: "CLK_SRC")

// Multiple enum fields (e.g., pin modes)
.WithEnumFields<DoubleWordRegister, PinMode>(0, 2, 16, out pinModes, name: "PIN_MODE")
```

#### 4. Reserved/Tagged Fields

```csharp
// Reserved bits (unused, logged as warning if written non-zero)
.WithReservedBits(8, 24)

// Tagged flag (placeholder - read/write but no logic)
.WithTaggedFlag("FEATURE_NOT_IMPLEMENTED", 5)

// Tagged value (placeholder)
.WithTag("UNIMPLEMENTED_FIELD", 16, 8)
```

### Register-Level Callbacks

```csharp
// Callback after any write to the register
.WithWriteCallback((_, __) => UpdateInterrupts())

// Callback after any read from the register
.WithReadCallback((_, __) => ClearStatus())
```

### FieldMode Flags

| Mode | Description |
|------|-------------|
| `Read` | Readable |
| `Write` | Writable |
| `Set` | Write-1-to-set |
| `Toggle` | Write-1-to-toggle |
| `WriteOneToClear` | Write-1-to-clear (W1C) — standard for IRQ flags |
| `WriteZeroToClear` | Write-0-to-clear |
| `ReadToClear` | Read clears value |

Common combinations:
- `FieldMode.Read | FieldMode.Write` — Standard R/W
- `FieldMode.Read | FieldMode.WriteOneToClear` — Interrupt status register
- `FieldMode.Read` — Read-only status
- `FieldMode.Write` — Write-only command

### DefineMany (Repeated Register Groups)

```csharp
// Define 4 consecutive 8-bit sub-registers forming a 32-bit value
Registers.Load0.DefineMany(this, 4, (reg, idx) =>
{
    reg.WithValueField(0, 8, name: $"LOAD{idx}",
        writeCallback: (_, val) =>
        {
            BitHelper.ReplaceBits(ref loadValue, width: 8,
                source: (uint)val, destinationPosition: 24 - idx * 8);
        });
});
```

## GPIO and Interrupt Handling

### Declaring GPIOs

```csharp
// Single interrupt output
public GPIO IRQ { get; } = new GPIO();

// Multiple named outputs
public GPIO TxIRQ { get; } = new GPIO();
public GPIO RxIRQ { get; } = new GPIO();

// Numbered GPIO outputs (for DMA, multi-channel)
public IReadOnlyDictionary<int, IGPIO> Connections { get; }
```

### Standard Interrupt Pattern

```csharp
private void UpdateInterrupts()
{
    var shouldInterrupt = (txInterruptEnabled.Value && txInterruptPending.Value)
                       || (rxInterruptEnabled.Value && rxInterruptPending.Value)
                       || (errorEnabled.Value && errorPending.Value);
    IRQ.Set(shouldInterrupt);
}
```

### Triggering Interrupts

```csharp
private void OnDataReceived()
{
    rxInterruptPending.Value = true;
    UpdateInterrupts();
}
```

## Timer Integration

### Using LimitTimer

```csharp
private readonly LimitTimer timer;

public MyTimer(IMachine machine, long frequency) : base(machine)
{
    timer = new LimitTimer(
        machine.ClockSource,
        frequency,
        this,
        nameof(timer),
        limit: 0xFFFFFFFF,
        direction: Direction.Descending,
        enabled: false,
        eventEnabled: true,
        autoUpdate: true
    );

    timer.LimitReached += () =>
    {
        irqPending.Value = true;
        UpdateInterrupts();
    };
}

public override void Reset()
{
    base.Reset();
    timer.Reset();
}
```

### Using ClockSource Directly

```csharp
machine.ClockSource.AddClockEntry(new ClockEntry(
    period: ticksPerFlush,
    ratio: (long)TimeInterval.TicksPerSecond,
    handler: FlushBuffer,
    owner: this,
    localName: "UART flush",
    enabled: false
));
```

## Complete Peripheral Templates

### Template 1: Basic Register Peripheral (Generic)

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public class MyPeripheral : BasicDoubleWordPeripheral, IKnownSize
    {
        public MyPeripheral(IMachine machine) : base(machine)
        {
            IRQ = new GPIO();
            DefineRegisters();
        }

        public override void Reset()
        {
            base.Reset();
            UpdateInterrupts();
        }

        public GPIO IRQ { get; }
        public long Size => 0x100;

        private void DefineRegisters()
        {
            Registers.Control.Define(this)
                .WithFlag(0, out enableFlag, name: "ENABLE")
                .WithReservedBits(1, 31);

            Registers.Status.Define(this)
                .WithFlag(0, FieldMode.Read, name: "READY",
                    valueProviderCallback: _ => true)
                .WithReservedBits(1, 31);

            Registers.InterruptStatus.Define(this)
                .WithFlag(0, out irqPending,
                    FieldMode.Read | FieldMode.WriteOneToClear, name: "IRQ",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(1, 31);

            Registers.InterruptEnable.Define(this)
                .WithFlag(0, out irqEnabled, name: "IRQ_EN",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(1, 31);
        }

        private void UpdateInterrupts()
        {
            IRQ.Set(irqEnabled.Value && irqPending.Value);
        }

        private IFlagRegisterField enableFlag;
        private IFlagRegisterField irqPending;
        private IFlagRegisterField irqEnabled;

        private enum Registers : long
        {
            Control = 0x00,
            Status = 0x04,
            InterruptStatus = 0x08,
            InterruptEnable = 0x0C,
        }
    }
}
```

### Template 2: UART Peripheral

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using System.Collections.Generic;
using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;

namespace Antmicro.Renode.Peripherals.UART
{
    public class MyVendor_UART : UARTBase, IDoubleWordPeripheral, IKnownSize,
        IProvidesRegisterCollection<DoubleWordRegisterCollection>
    {
        public MyVendor_UART(IMachine machine) : base(machine)
        {
            IRQ = new GPIO();
            RegistersCollection = new DoubleWordRegisterCollection(this);
            DefineRegisters();
        }

        public uint ReadDoubleWord(long offset)
        {
            return RegistersCollection.Read(offset);
        }

        public void WriteDoubleWord(long offset, uint value)
        {
            RegistersCollection.Write(offset, value);
        }

        public override void Reset()
        {
            base.Reset();
            RegistersCollection.Reset();
            UpdateInterrupts();
        }

        public GPIO IRQ { get; }
        public long Size => 0x400;
        public DoubleWordRegisterCollection RegistersCollection { get; }

        public override Bits StopBits => Bits.One;
        public override Parity ParityBit => Parity.None;
        public override uint BaudRate => 115200;

        protected override void CharWritten()
        {
            rxNotEmpty.Value = true;
            UpdateInterrupts();
        }

        protected override void QueueEmptied()
        {
            rxNotEmpty.Value = false;
            UpdateInterrupts();
        }

        private void DefineRegisters()
        {
            Registers.Data.Define(this)
                .WithValueField(0, 8, name: "DATA",
                    writeCallback: (_, value) => TransmitCharacter((byte)value),
                    valueProviderCallback: _ =>
                    {
                        if(!TryGetCharacter(out var c))
                        {
                            this.Log(LogLevel.Warning, "Reading from empty RX FIFO");
                        }
                        return c;
                    })
                .WithReservedBits(8, 24);

            Registers.Status.Define(this)
                .WithFlag(0, FieldMode.Read, name: "TX_EMPTY",
                    valueProviderCallback: _ => true)
                .WithFlag(1, out rxNotEmpty, FieldMode.Read, name: "RX_NOT_EMPTY")
                .WithReservedBits(2, 30);

            Registers.Control.Define(this)
                .WithFlag(0, out txEnabled, name: "TX_EN")
                .WithFlag(1, out rxEnabled, name: "RX_EN")
                .WithReservedBits(2, 30);

            Registers.InterruptStatus.Define(this)
                .WithFlag(0, out txInterruptPending,
                    FieldMode.Read | FieldMode.WriteOneToClear, name: "TX_INT",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithFlag(1, out rxInterruptPending,
                    FieldMode.Read | FieldMode.WriteOneToClear, name: "RX_INT",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(2, 30);

            Registers.InterruptEnable.Define(this)
                .WithFlag(0, out txInterruptEnabled, name: "TX_INT_EN",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithFlag(1, out rxInterruptEnabled, name: "RX_INT_EN",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(2, 30);
        }

        private void UpdateInterrupts()
        {
            var pending = (txInterruptEnabled.Value && txInterruptPending.Value)
                       || (rxInterruptEnabled.Value && rxInterruptPending.Value);
            IRQ.Set(pending);
        }

        private IFlagRegisterField txEnabled;
        private IFlagRegisterField rxEnabled;
        private IFlagRegisterField rxNotEmpty;
        private IFlagRegisterField txInterruptPending;
        private IFlagRegisterField rxInterruptPending;
        private IFlagRegisterField txInterruptEnabled;
        private IFlagRegisterField rxInterruptEnabled;

        private enum Registers : long
        {
            Data = 0x00,
            Status = 0x04,
            Control = 0x08,
            InterruptStatus = 0x0C,
            InterruptEnable = 0x10,
        }
    }
}
```

### Template 3: Timer Peripheral

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Time;

namespace Antmicro.Renode.Peripherals.Timers
{
    public class MyVendor_Timer : BasicDoubleWordPeripheral, IKnownSize
    {
        public MyVendor_Timer(IMachine machine, long frequency) : base(machine)
        {
            IRQ = new GPIO();
            timer = new LimitTimer(
                machine.ClockSource, frequency, this, nameof(timer),
                limit: DefaultLimit,
                direction: Direction.Descending,
                enabled: false,
                eventEnabled: true,
                autoUpdate: true
            );
            timer.LimitReached += OnTimerExpired;
            DefineRegisters();
        }

        public override void Reset()
        {
            base.Reset();
            timer.Reset();
            UpdateInterrupts();
        }

        public GPIO IRQ { get; }
        public long Size => 0x40;

        private void OnTimerExpired()
        {
            this.Log(LogLevel.Noisy, "Timer expired");
            irqPending.Value = true;
            UpdateInterrupts();
        }

        private void DefineRegisters()
        {
            Registers.Control.Define(this)
                .WithFlag(0, name: "ENABLE",
                    writeCallback: (_, val) => timer.Enabled = val,
                    valueProviderCallback: _ => timer.Enabled)
                .WithFlag(1, name: "ONE_SHOT",
                    writeCallback: (_, val) => timer.AutoUpdate = !val)
                .WithReservedBits(2, 30);

            Registers.Load.Define(this)
                .WithValueField(0, 32, name: "LOAD_VALUE",
                    writeCallback: (_, val) => timer.Limit = val,
                    valueProviderCallback: _ => (uint)timer.Limit);

            Registers.Value.Define(this)
                .WithValueField(0, 32, FieldMode.Read, name: "CURRENT_VALUE",
                    valueProviderCallback: _ =>
                    {
                        if(machine.SystemBus.TryGetCurrentCPU(out var cpu))
                        {
                            cpu.SyncTime();
                        }
                        return (uint)timer.Value;
                    });

            Registers.InterruptStatus.Define(this)
                .WithFlag(0, out irqPending,
                    FieldMode.Read | FieldMode.WriteOneToClear, name: "EXPIRED",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(1, 31);

            Registers.InterruptEnable.Define(this)
                .WithFlag(0, out irqEnabled, name: "IRQ_EN",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(1, 31);
        }

        private void UpdateInterrupts()
        {
            IRQ.Set(irqEnabled.Value && irqPending.Value);
        }

        private IFlagRegisterField irqPending;
        private IFlagRegisterField irqEnabled;

        private readonly LimitTimer timer;
        private const uint DefaultLimit = 0xFFFFFFFF;

        private enum Registers : long
        {
            Control = 0x00,
            Load = 0x04,
            Value = 0x08,
            InterruptStatus = 0x0C,
            InterruptEnable = 0x10,
        }
    }
}
```

### Template 4: I2C Sensor

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using System;
using System.Collections.Generic;
using System.Linq;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Peripherals.Sensor;
using Antmicro.Renode.Utilities;
using Antmicro.Renode.Exceptions;

namespace Antmicro.Renode.Peripherals.Sensors
{
    public class MyVendor_TempSensor : II2CPeripheral, ITemperatureSensor
    {
        public MyVendor_TempSensor()
        {
            outputBuffer = new Queue<byte>();
            Reset();
        }

        public byte[] Read(int count = 1)
        {
            var result = outputBuffer.DequeueRange(Math.Min(count, outputBuffer.Count));
            this.Log(LogLevel.Noisy, "Read {0} bytes: [{1}]",
                result.Length, string.Join(", ", result.Select(x => $"0x{x:X2}")));
            return result;
        }

        public void Write(byte[] data)
        {
            this.Log(LogLevel.Noisy, "Write {0} bytes: [{1}]",
                data.Length, string.Join(", ", data.Select(x => $"0x{x:X2}")));

            if(data.Length == 0) return;

            var register = (Register)data[0];
            switch(register)
            {
                case Register.Temperature:
                    var raw = TemperatureToRaw(Temperature);
                    outputBuffer.Enqueue((byte)(raw >> 8));
                    outputBuffer.Enqueue((byte)(raw & 0xFF));
                    break;
                case Register.DeviceId:
                    outputBuffer.Enqueue(DeviceId);
                    break;
                default:
                    this.Log(LogLevel.Warning, "Unknown register: 0x{0:X2}", data[0]);
                    break;
            }
        }

        public void FinishTransmission()
        {
            // Called when I2C STOP condition occurs
        }

        public void Reset()
        {
            Temperature = 25.0m;
            outputBuffer.Clear();
        }

        public decimal Temperature
        {
            get => temperature;
            set
            {
                if(value < MinTemperature || value > MaxTemperature)
                {
                    throw new RecoverableException(
                        $"Temperature must be between {MinTemperature} and {MaxTemperature}");
                }
                temperature = value;
            }
        }

        private ushort TemperatureToRaw(decimal temp)
        {
            // Convert temperature to raw ADC value (device-specific formula)
            return (ushort)((temp + 40.0m) * 256.0m / 165.0m);
        }

        private decimal temperature;
        private readonly Queue<byte> outputBuffer;

        private const decimal MinTemperature = -40.0m;
        private const decimal MaxTemperature = 125.0m;
        private const byte DeviceId = 0x5A;

        private enum Register : byte
        {
            Temperature = 0x00,
            Configuration = 0x01,
            DeviceId = 0x0F,
        }
    }
}
```

## Conventions and Best Practices

### Naming Conventions
- **Namespace**: `Antmicro.Renode.Peripherals.<Category>` (UART, Timers, GPIOPort, SPI, I2C, Sensors, etc.)
- **Class name**: `Vendor_PeripheralName` (e.g., `STM32_UART`, `LiteX_Timer`, `NRF52840_UART`)
- **Register enum**: `private enum Registers : long` (PascalCase names, hex offsets)
- **Register names**: Human-readable PascalCase (e.g., `InterruptEnable` not `IEN`)
- **Fields**: Use `out` parameter for fields accessed programmatically

### Register Enum Values
- Use **relative offsets** from peripheral base (not absolute addresses)
- Values represent byte offsets (0x00, 0x04, 0x08... for 32-bit registers)

### Implementation Guidelines
1. **List ALL registers** in the enum but only **implement** those used by firmware
2. **Mark unimplemented fields** as `WithTaggedFlag` or `WithTag` (better logging)
3. **Fill remaining bits** with `WithReservedBits` (catches firmware bugs)
4. **Always implement `Reset()`** — call `base.Reset()` then `RegistersCollection.Reset()`
5. **Always implement `IKnownSize`** — avoids needing explicit size in .repl files
6. **Call `UpdateInterrupts()`** after any state change affecting IRQ line
7. **Use `this.Log()`** for debug messages (LogLevel.Warning for unexpected states)
8. **Prefer `changeCallback` over `writeCallback`** when only caring about value changes

### Constructor Parameters
- Constructor parameters exposed in .repl files start with **lowercase**
- Properties exposed in .repl files start with **uppercase**

```csharp
// In .repl file:
// timer: Timers.MyTimer @ sysbus 0x40000000
//     frequency: 48000000          ← constructor parameter (lowercase)
//     InitialLimit: 0xFFFF         ← property (uppercase)

public MyTimer(IMachine machine, long frequency) : base(machine) { ... }
public uint InitialLimit { get; set; }
```

## Validation Checklist

When generating a peripheral model:

1. **Correct namespace** matches peripheral category
2. **Implements IKnownSize** with appropriate Size property
3. **All register bits accounted for** (fields + reserved = register width)
4. **Reset() resets all state** (RegistersCollection, timers, FIFOs, fields)
5. **IRQ pattern is correct** (enable AND pending → GPIO.Set)
6. **No overlapping register offsets** in enum
7. **Register offsets match datasheet** (verify alignment: 0x0, 0x4, 0x8...)
8. **Callbacks don't throw** (use `this.Log(LogLevel.Warning, ...)` instead)
9. **Thread safety** for fields accessed from timer callbacks
10. **Constructor parameters named in camelCase** (for .repl compatibility)

## Output Format

Generate complete, compilable C# files with proper copyright header, using statements, namespace, and class definition. Follow the Renode coding style (4-space indentation, Allman braces, PascalCase methods/properties, camelCase locals/parameters).

## Automatic Stub Generation (peakrdl-renode)

For large peripherals with many registers, Renode provides the `peakrdl-renode` tool to automatically generate register scaffolding from SystemRDL files:

```bash
# Install the tool
pip install peakrdl
pip install git+https://github.com/renode/renode/#subdirectory=tools/PeakRDL-renode

# Generate scaffolding
peakrdl renode -n MyPeripheral -N Miscellaneous -o MyPeripheral_generated.cs peripheral.rdl
```

This generates a `partial class` with all register definitions. Create a separate `MyPeripheral.cs` file to implement behavioral logic (callbacks, state machines). This approach is especially useful during hardware development when register layouts are not yet stable.
