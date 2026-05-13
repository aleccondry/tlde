#include <zephyr/sys/printk.h>

int main(void) {
    printk("Hello world!\n");
    printk("Image version: %s\n", CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION);
    return 0;
}

