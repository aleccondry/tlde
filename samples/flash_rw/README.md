# Flash read/write samples

The samples in this folder correspond to basic read/write tests in flash using the C wrappers called directly from the "Zephyr main application" and using from the Rust API through C bindings.
QEMU boards show limitations on flash memory emulation as no persistence is implemented and are also constrained by the qemu-machine associated with the targets. For instance, `qemu_cortex_m3` has a limited amount of flash and ram memory that would compile if increased virtually through the device tree but will not work in the emulation as the qemu-machine emulate the exact configuration described in the device tree.

The main purpose of this sample is to test the C wrappers and bindings in Rust both in hardware and emulation. This could later be included in CI tests.

Current supported boards: 
* bbc_microbit_v2

> Make sure you have the Rust target installed and virtual python environment activated.

## Getting started

* Run `make` or alternatively `make *<target>*` as per Makefile
