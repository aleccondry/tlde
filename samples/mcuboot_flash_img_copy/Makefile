.PHONY: clean build nucleo_h753zi

# Target board to actual Zephyr target board
TARGET_BOARD_ZEPHYR ?= esp32c3_devkitm
FLASH ?= no

default: build
all : esp32c3_devkitm bbc_microbit_v2 qemu_cortex_m0 nucleo_h753zi

# Target build command
esp32c3_devkitm:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

esp32s3_devkitm:
	$(MAKE) build TARGET_BOARD_ZEPHYR=esp32s3_devkitm/esp32s3/procpu

rpi_pico:
	$(MAKE) build TARGET_BOARD_ZEPHYR=rpi_pico/rp2040/w

bbc_microbit_v2:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

nucleo_h753zi:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

qemu_cortex_m0:
	$(warning $@ only supports compilation: QEMU flash emulation issue)
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH=no

qemu_riscv32:
	$(error $@ is not currently supported: QEMU flash emulation issue)
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH=no

qemu_cortex_m3:
	$(error $@ is not currently supported: QEMU flash emulation issue)
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH=no

# Build images (using sysbuild)
build:
	west build -b $(TARGET_BOARD_ZEPHYR) -p always --sysbuild .
ifeq ($(FLASH),yes)
	python flash.py $(TARGET_BOARD_ZEPHYR) --mcuboot --good-update
endif

# Clean build artefacts
clean:
	@rm -rf build
