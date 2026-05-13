# Skill: Renode Peripheral Model Patterns (Advanced Types)

## Purpose

Provides advanced patterns and templates for specific peripheral types beyond the basics covered in the general peripheral model skill. Covers GPIO controllers, SPI/I2C controllers, DMA engines, network interfaces, and complex multi-register peripherals.

## Template 5: GPIO Port Controller

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using System;
using System.Collections.Generic;
using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Utilities;

namespace Antmicro.Renode.Peripherals.GPIOPort
{
    public class MyVendor_GPIO : BaseGPIOPort, IDoubleWordPeripheral, IKnownSize,
        IProvidesRegisterCollection<DoubleWordRegisterCollection>
    {
        public MyVendor_GPIO(IMachine machine, int numberOfPins = 32) : base(machine, numberOfPins)
        {
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
        }

        public long Size => 0x400;
        public DoubleWordRegisterCollection RegistersCollection { get; }

        private void DefineRegisters()
        {
            Registers.Direction.Define(this)
                .WithValueField(0, 32, out directionRegister, name: "DIR",
                    writeCallback: (_, val) =>
                    {
                        // Bit = 1 means output, 0 means input
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            var isOutput = (val & (1u << i)) != 0;
                            // Update pin configuration
                        }
                    });

            Registers.OutputData.Define(this)
                .WithValueField(0, 32, name: "OUT",
                    writeCallback: (_, val) =>
                    {
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            var pinState = (val & (1u << i)) != 0;
                            Connections[i].Set(pinState);
                        }
                    },
                    valueProviderCallback: _ =>
                    {
                        uint result = 0;
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            if(Connections[i].IsSet)
                            {
                                result |= 1u << i;
                            }
                        }
                        return result;
                    });

            Registers.InputData.Define(this)
                .WithValueField(0, 32, FieldMode.Read, name: "IN",
                    valueProviderCallback: _ =>
                    {
                        uint result = 0;
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            if(State[i])
                            {
                                result |= 1u << i;
                            }
                        }
                        return result;
                    });

            Registers.OutputSet.Define(this)
                .WithValueField(0, 32, FieldMode.Write, name: "OUT_SET",
                    writeCallback: (_, val) =>
                    {
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            if((val & (1u << i)) != 0)
                            {
                                Connections[i].Set(true);
                            }
                        }
                    });

            Registers.OutputClear.Define(this)
                .WithValueField(0, 32, FieldMode.Write, name: "OUT_CLR",
                    writeCallback: (_, val) =>
                    {
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            if((val & (1u << i)) != 0)
                            {
                                Connections[i].Set(false);
                            }
                        }
                    });

            Registers.OutputToggle.Define(this)
                .WithValueField(0, 32, FieldMode.Write, name: "OUT_TGL",
                    writeCallback: (_, val) =>
                    {
                        for(int i = 0; i < NumberOfConnections; i++)
                        {
                            if((val & (1u << i)) != 0)
                            {
                                Connections[i].Toggle();
                            }
                        }
                    });
        }

        private IValueRegisterField directionRegister;

        private enum Registers : long
        {
            Direction = 0x00,
            OutputData = 0x04,
            InputData = 0x08,
            OutputSet = 0x0C,
            OutputClear = 0x10,
            OutputToggle = 0x14,
        }
    }
}
```

## Template 6: SPI Controller

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using System.Collections.Generic;
using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.SPI;

namespace Antmicro.Renode.Peripherals.SPI
{
    public class MyVendor_SPI : SimpleContainer<ISPIPeripheral>, IDoubleWordPeripheral,
        IKnownSize, IProvidesRegisterCollection<DoubleWordRegisterCollection>
    {
        public MyVendor_SPI(IMachine machine) : base(machine)
        {
            IRQ = new GPIO();
            txFifo = new Queue<byte>();
            rxFifo = new Queue<byte>();
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
            txFifo.Clear();
            rxFifo.Clear();
            UpdateInterrupts();
        }

        public GPIO IRQ { get; }
        public long Size => 0x100;
        public DoubleWordRegisterCollection RegistersCollection { get; }

        private void DefineRegisters()
        {
            Registers.Control.Define(this)
                .WithFlag(0, out spiEnabled, name: "SPE")
                .WithFlag(1, name: "MSTR")       // Master mode
                .WithEnumField<DoubleWordRegister, ClockPolarity>(2, 1, out cpol, name: "CPOL")
                .WithEnumField<DoubleWordRegister, ClockPhase>(3, 1, out cpha, name: "CPHA")
                .WithValueField(4, 3, out clockDivider, name: "BR")
                .WithReservedBits(7, 25);

            Registers.Status.Define(this)
                .WithFlag(0, FieldMode.Read, name: "TXE",
                    valueProviderCallback: _ => txFifo.Count == 0)
                .WithFlag(1, FieldMode.Read, name: "RXNE",
                    valueProviderCallback: _ => rxFifo.Count > 0)
                .WithFlag(7, FieldMode.Read, name: "BSY",
                    valueProviderCallback: _ => false)
                .WithReservedBits(8, 24);

            Registers.Data.Define(this)
                .WithValueField(0, 8, name: "DR",
                    writeCallback: (_, val) => DoTransfer((byte)val),
                    valueProviderCallback: _ =>
                    {
                        if(rxFifo.Count == 0)
                        {
                            this.Log(LogLevel.Warning, "Reading from empty RX FIFO");
                            return 0;
                        }
                        return rxFifo.Dequeue();
                    })
                .WithReservedBits(8, 24);

            Registers.InterruptEnable.Define(this)
                .WithFlag(0, out txEmptyIrqEn, name: "TXEIE",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithFlag(1, out rxNotEmptyIrqEn, name: "RXNEIE",
                    changeCallback: (_, __) => UpdateInterrupts())
                .WithReservedBits(2, 30);
        }

        private void DoTransfer(byte txData)
        {
            if(!spiEnabled.Value)
            {
                this.Log(LogLevel.Warning, "Transfer while SPI disabled");
                return;
            }

            // Find connected device (chip select)
            if(!TryGetByAddress(0, out var device))
            {
                this.Log(LogLevel.Warning, "No SPI device connected");
                rxFifo.Enqueue(0xFF);
                return;
            }

            var rxData = device.Transmit(txData);
            rxFifo.Enqueue(rxData);
            UpdateInterrupts();
        }

        private void UpdateInterrupts()
        {
            var pending = (txEmptyIrqEn.Value && txFifo.Count == 0)
                       || (rxNotEmptyIrqEn.Value && rxFifo.Count > 0);
            IRQ.Set(pending);
        }

        private IFlagRegisterField spiEnabled;
        private IFlagRegisterField txEmptyIrqEn;
        private IFlagRegisterField rxNotEmptyIrqEn;
        private IEnumRegisterField<ClockPolarity> cpol;
        private IEnumRegisterField<ClockPhase> cpha;
        private IValueRegisterField clockDivider;

        private readonly Queue<byte> txFifo;
        private readonly Queue<byte> rxFifo;

        private enum ClockPolarity
        {
            IdleLow = 0,
            IdleHigh = 1,
        }

        private enum ClockPhase
        {
            FirstEdge = 0,
            SecondEdge = 1,
        }

        private enum Registers : long
        {
            Control = 0x00,
            Status = 0x04,
            Data = 0x08,
            InterruptEnable = 0x0C,
        }
    }
}
```

## Template 7: DMA Controller

```csharp
//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using System;
using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;

namespace Antmicro.Renode.Peripherals.DMA
{
    public class MyVendor_DMA : BasicDoubleWordPeripheral, IKnownSize, INumberedGPIOOutput
    {
        public MyVendor_DMA(IMachine machine, int numberOfChannels = 8) : base(machine)
        {
            this.numberOfChannels = numberOfChannels;
            channels = new DMAChannel[numberOfChannels];
            var gpios = new Dictionary<int, IGPIO>();
            for(int i = 0; i < numberOfChannels; i++)
            {
                channels[i] = new DMAChannel(i);
                gpios[i] = new GPIO();
            }
            Connections = gpios;
            DefineRegisters();
        }

        public override void Reset()
        {
            base.Reset();
            foreach(var ch in channels)
            {
                ch.Reset();
            }
        }

        public IReadOnlyDictionary<int, IGPIO> Connections { get; }
        public long Size => 0x100 + (numberOfChannels * ChannelRegisterSpan);

        private void DefineRegisters()
        {
            // Global interrupt status register
            Registers.InterruptStatus.Define(this)
                .WithValueField(0, 32, FieldMode.Read, name: "ISR",
                    valueProviderCallback: _ =>
                    {
                        uint status = 0;
                        for(int i = 0; i < numberOfChannels; i++)
                        {
                            if(channels[i].TransferComplete)
                                status |= 1u << (i * 4);
                            if(channels[i].HalfTransfer)
                                status |= 1u << (i * 4 + 1);
                            if(channels[i].Error)
                                status |= 1u << (i * 4 + 2);
                        }
                        return status;
                    });

            // Per-channel registers
            for(int ch = 0; ch < numberOfChannels; ch++)
            {
                var channelIdx = ch;
                var baseOffset = ChannelBaseOffset + ch * ChannelRegisterSpan;

                ((Registers)(baseOffset + 0x00)).Define(this)
                    .WithFlag(0, name: $"CH{ch}_EN",
                        writeCallback: (_, val) =>
                        {
                            if(val) StartTransfer(channelIdx);
                        })
                    .WithFlag(1, name: $"CH{ch}_TCIE",
                        writeCallback: (_, val) => channels[channelIdx].TransferCompleteIrqEnabled = val)
                    .WithEnumField<DoubleWordRegister, TransferDirection>(4, 1, name: $"CH{ch}_DIR",
                        writeCallback: (_, val) => channels[channelIdx].Direction = val)
                    .WithFlag(7, name: $"CH{ch}_MINC",
                        writeCallback: (_, val) => channels[channelIdx].MemoryIncrement = val)
                    .WithFlag(6, name: $"CH{ch}_PINC",
                        writeCallback: (_, val) => channels[channelIdx].PeripheralIncrement = val)
                    .WithReservedBits(8, 24);

                ((Registers)(baseOffset + 0x04)).Define(this)
                    .WithValueField(0, 16, name: $"CH{ch}_NDT",
                        writeCallback: (_, val) => channels[channelIdx].Count = (uint)val,
                        valueProviderCallback: _ => channels[channelIdx].Count);

                ((Registers)(baseOffset + 0x08)).Define(this)
                    .WithValueField(0, 32, name: $"CH{ch}_PAR",
                        writeCallback: (_, val) => channels[channelIdx].PeripheralAddress = (uint)val);

                ((Registers)(baseOffset + 0x0C)).Define(this)
                    .WithValueField(0, 32, name: $"CH{ch}_MAR",
                        writeCallback: (_, val) => channels[channelIdx].MemoryAddress = (uint)val);
            }
        }

        private void StartTransfer(int channelIdx)
        {
            var ch = channels[channelIdx];
            this.Log(LogLevel.Debug,
                "DMA Ch{0}: Transfer {1} bytes, Src=0x{2:X8}, Dst=0x{3:X8}",
                channelIdx, ch.Count,
                ch.Direction == TransferDirection.PeripheralToMemory ? ch.PeripheralAddress : ch.MemoryAddress,
                ch.Direction == TransferDirection.PeripheralToMemory ? ch.MemoryAddress : ch.PeripheralAddress);

            for(uint i = 0; i < ch.Count; i++)
            {
                uint srcAddr, dstAddr;
                if(ch.Direction == TransferDirection.PeripheralToMemory)
                {
                    srcAddr = ch.PeripheralAddress + (ch.PeripheralIncrement ? i : 0);
                    dstAddr = ch.MemoryAddress + (ch.MemoryIncrement ? i : 0);
                }
                else
                {
                    srcAddr = ch.MemoryAddress + (ch.MemoryIncrement ? i : 0);
                    dstAddr = ch.PeripheralAddress + (ch.PeripheralIncrement ? i : 0);
                }

                var data = machine.SystemBus.ReadByte(srcAddr);
                machine.SystemBus.WriteByte(dstAddr, data);
            }

            ch.TransferComplete = true;
            if(ch.TransferCompleteIrqEnabled)
            {
                ((GPIO)Connections[channelIdx]).Set(true);
            }
        }

        private readonly int numberOfChannels;
        private readonly DMAChannel[] channels;

        private const int ChannelBaseOffset = 0x08;
        private const int ChannelRegisterSpan = 0x14;

        private enum TransferDirection
        {
            PeripheralToMemory = 0,
            MemoryToPeripheral = 1,
        }

        private class DMAChannel
        {
            public DMAChannel(int index)
            {
                Index = index;
                Reset();
            }

            public void Reset()
            {
                Count = 0;
                PeripheralAddress = 0;
                MemoryAddress = 0;
                TransferComplete = false;
                HalfTransfer = false;
                Error = false;
                TransferCompleteIrqEnabled = false;
                MemoryIncrement = false;
                PeripheralIncrement = false;
                Direction = TransferDirection.PeripheralToMemory;
            }

            public int Index { get; }
            public uint Count { get; set; }
            public uint PeripheralAddress { get; set; }
            public uint MemoryAddress { get; set; }
            public bool TransferComplete { get; set; }
            public bool HalfTransfer { get; set; }
            public bool Error { get; set; }
            public bool TransferCompleteIrqEnabled { get; set; }
            public bool MemoryIncrement { get; set; }
            public bool PeripheralIncrement { get; set; }
            public TransferDirection Direction { get; set; }
        }

        private enum Registers : long
        {
            InterruptStatus = 0x00,
            InterruptClear = 0x04,
            // Channel registers are dynamic (calculated from base + index * span)
        }
    }
}
```

## Template 8: Watchdog Timer

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
    public class MyVendor_Watchdog : BasicDoubleWordPeripheral, IKnownSize
    {
        public MyVendor_Watchdog(IMachine machine, long frequency) : base(machine)
        {
            IRQ = new GPIO();
            watchdogTimer = new LimitTimer(
                machine.ClockSource, frequency, this, nameof(watchdogTimer),
                limit: DefaultTimeout,
                direction: Direction.Descending,
                enabled: false,
                eventEnabled: true,
                autoUpdate: true
            );
            watchdogTimer.LimitReached += OnWatchdogExpired;
            DefineRegisters();
        }

        public override void Reset()
        {
            base.Reset();
            watchdogTimer.Reset();
            locked = false;
        }

        public GPIO IRQ { get; }
        public long Size => 0x20;

        private void OnWatchdogExpired()
        {
            this.Log(LogLevel.Warning, "Watchdog timer expired!");
            if(resetOnExpiry.Value)
            {
                this.Log(LogLevel.Warning, "Triggering system reset");
                machine.RequestReset();
            }
            else
            {
                irqPending.Value = true;
                IRQ.Set(true);
            }
        }

        private void DefineRegisters()
        {
            Registers.Control.Define(this)
                .WithFlag(0, name: "WDT_EN",
                    writeCallback: (_, val) =>
                    {
                        if(locked && !val)
                        {
                            this.Log(LogLevel.Warning, "Cannot disable watchdog while locked");
                            return;
                        }
                        watchdogTimer.Enabled = val;
                    },
                    valueProviderCallback: _ => watchdogTimer.Enabled)
                .WithFlag(1, out resetOnExpiry, name: "RSTEN")
                .WithFlag(7, name: "LOCK",
                    writeCallback: (_, val) => { if(val) locked = true; })
                .WithReservedBits(8, 24);

            Registers.Reload.Define(this)
                .WithValueField(0, 32, name: "RELOAD",
                    writeCallback: (_, val) => watchdogTimer.Limit = val,
                    valueProviderCallback: _ => (uint)watchdogTimer.Limit);

            Registers.Kick.Define(this)
                .WithValueField(0, 32, FieldMode.Write, name: "KICK",
                    writeCallback: (_, val) =>
                    {
                        if(val == KickMagicValue)
                        {
                            watchdogTimer.Value = watchdogTimer.Limit;
                            this.Log(LogLevel.Noisy, "Watchdog kicked");
                        }
                    });

            Registers.InterruptStatus.Define(this)
                .WithFlag(0, out irqPending,
                    FieldMode.Read | FieldMode.WriteOneToClear, name: "WDT_INT",
                    writeCallback: (_, __) => IRQ.Set(false))
                .WithReservedBits(1, 31);
        }

        private bool locked;
        private IFlagRegisterField resetOnExpiry;
        private IFlagRegisterField irqPending;
        private readonly LimitTimer watchdogTimer;

        private const uint DefaultTimeout = 0xFFFFFFFF;
        private const uint KickMagicValue = 0x6969;

        private enum Registers : long
        {
            Control = 0x00,
            Reload = 0x04,
            Kick = 0x08,
            InterruptStatus = 0x0C,
        }
    }
}
```

## Advanced Patterns

### Pattern: FIFO with Threshold Interrupts

```csharp
private readonly Queue<byte> rxFifo = new Queue<byte>();
private const int FifoDepth = 16;

private void CheckFifoThreshold()
{
    var aboveThreshold = rxFifo.Count >= fifoThreshold.Value;
    rxThresholdReached.Value = aboveThreshold;
    UpdateInterrupts();
}
```

### Pattern: Multi-Register Value (Split Across Registers)

```csharp
// 32-bit value split across 4 x 8-bit registers (common in LiteX)
private uint compositeValue;

Registers.ValueByte0.DefineMany(this, 4, (reg, idx) =>
{
    reg.WithValueField(0, 8, name: $"VAL{idx}",
        writeCallback: (_, val) =>
        {
            BitHelper.ReplaceBits(ref compositeValue,
                width: 8, source: (uint)val,
                destinationPosition: 24 - idx * 8);
        },
        valueProviderCallback: _ =>
            BitHelper.GetValue(compositeValue, 24 - idx * 8, 8));
});
```

### Pattern: Clock Divider / Baud Rate Generator

```csharp
public override uint BaudRate
{
    get
    {
        if(baudDivisor.Value == 0) return 0;
        return (uint)(InputFrequency / (16 * (baudDivisor.Value + 1)));
    }
}
```

### Pattern: Peripheral with Internal State Machine

```csharp
private enum State
{
    Idle,
    WaitingForAddress,
    Transmitting,
    Receiving,
    Error,
}

private State currentState = State.Idle;

private void ProcessCommand(byte cmd)
{
    switch(currentState)
    {
        case State.Idle:
            if(cmd == StartByte)
            {
                currentState = State.WaitingForAddress;
            }
            break;
        case State.WaitingForAddress:
            targetAddress = cmd;
            currentState = State.Transmitting;
            break;
        // ...
    }
}
```

### Pattern: Conditional Register Definition

```csharp
// Register exists only when feature is enabled
Registers.AdvancedConfig.DefineConditional(this, () => hasAdvancedFeature, resetValue: 0)
    .WithFlag(0, out advancedFlag, name: "ADV_EN")
    .WithReservedBits(1, 31);
```

### Pattern: Register with Side Effects on Read

```csharp
Registers.Data.Define(this)
    .WithValueField(0, 8, name: "DATA",
        valueProviderCallback: _ =>
        {
            if(!TryGetCharacter(out var c))
            {
                return 0;
            }
            // Side effect: update status after read
            if(Count == 0)
            {
                rxNotEmpty.Value = false;
                UpdateInterrupts();
            }
            return c;
        });
```

### Pattern: Peripheral Connected to Another Peripheral

```csharp
// In REPL: dma -> spi controller notification
public class MyDMA_Aware_SPI : BasicDoubleWordPeripheral
{
    // Property set from REPL file
    public IDMA DmaController { get; set; }

    private void OnTransferComplete()
    {
        DmaController?.RequestTransfer(dmaChannel);
    }
}
```

## Peripheral Categories Quick Reference

| Category | Base Class | Key Interfaces | Example |
|----------|-----------|----------------|---------|
| UART | `UARTBase` | `IDoubleWordPeripheral`, `IKnownSize` | LiteX_UART |
| Timer | `BasicDoubleWordPeripheral` | `IKnownSize` + `LimitTimer` | LiteX_Timer |
| GPIO | `BaseGPIOPort` | `IDoubleWordPeripheral`, `IKnownSize` | MPFS_GPIO |
| SPI Controller | `SimpleContainer<ISPIPeripheral>` | `IDoubleWordPeripheral` | MPFS_SPI |
| I2C Controller | `SimpleContainer<II2CPeripheral>` | `IDoubleWordPeripheral` | MPFS_I2C |
| I2C Sensor | — | `II2CPeripheral`, `ITemperatureSensor` | SI70xx |
| SPI Sensor | — | `ISPIPeripheral` | TI_LM74 |
| DMA | `BasicDoubleWordPeripheral` | `INumberedGPIOOutput` | STM32G0DMA |
| Watchdog | `BasicDoubleWordPeripheral` | `IKnownSize` | — |
| IRQ Controller | — | `IIRQController`, `IKnownSize` | NVIC |
| Network | — | `IMACInterface`, `IKnownSize` | LiteX_Ethernet |

## File Organization

Place peripheral source files in the correct directory:
```
src/Emulator/Peripherals/Peripherals/
├── UART/           ← Serial ports
├── Timers/         ← Timer/counter peripherals
├── GPIOPort/       ← GPIO controllers
├── SPI/            ← SPI controllers
├── I2C/            ← I2C controllers
├── Sensors/        ← I2C/SPI sensor devices
├── DMA/            ← DMA controllers
├── Miscellaneous/  ← LEDs, buttons, other
├── Network/        ← Ethernet, WiFi
├── SD/             ← SD/MMC controllers
├── IRQControllers/ ← NVIC, GIC, PLIC
├── Wireless/       ← BLE, 802.15.4 radios
└── Sound/          ← Audio peripherals (I2S, etc.)
```

## Output Format

Generate complete C# files following Renode conventions. Include copyright header, proper namespace, and all required using statements. Each class should be self-contained and compilable within the renode-infrastructure project structure.
