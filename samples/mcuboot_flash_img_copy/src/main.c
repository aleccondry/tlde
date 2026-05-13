/* mcuboot_flash_img_copy: copy an img from flash storage to slo1

    - destination partition is set in Kconfig
    - source partition is passed in the C main
*/

#include <zephyr/drivers/flash.h>
#include <zephyr/logging/log.h>
#include <zephyr/storage/flash_map.h>
LOG_MODULE_REGISTER(mcuboot_flash_img_copy, LOG_LEVEL_DBG);

#include <stdio.h>

#include "mcuboot_flash_img_copy.h"

// Use 'scratch' instead for microbit as storage is too small
#ifdef CONFIG_BOARD_BBC_MICROBIT_V2
    #define STORAGE_PARTITION_LABEL scratch_partition
#else
    #define STORAGE_PARTITION_LABEL storage_partition
#endif

// Select storage partition
#define STORAGE_PARTITION_ID FIXED_PARTITION_ID(STORAGE_PARTITION_LABEL)

int main(void) {
    LOG_INF("Hello World! %s", CONFIG_BOARD_TARGET);

    // Image copy from flash handled by the Rust application
    int rc = ubx_mcuboot_flash_img_copy(STORAGE_PARTITION_ID);
    if (rc < 0) {
        LOG_ERR("ubx_mcuboot_flash_img_copy()...failed(%d)", rc);
        return rc;
    }

    return 0;
}

