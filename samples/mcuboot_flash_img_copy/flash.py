#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @title      Flashing script for MCUboot flash copy tests
# @file       flash.py
#
# @brief Flash firmware to target boards using various flashing tools.
#   Current support for: Espressif, Raspberry Pi Pico, Nordic and STM32 boards.

import os
import subprocess
import sys
import argparse

# Flash tools for different boards
BOARDS = [
    "bbc_microbit_v2",
]

# OpenOCD target config for Nordic targets
OPENOCD_NORDIC_TARGET = {
    "bbc_microbit_v2": "target/nrf52.cfg",
}

# Flash tools for different boards
VENDOR_FLASH_TOOLS = {
    "bbc_microbit_v2": "nordic",
}

# Define binary images to flash
BIN_IMG = {
    "mcuboot":    "build/mcuboot/zephyr/zephyr.bin",
    "img_v0_0_0": "build/mcuboot_flash_img_copy/zephyr/zephyr.signed.bin",
    "img_v1_0_0": "build/img_v1_0_0/zephyr/zephyr.bin",
    "img_v2_0_0": "build/img_v2_0_0/zephyr/zephyr.signed.bin",
}

# Partitions offsets
CONFIG_PARTITION_OFFSETS ={
    "bbc_microbit_v2": {
        'mcuboot': "0x00000000", # mcuboot offset
        'slot0':   "0x0000C000", # slot0_partition offset
        'slot1':   "0x0003E000", # slot1_partition offset
        'storage': "0x00070000", # scratch_partition offset, storage is 0x0007A000
    },
}

# Run flashing commands in the current directory
def run(cmd):
    """Run a command in current dir"""
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

# Run monitorng for Espressif boards
def monitoring(board):
    """Monitoring boards"""
    subprocess.run(["west", "espressif", "monitor"], check=True, cwd="./")

# Flashing calling appropriate flashing tool based on board type
def flash(board, offset, img, erase=False):
    """Flashing depending on vendor"""
    if VENDOR_FLASH_TOOLS[board] == "nordic":
        flash_nordic(board, offset, img, erase)
    else:
        raise ValueError("Unknown board")


# Flashing Nordic targets using openocd via CMSIS-DAP
def flash_nordic(board, offset, img, erase=False):
    """Flashing for Nordic targets using openocd via CMSIS-DAP"""
    zephyr_sdk = os.environ.get("ZEPHYR_SDK_INSTALL_DIR", "/home/ubuntu/zephyr-sdk-0.17.4")


    openocd_bin = f"{zephyr_sdk}/sysroots/x86_64-pokysdk-linux/usr/bin/openocd"
    openocd_scripts = f"{zephyr_sdk}/sysroots/x86_64-pokysdk-linux/usr/share/openocd/scripts"

    cmd_base = [openocd_bin, "-s", openocd_scripts,
                "-f", "interface/cmsis-dap.cfg",
                "-f", OPENOCD_NORDIC_TARGET[board],
                "-c", "transport select swd"]

    if erase:
        run(cmd_base + ["-c", "init", "-c", "targets", "-c", "reset init", "-c", "nrf5 mass_erase", "-c", "shutdown"])
    else:
        run(cmd_base + ["-c", f"program {img} verify reset exit {offset}"])

# Completely erase the flash memory of the target board
def erase(board):
    """Erase flash memory depending on vendor"""
    if VENDOR_FLASH_TOOLS[board] == "nordic":
        flash_nordic(board, "0x0", "", erase=True)
    else:
        raise ValueError("Unknown board")

def reboot(board):
    """Reboot target board depending on vendor"""
    if VENDOR_FLASH_TOOLS[board] == "esp":
        pass
    elif VENDOR_FLASH_TOOLS[board] == "rasp":
        flash_rpi_pico(board, "0x0", "", reboot=True)
    elif VENDOR_FLASH_TOOLS[board] == "nordic":
        pass
    elif VENDOR_FLASH_TOOLS[board] == "stm32":
        # openocd resets the target after flashing
        pass
    else:
        raise ValueError("Unknown board")

# Parse command line arguments and flash firmwares
def main():
    # Parse command arguments
    parser = argparse.ArgumentParser(description="Flash firmware to target boards")
    parser.add_argument("board", choices=BOARDS, help="Target board")
    parser.add_argument("--mcuboot", action="store_true", help="Flash mcuboot bootloader")
    parser.add_argument("--good-update", action="store_true", help="Flash configuration for a successful update")
    parser.add_argument("--bad-update", action="store_true", help="Flash configuration for a failed update")
    parser.add_argument("--erase-all", action="store_true", help="Completely erase the flash memory (boot included)")
    args = parser.parse_args()

    # Override offsets for specific boards
    if args.board not in BOARDS:
        print(f"Board {args.board} not supported")
        sys.exit(1)

    partition_offsets = CONFIG_PARTITION_OFFSETS[args.board]

    # Erase flash memory if requested
    if args.erase_all:
        print(f"> Erasing flash memory of {args.board}")
        erase(args.board)

    # Flashing firmware for boards
    if args.mcuboot:
        print(f"> Flashing mcuboot to {args.board} at boot_partition ({partition_offsets['mcuboot']})")
        flash(args.board, partition_offsets["mcuboot"], BIN_IMG['mcuboot'])

    if args.good_update:
        print(f"> Flashing img_v2_0_0 to {args.board} in storage_partition ({partition_offsets['storage']})")
        flash(args.board, partition_offsets["storage"], BIN_IMG['img_v2_0_0'])
        print(f"> Flashing img_v0_0_0 to {args.board} in slot0_partition ({partition_offsets['slot0']})")
        flash(args.board, partition_offsets["slot0"],   BIN_IMG['img_v0_0_0'])
        reboot(args.board)
    elif args.bad_update:
        print(f"> Flashing img_v1_0_0 to {args.board} in storage_partition ({partition_offsets['storage']})")
        flash(args.board, partition_offsets["storage"], BIN_IMG['img_v1_0_0'])
        print(f"> Flashing img_v0_0_0 to {args.board} in slot0_partition ({partition_offsets['slot0']})")
        flash(args.board, partition_offsets["slot0"],   BIN_IMG['img_v0_0_0'])
        reboot(args.board)
    
    # Launch monitoring for Espressif boards to get buffered logs
    if "esp" in args.board:
        monitoring(args.board)

if __name__ == "__main__":
    main()
