# Hardcoded Makefile of tested targets
.PHONY: build bbc_microbit_v2 all clean

FLASH ?= no
FLASH_TOOL ?= west
TARGET_BOARD_ZEPHYR ?= bbc_microbit_v2

bbc_microbit_v2:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@ FLASH_TYPE=west

# Build binaries
build:
	west build -b $(TARGET_BOARD_ZEPHYR) -p always . $(EXTRA_CFG)
ifeq ($(FLASH),yes)
	$(MAKE) flash
endif

# Flash binaries on target
flash:
	west flash

# Build for all supported targets
all: bbc_microbit_v2

# Clean build artefacts
clean:
	@rm -rf build

