# Hardcoded Makefile of tested targets
.PHONY: build

FLASH ?= no
FLASH_TOOL ?= west
TARGET_BOARD_ZEPHYR ?= esp32c3_devkitm

esp32c3_devkitm:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=west-espressif

esp32s3_devkitm:
	$(MAKE) build TARGET_BOARD_ZEPHYR=esp32s3_devkitm/esp32s3/procpu FLASH_TYPE=west-espressif

rpi_pico:
	$(MAKE) build TARGET_BOARD_ZEPHYR=rpi_pico/rp2040/w FLASH_TYPE=picotool

bbc_microbit_v2:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=west

nucleo_h753zi:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=west

qemu_cortex_m0:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=qemu

qemu_cortex_m3:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=qemu

qemu_riscv32:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=qemu

# Build binaries
build:
	west build -b $(TARGET_BOARD_ZEPHYR) -p always . $(EXTRA_CFG)
ifeq ($(FLASH),yes)
	$(MAKE) flash
endif

# Flash binaries on target
flash:
ifeq ($(FLASH_TYPE),west)
	west flash
else ifeq ($(FLASH_TYPE),west-espressif)
	west flash
	west espressif monitor
else ifeq ($(FLASH_TYPE),picotool)
	picotool load ./build/zephyr/zephyr.bin -N -o 0x10000000 -x
else ifeq ($(FLASH_TYPE),qemu)
	west build -t run
endif

# Build for all supported targets
all: esp32c3_devkitm rpi_pico bbc_microbit_v2 qemu_cortex_m0 qemu_cortex_m3 qemu_riscv32 nucleo_h753zi

# Clean build artefacts
clean:
	@rm -rf build

