#ifndef FLASH_TEST_H
#define FLASH_TEST_H

#include <stddef.h>
#include <stdint.h>

/* Mirror of the Rust FlashParams struct passed across the C boundary. */
struct flash_params {
    size_t  page_size;
    size_t  partition_size;
    uint8_t erase_value;
    size_t  write_block_size;
};

/**
 * @brief Run a simple flash erase / write / read verification loop.
 *
 * @return 0 on success, negative errno on failure.
 */
int ubx_flash_test(void);

#endif /* FLASH_TEST_H */
