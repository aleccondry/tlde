# Skill: Renode-Test Robot Framework File Generation

## Purpose

Generate Robot Framework `.robot` test files for automated testing of firmware running in Renode emulation. These tests verify that emulated hardware platforms execute firmware correctly by monitoring UART output, peripheral states, timing, and inter-device communication.

## Context

Renode integrates with Robot Framework via a built-in server (port 9999 by default). The `renode-test` command launches Renode in the background, connects the Robot executor, and runs test cases. Tests use Renode-specific keywords for machine creation, UART monitoring, peripheral interaction, and emulation control.

## File Structure

### Mandatory Settings Section

Every Renode robot test file MUST include this settings block:

```robot
*** Settings ***
Suite Setup       Setup
Suite Teardown    Teardown
Test Setup        Test Setup
Test Teardown     Test Teardown
Resource          ${RENODEKEYWORDS}
```

The `${RENODEKEYWORDS}` variable is automatically set by `renode-test` to point to `renode-keywords.robot`.

### Complete File Skeleton

```robot
*** Settings ***
Suite Setup       Setup
Suite Teardown    Teardown
Test Setup        Test Setup
Test Teardown     Test Teardown
Resource          ${RENODEKEYWORDS}

*** Variables ***
${UART}           sysbus.uart0
${SCRIPT}         ${CURDIR}/path/to/script.resc
${BIN}            @https://dl.antmicro.com/projects/renode/firmware.elf-s_size-hash

*** Keywords ***
Create Machine
    Execute Command           mach create
    Execute Command           machine LoadPlatformDescription @platforms/cpus/target.repl
    # Use LoadELF, LoadBinary, or LoadHEX depending on firmware format
    Execute Command           sysbus LoadELF ${BIN}
    Create Terminal Tester    ${UART}

*** Test Cases ***
Should Print Hello World
    [Documentation]     Verifies firmware prints expected output
    [Tags]              uart  basic
    Create Machine
    Start Emulation
    Wait For Line On Uart     Hello World!
```

## Core Keywords

### Machine Setup Keywords

```robot
# Execute any Renode monitor command
Execute Command    mach create
Execute Command    machine LoadPlatformDescription @path/to/platform.repl

# Load firmware — use the command matching the binary format:
#   LoadELF for .elf files (most common, entry point from ELF header)
#   LoadBinary for raw .bin files (requires explicit load address)
#   LoadHEX for Intel .hex files (addresses embedded in file)
Execute Command    sysbus LoadELF @path/to/firmware.elf
Execute Command    sysbus LoadELF ${BIN}
Execute Command    sysbus LoadBinary @path/to/firmware.bin 0x08000000
Execute Command    sysbus LoadHEX @path/to/firmware.hex

# Execute and capture return value
${result}=    Execute Command    sysbus.cpu PC

# Execute a .resc script
Execute Script    ${SCRIPT}

# Set Renode variables before script execution
Execute Command    $bin = ${BIN}
Execute Script     ${SCRIPT}
```

### Terminal Tester (UART Monitoring)

```robot
# Create UART monitor (REQUIRED before any UART assertions)
Create Terminal Tester    ${UART}
Create Terminal Tester    ${UART}    timeout=15
Create Terminal Tester    ${UART}    defaultPauseEmulation=True
Create Terminal Tester    ${UART}    endLineOption=TreatCarriageReturnAsEndLine
Create Terminal Tester    ${UART}    machine=machine_name

# Multiple UARTs in multi-machine tests
${uart_central}=     Create Terminal Tester    ${UART}    machine=central
${uart_peripheral}=  Create Terminal Tester    ${UART}    machine=peripheral
```

### Emulation Control

```robot
Start Emulation
Reset Emulation

# Run for specific virtual time
Execute Command    emulation RunFor "0.01"
Execute Command    emulation RunFor "5.0"
```

### UART Assertions

```robot
# Wait for exact line (default timeout: 8 seconds)
Wait For Line On Uart    Hello World!

# With custom timeout
Wait For Line On Uart    Boot complete    timeout=30

# With regex pattern matching
Wait For Line On Uart    Temperature: \\d+\\.\\d+ C    treatAsRegex=true

# Wait for prompt (partial line match)
Wait For Prompt On Uart    uart:~$
Wait For Prompt On Uart    shell>    timeout=25

# Multi-machine UART (specify tester ID)
Wait For Line On Uart    Booting Zephyr    testerId=${uart_central}
Wait For Line On Uart    Connected        testerId=${uart_peripheral}

# Wait for next line (any content)
${line}=    Wait For Next Line On Uart

# Verify UART is silent
Test If Uart Is Idle    5    # 5 second silence check

# Pause emulation during wait (prevents timeout races in timing-sensitive tests)
# When pauseEmulation=true, the emulation is paused while waiting for UART output,
# which prevents race conditions where the emulation runs ahead of the test assertions
Wait For Line On Uart    Ready    pauseEmulation=true
```

### UART Writing

```robot
# Write line (with newline appended)
Write Line To Uart    ls -la
Write Line To Uart    ping 192.168.1.1

# Write single character
Write Char On Uart    y

# Write to specific UART
Write Line To Uart    command    testerId=${uart_id}
```

### LED Testing

```robot
# Create LED tester
Create LED Tester    sysbus.gpioPortA.led    defaultTimeout=1

# Assert LED state
Assert LED State    true     # LED is on
Assert LED State    false    # LED is off
Assert LED State    true  0  # timeout=0 (immediate check)
```

### Log Testing

```robot
# Create log tester (monitors Renode internal logs)
Create Log Tester    1    # 1 second default timeout

# Set log level for peripheral
Execute Command    logLevel -1 sysbus.gic

# Wait for log entry
Wait For Log Entry    Interrupt triggered    timeout=5
Wait For Log Entry    gic: Setting IRQ    keep=True    pauseEmulation=True

# Negative assertion
Should Not Be In Log    Error occurred
```

### Peripheral Interaction

```robot
# Set peripheral properties
Execute Command    ${SENSOR} Temperature 25.00
Execute Command    ${SENSOR} Humidity 50.0
Execute Command    sysbus.gpioPortA.button Press
Execute Command    sysbus.gpioPortA.button Release
Execute Command    sysbus.timer0 Frequency 1000000

# Read peripheral state
${value}=    Execute Command    sysbus.cpu PC
Should Contain    ${value}    0x0800
```

### File Operations

```robot
# Allocate temporary file
${tmp_file}=    Allocate Temporary File

# Create binary test data
Create Binary File    ${tmp_file}    \x00\x01\x02\x03

# Get file size
${size}=    Get File Size    ${tmp_file}
```

### Test Dependencies (Provides/Requires)

```robot
*** Test Cases ***
Boot Linux
    [Documentation]    Boot Linux kernel (long-running)
    Create Machine
    Start Emulation
    Wait For Prompt On Uart    login:    timeout=120
    Provides    booted-linux

Run Shell Command
    [Documentation]    Run command after boot
    Requires    booted-linux
    Write Line To Uart    root
    Wait For Prompt On Uart    \#${SPACE}
    Write Line To Uart    uname -a
    Wait For Line On Uart    Linux
```

## Common Test Patterns

### Pattern 1: Basic UART Output Test

```robot
*** Settings ***
Suite Setup       Setup
Suite Teardown    Teardown
Test Setup        Test Setup
Test Teardown     Test Teardown
Resource          ${RENODEKEYWORDS}

*** Variables ***
${UART}           sysbus.usart2
${BIN}            @https://dl.antmicro.com/projects/renode/zephyr-hello-world.elf-s_123-hash

*** Keywords ***
Create Machine
    Execute Command           mach create
    Execute Command           machine LoadPlatformDescription @platforms/cpus/stm32f4.repl
    Execute Command           sysbus LoadELF ${BIN}
    Create Terminal Tester    ${UART}

*** Test Cases ***
Should Print Hello World
    [Documentation]    Verifies Zephyr hello_world sample runs correctly
    [Tags]             zephyr  uart
    Create Machine
    Start Emulation
    Wait For Line On Uart    Hello World! stm32f4
```

### Pattern 2: Interactive Shell Test

```robot
*** Test Cases ***
Should Run Shell Commands
    [Documentation]    Tests interactive shell functionality
    [Tags]             zephyr  shell  uart
    Create Machine
    Start Emulation
    Wait For Prompt On Uart    uart:~$    timeout=30
    Write Line To Uart         help
    Wait For Line On Uart      Available commands:
    Write Line To Uart         kernel version
    Wait For Line On Uart      Zephyr version
```

### Pattern 3: Peripheral Sensor Test

```robot
*** Variables ***
${UART}       sysbus.usart2
${SENSOR}     sysbus.i2c1.bme280
${PLATFORM}   platforms/cpus/stm32l072.repl

*** Keywords ***
Create Machine
    Execute Command    mach create
    Execute Command    machine LoadPlatformDescription @${PLATFORM}
    Execute Command    machine LoadPlatformDescriptionFromString "bme280: Sensors.BME280 @ i2c1 0x76"
    Execute Command    sysbus LoadELF ${BIN}
    Create Terminal Tester    ${UART}

*** Test Cases ***
Should Read Temperature
    [Documentation]    Verifies temperature sensor reading
    [Tags]             i2c  sensor
    Create Machine
    Execute Command    ${SENSOR} Temperature 25.5
    Start Emulation
    Wait For Line On Uart    Temperature: 25.5    timeout=10
```

### Pattern 4: Timer/LED Blink Test

```robot
*** Keywords ***
Create Machine
    Execute Command    mach create
    Execute Command    machine LoadPlatformDescription @platforms/cpus/stm32f4.repl
    Execute Command    machine LoadPlatformDescriptionFromString "led: Miscellaneous.LED @ gpioPortD 12"
    Execute Command    sysbus LoadELF ${BIN}
    Create LED Tester  sysbus.gpioPortD.led    defaultTimeout=2

*** Test Cases ***
Should Blink LED
    [Documentation]    Verifies LED toggles via timer interrupt
    [Tags]             timer  gpio  led
    Create Machine
    Assert LED State   false  0
    Start Emulation
    Assert LED State   true
    Assert LED State   false
    Assert LED State   true
```

### Pattern 5: Multi-Machine Wireless Test

```robot
*** Variables ***
${UART}            sysbus.uart0
${CENTRAL_BIN}     @https://dl.antmicro.com/projects/renode/central.elf-s_123-hash
${PERIPHERAL_BIN}  @https://dl.antmicro.com/projects/renode/peripheral.elf-s_456-hash

*** Keywords ***
Create Network
    Execute Command          emulation CreateBLEMedium "wireless"

    Execute Command          mach create "central"
    Execute Command          machine LoadPlatformDescription @platforms/cpus/nrf52840.repl
    Execute Command          connector Connect sysbus.radio wireless
    Execute Command          sysbus LoadELF ${CENTRAL_BIN}
    ${cen_uart}=             Create Terminal Tester    ${UART}    machine=central

    Execute Command          mach create "peripheral"
    Execute Command          machine LoadPlatformDescription @platforms/cpus/nrf52840.repl
    Execute Command          connector Connect sysbus.radio wireless
    Execute Command          sysbus LoadELF ${PERIPHERAL_BIN}
    ${per_uart}=             Create Terminal Tester    ${UART}    machine=peripheral

    Set Suite Variable       ${cen_uart}
    Set Suite Variable       ${per_uart}

*** Test Cases ***
Should Establish BLE Connection
    [Documentation]    Verifies BLE central connects to peripheral
    [Tags]             ble  multi-node
    Create Network
    Start Emulation
    Wait For Line On Uart    Advertising started    testerId=${per_uart}    timeout=15
    Wait For Line On Uart    Connected              testerId=${cen_uart}    timeout=30
    Wait For Line On Uart    Connected              testerId=${per_uart}    timeout=5
```

### Pattern 6: Timing Verification

```robot
*** Test Cases ***
Should Trigger Alarm At 2 Seconds
    [Documentation]    Verifies timer fires at correct virtual time
    [Tags]             timer  timing
    Create Machine
    Start Emulation
    Wait For Line On Uart    !!! Alarm !!!    timeout=10
    ${time}=    Execute Command    emulation GetTimeSourceInfo
    Should Contain    ${time}    Elapsed Virtual Time: 00:00:02
```

### Pattern 7: Using RESC Script

```robot
*** Variables ***
${UART}      sysbus.uart0
${SCRIPT}    ${CURDIR}/../../../scripts/single-node/sifive_fe310.resc
${BIN}       @https://dl.antmicro.com/projects/renode/zephyr-fe310.elf-s_123-hash

*** Keywords ***
Create Machine
    Execute Command    $bin = ${BIN}
    Execute Script     ${SCRIPT}
    Create Terminal Tester    ${UART}

*** Test Cases ***
Should Boot Zephyr
    [Documentation]    Boots Zephyr on SiFive FE310 using standard script
    [Tags]             zephyr  riscv
    Create Machine
    Start Emulation
    Wait For Line On Uart    Booting Zephyr
```

### Pattern 8: Loop-Based Data Verification

```robot
*** Keywords ***
Verify Sensor Readings
    [Arguments]    ${count}    ${expected}
    FOR    ${i}    IN RANGE    ${count}
        Wait For Line On Uart    Reading: ${expected}    timeout=5
        Execute Command           emulation RunFor "0.1"
    END

*** Test Cases ***
Should Read Multiple Samples
    [Documentation]    Verifies periodic sensor readings
    [Tags]             sensor  loop
    Create Machine
    Execute Command    ${SENSOR} Temperature 22.0
    Start Emulation
    Verify Sensor Readings    10    22.0
```

### Pattern 9: Inline Platform Description

```robot
*** Variables ***
${PLATFORM}=    SEPARATOR=
...    """                                             ${\n}
...    using "platforms/cpus/stm32l072.repl"           ${\n}
...    bme280: Sensors.BME280 @ i2c1 0x76             ${\n}
...    """

*** Keywords ***
Create Machine
    Execute Command    mach create
    Execute Command    machine LoadPlatformDescriptionFromString ${PLATFORM}
    Execute Command    sysbus LoadELF ${BIN}
    Create Terminal Tester    ${UART}
```

### Pattern 10: Loading Non-ELF Firmware (BIN/HEX)

```robot
*** Variables ***
${UART}           sysbus.usart2
${HEX_FW}        @https://dl.antmicro.com/projects/renode/firmware.hex-s_size-hash
${BIN_FW}        @https://dl.antmicro.com/projects/renode/firmware.bin-s_size-hash
${LOAD_ADDR}     0x08000000

*** Keywords ***
Create Machine With HEX
    Execute Command           mach create
    Execute Command           machine LoadPlatformDescription @platforms/cpus/stm32f4.repl
    Execute Command           sysbus LoadHEX ${HEX_FW}
    Create Terminal Tester    ${UART}

Create Machine With BIN
    Execute Command           mach create
    Execute Command           machine LoadPlatformDescription @platforms/cpus/stm32f4.repl
    Execute Command           sysbus LoadBinary ${BIN_FW} ${LOAD_ADDR}
    Execute Command           cpu VectorTableOffset ${LOAD_ADDR}
    Create Terminal Tester    ${UART}

*** Test Cases ***
Should Boot From HEX File
    [Documentation]    Verifies firmware loaded from Intel HEX format runs correctly
    [Tags]             uart  hex
    Create Machine With HEX
    Start Emulation
    Wait For Line On Uart    Hello World!

Should Boot From BIN File
    [Documentation]    Verifies firmware loaded from raw binary format runs correctly
    [Tags]             uart  bin
    Create Machine With BIN
    Start Emulation
    Wait For Line On Uart    Hello World!
```

## Tags Convention

Standard tags used in Renode tests:

| Tag | Purpose |
|-----|---------|
| `zephyr` | Tests using Zephyr RTOS |
| `linux` | Tests booting Linux |
| `uart` | UART functionality tested |
| `i2c` | I2C bus tested |
| `spi` | SPI bus tested |
| `gpio` | GPIO functionality |
| `timer` | Timer/counter tests |
| `interrupts` | Interrupt handling |
| `dma` | DMA transfers |
| `ble` | Bluetooth Low Energy |
| `multi-node` | Multi-machine tests |
| `non_critical` | Lower priority tests |
| `skipped` | Temporarily disabled |

## Important Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `${RENODEKEYWORDS}` | (auto) | Path to renode-keywords.robot |
| `${CURDIR}` | (auto) | Directory of current .robot file |
| `${DEFAULT_UART_TIMEOUT}` | 8 | Default UART wait timeout (seconds) |
| `${SPACE}` | ` ` | Single space character |
| `${\n}` | newline | Newline for multiline variables |

## Validation Checklist

When generating a Robot test file, verify:

1. **Settings section is complete** with all Setup/Teardown entries and Resource
2. **`Create Terminal Tester` before any UART assertions**
3. **`Start Emulation` before any `Wait For` keywords**
4. **Timeouts are reasonable** (8s default, increase for boot sequences)
5. **Multi-machine: `testerId=` parameter on UART keywords**
6. **Variables use `${CURDIR}` for relative paths** to other files
7. **Tags are lowercase and hyphenated** for consistency
8. **Each test is independent** (or uses Provides/Requires explicitly)
9. **Documentation string on every test case**
10. **Binary paths include size and hash** for reproducibility

## Running Tests

```bash
# Single test file
renode-test my_test.robot

# With logging visible
renode-test --show-log my_test.robot

# Multiple files in parallel
renode-test -j4 -t tests.yaml

# Specific test by name pattern
renode-test -f "*Hello*" my_test.robot

# Debug on failure (opens Renode UI)
renode-test --debug-on-error my_test.robot

# Custom port (avoid conflicts)
renode-test -P 9998 my_test.robot
```

## Output Format

Generate complete, executable `.robot` files. Always include the full Settings section, meaningful documentation on test cases, and appropriate tags. Structure keywords for reusability across test cases.
