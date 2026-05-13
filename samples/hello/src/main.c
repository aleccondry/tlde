#include <stdio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(hello, LOG_LEVEL_DBG);

int main(void) {
    int count_max = 100;
    int count = 0;
    LOG_INF("Hello World! %s", CONFIG_BOARD_TARGET);
    for (count = 0; count <= count_max; ++count) {
        LOG_INF("Hello World! %s - %d/%d", CONFIG_BOARD_TARGET, count, count_max);
        k_msleep(1000);
    }
    return 0;
}

