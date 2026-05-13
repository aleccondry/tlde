FLASH ?= no
TARGET_BOARD_ZEPHYR ?= qemu_cortex_m3

.PHONY: clean qemu_cortex_m3 qemu_riscv32 nucleo_h753zi build

qemu_cortex_m3:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

qemu_riscv32:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

nrf52840dk:
	$(MAKE) build TARGET_BOARD_ZEPHYR=nrf52840dk/nrf52840

nrf5340dk:
	$(MAKE) build TARGET_BOARD_ZEPHYR=nrf5340dk/nrf5340/cpuapp
	$(MAKE) build TARGET_BOARD_ZEPHYR=nrf5340dk/nrf5340/cpunet 

arduino_nano_33_iot:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

stm32h573i_dk:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

esp32c3_devkitm:
	$(MAKE) build TARGET_BOARD_ZEPHYR=esp32c3_devkitm

esp32s3_devkitm:
	$(MAKE) build TARGET_BOARD_ZEPHYR=esp32s3_devkitm/esp32s3/procpu

nucleo_h753zi:
	$(MAKE) build TARGET_BOARD_ZEPHYR=$@

all: qemu_cortex_m3 qemu_riscv32 nrf52840dk nrf5340dk arduino_nano_33_iot stm32h573i_dk \
	 esp32c3_devkitm esp32s3_devkitm nucleo_h753zi

build:
	west build -p -b $(TARGET_BOARD_ZEPHYR) .
ifeq ($(FLASH),yes)
	west flash
endif


clean:
	@rm -rf build/
