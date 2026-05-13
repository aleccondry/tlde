/*
    R/W test on flash (pure Zephyr C)

    Requirements:
        - flash-controller chosen and enabled in device tree
        - flash partitions defined in device tree (slot1_partition)
*/

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(flash_rw, LOG_LEVEL_DBG);

#include "flash_test.h"

int main(void) {
    LOG_INF("Hello World! %s", CONFIG_BOARD_TARGET);

    ubx_flash_test();

    LOG_INF("--- OK ---");
    LOG_INF("Goodbye! %s", CONFIG_BOARD_TARGET);
    return 0;
}

