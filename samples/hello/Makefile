FLASH ?= no
TARGET_BOARD_ZEPHYR ?= bbc_microbit_v2

.PHONY: clean bbc_microbit_v2 build

bbc_microbit_v2:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

build:
	west build -b $(TARGET_BOARD_ZEPHYR) .
ifeq ($(FLASH),yes)
	west flash
endif

clean:
	@rm -rf build/
